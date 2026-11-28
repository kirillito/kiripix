"""`import --loop` of a Pixelbolt atlas into a room's frame Loop (ticket 0406): the animation's frames become frames 1 to N, its
durations the `timing` (ticks, rest), in one `kit` Decision so one `undo` reverts the import. The fixture is made here: a few
palette-coloured pixels on transparent cells of the Loop's box size, laid out as Pixelbolt's atlas (see test_import_atlas)."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_export import godot_project, set_target
from test_export_looks import FOLDER, exported_room
from test_import_atlas import atlas_of, frame_entry, snapshot
from test_layers_stage import ROOM, rgba
from test_loop_kit import KIT, a_frame_loop, write_kit
from test_loops import LOOP, build, findings, out, record, tiles
from test_masks import decide as decide_mask
from test_place import place

BOX = 30  # the triangle region's box of the test room


def room_cell(project: Kiripix) -> np.ndarray:
    return rgba(project.cwd / KIT / "frame_000.png")


def sheet_of(project: Kiripix, cells: int) -> np.ndarray:
    """`cells` cells side by side; cell n has a 2x2 patch (the room's colour from elsewhere in the room) at (3 + 2n, 3 + 2n)."""
    room = room_cell(project)
    colour = room[10, 10].copy()
    other = room[6, 20].copy()
    sheet = np.zeros((BOX, cells * BOX, 4), dtype=np.uint8)
    for n in range(cells):
        sheet[3 + 2 * n:5 + 2 * n, n * BOX + 3 + 2 * n:n * BOX + 5 + 2 * n] = colour if n % 2 == 0 else other
    return sheet


def render(project: Kiripix, atlas: dict[str, Any], cells: int = 3, folder: str = "render", name: str = "fx") -> Path:
    where = project.cwd / folder
    where.mkdir(exist_ok=True)
    Image.fromarray(sheet_of(project, cells), "RGBA").save(where / atlas["meta"]["image"])
    (where / f"{name}.atlas.json").write_text(json.dumps(atlas), "utf-8")
    (where / f"{name}.pixel.json").write_text('{"recipe": true}', "utf-8")
    return where / f"{name}.atlas.json"


def drip(durations: tuple[int, ...] = (50, 70, 50), loop: bool = True, names: tuple[str, ...] | None = None,
         extra: dict[str, tuple[list[str], bool]] | None = None) -> dict[str, Any]:
    """An atlas of BOX-sized cells with one animation `drip` over frames drip-0.. (`names` is its playback order)."""
    frames = {f"drip-{n}": frame_entry(n * BOX, 0, d, size=BOX) for n, d in enumerate(durations)}
    order = list(names or frames)
    animations = {"drip": (order, loop), **(extra or {})}
    atlas = atlas_of(frames, animations, image="fx.png", width=BOX * len(durations))
    return atlas


def loop_room(project: Kiripix) -> Path:
    folder = a_frame_loop(project, lamp_layer=False)
    write_kit(project, 2)  # only to read the room's own frame 0 for palette colours
    return folder


def kit_entries(folder: Path) -> list[dict[str, Any]]:
    lines = (folder / "decisions" / "loops.jsonl").read_text("utf-8").splitlines()
    return [json.loads(line) for line in lines]


def refused(project: Kiripix, file: str, code: str, *extra: str) -> dict[str, Any]:
    before = snapshot(project)
    result = project.json("import", ROOM, file, "--loop", LOOP, *extra, expect=1)
    finding = result["findings"][0]
    assert result["ok"] is False and finding["code"] == code
    assert (finding["fix"] is None) != (finding["owner_action"] is None)
    assert snapshot(project) == before
    return result


def test_an_atlas_becomes_frames_1_to_n_with_the_rounded_ticks_and_rest_and_builds(project: Kiripix) -> None:
    folder = loop_room(project)
    atlas_file = render(project, drip())

    result = project.json("import", ROOM, atlas_file, "--loop", LOOP)

    data = result["data"]
    assert data["loop"] == LOOP and data["animation"] == "drip" and data["ticks"] == [3, 4, 3] and data["created"]
    assert len(data["loop_frames"]) == 3 and data["file"].startswith(f"assets/room/")
    assert result["findings"] == []
    [kit] = [e for e in kit_entries(folder) if e.get("decision") == "kit"]
    assert kit["data"]["timing"] == {"ticks": [3, 4, 3], "rest": True} and kit["data"]["box"] == [1, 1, BOX, BOX]
    stored = sorted(p.name for p in (folder / "src" / "loops" / LOOP / "atlas").iterdir())
    assert len(stored) == 3 and sum(n.endswith(".png") for n in stored) == 1
    assert any(n.endswith(".atlas.json") for n in stored) and any(n.endswith(".pixel.json") for n in stored)

    build(project)
    assert stage_status(project, ROOM)["loops"] == "done"
    built = record(folder)
    assert built["frames"] == 4 and built["timing"] == {"ticks": [3, 4, 3], "rest": True}
    assert [list(s) for s in built["sequence"]] == [[1, 3], [2, 4], [3, 3]]
    pieces = tiles(out(folder) / built["plate"], built["box"], built["frames"], built["columns"])
    room = room_cell(project)
    inside = room[..., 3] > 0
    assert (pieces[0] == 0).all(), "frame 0 is the room: a strip leaves it clear"
    room_pixels = rgba(folder / "work" / "palette" / "palette.png")[1:31, 1:31]
    for piece in pieces[1:]:
        shown = piece[..., 3] > 0
        assert (piece[shown] != room_pixels[shown]).any(axis=1).all(), "a strip keeps only what differs"
    assert any((piece[..., 3] > 0).any() for piece in pieces[1:]), "a patch of another colour is kept"
    assert not (pieces[2] == pieces[1]).all(), "the frames differ (frame 1's patch is the room's own colour: clear)"
    assert [f for f in findings(project) if f["severity"] == "error"] == []
    assert project("check", ROOM, "--json").code == 0


def test_the_loop_exports_with_the_sequence_and_rest(project: Kiripix) -> None:
    folder = loop_room(project)
    decide_mask(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")  # `reach` needs a Spawn before `export` runs
    godot_project(project)
    set_target(project)
    project.json("run", ROOM, "masks")  # the solid flood re-staled it, and the atlas is cut by it
    project.json("import", ROOM, render(project, drip()), "--loop", LOOP)
    project.json("run", ROOM)

    project.json("export", ROOM)

    [loop] = exported_room(project)["loops"]
    assert loop["id"] == LOOP and loop["frames"] == 4 and loop["sequence"] == [1, 3, 2, 4, 3, 3] and loop["rest"] is True
    assert (project.cwd / FOLDER).is_dir() and folder.is_dir()


def test_a_pingpong_animation_plays_its_repeated_frame_twice_each_play_with_its_own_ticks(project: Kiripix) -> None:
    folder = loop_room(project)
    atlas = drip((50, 60, 70), names=("drip-0", "drip-1", "drip-2", "drip-1"))

    data = project.json("import", ROOM, render(project, atlas), "--loop", LOOP)["data"]

    assert data["ticks"] == [3, 4, 4, 4]
    frames = data["loop_frames"]
    assert len(frames) == 4 and frames[1] == frames[3] and len(set(frames)) == 3
    assert len(list((folder / "src" / "loops" / LOOP).glob("*.png"))) == 3, "the repeated frame is stored once"
    build(project)
    built = record(folder)
    assert built["frames"] == 5 and [list(s) for s in built["sequence"]] == [[1, 3], [2, 4], [3, 4], [4, 4]]
    pieces = tiles(out(folder) / built["plate"], built["box"], built["frames"], built["columns"])
    assert (pieces[2] == pieces[4]).all() and not (pieces[2] == pieces[3]).all()


def test_a_trimmed_frame_is_placed_by_sprite_source_size(project: Kiripix) -> None:
    folder = loop_room(project)
    room = room_cell(project)
    colour = room[10, 10].copy()
    frames = {"t-0": frame_entry(0, 0, 50, size=BOX, trimmed=(4, 5, 3, 2)), "t-1": frame_entry(3, 0, 50, size=BOX)}
    sheet = np.zeros((BOX, 3 + BOX, 4), dtype=np.uint8)
    sheet[0:2, 0:3] = colour
    sheet[:, 3:3 + BOX] = 0
    sheet[7, 3 + 7] = colour
    where = project.cwd / "render"
    where.mkdir()
    Image.fromarray(sheet, "RGBA").save(where / "fx.png")
    atlas = atlas_of(frames, {"t": (["t-0", "t-1"], True)}, image="fx.png", width=3 + BOX)
    (where / "fx.atlas.json").write_text(json.dumps(atlas), "utf-8")

    data = project.json("import", ROOM, where, "--loop", LOOP)["data"]  # a folder holding one atlas

    first = np.array(Image.open(folder / "src" / "loops" / LOOP / f"{data['loop_frames'][0]}.png"))
    assert first.shape == (BOX, BOX, 4) and int(first[..., 3].sum()) == 6 * 255 and (first[5:7, 4:7] == colour).all()


def test_two_animations_need_one_named_and_an_unknown_name_is_refused(project: Kiripix) -> None:
    loop_room(project)
    atlas = drip(extra={"spare": (["drip-0", "drip-1"], True)})
    render(project, atlas)

    result = refused(project, "render/fx.atlas.json", "import.atlas_ambiguous")
    assert "drip" in result["findings"][0]["message"] and "spare" in result["findings"][0]["message"]
    refused(project, "render/fx.atlas.json", "import.atlas_animation", "--animation", "nope")

    data = project.json("import", ROOM, "render/fx.atlas.json", "--loop", LOOP, "--animation", "spare")["data"]
    assert data["animation"] == "spare" and data["ticks"] == [3, 4]


def test_a_cell_of_another_size_is_refused_naming_both_sizes(project: Kiripix) -> None:
    loop_room(project)
    frames = {f"drip-{n}": frame_entry(n * 8, 0, 50, size=8) for n in range(3)}
    where = project.cwd / "render"
    where.mkdir()
    Image.fromarray(np.zeros((8, 24, 4), dtype=np.uint8), "RGBA").save(where / "fx.png")
    (where / "fx.atlas.json").write_text(json.dumps(atlas_of(frames, {"drip": (list(frames), True)}, width=24)), "utf-8")

    result = refused(project, "render/fx.atlas.json", "import.atlas_size")

    assert "8x8" in result["findings"][0]["message"] and "30x30" in result["findings"][0]["message"]


def test_the_atlas_refusals_change_nothing(project: Kiripix) -> None:
    loop_room(project)
    missing = render(project, drip(), folder="missing")
    (missing.parent / "fx.png").unlink()
    refused(project, "missing/fx.atlas.json", "import.atlas_image_missing")
    rotated = drip()
    rotated["frames"]["drip-1"]["rotated"] = True
    render(project, rotated, folder="rotated")
    refused(project, "rotated/fx.atlas.json", "import.atlas_rotated")
    outside = drip()
    outside["frames"]["drip-2"]["frame"]["x"] = 70
    render(project, outside, folder="outside")
    refused(project, "outside/fx.atlas.json", "import.atlas_rect")
    one = drip((50,))
    render(project, one, cells=1, folder="one")
    refused(project, "one/fx.atlas.json", "import.atlas_frames")
    (project.cwd / "other.json").write_text(json.dumps({"meta": {"app": "TexturePacker"}}), "utf-8")
    result = project.json("import", ROOM, "other.json", "--loop", LOOP, expect=1)
    assert result["findings"][0]["code"] not in ("import.atlas_invalid", "import.atlas_size")


def test_an_atlas_with_a_kit_or_more_frames_is_refused_and_a_loop_that_isnt_a_frame_loop_too(project: Kiripix) -> None:
    loop_room(project)
    render(project, drip())
    (project.cwd / "more.png").write_bytes((project.cwd / "render" / "fx.png").read_bytes())

    refused(project, "render/fx.atlas.json", "import.atlas_takes_one_file", str(project.cwd / "more.png"))
    before = snapshot(project)
    result = project.json("import", ROOM, "render/fx.atlas.json", "--loop", "nowhere", expect=1)
    assert result["findings"][0]["code"] == "import.loop_unknown" and snapshot(project) == before


def test_the_findings_say_the_ticks_rounded_the_version_and_the_one_shot(project: Kiripix) -> None:
    loop_room(project)
    atlas = drip((70,) * 6, loop=False)
    atlas["meta"]["version"] = "9"

    result = project.json("import", ROOM, render(project, atlas, cells=6), "--loop", LOOP)

    by_code = {f["code"]: f for f in result["findings"]}
    assert set(by_code) == {"import.ticks_rounded", "import.atlas_version", "import.atlas_one_shot"}
    assert by_code["import.atlas_one_shot"]["severity"] == "warning" and by_code["import.ticks_rounded"]["severity"] == "info"
    assert by_code["import.atlas_version"]["data"] == {"version": "9"} and "Loop" in by_code["import.ticks_rounded"]["message"]
    assert all((f["fix"] is None) != (f["owner_action"] is None) for f in result["findings"])


def test_a_reimport_is_one_undo_and_the_same_atlas_again_records_nothing(project: Kiripix) -> None:
    folder = loop_room(project)
    project.json("import", ROOM, render(project, drip()), "--loop", LOOP)
    build(project)
    before = record(folder)
    journal = folder / "decisions" / "loops.jsonl"
    size = journal.read_bytes()
    project.json("import", ROOM, "render/fx.atlas.json", "--loop", LOOP)
    assert journal.read_bytes() == size

    longer = drip((100, 70, 50, 50), names=("drip-0", "drip-1", "drip-2", "drip-3"))
    entries = len(journal.read_text("utf-8").splitlines())
    render(project, longer, cells=4, folder="render2")
    project.json("import", ROOM, "render2/fx.atlas.json", "--loop", LOOP)
    assert len(journal.read_text("utf-8").splitlines()) == entries + 1
    build(project)
    assert record(folder)["frames"] == 5 and record(folder)["timing"]["ticks"] == [6, 4, 3, 3]

    project.json("undo", ROOM, "loops")

    build(project)
    again = record(folder)
    assert again["frames"] == before["frames"] and again["timing"] == before["timing"] and again["sequence"] == before["sequence"]
    assert (out(folder) / again["plate"]).read_bytes() == (out(folder) / before["plate"]).read_bytes()


def test_a_timing_decided_after_the_import_wins_and_a_plain_kit_import_works_as_before(project: Kiripix) -> None:
    folder = loop_room(project)
    project.json("import", ROOM, render(project, drip()), "--loop", LOOP)
    project.json("decide", ROOM, "loops", "--decision", json.dumps(
        {"decision": "timing", "data": {"loop": LOOP, "ticks": [9, 9, 9], "rest": True}}))
    build(project)
    assert record(folder)["timing"]["ticks"] == [9, 9, 9]

    project.json("undo", ROOM, "loops")  # the timing Decision
    build(project)
    assert record(folder)["timing"]["ticks"] == [3, 4, 3]


def test_a_plain_kit_import_is_unchanged_and_has_no_timing(project: Kiripix) -> None:
    folder = loop_room(project)
    painted = project.cwd / KIT / "frame_001.png"
    frame = room_cell(project)
    frame[8, 8] = frame[11, 11]
    Image.fromarray(frame, "RGBA").save(painted)

    data = project.json("import", ROOM, painted, "--loop", LOOP)["data"]

    assert data["animation"] is None and data["ticks"] == [] and len(data["loop_frames"]) == 1
    [kit] = [e for e in kit_entries(folder) if e.get("decision") == "kit"]
    assert "timing" not in kit["data"]


def test_a_plain_kit_import_after_an_atlas_drops_the_atlas_timing_for_the_timing_decided_before(project: Kiripix) -> None:
    folder = loop_room(project)
    project.json("decide", ROOM, "loops", "--decision", json.dumps(
        {"decision": "timing", "data": {"loop": LOOP, "ticks": 5}}))
    project.json("import", ROOM, render(project, drip()), "--loop", LOOP)
    build(project)
    assert record(folder)["timing"]["ticks"] == [3, 4, 3]

    painted = project.cwd / KIT / "frame_001.png"
    frame = room_cell(project)
    frame[8, 8] = frame[11, 11]
    Image.fromarray(frame, "RGBA").save(painted)
    project.json("import", ROOM, painted, "--loop", LOOP)
    build(project)

    assert record(folder)["frames"] == 2 and record(folder)["timing"]["ticks"] == 5 and "rest" not in record(folder)["timing"]
