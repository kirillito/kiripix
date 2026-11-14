# The agent acceptance test

Spec §14, ticket 0028. An agent with no project knowledge takes a room from `import` to `export` using only the
`kiripix` tool. A real run costs money, so CI and a plain `uv run pytest` never start one. They do run the harness's own
tests, including the scripted dry run, which is free.

```
uv run python -m tests.acceptance.run                 # the real run: claude -p, claude-haiku-5-5, 200k fresh tokens
uv run python -m tests.acceptance.run --dry-run       # a scripted agent that follows `next`; free, writes no report
```

Flags: `--agent-version`, `--budget` (fresh tokens, that is in + out + cache written, across all resumes), `--max-usd`
(`--max-budget-usd` of each `claude` call), `--milestone`, `--report` (write a report for a dry run too), `--keep`.
A real run writes `docs/acceptance/<date>-<milestone>.md` (a second run that day gets `-2`). The harness itself is
tested without a model by `uv run pytest tests/acceptance` (the dry run, the isolation, the stream parser).

How the agent is held to the tool, how the stand-in owner works and what counts as a pass are in the docstrings of
`tests/acceptance/claude_agent.py` and `harness.py`. The owner's Decisions are `tests/acceptance/fixtures/owner.json`.

**M2 and later.** The room has a red crate for the stand-in owner to lift into a foreground Layer (`click` on `layers`,
then `accept`, then a y-sort line on `place`). The Runners are fakes (0037's D16): `tests/acceptance/fixtures/acceptance_recipes.py`
loads the fakes from `tests/fixtures` and removes the test Kinds, so `describe` shows only the real ones. The harness's own
calls get `KIRIPIX_TEST_RECIPES`; the agent gets it only through the `kiripix` and `kpx` shims first on its PATH. A pass also
needs the Layer in the export's Manifest. Use `--milestone m2` for that record.

**M3 and later.** The task also names a character, `character.hero`, created but empty, and the file of its 3D Model
(`tests/fixtures/characters/rigged.glb`, copied outside the Project): the agent imports it, so `rig` needs no Mixamo.
The renderer is the fake Blender that `tests/fixtures/kiripix_test_recipes.py` sets, reached the same way as the fake
Runners. The stand-in owner's three `clip` Decisions (idle, walk, attack) are the `character.hero` entries of
`owner.json`. A pass also needs every `<clip>_<dir>` animation in the character's Manifest, both Assets' exports
up to date, and `check --all` clean. Use `--milestone m3` for that record.

**M4 and later.** The room is 240 x 160 and arrives in two pieces. The Project starts with the first (144 x 160, imported and
picked, `[extend] canvas = [144, 160]` set as the Owner's own setting) and the task names the file of the second, outside
the Project, which is what `extend canvas --side east` writes the canvas for, filled in: the agent runs `extend canvas`,
`add`, `done` and picks the joined Variant. The floor is blobs of two palette colours, because `extend` registers a piece
on texture, and the room has only the four colours the `palette` Stage keeps. The task also asks for an `area` Marker
`battle.test` on 32 px cells that can be stood on. The stand-in owner first puts it on the wall (`area.no_walkable`), and
moves it onto the floor when the agent reports the finding (the entry with `when_stage: place`). A pass also needs the
room's export to hold the `Area2D` (the box snapped to cells, `walkable`, `cell`), `masks/solid.png` at the room's size and
`room.json` beside the scene. Use `--milestone m4` for that record; the token count is the one to set against M3's.
