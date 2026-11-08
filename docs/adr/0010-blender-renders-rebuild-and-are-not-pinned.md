# Blender renders rebuild; they aren't pinned

ADR 0002 pins Runner and Provider calls because they aren't bit-exact across devices, so rebuilding could silently change
an exported asset. A Blender render (the character's `render` Stage, spec §6.3) is neither a Runner nor a Provider, but
it isn't bit-exact either: across GPU and CPU, between render engines, or across 5.2.x patch releases. So we had to
choose which rule applies. We considered three options:

1. **Pin each render call**, as ADR 0002 does for Runners. Every frame of every clip and direction would be committed
   to LFS under `pinned/`, keyed on the Model, the clip, the camera preset and the render settings. A camera tweak would
   send `render` to `needs-input` until `run --rerun`, and the result to `needs-review` until `accept`. A character
   has about 1,000 frames, so every render change would need an accept step.
2. **Rebuild as deterministic work.** `render` is an ordinary Stage. Its inputs include the Blender version and the
   render settings (engine, camera preset, shading, sizes), so a change to any of them makes `render` stale, and `run`
   rebuilds it.
3. **Pin only the frames that reach `out/`.** Renders rebuild in `work/`, but the exported frames are compared with
   the committed ones, and a difference stops export for the Owner. This needs a second pinning path just for export,
   and it fires on every intended change as well as on accidental ones.

**Measurement: not yet made.** No Blender is installed on the development machine, and there is no fixture Model or
`render` Stage yet. The plan is to render one clip of the fixture Model ([0100](../../backlog/0100-m3-character-test-fixtures.md))
on Blender 5.2, twice on the GPU and once on the CPU, with the `render` Stage's engine and settings, and to compare the
frames pixel by pixel. The result tells how much a rebuild on another device can change. It doesn't decide the choice
below, and it is recorded in ticket 0098 when it's made.

We chose 2 (the Owner, 2026-11-07). Nothing reaches the game unseen: export writes into the game repo, and the Owner
reviews that diff before committing it. That review is the guard that option 1 or 3 would add, and it already
exists. Pinning was turned down because it adds an accept step to every rerun of about 1,000 frames per character. LFS
size wasn't the issue: a 52 px frame is about 1 KB.

## Consequences

- This narrows ADR 0002's "only deterministic Ops rebuild implicitly": a Blender render also rebuilds implicitly.
  Principle 11 still holds, because Blender is not a Runner (glossary) and a render costs no money.
- `render`'s inputs include the Blender major and minor version it runs on (5.2) and every render setting. A new
  Blender LTS or a setting change shows `render` as stale, and the Owner rebuilds when they choose. A 5.2.x patch
  release isn't an input (the Owner, 2026-11-07): it may change a few pixels on the next rebuild, and that shows in the
  game repo's diff.
- A Blender other than the pinned version (`docs/versions.md`) is a finding. Kiripix doesn't guess.
- Deleting `work/`, or a fresh checkout on another machine, can produce frames that differ by a few pixels. Export
  writes those differences into the game repo, where they appear in the Owner's diff.
- Render output lives in `work/` and isn't committed. Only the exported sheet in `out/` is.
- Tests never check render pixels. The real-Blender test (mark `blender`) checks sizes, passes and frame counts.
  Pixel-exact golden tests stay on the Ops downstream of `render`.
