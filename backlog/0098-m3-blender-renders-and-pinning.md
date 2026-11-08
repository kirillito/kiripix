---
status: todo
milestone: M3
agent: reviewer
type: decision
parent: 0097-m3-characters.md
---

# M3: decide whether a Blender render is pinned, and record it as an ADR

Spec §2 (principles 2 and 11), §5 (pinned calls), §6.3 and ADR 0002. Q1 of [0097](0097-m3-characters.md).

ADR 0002 pins Runner and Provider calls because they aren't bit-exact across devices. A Blender render is neither: it is an
external program, but it isn't bit-exact either, across GPU and CPU, between render engines, or across 5.2.x patch releases.
The spec doesn't say which rule applies. If renders rebuild, deleting `work/` on another machine could change an exported
character silently. If they're pinned, every frame of every clip and direction is committed to LFS, and a camera tweak sends
the `render` Stage to `needs-input` until `run --rerun`.

**The Owner's choice (2026-11-07): renders aren't pinned.** `render` is deterministic work, rebuilt like any other Stage. The
Blender version and the render settings (engine, camera preset, shading, sizes) are among its inputs, so an upgrade or a
setting change shows `render` as out of date, and the Owner rebuilds when they choose. A Blender other than the pinned
version is a finding. Nothing reaches the game unseen: export writes into the game repo, where the Owner reviews the diff
before committing. Pinning was turned down because it adds an accept step to every rerun of about 1,000 frames per
character; LFS size wasn't the issue (a 52 px frame is about 1 KB).

## What to do

- Measure, on the pinned Blender 5.2: render one clip of a fixture Model twice on the GPU and once on the CPU, with the
  render engine the `render` ticket expects, and compare the frames pixel by pixel. Record the result here. It says how
  much a rebuild on another device can change, not whether to pin.
- Write an ADR in `docs/adr/`, in the folder's format: the options considered (pin each render call; rebuild as
  deterministic work; pin only the frames that reach `out/`), the measurement, and the Owner's choice above with its reasons.

## Acceptance criteria

- [ ] The measurement is recorded here: equal or not, and by how many pixels.
- [x] An ADR in `docs/adr/`, in the folder's format, recording the Owner's choice:
      [0010](../docs/adr/0010-blender-renders-rebuild-and-are-not-pinned.md).
- [x] If the choice changes the spec's wording (§2, §5, §6.3), the changes are listed here for the main session to make.

## Measurement

**Pending (2026-11-07).** It can't be made yet: Blender isn't installed on the development machine (not on `PATH`,
not under `C:\Program Files`), the repo has no fixture Model, and no `render` Stage exists to say which engine and
settings to use. It needs:
- Blender 5.2 LTS (5.2.3, `docs/versions.md`) installed, on a machine with both a CUDA GPU and the CPU device;
- the fixture Model from [0100](0100-m3-character-test-fixtures.md);
- the render engine and settings fixed by the `render` ticket ([0104](0104-m3-render-stage.md)): toon shading, no
  anti-aliasing, colour, normal, depth and object-mask passes, at the target pixel size.

Then render one clip in one direction twice on the GPU and once on the CPU, and compare each pass pixel by pixel:
GPU against GPU, and GPU against CPU. Record "equal" or the count of differing pixels per pass. It decides nothing: the
choice (ADR 0010) stands either way.

## Spec wording changes (made)

- **§2, principle 11.** "A rebuild re-runs only deterministic Ops." became "A rebuild re-runs only deterministic work:
  Ops, and Blender renders (ADR 0010)."
- **§2, principle 2.** Added: "A Blender render counts as a function of its inputs, the Blender version and render
  settings among them, though it isn't bit-exact across devices (ADR 0010)."
- **§5, "Pinned calls".** Added: "A Blender render is not a pinned call (ADR 0010): it rebuilds like deterministic work,
  with the Blender version and render settings among the Stage's inputs."
- **§6.3:** none.

## Which Blender version is an input

**The Owner's choice (2026-11-07): patch releases are fine.** `render`'s input is the Blender major and minor version
(5.2), not the patch. A 5.2.x patch upgrade doesn't make `render` stale; a new LTS does. A patch can still change a few
pixels on a rebuild, and that shows in the game repo's diff like any other rebuild. The `render` ticket
([0104](0104-m3-render-stage.md)) implements this.
