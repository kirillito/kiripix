---
status: todo
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

- [ ] CLI seam: in a temporary Project, `palette --json` lists the colours of `style/palette.gpl` in order. After the
      `palette` setting is pointed at another file, it lists that file's colours.
- [ ] CLI seam: a missing palette file exits 1 with a finding that has a `fix` or an `owner_action`.
- [ ] A sample in `tests/cli/test_contract.py`, an entry in `BODIES` in `tests/cli/test_serve.py`; `lint-imports` and
      `mypy` pass.

Budget: 30–60k tokens.
