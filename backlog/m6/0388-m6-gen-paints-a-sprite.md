---
status: done
milestone: M6
agent: core-engineer
type: ticket
parent: 0386-m6-pixellab-provider.md
depends_on: [0387-m6-pixellab-provider-jobs-and-operations.md]
---

# M6: `gen` paints a sprite through PixelLab: characters, states and motion by its own rig

Spec §6.4, §10 ("Spend") and §10.3. Part of [0386](0386-m6-pixellab-provider.md): read its Decisions first. The Provider and
its operations are [0387](0387-m6-pixellab-provider-jobs-and-operations.md); motion from a character's render is
[0389](0389-m6-pixellab-skeleton-motion-from-a-render.md).

## What to build

1. **`gen` takes a sprite** (`GEN_KINDS`), with PixelLab as its only Provider (`gen.provider_unsupported` for another, naming
   PixelLab). The targets, in 0386's table:
   - `--prompt "<who>" [--canvas N]`: a character from text, in the sprite's `directions`; its rotations stored as clip `idle`.
   - `--from-frames [--from <clip>]`: a character from the sprite's `frames` output (the clip's first frame in each direction,
     `idle` by default; `gen.frames_needed` when `frames` hasn't run). Stores no sheet.
   - `--state <name> --prompt "<the pose>" [--canvas N]`: a state; its rotations stored as clip `<name>`. A name the sprite's
     sheets already hold is sent as `<name>_2`, `_3`... (0386, "a retry is a new name").
   - `--clip <name> --motion rig --prompt "<the action>" [--frames N] [--directions ...] [--from <clip>]`: per direction,
     `estimate_rig` on that direction's first frame of `--from`, then `animate_skeleton` with `write_motion_frames`. Stored as
     `animations/<name>/<direction>/frame_NNN.png`. `--frames` is PixelLab's range (1 to 15 with a rig, 3 to 15 with keypoints, as the
     trial read it; check the OpenAPI again), refused before planning otherwise. `--motion skeleton` is refused as not yet built until 0389.
   - Each flag that doesn't fit the Kind or target is refused before planning, as `--side` and `--look` are today.
2. **`[sprite.pixellab]` in `asset.toml`** (optional): `character_id`, `canvas` (WIDTHxHEIGHT), `made_from` (`frames` or
   `text`), written by core after a character call (atomic). `--state` and `--clip` without it are `gen.character_needed` with
   the `fix` `kiripix gen <id> --from-frames` (or `--prompt "<who>"` when the sprite has no sheet). A second character call
   replaces it and says so in the result. Say in the Result whether `schema_version` moves (0385 added an optional key without
   one); if it does, add the migration.
3. **One pending call for an operation's jobs.** `PendingCall` gains the operation, its inputs that aren't images (the character
   ID, the canvas, the directions, the frame count, the state name) and its planned jobs (each: endpoint, direction, estimate),
   with the images it sends as `inputs` and their hashes, as today. The estimate is the jobs' sum; the limits check that sum;
   `max_calls_per_day` counts the operation once. `approve` sends the jobs in order; a failed or cancelled job stops the rest,
   each job sent is its own ledger line, and the directions that came back are stored. `CALL_SCHEMA_VERSION` 1 → 2, with a
   pure migration (a version-1 pending call is a plain image call).
4. **A sheet per call** (0386): core unpacks the character's ZIP, keeps only what the call made (the new state's
   `<state>/rotations/`, or a text character's `rotations/` as `Idle`), repacks it in PixelLab's layout, and stores it in
   `src/sheets/` by hash, as `import --role sheet` does (the same ZIP checks). `imported.jsonl` records it with `provider` and
   `call`. The whole answer is kept in `.kiripix/calls/sent/<call>/` for the record, never read by a Stage. The result's `data`
   names the sheet and the clip, and a `next` hint to run `frames`.
5. **The ledger:** `LedgerLine` gains `generations` (a float, `null` when charged in USD) and `operation` (the endpoint);
   `usage` stays token counts. `SCHEMA_VERSION` 1 → 2 with its migration (version-1 lines: `generations` null, `operation`
   null). `kiripix cost` shows generations beside USD per Provider for the month, and the Provider's `terms`.
6. **Key and history:** `PIXELLAB_API_KEY` from the Project's `.env` (`key_for`, unchanged). The Asset's call history gains the
   operation, the state name and the character ID.
