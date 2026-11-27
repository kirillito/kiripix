"""`import --role sheet` of a Pixelbolt atlas (ticket 0401, spec §6.4): the clips, their frame order, `loop` and `ticks` and the
anchor come from the atlas's JSON. The fixture is made here: a few pixels laid out as Pixelbolt's TexturePacker-style atlas
(`frames`, `animations`, `meta`), not a real effect."""

import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_sprite import SPRITE, WORDS, load, make_zip, new_sprite, pixellab_zip

CELL = 4
ANCHOR = {"x": 2, "y": 3}


def frame_entry(x: int, y: int, duration: int, anchor: dict[str, int] | None = ANCHOR, size: int = CELL,
                trimmed: tuple[int, int, int, int] | None = None, rotated: bool = False) -> dict[str, Any]:
    """One `frames` entry. `trimmed` is the spriteSourceSize (x, y, w, h) of a frame cut down inside a `size` cell."""
    sx, sy, sw, sh = trimmed or (0, 0, size, size)
    entry: dict[str, Any] = {
        "frame": {"x": x, "y": y, "w": sw, "h": sh}, "rotated": rotated, "trimmed": trimmed is not None,
        "spriteSourceSize": {"x": sx, "y": sy, "w": sw, "h": sh}, "sourceSize": {"w": size, "h": size},
        "duration": duration, "pivot": {"x": 0.5, "y": 0.75}, "anchor": {"x": 0.5, "y": 0.75}}
    if anchor is not None:
        entry["anchorPx"] = anchor
    return entry


def atlas_of(frames: dict[str, dict[str, Any]], animations: dict[str, tuple[list[str], bool]], image: str = "fx.png",
             version: str | None = "1", width: int = 6 * CELL) -> dict[str, Any]:
    meta: dict[str, Any] = {"app": "Pixelbolt", "image": image, "format": "RGBA8888", "size": {"w": width, "h": CELL},
                            "scale": "1"}
    if version is not None:
        meta["version"] = version
    return {"frames": frames, "animations": {
        name: {"frames": names, "loop": loop, "duration": sum(frames[n]["duration"] for n in names)}
        for name, (names, loop) in animations.items()}, "meta": meta}


def sheet_png(cells: int = 6, blank: tuple[int, ...] = (5,)) -> np.ndarray:
    """`cells` 4 px cells in a row, each a different colour, the cells in `blank` empty."""
    sheet = np.zeros((CELL, cells * CELL, 4), dtype=np.uint8)
    for n in range(cells):
        if n not in blank:
            sheet[:, n * CELL:(n + 1) * CELL] = (40 * (n + 1), 255 - 30 * n, 90, 255)
    return sheet


def two_animations() -> dict[str, Any]:
    """glow: 3 frames of 50 ms, looping. burst: 3 frames of 70 ms, once, ending on a blank frame."""
    frames = {f"glow-{n}": frame_entry(n * CELL, 0, 50) for n in range(3)}
    frames.update({f"burst-{n}": frame_entry((3 + n) * CELL, 0, 70) for n in range(3)})
    return atlas_of(frames, {"glow": ([f"glow-{n}" for n in range(3)], True),
                             "burst": ([f"burst-{n}" for n in range(3)], False)})


def write_render(project: Kiripix, atlas: dict[str, Any], sheet: np.ndarray | None = None, folder: str = "render",
                 name: str = "fx") -> Path:
    """The PNG and `<name>.atlas.json` (and a recipe) as Pixelbolt writes them. Returns the atlas file's path."""
    where = project.cwd / folder
    where.mkdir(exist_ok=True)
    Image.fromarray(sheet_png() if sheet is None else sheet, "RGBA").save(where / atlas["meta"]["image"])
    (where / f"{name}.atlas.json").write_text(json.dumps(atlas, indent=2), "utf-8")
    (where / f"{name}.pixel.json").write_text('{"recipe": true}', "utf-8")
    return where / f"{name}.atlas.json"


def codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"]]


def snapshot(project: Kiripix) -> dict[str, bytes]:
    """Every file of the Project outside `.kiripix/`, by path."""
    return {p.relative_to(project.cwd).as_posix(): p.read_bytes() for p in sorted(project.cwd.rglob("*"))
            if p.is_file() and ".kiripix" not in p.relative_to(project.cwd).parts}


