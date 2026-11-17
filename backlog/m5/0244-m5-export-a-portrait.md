---
status: todo
milestone: M5
agent: godot-export
type: ticket
parent: 0240-m5-portrait-kind.md
depends_on: [0243-m5-portrait-recipe.md]
---

# M5: export a portrait set

Spec §9. Part of [0240](0240-m5-portrait-kind.md).

## What to build

- The portrait's `export` Stage leaves `<emotion>.png` per emotion and `portrait.json` in `out/export/`: `schema_version`,
  `asset`, `canvas`, `anchor`, `fallback`, and `emotions` (ID and file, in the Decisions' order).
- The Exporter writes them under `portraits/<asset>/` beside the other exports, with no scene: the game's portrait UI loads
  the PNGs and reads `portrait.json`.
- **The Manifest:** the emotion IDs are exported IDs in their own list, frozen once exported. A `remove` or `rename` of an
  exported emotion is refused before it's recorded, as a Loop's is.
- **Checks:** every image is the canvas's size, with the same anchor (`export.portrait_canvas`); the fallback names an
  emotion of the set; binary alpha.

## Acceptance criteria

- [ ] CLI seam: a built portrait exports one PNG per emotion and `portrait.json`, and the Manifest lists the emotions.
- [ ] A rename of an exported emotion is refused. Adding an emotion after export is fine.
- [ ] Spec §9 gets a Portrait row.
