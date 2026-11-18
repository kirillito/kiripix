---
status: todo
milestone: M5
agent: core-engineer
type: ticket
---

# M5: refactors the batch review left (2026-11-18)

From the code review of the batch of 0242, 0263–0295. Its bugs were fixed in the batch; these are the judgement calls it
left, none a defect today. No behaviour changes: every test passes before and after.

## What to do

- **Body and base hooks in core** (`kiripix/core/graph.py`): `_body_view`, `_body_not_built` and the body hashes copy
  `_base_view`, `_base_not_built` and the base hashing (ADR 0012). One "related Asset" mechanism for both, so a third (a
  Wearable's held thing, 0238) doesn't copy them again.
- **A Wearable's `order` read in core** (`graph._wearing`): core reads the Wearable's `sheet` parameter by name, with a
  fallback of 0 against the parameter's default of 10, and skips a Wearable it can't read without a word. Give `StageSpec` a
  hook the Wearable's recipe fills (for example `worn_order`), so core names no Stage or parameter, and report an unreadable
  Wearable instead of skipping it.
- **Built-record readers in export:** `read_wearable` (`export/wearable.py`), `read_icon` (`export/icon.py`), `read_prop`
  and `read_room` each read a JSON from the built folder, compare `schema_version` and fail with `run … --force`. One helper.
- **Export's Wearable branch** (`export/__init__.py`): `wearable` is in `_FILES_BY_KIND`, then bypassed with
  `if asset.kind == "wearable"` and sorted last with `a.kind == "wearable"`. Let the Kind's entry carry what it needs (a
  `planned` argument, an export rank) instead of switches on the Kind's name.
- **`decide` and `redo` read the redo journal twice** (`commands/decisions.py`, the two `if arguments.stage == "source"`
  blocks for Prop states and portrait emotions): one call for a `source` edit's findings.
- **`core/emotions.py`:** `graph.asset.kind != PORTRAIT` three times beside `is_portrait`; `neutral_source` has no guard, so
  `commands/show.py` adds its own. One guard.
- **The UI's stacking** (`stack()` in `web/src/wearableScreens.tsx`) re-implements `kiripix/ops/stack.py`. Either a file the
  body's `sheet` writes (a stacked preview atlas, with [0296](0296-m5-ui-read-gaps.md)'s `depth.png`), or an ADR note under
  ADR 0007 that a preview may composite client-side. Also: `picture` and `gray` there duplicate their fetch-and-cache.

## Acceptance criteria

- [ ] Each item done, or written up here with why it stays.
- [ ] The tests of the files touched pass unchanged (no test edited to fit); `uv run mypy`, `uv run lint-imports` and, for
      the UI item, `npm run build` and `web/e2e/wearables.spec.ts` pass.
- [ ] No Stage's outputs change, so no `version` bump.