7. **Spec and glossary:** §6.4 (`gen` for a sprite), §10 ("Spend": operations, generations, one approval for a clip's jobs),
   §14 (PixelLab no longer "until 0386, through `import`"), §16 open decision 5 (built). The glossary only if a new domain word
   appears (the reviewer's call; "character" here is PixelLab's word and stays inside the Provider and `[sprite.pixellab]`).

## Acceptance criteria

CLI seam, with 0387's fake transport and `approve = "none"` unless the test is about approval:

- [x] `gen sprite.x --prompt` stores one sheet with clip `idle` and `[sprite.pixellab]`; `frames` reads it with no Decision.
- [x] `gen --from-frames` sends the sprite's first frames (checked in the kept request), stores no sheet, keeps the ID.
- [x] `gen --state hop` stores a sheet with only `hop` from a fake ZIP holding three states; a second one is `hop_2`, and the
      `sheet` Decision's `leave_out` keeps one (0385).
- [x] `gen --clip walk --motion rig --directions s,e` plans one pending call of four jobs with the summed estimate; `approve`
      sends four, writes four ledger lines, and stores one sheet with `walk` in `s` and `e`; a failed second job stores nothing
      past it and records what was charged.
- [x] `--state` without `[sprite.pixellab]` is `gen.character_needed`; `--motion skeleton` is refused until 0389; `--look` or
      `--side` on a sprite is refused.
- [x] A ledger with version-1 lines reads; `cost` shows generations; a version-1 pending call approves.
- [x] Contract samples for the changed `gen`, `approve` and `cost`; `describe gen` names the sprite targets.

Budget: 200–350k tokens.

(Ticked: written in `tests/cli/test_gen_sprite.py` and `tests/cli/test_contract.py`; **not run**, the owner's instruction for this
batch: the main session runs `uv run pytest`. `uv run mypy` and `uv run lint-imports` pass.)

## Result

Built `kiripix/core/gen_sprite.py` (plan and send for a sprite) and changed `gen.py`, `ledger.py`, `settings.py`, `sources.py`,
`kiripix/commands/gen.py`, the spec (§6.4, §10 "Spend", §14, §16 item 5). The glossary needs nothing ("character" stays in the
Provider, `[sprite.pixellab]` and `gen_sprite`).

- **Targets and refusals.** `gen` takes `--canvas`, `--from-frames`, `--from <clip>`, `--clip`, `--motion`, `--frames`,
  `--directions` beside the old flags; a sprite is `gen_sprite.plan`, any other Asset refuses the new flags (`gen.sprite_flag`).
  Refused before planning: `--look/--emotion/--side/--reference/-n` on a sprite (`gen.flag_unsupported`), another Provider
  (`gen.provider_unsupported`), two targets (`gen.one_target`), `--motion/--frames/--directions` without `--clip`
  (`gen.clip_needed`), `--clip` without `--motion` (`gen.motion_needed`), `--motion skeleton` (`gen.motion_not_built`, in
  `gen_sprite.plan`), `--frames` outside 1 to 15 (`gen.frames_range`), `--canvas` outside 32 to 256 (`gen.canvas_range`),
  `--state` or `--clip` with no `[sprite.pixellab]` (`gen.character_needed`, fix `--from-frames` or `--prompt "<who>"`),
  `frames` not built (`gen.frames_needed`). With no `--provider`, a sprite uses PixelLab whatever `[providers] default` says.
  The frame range (1 to 15 with a rig) is the trial's and the Provider's; the OpenAPI was **not** re-read (no network).
- **`[sprite.pixellab]`** is `PixelLabCharacter` (`character_id`, `canvas` WxH, `made_from`) in `AssetSettings.sprite`; written
  atomically by core after a character call; a second call replaces it and `replaced_character_id` says so. **`schema_version`
  stays 1** (an optional key, as 0385's): nothing needs a migration, but an older Kiripix would refuse an `asset.toml` that has it.
  A state call does not replace it (PixelLab's new state is a new character in the group; the stored ID is kept).
- **Pending call, schema 2** (`CALL_SCHEMA_VERSION`; a version-1 call reads in memory as a plain image call, so it approves).
  New fields: `operation` (`character`, `state`, `motion`), `params` (non-image inputs: character ID, canvas, directions,
  frame count, state name, `from_clip`...), `jobs` (`PlannedJob`: `operation`, `endpoint`, `direction`, `estimate_usd`,
  `params`, `images` role -> index into `inputs`, `needs`); `target` gains `character`, `sprite_state`, `motion`; `CallInput.role`
  gains `frame`. `estimated_usd` is the jobs' sum, the limits check it (images count 1, inputs 0), `recheck` too.
- **Sending** (`gen_sprite.send`): jobs in order, `cancel.check()` before each, `Provider.operate(..., cancel.check,
  cancel.sleep)`; a job that `needs` an earlier one is fed its rig or keypoints at its turn (`_feed`). One ledger line per job
  sent (done; failed only when billed; cancelled at its estimate), model and `operation` = the Provider's endpoint
  (`Provider.endpoints`, a new small attribute in `providers/base.py`, filled by PixelLab). A failed or cancelled job stops the
  rest; the directions that came back are stored; the call stays pending for the Owner to reject (the failure's `owner_action`
  says so). `Sent`/`gen` data gain `operation`, `jobs`, `generations`, `sheet`, `clips`, `character_id`,
  `replaced_character_id`, `next` (`kiripix run <id> frames`), `terms`.
- **Sheets.** The character's or state's ZIP is checked (`sheets.check`), only the wanted rotations are kept (a state: the
  folder whose snake_case is the state's, else `gen.state_missing`; a text character: a top-level `rotations/`, else the state
  `idle`, else the first) and repacked deterministically (fixed times, sorted) as `Idle/rotations/<word>.png`,
  `<state>/rotations/<word>.png` or `animations/<clip>/<word>/frame_NNN.png`; stored by hash through
  `sources.import_generated_sheet`, which records `provider` and `call` in `imported.jsonl`. **`IMPORTED_SCHEMA_VERSION` 1 -> 2**
  (two optional keys; version-1 lines read as before). The whole answer is in `.kiripix/calls/sent/<call>/NN-<endpoint>[-dir]
  .zip|.json|/frame_NNN.png`.
- **Ledger** schema 2: `generations`, `operation`; version-1 lines read with both null, in memory. `calls_on_day` and the
  month's `calls` count distinct call IDs (an operation is one). `cost` shows generations per Provider (`MonthSpend.generations`)
  and every Provider's `terms` (`CostData.terms`); `gen` data has the Provider's `terms`.
- **History** entries of an operation gain `operation`, `params`, `jobs` (endpoints), `character_id`, `sheet`, `clips`, `state`.
  A rig's `description` is the last text character call's prompt in the history, else the Asset's name.
- **Tests**: `tests/cli/test_gen_sprite.py` (text character, replacement, `--from-frames`, states and `_2` with `leave_out`,
  canvas, the four-job clip with approve, a billed failure at job 2, a partial clip, refusals, a 402, version-1 ledger and
  pending call, the daily limit, the schema) and a sample in `test_contract.py`. The fake transport gained the state name in
  the ZIP and `STOP-<direction|animate>` / `STOPBILLED-...` markers (fail only some jobs). Not run.

Not settled without a real answer: where `animate-with-skeleton-v3` puts its images and `estimate-custom-skeleton`'s
`frames` shape (0387's note), the frame limits above, and the real ZIP's folder for a text character's first state.

**Fixes after the batch's code review (2026-11-26, main session; touch 0387's Provider too):**

- A character made and charged is never lost: when its ZIP can't be fetched (refused, still building, a network error, or a
  cancel while waiting) the Provider returns the character ID and the charge with `archive` None. Core records the real
  charge, keeps `[sprite.pixellab]`, and answers `gen.archive_missing` (exit 3) with the `owner_action` to download the ZIP
  and `import --role sheet`; after a cancel it stops instead. Fake transport: `pixellab-zip-fails`.
- `Provider.edits` (default True; PixelLab False): `gen --look`, `--state`, `--emotion`, `--side` through a Provider that
  can't edit is `gen.provider_cannot_edit`, refused before anything is planned, its `fix` naming another Provider.
- The plain image call keeps PixelLab's generations: `_ledger`, `Sent`, history and the sent line; `ProviderError` gains
  `billed_generations`, recorded on a failed call that was charged.
- Motion for a clip already held is sent as `walk_2` (`_new_name`), as a state is; the planned call keeps `asked`.
- The names held count the `sheet` Decisions' `clip` and `clips` renames and the last `frames.json`, not only raw ZIP
  folders, so a state never joins a renamed clip.
- A refusal's `fix` takes out only the faulty flag (`_without`), keeping `--prompt` and the rest.

Tests: `test_a_character_whose_zip_never_comes_is_kept_with_its_charge`, `test_motion_for_a_clip_already_held_is_a_new_name`,
`test_a_state_never_joins_a_clip_a_sheet_decision_named`, `test_a_fix_replaces_only_the_faulty_flag` (`test_gen_sprite.py`);
`test_pixellab_cant_edit_so_an_edit_or_extend_is_refused_before_anything_is_sent` and generations in
`test_a_charge_in_generations_is_priced_at_the_dated_rate` (`test_pixellab.py`).

Left as the review's nits, for the Owner: the v1 → v2 migrations of the ledger, the pending call and `imported.jsonl` live in
their own modules, not `settings.py`; `[sprite.pixellab]` was added without a `schema_version` bump; the names `endpoint` /
`endpoints` use a word the glossary avoids (they are PixelLab's HTTP paths).
