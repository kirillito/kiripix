---
status: todo
milestone: M6
agent: core-engineer
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0333-m6-style-measures-and-check.md]
---

# M6: style references in the Project, and the style Checks in `check`

Spec §4 (`kiripix.toml`), §10.3 (owner-only Commands) and §14 (M6). Part of
[0324](0324-m6-rooms-at-chapter-scale-style-npcs.md), written to the Owner's Q4 there. The measures and Checks are
[0333](0333-m6-style-measures-and-check.md).

## What to build

- **`[style]` in `kiripix.toml`:** `references`, a list of Asset IDs of any Kind the Checks support. A `schema_version` bump
  and a pure migration from N to N + 1 in `kiripix/core/settings.py` that adds an empty list. An unknown ID or an unsupported
  Kind is a settings finding (`style.reference_unknown`).
- **`kiripix style-add <id>` and `kiripix style-remove <id>`**, owner-only (the session token, §10.3), each an atomic write
  that keeps the file's comments (as M5's [0235](../m5/0235-m5-settings-writes-keep-comments.md) does for other settings).
  A session's call gets the usual owner-only refusal.
- **In `check`:** for each Asset whose Kind has style Checks, on the Stage 0332 named, the Asset's measures against the
  references' (the Asset itself left out when it's a reference). With no references, nothing runs and nothing is reported.
  A reference whose Stage isn't built is `style.reference_unbuilt` (info), and it's left out of the range.
- **A cache:** each Asset's measures in `.kiripix/`, keyed by the measured Stage's input hash and the measures' version, so
  `check --all` over 30 rooms measures only what changed. Skip it if 0332's times say it's not needed, and record that here.
- **`kiripix probe style <id>`:** the Asset's measures, each reference's, and the range, as numbers. The UI
  ([0335](0335-m6-ui-style-scores.md)) reads it.
- `describe` and `schema` cover the new settings and Commands.

## Acceptance criteria

- [ ] CLI seam: an older `kiripix.toml` migrates and gains `[style]`; an unknown reference is a finding.
- [ ] CLI seam: `style-add` from a session is refused as owner-only, and with the token it writes the list.
- [ ] CLI seam: on a test Project with two matching test Assets as references, a third out of range gets its `style.*`
      warning from `check` and `check --all`; with no references there are none.
- [ ] CLI seam: a second `check --all` with nothing changed measures nothing (the cache), if the cache is built.
- [ ] Samples for `style-add`, `style-remove` and `probe style` in `tests/cli/test_contract.py`.
- [ ] Spec §4, §10.3 and §10.5 updated.
