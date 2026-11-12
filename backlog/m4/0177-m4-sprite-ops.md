---
status: done
milestone: M4
agent: imaging-engineer
type: ticket
parent: 0174-m4-sprite-kind.md
---

# M4: Ops for sprites: slice a sheet, find the feet, normals from height

Spec §7 ("normals: normals from height (Sobel)", listed since v0.1 and not built). Part of [0174](0174-m4-sprite-kind.md).
Ops are pure: numpy in, numpy out, no I/O.

## What to build

In `kiripix/ops/`, exported from `kiripix/ops/__init__.py`:

- `slice_grid(sheet, columns, rows) -> list[list[U8]]`: an RGBA sheet cut into `rows` × `columns` equal cells, row by row. A
  sheet whose size isn't a whole multiple of the counts raises an error that gives both sizes.
- `feet_point(alpha) -> tuple[int, int] | None`: the figure's feet in a binary alpha: `y` is the lowest opaque row; `x` is the
  centre of the opaque pixels in the lowest two rows, rounded half down. None for an empty frame. Specks are not this Op's job:
  `fit` runs after the alpha vote, which leaves none. The docstring says that a shadow or a tail at the lowest row moves the
  point, and that the `pivot` Decision is the cure.
- `height_from_alpha(alpha, saturate=4.0) -> F64`: a rounded "pillow" height, 0 outside and rising to 1 at `saturate` px in
  from the edge (the square root of the clamped distance), from a two-pass chamfer distance (1 and √2). This is the game's
  `tools/normal_map.py` (`chamfer_distance`, `SATURATE_PX`), vectorised by rows rather than per pixel.
- `normals_from_height(height, alpha, strength=1.6) -> U8`: Sobel on `height`, normal = normalise(−dx·strength, dy·strength, 1)
  with Y up (the OpenGL convention Godot's `CanvasTexture` uses, as `encode_normals` documents), encoded as
  (v + 1) / 2 × 255. Alpha 0 pixels are (0, 0, 0, 0). The output goes through `quantise_normals` and `encode_normals` unchanged.
  Check the sign of Y against `encode_normals`' note and the game's tool, which was checked under a `PointLight2D`.

## Acceptance criteria

- [x] Golden tests: a 3 × 4 sheet sliced; a sheet of the wrong size refused; the feet of a standing figure, of a figure with
      one leg forward, and of an empty frame; the height and the normals of a disc and of a 52 px test silhouette.
- [x] On the test silhouette, `normals_from_height` matches the game's `tools/normal_map.py` within 1 per channel (the tool is
      copied into the test as the reference, not imported).
- [x] Existing goldens are unchanged; `uv run lint-imports` passes.

Budget: 120–200k tokens.
