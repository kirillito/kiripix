# Runners run before the palette

The old `clean` Stage is split into `fit` (grid detection or downscale to the target size, palette-free) and `palette`
(OKLab mapping, dithering, orphan cleanup), and every Runner Stage sits between them:
room: brief → source → fit → layers → masks → palette → place → reach → export;
prop: brief → source → cutout → fit → palette → finish → footprint → export;
character (rendered at the target size, so no `fit`): model → rig → clips → render → palette → finish → sheet → export.
`palette` means the same thing in every Recipe; outlines and normal-map alignment happen in `finish`, after mapping.
With `clean` first, a palette tweak changed the input of every SAM 2 and LaMa call, and every Room stopped at
needs-input for a small change. Now a palette change only invalidates deterministic work.

## Consequences

- `fit` records the Source-to-target transform (scale and offset). Runners work on the high-resolution Source, and
  their inputs, outputs and the click Decisions all map through that one transform. Clicks are stored in target pixels
  and map to the centre of their target pixel on the Source; brushes and Overrides exist in target pixels only.
- A lifted Layer and its Plate hole share one grow parameter, in target pixels after `fit`, applied only where the
  Runner's alpha was partial (default 1 px, 0 allowed). The hole therefore equals the Layer's alpha, and any leftover
  background rim is trimmed with an Override.
- Runner inputs are capped (about 1–1.5k px, or a crop around each hole) to fit 8 GB of VRAM.
- `palette` maps the whole composite once; each foreground Layer is that mapped image cut by its alpha, and the Plate is
  the same image with only its inpainted areas mapped separately. Recomposing the Plate and Layers is therefore exact
  both at `layers` (against the fit image) and after `palette`.
