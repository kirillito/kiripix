---
status: done
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

- [x] REST (`tests/cli/test_serve.py`): a multipart `import` with three `frames` parts and a `kit` part stores the frames in
      name order, the same as the CLI with the same files.
- [x] REST: a repeated `file` part is still refused with `input.invalid`.
- [x] CLI seam: `--kit` with a `kit.json` from before a region change gives `import.loop_region_changed`.
- [x] The contract sample and `BODIES` are updated; `lint-imports` and `mypy` pass.

Budget: 30–60k tokens.

## Result (2026-11-14)

- A file input can be a list: `Session` (`_multipart`) lets a part repeat when its field is annotated `list[...]`, keeps each
  part's file name, and stores each in a folder of its own (`FileInputs.store(..., number=)`) so two can share a name. A single
  file input sent twice is still refused with `input.invalid`. `import` declares `files=("file", "frames", "kit")`; `describe`
  and the schema show `frames` as an array and list all three file inputs.
- `import --loop ... --kit <kit.json>` (`kit`, a file input): read as if it sat beside the frames; it gives the kit's box,
  fit and palette, so `import.loop_region_changed` and "painted on another fit" work for uploaded frames. A `kit.json` that
  isn't this Asset's and Loop's is `import.kit_invalid`; `--kit` without `--loop` is `import.kit_needs_loop`.
- New warning `import.loop_no_kit` (with a `fix` naming `--kit`) when no kit.json came with the frames (none given, none beside
  the first frame): the frames are taken as painted on the room as it is now. The import is unchanged otherwise.
- Extension point for 0219: `kiripix.core.loopkit.import_frames(project, asset, files, shown, loop, kit_file, kit_shown)`; the
  kit lookup is `_kit_file(path, asset, loop)`, and the Command's argument checks are at the top of `import_variant`.
- Tests: `tests/cli/test_loop_kit.py` (`--kit`, old kit.json), `tests/cli/test_serve.py` (three `frames` parts and a `kit`
  part equal the CLI, sent out of name order; repeated `file` refused; `FILE_INPUTS` and `_as_parts` take lists).
- Left for the UI: the loops screen can switch from a server folder to uploads (`frames` parts plus the `kit` part).