def refused(project: Kiripix, file: str, code: str, expect: int = 1) -> dict[str, Any]:
    if not (project.cwd / "assets" / "sprite" / "npc").exists():
        new_sprite(project)
    before = snapshot(project)
    result = project.json("import", SPRITE, file, "--role", "sheet", expect=expect)
    finding = result["findings"][0]
    assert result["ok"] is False and finding["code"] == code
    assert (finding["fix"] is None) != (finding["owner_action"] is None)
    assert snapshot(project) == before
    return result


def effect_sprite(project: Kiripix, atlas: dict[str, Any] | None = None) -> tuple[Path, dict[str, Any]]:
    folder = new_sprite(project)
    result = project.json("import", SPRITE, write_render(project, atlas or two_animations()), "--role", "sheet")
    project.json("set", SPRITE, "fit", "effect=true", "anchor=2,3")
    project.json("set", SPRITE, "finish", "outline=false")
    project.json("set", SPRITE, "frames", "directions=1")
    return folder, result


def test_two_animations_become_two_clips_with_the_atlas_timing_and_build(project: Kiripix) -> None:
    folder = new_sprite(project)
    atlas_file = write_render(project, two_animations())

    result = project.json("import", SPRITE, atlas_file, "--role", "sheet")

    data = result["data"]
    assert data["role"] == "sheet" and data["created"] and data["variant"] is None
    assert data["sheets"] == [data["sheet"]] and data["file"] == f"assets/sprite/npc/src/sheets/{data['sheet']}.png"
    assert [(c["name"], c["frames"], c["loop"], c["ticks"]) for c in data["atlas"]["clips"]] == [
        ("glow", 3, True, [3, 3, 3]), ("burst", 3, False, [4, 4, 4])]
    assert data["atlas"]["anchor"] == [2, 3] and data["atlas"]["cell"] == [4, 4] and data["atlas"]["version"] == "1"
    by_code = {f["code"]: f for f in result["findings"]}
    assert set(by_code) == {"import.anchor", "import.directions"}
    assert by_code["import.anchor"]["severity"] == "info" and by_code["import.anchor"]["fix"] == f"kiripix set {SPRITE} fit anchor=2,3"
    assert by_code["import.directions"]["fix"] == f"kiripix set {SPRITE} frames directions=1"
    stored = sorted(p.name for p in (folder / "src" / "sheets").iterdir())
    name = data["sheet"]
    assert stored == [f"{name}.atlas.json", f"{name}.pixel.json", f"{name}.png"]
    assert (folder / "src" / "sheets" / f"{name}.atlas.json").read_bytes() == atlas_file.read_bytes()
    assert (folder / "src" / "sheets" / f"{name}.png").read_bytes() == (atlas_file.parent / "fx.png").read_bytes()
    [shown] = project.json("show", SPRITE)["data"]["sheets"]
    assert shown["name"] == name and shown["imported_as"] == "fx.atlas.json"

    project.json("set", SPRITE, "fit", "effect=true", "anchor=2,3")  # the findings' `fix`, and the effect mode
    project.json("set", SPRITE, "frames", "directions=1")
    project.json("set", SPRITE, "finish", "outline=false")
    built = project.json("run", SPRITE)
    assert built["ok"] is True
    frames = load(folder / "work" / "frames" / "frames.json")
    clips = {c["name"]: c for c in frames["clips"]}
    assert list(clips) == ["burst", "glow"] and clips["glow"]["loop"] is True and clips["burst"]["loop"] is False
    assert clips["glow"]["ticks"] == [3, 3, 3] and clips["burst"]["ticks"] == [4, 4, 4]
    assert [f["source"] for f in clips["burst"]["directions"]["s"]] == ["burst-0", "burst-1", "burst-2"]
    cell = np.array(Image.open(folder / "work" / "frames" / clips["glow"]["directions"]["s"][1]["file"]))
    assert cell.shape == (4, 4, 4) and (cell == sheet_png()[:, 4:8]).all()
    assert [w["code"] for w in project.json("check", SPRITE)["findings"] if w["severity"] == "warning"] == ["sheet.empty_frame"]


