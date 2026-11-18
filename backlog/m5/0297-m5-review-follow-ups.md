---
status: done
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

- [x] Each item done, or written up here with why it stays.
- [x] The tests of the files touched pass unchanged (no test edited to fit); `uv run mypy`, `uv run lint-imports` and, for
      the UI item, `npm run build` and `web/e2e/wearables.spec.ts` pass.
- [x] No Stage's outputs change, so no `version` bump.

## Result

- **Body and base hooks:** done in `core/graph.py`. `_built_hashes` (the hash of each named Stage of a related Asset) and
  `_unbuilt` (why a Stage waits for it, given the role) serve the base and the body; `body_hashes`, `_base_not_built`,
  `_body_not_built` and `input_extra` call them. `_base_view` and `_body_view` stay apart: what a Stage is handed of each
  differs (the base's Decisions and params, the body's Kind-keyed folders), so a shared builder would only be flags. A third
  related Asset (a Wearable's held thing, 0238) adds a property and calls the two helpers.
- **A Wearable's `order`:** `StageSpec.worn_order` (parameters in, `int` out) is filled by the Wearable's `sheet`;
  `AssetGraph.worn_order()` finds it with `stage_with`, so core names no Stage or parameter. `_wearing` and `show`'s
  `wearables` both call it. An unreadable Wearable is no longer skipped or given 0: its finding (`config.invalid` naming
  its `asset.toml`, or the load error) now stops the body's Stage and `show`, which is the report the item asked for.
- **Built-record readers:** `read_built_record(graph, kind, file, version)` in `export/room.py`; `read_room`, `read_prop`,
  `read_icon`, `read_wearable` and `read_portrait` call it (the same `export.<kind>_invalid` codes and message).
- **Export's Wearable branch:** every Kind's function takes `(graph, target, planned)` and `_EXPORT_RANK` orders the Kinds in
  an `--all`; the two switches on `"wearable"` are gone. `export/checks.py`'s `_current_ids` no longer switches on the Kind
  either: `_IDS_OF_KIND` maps a Kind to a function that gives the `ExportedIds` fields its Decisions set (room, character,
  sprite, prop, portrait).
- **`decide` and `redo`:** `_edit_findings` runs the four edit checks (Loop, Prop state, emotion, emotion freeze) in order;
  `decide` and `redo` use it, and `redo` calls `next_redo` once for `loops` and `source`.
- **`core/emotions.py`:** the Kind test is `is_portrait` everywhere, and `neutral_source` has the guard, so `show` lost its own.
- **Also, from 0296:** `run_body_sheet`, `add_depth_atlas`, `DEPTH_ATLAS` and `FAR` moved into `recipes/character_sheet.py`;
  `wearable_sheet.py` imports them (the body's `sheet` no longer reaches into the Wearable's module).
- **The UI's stacking:** left for a ui-engineer (a ui-engineer was in `web/` on 0245, so nothing there was touched). Written
  as an ADR note under ADR 0007: a preview may composite client-side from files a Command wrote, since it changes nothing
  in the Project and the game stacks by `order` and `depth.png`. Still to do in `web/src/wearableScreens.tsx`: fold
  `picture` and `gray`'s duplicated fetch-and-cache into one helper, then `npm run build` and `web/e2e/wearables.spec.ts`.
  Why the status is `done` regardless: the item allowed the ADR note; the dedup is a small web-only leftover.

### Review fixes (2026-11-18, main session)

- `picture` and `gray` in `web/src/wearableScreens.tsx` share one fetch-and-cache (`cached`); `npm run build` and
  `web/e2e/wearables.spec.ts` pass.
