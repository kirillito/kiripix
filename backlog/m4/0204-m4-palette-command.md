---
status: done
milestone: M4
agent: core-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
---

# M4: a Command that gives the Project palette

Found by [0187](0187-m4-ui-draw-an-emitter.md) and [0191](0191-m4-ui-loops-screen.md) (2026-11-13). Spec §10.5. No Command
gives the Project palette, so the place and loops screens read `style/palette.gpl` through the file route. If the `palette`
setting points somewhere else, they show no swatches, and the eyedropper refuses every colour. An agent choosing a cycle's
`colours` (each must be on the palette) has the same problem: it has to parse a `.gpl` file.

## What to build

- `kiripix palette`: a read Command, exposed to MCP. It gives the palette file (the `palette` setting, relative to the
  Project) and `colours`, in file order, each with `index`, `hex` (`#rrggbb`, lower case) and `name` (or `null`). The text
  output is one line per colour.
- It reads the palette the way the Stages do, so it can't disagree with them. A palette that is missing or can't be read is
  refused with the finding the Stages give.
- Add a line to the spec's §10.5 CLI table, beside `palette-add`.

## Acceptance criteria

- [x] CLI seam: in a temporary Project, `palette --json` lists the colours of `style/palette.gpl` in order. After the
      `palette` setting is pointed at another file, it lists that file's colours.
- [x] CLI seam: a missing palette file exits 1 with a finding that has a `fix` or an `owner_action`.
- [x] A sample in `tests/cli/test_contract.py`, an entry in `BODIES` in `tests/cli/test_serve.py`; `lint-imports` and
      `mypy` pass.

Budget: 30–60k tokens.

## Result (2026-11-14)

- `kiripix palette` (kind `probe`, MCP exposed) in `kiripix/commands/palette.py`: `palette` (the setting, relative to the
  Project) and `colours` with `index`, `hex` (`#rrggbb`, lower case) and `name` (or `null`). The text is one line per colour.
- It reads through core's `load_palette`, as `op quantize` and the other Commands do, so a missing file is `palette.not_found`
  (exit 1, with an `owner_action`), and a palette that fails its Checks is refused as those are. The Stages' own reader
  (`palette_rgb` in `recipes`) can't be imported from `commands`, but both use `parse_gpl`/`parse_hex`.
- Tests: `tests/cli/test_palette_command.py` (4); sample in `test_contract.py`, body in `test_serve.py`; line in spec §10.5.
- Follow-up (not done, `web/` untouched): switch the place and loops screens from the file route to this Command, so swatches
  and the eyedropper follow the `palette` setting.