def test_the_export_carries_the_clips_loop_ticks_and_the_anchor_as_pivot(project: Kiripix) -> None:
    folder, _ = effect_sprite(project)

    project.json("run", SPRITE)
    project.json("export", SPRITE)

    built = load(folder / "out" / "export" / "character.json")
    clips = {c["name"]: c for c in built["clips"]}
    assert clips["glow"]["loop"] is True and clips["glow"]["ticks"] == [3, 3, 3]
    assert clips["burst"]["loop"] is False and clips["burst"]["ticks"] == [4, 4, 4]
    assert [len(c["directions"]["s"]) for c in built["clips"]] == [3, 3]
    assert built["pivot"] == {"x": 2, "y": 3}  # the atlas's anchor, `fit anchor=2,3`
    assert "normal" not in built["files"]


def test_a_pingpong_repeated_frame_is_cut_once_and_played_twice(project: Kiripix) -> None:
    frames = {f"ping-{n}": frame_entry(n * CELL, 0, 50 + 10 * n) for n in range(3)}
    atlas = atlas_of(frames, {"ping": (["ping-0", "ping-1", "ping-2", "ping-1", "ping-0"], True)})
    folder = new_sprite(project)
    project.json("set", SPRITE, "frames", "directions=1")

    result = project.json("import", SPRITE, write_render(project, atlas, sheet_png(3, ())), "--role", "sheet")

    [clip] = result["data"]["atlas"]["clips"]
    assert clip["frames"] == 5 and clip["cells"] == 3 and clip["ticks"] == [3, 4, 4, 4, 3]
    journal = (folder / "decisions" / "frames.jsonl").read_text("utf-8").splitlines()
    sheet = next(json.loads(line)["data"] for line in journal if json.loads(line).get("decision") == "sheet")
    assert [c["name"] for c in sheet["cells"]] == ["ping-0", "ping-1", "ping-2"] and sheet["plays"] == {"ping": [0, 1, 2, 1, 0]}
    project.json("run", SPRITE, "frames")
    listed = load(folder / "work" / "frames" / "frames.json")["clips"][0]["directions"]["s"]
    assert [f["source"] for f in listed] == ["ping-0", "ping-1", "ping-2", "ping-1", "ping-0"]
    images = [np.array(Image.open(folder / "work" / "frames" / f["file"])) for f in listed]
    assert (images[1] == images[3]).all() and (images[0] == images[4]).all() and not (images[0] == images[1]).all()


def test_trimmed_frames_sit_by_sprite_source_size_in_the_untrimmed_cell(project: Kiripix) -> None:
    frames = {"t-0": frame_entry(0, 0, 50, trimmed=(1, 2, 2, 1)), "t-1": frame_entry(2, 0, 50, trimmed=(0, 0, 3, 2))}
    sheet = np.zeros((CELL, 6, 4), dtype=np.uint8)
    sheet[0:1, 0:2] = (200, 10, 10, 255)
    sheet[0:2, 2:5] = (10, 200, 10, 255)
    folder = new_sprite(project)
    project.json("set", SPRITE, "frames", "directions=1")

    result = project.json("import", SPRITE, write_render(project, atlas_of(frames, {"t": (["t-0", "t-1"], False)}, width=6),
                                                         sheet), "--role", "sheet")
    project.json("run", SPRITE, "frames")

    assert result["data"]["atlas"]["cell"] == [4, 4]
    first, second = (np.array(Image.open(folder / "work" / "frames" / "color" / "t" / "s" / f"{n:03d}.png")) for n in (0, 1))
    assert first.shape == (4, 4, 4) and (first[2, 1:3] == (200, 10, 10, 255)).all() and first[..., 3].sum() == 2 * 255
    assert (second[0:2, 0:3] == (10, 200, 10, 255)).all() and second[..., 3].sum() == 6 * 255


