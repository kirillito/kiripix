---
status: done
milestone: M6
agent: godot-export
type: ticket
parent: 0324-m6-rooms-at-chapter-scale-style-npcs.md
depends_on: [0341-m6-room-normals-stage.md]
---

# M6: export a room's normal maps as `CanvasTexture`s

Spec §9 (Room) and §14 (M6). Part of [0324](0324-m6-rooms-at-chapter-scale-style-npcs.md). Ticket 3 of 0252's outline;
the trial's Godot test project (`backlog/m5/0252-trial/`) is the reference.

## What to build

- For a room whose `normals` Stage has output: export **cuts** the Stage's one `normal.png` (ADR 0014 decision 4) into
  `normals/plate.png` and `normals/<layer>.png` by each one's alpha, as `palette` cuts its mapped composite, and writes them
  beside the scene. Each `Sprite2D` (the Plate and every foreground Layer) gets a `CanvasTexture` `.tres` with
  `diffuse_texture` and `normal_texture`, in place of its plain texture. A Look's and a Loop's pieces take the room's normal
  map cut to their box (ADR 0014 decision 7), with no depth call of their own, so a lit Look matches the room. A Loop's
  frames share one normal map.
- `room.json` gains `normals`: `null`, or the files by Plate and Layer. That is a `schema_version` bump, 14 to 15 (0345 took
  it to 13, 0352 to 14), with its migration. Every file goes in the Manifest. A room with `mode=off` exports as before, byte for byte
  except for `room.json`'s version.
- The export Stage's `version` bumps, 5 to 6 (0345 took it to 4, 0352 to 5), and `export` gains the `normals` edge; named in the
  Result.
- A note to the game for its M10-02, in the Result: the light height and energy need tuning to a room, and a normal-mapped
  Plate reads darker under the same light (0252's finding 4).

## Acceptance criteria

- [x] CLI seam: a test room with normals exports the `CanvasTexture`s, the files and `room.json`'s `normals`, all in the
      Manifest; a room without normals has `normals: null` and the scene unchanged.
- [x] Headless Godot (as the other export tests): the scene loads, and the Plate's material has a normal texture.
- [x] Spec §9 updated; `room.json`'s new version named.

## Result

**Version bumps.** `room.json` `schema_version` 14 to 15 (0352 took it to 14): `normals`, `null` or the files. The `export` Stage
`version` 5 to 6 (0352 took it to 5), and `export` reads `normals` too (`upstream` gains it), so a room's export is stale on every room.
No migration of an old `room.json`: it is a Stage's rebuilt output, so, as with every bump before it, `read_room` refuses a schema 14
file with the finding that names the rebuild (`export.room_invalid`, fix `kiripix run <asset> export --force`); nothing of the owner's lives in it. The Manifest
format is unchanged (`schema_version` 4): the new files are listed in its `files`, and no ID is added.

**What it writes.** With `work/normals/normal.png` present, the `export` Stage cuts it, by the alpha of the picture it goes with, into
`normals/<file>` for the Plate (`normals/plate.png`), each Layer (`normals/layer.<id>.png`), each remainder
(`normals/remainders/<id>.png`), and each piece of a Look (`normals/looks/<look>/...`) and a Loop (`normals/loops/<loop>/...`): pixels
outside the picture's alpha are all zero. A Look's or Loop's piece takes the room's map cut to the Look's or Loop's box (no depth call);
a Loop's strip tiles that one cell across its `hframes` x `vframes`, so the frames share it. The Exporter writes, beside each map, a
`CanvasTexture` `.tres` of the same name (`diffuse_texture`, `normal_texture`; no `texture_filter`, so a picture is drawn as before),
and the scene's `ext_resource` of each picture is that `.tres` (type `CanvasTexture`, same ID), so every node is unchanged. A room
without normals, `mode=off`, writes none of it: `normals: null`, the scene byte for byte as before, only `room.json`'s version differs.
`room.json`'s `normals` is `{plate, layers: {id: file}, remainders: {id: file}, looks: {id: {file, pieces: {layer: file}}}, loops: {...}}`.
Code: `_export_normals` in `kiripix/recipes/room.py`, `normal_pairs`, `canvas_file` and `room_canvas_texture` in `kiripix/export/godot.py`,
`_room_files` in `kiripix/export/__init__.py`. Spec §6.1 (export row) and §9 (Room) are updated.

**Tests.** `tests/cli/test_export_room_normals.py` (CLI seam: the files, `room.json`, the `.tres` text, the scene, the Manifest, a second
export writing nothing, `normals: null` and the plain scene; and the marked Godot test: the scene loads and the Plate and each Layer show a
`CanvasTexture` with a normal texture of the room's size, run on Godot 4.7.2). Loops and Looks with normals have no test of their own: the
cut is the same function, and Godot's handling of a strip's `CanvasTexture` is untried.

**Note to the game for its M10-02.** The light's height and energy need tuning to a room, and a normal-mapped Plate reads darker under the
same light (0252's finding 4). A Loop's sprite keeps its unshaded `CanvasItemMaterial` (`light_mode = 1`), so its normal map does
nothing until the game drops that material from it; a Look's pieces are lit like the Plate.

**The Owner's decision, 2026-11-20:** no migration function for this bump. An old file is a Stage's rebuilt output, so it is refused with a finding that names the rebuild (CLAUDE.md's rule for rebuilt output), and the `version` bump makes the Stage stale, so one `run` rebuilds it. That stands in for "with its migration" above.
