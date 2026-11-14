---
status: todo
milestone: M4
agent: core-engineer
type: ticket
parent: 0183-m4-ambient-animation.md
depends_on: [0193-m4-loop-kit-and-import.md]
---

# M4: `import --loop` takes several files over REST

Found by [0196](0196-m4-ui-frame-loops.md) (2026-11-13). Spec §10.6. A multipart request refuses repeated parts
(`_multipart` in `kiripix/commands/session.py`), and only `file` is a file input. So the browser can't upload a kit's frames,
and the loops screen reads them from a folder on the server's machine instead.

## What to build

- A file input can be a list. `import` declares `frames` as one, and its parts can repeat. Each part keeps the file name it
  was sent with, so `import --loop` sorts by the names the Owner gave. A single file input sent twice is still refused.
- **`kit` (CLI `--kit <kit.json>`):** the kit's `kit.json`, read as if it sat beside the frames. Uploaded frames then keep
  the kit's checks: "painted on another fit" and `import.loop_region_changed`. Without it, `import --loop` warns that the
  frames are taken against the room as it is now.
- `describe` and the REST schema show the list input.

## Acceptance criteria

- [ ] REST (`tests/cli/test_serve.py`): a multipart `import` with three `frames` parts and a `kit` part stores the frames in
      name order, the same as the CLI with the same files.
- [ ] REST: a repeated `file` part is still refused with `input.invalid`.
- [ ] CLI seam: `--kit` with a `kit.json` from before a region change gives `import.loop_region_changed`.
- [ ] The contract sample and `BODIES` are updated; `lint-imports` and `mypy` pass.

Budget: 30–60k tokens.
