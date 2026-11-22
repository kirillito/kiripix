---
status: done
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

- [x] CLI seam: an older `kiripix.toml` migrates and gains `[style]`; an unknown reference is a finding.
- [x] CLI seam: `style-add` from a session is refused as owner-only, and with the token it writes the list.
- [x] CLI seam: on a test Project with two matching test Assets as references, a third out of range gets its `style.*`
      warning from `check` and `check --all`; with no references there are none.
- [x] CLI seam: a second `check --all` with nothing changed measures nothing (the cache), if the cache is built. (No cache is built: see the Result.)
- [x] Samples for `style-add`, `style-remove` and `probe style` in `tests/cli/test_contract.py`.
- [x] Spec §4, §10.3 and §10.5 updated.

## Result (2026-11-20, core-engineer)

Built to the Owner's verdict in [0332](0332-m6-style-match-trial.md): `style.outline_density` for character, sprite and wearable,
`style.pixel_scale` for every Kind with a measured Stage. Spec §4 (the example), §6 (the Style Checks table per Kind), §10.3 and §10.5
are updated. No Stage's output changed, so no `version` bump.

- **`kiripix.toml` `schema_version` 11:** `[style] references = []` (`StyleSection`), migration 10 to 11 `_add_style_section` in
  `kiripix/core/settings.py` (pure; a writing Command writes it back). `kiripix init` writes the section (commented). Tickets that
  take the next bump (0356) start at 12. The tests that wrote `schema_version = 10` now say 11.
- **`style-add <id>` / `style-remove <id>`** (`kiripix/commands/style.py`), owner-only, locks the Project, comments kept
  (`save_settings`). `style-add` of an unknown ID or a Kind with no style Checks is `style.reference_unknown` (exit 1); a second add,
  or removing what isn't listed, is `changed: false`. `style-remove` takes out an entry that names no Asset too. A session's call gets
  the usual refusal (exit 3).
- **`check`:** `kiripix/core/style.py` (wired in `check_all`, `check_asset`'s caller in `commands/checks.py`). Measured Stage per Kind is
  `STYLE_STAGES` in `kiripix/checks/style.py` (character, sprite, wearable: `finish`; room: `palette`; prop: `export`). Figures:
  clip `idle` (else the first), direction `s` (else the first), frame 0, cut to its opaque box. The outline colour is `finish.json`'s
  `outline.rgb`; with the outline off, the palette colour of `finish`'s `outline_colour`; a Wearable's `finish` has no such parameter and
  draws none, so only its scale is judged (see below). The Asset is measured against the other built references; with none, nothing runs
  and nothing is reported. `style.reference_unbuilt` (info, fix `kiripix run <ref> <stage>`) once per call. `style.reference_unknown`
  (error, `owner_action` to `style-remove` it) is reported by `check --all`, not by a single-Asset `check`, and `--match` drops it.
  `fix` for `style.outline_density`: `kiripix set <id> finish outline=true` (or `placement=outside` when `finish` drew one); for
  `style.pixel_scale`: `kiripix set <id> fit mode=downscale` for a sprite, an `owner_action` (a Source or render at the Project's pixel size) otherwise.
- **The cache: not built.** Timed on the art Project's real Plates (`pixel_scale`, after the PNG load): 0.009 to 0.011 s for a 336 x 192
  room, 0.036 s for 640 x 528, 0.088 s for the laneway at 1120 x 624; a random-noise 1920 x 1080 image, the worst case, 0.43 s. A figure
  frame is a few ms. `check --all` over 30 rooms is about 1 to 3 s for the measures, against a Plate load of the same order, and each
  reference is measured once per call. Not worth a cache key and a file in `.kiripix/`. If rooms grow far past 1080p, add it then (the
  derived cache of `HashCache` is there, keyed by the Stage's input hash).
- **`kiripix probe style <id>`** (no arguments; `kiripix/commands/probes.py`, logic in `core/style.py: probe_style`). The Probe's own
  object is `data.result`:
  `asset`, `kind`, `stage` (null for a Kind without style Checks), `built` (the Stage has output),
  `measures`: `{outline_density: {outline_px, edge_px, density} | null, pixel_scale: {runs, gcd, median, run1_share}} | null`;
  `references`: one row per `[style] references` entry, in file order, `{asset, kind, stage, built, left_out (it is the Asset itself),
  measures (same shape) | null}`; `range`: `{outline_density, pixel_scale}` each `{low, high, furthest} | null`, over the built references
  other than the Asset (`pixel_scale` as the gcd); `limits`: `{outline_density_floor: 0.5, pixel_scale_gcd: 2, pixel_scale_min_runs: 50}`;
  `findings`: the `style.*` findings `check` would give (as finding objects), empty with no other built reference.
- Tests: `tests/cli/test_style_references.py` (migration, unknown reference, owner-only add and remove with comments kept, the warning
  from `check`, `check --all`, `--match`, the unbuilt reference, the probe), and `style-add`, `style-remove` and `probe style` in
  `tests/cli/test_contract.py`. The pixel-scale warning has no CLI test: the synthetic sprite sheets are downscaled by `fit`, so the
  Check's own numbers are covered at the golden seam (0333).
- **Settled (2026-11-20):** the Owner chose no outline on Wearables, as built; spec §9 is back to "No outline" and
  `OUTLINE_KINDS` is character and sprite only. A Wearable gets only `style.pixel_scale`.

### Changed after the code review (main session, 2026-11-20)

- A room is measured on `palette`'s `plate.png`, the mapped Plate, not `palette.png` (the composite with the Layers).
- A Wearable is measured: every `finish` Kind reads the figure frame, and only character and sprite (`OUTLINE_KINDS`) get the
  outline measure. Before, a Wearable fell through to the Plate branch, was never measured, and a built Wearable reference read
  `style.reference_unbuilt`.
- `style.pixel_scale` outside a sprite has an `owner_action` instead of a `kiripix show` "fix", which repaired nothing;
  `check_pixel_scale` takes exactly one of `fix` or `owner_action`.
- `kiripix.core.style` and `kiripix.ops.style` import numpy lazily, as the other Ops do (`test_start_imports`: `describe` must
  not load numpy). `style-add` and `style-remove` have REST bodies in `tests/cli/test_serve.py`.
- Left as found: `probe style` has no `closest` reference and no path of the measured image, so the UI panel shows a room by
  its Stage image (the composite) and re-derives a figure's frame (0335's Result). A small follow-up if wanted.