def test_a_folder_holding_one_atlas_imports_and_a_new_render_replaces_the_sheet_so_one_undo_steps_back(project: Kiripix) -> None:
    folder, first = effect_sprite(project)
    project.json("run", SPRITE, "frames")
    before = load(folder / "work" / "frames" / "frames.json")
    again = project.json("import", SPRITE, project.cwd / "render", "--role", "sheet")
    assert again["data"]["sheet"] == first["data"]["sheet"] and not again["data"]["created"]
    journal = folder / "decisions" / "frames.jsonl"
    entries = len(journal.read_text("utf-8").splitlines())

    longer = two_animations()
    longer["frames"]["glow-0"]["duration"] = 100
    del longer["animations"]["burst"]  # the new render has no burst: its old clip must not linger
    sheet = sheet_png()
    sheet[:, 0:4] = (9, 9, 9, 255)
    second = project.json("import", SPRITE, write_render(project, longer, sheet, folder="render2"), "--role", "sheet")

    assert second["data"]["created"] and second["data"]["sheet"] != first["data"]["sheet"]
    assert second["data"]["atlas"]["clips"][0]["ticks"] == [6, 3, 3]
    assert sorted(second["data"]["sheets"]) == sorted([first["data"]["sheet"], second["data"]["sheet"]])
    assert len(journal.read_text("utf-8").splitlines()) == entries + 1  # one Decision
    project.json("run", SPRITE, "frames")
    clips = {c["name"]: c for c in load(folder / "work" / "frames" / "frames.json")["clips"]}
    assert list(clips) == ["glow"] and clips["glow"]["ticks"] == [6, 3, 3]
    assert not [f for f in project.json("check", SPRITE, expect=0)["findings"] if f["severity"] == "error"]

    project.json("undo", SPRITE, "frames")  # one step

    project.json("run", SPRITE, "frames")
    restored = load(folder / "work" / "frames" / "frames.json")  # the new PNG stays in src/sheets/, cut by nothing
    assert restored["sheets"] == sorted([first["data"]["sheet"], second["data"]["sheet"]])
    assert {**restored, "sheets": before["sheets"]} == before
    assert [c["name"] for c in restored["clips"]] == ["burst", "glow"]
    project.json("redo", SPRITE, "frames")
    project.json("run", SPRITE, "frames")
    assert [c["name"] for c in load(folder / "work" / "frames" / "frames.json")["clips"]] == ["glow"]


def test_an_animation_whose_clip_name_ends_in_a_direction_is_refused_and_nothing_changes(project: Kiripix) -> None:
    atlas = two_animations()
    atlas["animations"]["glow-e"] = atlas["animations"].pop("glow")  # the clip glow_e
    write_render(project, atlas)

    result = refused(project, "render/fx.atlas.json", "import.atlas_invalid")

    assert "glow_e" in result["findings"][0]["message"]
    assert not (project.cwd / "assets" / "sprite" / "npc" / "decisions" / "frames.jsonl").exists()


def test_the_same_render_imported_twice_records_nothing_new(project: Kiripix) -> None:
    folder, _ = effect_sprite(project)
    journal = folder / "decisions" / "frames.jsonl"
    before = journal.read_bytes()

    project.json("import", SPRITE, project.cwd / "render" / "fx.atlas.json")

    assert journal.read_bytes() == before


def test_the_clip_decisions_keep_an_fps_the_owner_set(project: Kiripix) -> None:
    folder, _ = effect_sprite(project)
    project.json("decide", SPRITE, "frames", "--decision", json.dumps(
        {"decision": "clip", "data": {"name": "glow", "fps": 12, "loop": True, "ticks": [3, 3, 3]}}))

    project.json("import", SPRITE, write_render(project, two_animations(), folder="render3"), "--role", "sheet")
    project.json("run", SPRITE, "frames")

    clips = {c["name"]: c for c in load(folder / "work" / "frames" / "frames.json")["clips"]}
    assert clips["glow"]["fps"] == 12


def test_ticks_that_drift_over_a_tick_are_an_info_finding(project: Kiripix) -> None:
    frames = {f"slow-{n}": frame_entry(n * CELL, 0, 70) for n in range(6)}
    atlas = atlas_of(frames, {"slow": ([f"slow-{n}" for n in range(6)], True)})
    new_sprite(project)

    result = project.json("import", SPRITE, write_render(project, atlas), "--role", "sheet")

    [finding] = [f for f in result["findings"] if f["code"] == "import.ticks_rounded"]
    assert finding["severity"] == "info" and "slow" in finding["message"] and finding["data"]["clip"] == "slow"
    assert finding["data"]["ticks"] == 24 and finding["data"]["drift"] == -1.2
    assert (finding["fix"] is None) != (finding["owner_action"] is None)


def test_a_drift_of_a_tick_or_less_is_not_reported(project: Kiripix) -> None:
    new_sprite(project)

    result = project.json("import", SPRITE, write_render(project, two_animations()), "--role", "sheet")

    assert "import.ticks_rounded" not in codes(result)  # glow: 150 ms is 9 ticks and rounds to 9; burst: 210 ms is 12.6, 12


