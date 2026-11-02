# One binary image per Mask

Each Mask (`solid`, `oneway`, `ladder`, …) is stored as its own 1-bit PNG, not as one colour-indexed image where each
pixel holds a single layer value. With a single-value image, every overlap needs its own combined colour (`both`,
and next `oneway`+`foreground`, `ladder`+`foreground`), so the colour table grows with every new Mask. Separate binary
images make overlaps free, and they make "every Mask pixel is a defined value" true by construction.

## Consequences

- Colours exist only for display and import. Import still accepts a single colour image painted in an editor: it snaps
  each pixel to the nearest defined colour and splits the image into one Mask per name. A combined colour such as
  "both" is only an import mapping to several Masks, never stored.
- Changing this later means migrating every Asset's masks, which is why this is recorded.