def test_frames_with_different_anchors_are_a_warning_and_no_anchor_is_named(project: Kiripix) -> None:
    atlas = two_animations()
    atlas["frames"]["burst-1"]["anchorPx"] = {"x": 1, "y": 1}
    new_sprite(project)

    result = project.json("import", SPRITE, write_render(project, atlas), "--role", "sheet")

    [finding] = [f for f in result["findings"] if f["code"] == "import.anchor_varies"]
    assert finding["severity"] == "warning" and "burst-1" in finding["message"] and finding["owner_action"]
    assert "import.anchor" not in codes(result) and result["data"]["atlas"]["anchor"] is None


def test_a_format_version_kiripix_was_not_checked_against_is_an_info_finding(project: Kiripix) -> None:
    new_sprite(project)

    result = project.json("import", SPRITE, write_render(project, atlas_of(
        two_animations()["frames"], {"glow": (["glow-0", "glow-1"], True)}, version="2")), "--role", "sheet")

    [finding] = [f for f in result["findings"] if f["code"] == "import.atlas_version"]
    assert finding["severity"] == "info" and "version 2" in finding["message"] and finding["data"] == {"version": "2"}
    assert result["data"]["atlas"]["version"] == "2"
    assert "import.atlas_version" not in codes(project.json("import", SPRITE, write_render(
        project, two_animations(), folder="ok"), "--role", "sheet"))


def test_an_atlas_whose_image_is_missing_is_refused_and_nothing_changes(project: Kiripix) -> None:
    new_sprite(project)
    atlas_file = write_render(project, two_animations())
    (atlas_file.parent / "fx.png").unlink()

    refused(project, "render/fx.atlas.json", "import.atlas_image_missing")


def test_a_rotated_frame_is_refused_and_nothing_changes(project: Kiripix) -> None:
    atlas = two_animations()
    atlas["frames"]["glow-1"]["rotated"] = True
    write_render(project, atlas)

    result = refused(project, "render/fx.atlas.json", "import.atlas_rotated")

    assert "glow-1" in result["findings"][0]["message"]


def test_a_frame_rect_outside_the_png_is_refused_and_nothing_changes(project: Kiripix) -> None:
    atlas = two_animations()
    atlas["frames"]["burst-2"]["frame"]["x"] = 22
    write_render(project, atlas)

    result = refused(project, "render/fx.atlas.json", "import.atlas_rect")

    assert "burst-2" in result["findings"][0]["message"]


def test_a_json_that_is_not_a_pixelbolt_atlas_gets_the_plain_imports_error(project: Kiripix) -> None:
    (project.cwd / "other.json").write_text(json.dumps({"frames": {}, "meta": {"app": "TexturePacker"}}), "utf-8")
    (project.cwd / "broken.json").write_text("{not json", "utf-8")

    refused(project, "other.json", "import.sheet_invalid")
    refused(project, "broken.json", "import.sheet_invalid")


def test_an_atlas_with_a_frame_it_does_not_have_is_refused(project: Kiripix) -> None:
    atlas = two_animations()
    atlas["animations"]["glow"]["frames"].append("glow-9")
    write_render(project, atlas)

    refused(project, "render/fx.atlas.json", "import.atlas_invalid")


def test_a_folder_with_two_atlases_is_refused(project: Kiripix) -> None:
    write_render(project, two_animations())
    write_render(project, two_animations(), name="other")

    refused(project, "render", "import.atlas_ambiguous")


def test_an_atlas_on_a_room_is_the_plain_imports_refusal(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    write_render(project, two_animations())

    result = project.json("import", "room.alley", "render/fx.atlas.json", "--role", "sheet", expect=1)

    assert result["findings"][0]["code"] == "import.role_needs_sprite"


def test_a_plain_png_sheet_and_a_pixellab_zip_import_as_before(project: Kiripix) -> None:
    folder = new_sprite(project)
    Image.fromarray(sheet_png(), "RGBA").save(project.cwd / "walk.png")
    make_zip(project, "pixellab.zip", pixellab_zip(WORDS))

    png = project.json("import", SPRITE, "walk.png", "--role", "sheet")
    archive = project.json("import", SPRITE, "pixellab.zip", "--role", "sheet")

    assert png["findings"] == [] and archive["findings"] == [] and png["data"]["atlas"] is None
    assert sorted(p.name for p in (folder / "src" / "sheets").iterdir()) == sorted(
        [f"{png['data']['sheet']}.png", f"{archive['data']['sheet']}.zip"])
    assert zipfile.is_zipfile(folder / "src" / "sheets" / f"{archive['data']['sheet']}.zip")
