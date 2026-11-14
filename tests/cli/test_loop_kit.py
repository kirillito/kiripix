"""A frame Loop's kit and the frames painted on it (ticket 0193, Part A): `loop kit` writes the folder, `import --loop`
records the frames, and a refit puts them in needs-input. On the `layers` test room, with a triangle for a region."""

import json
from pathlib import Path

from PIL import Image

from conftest import Kiripix, stage_status
from test_layers_stage import ROOM, built_room, rgba
from test_loops import LOOP, decide, declare
from test_looks_build import room_with_a_lamp_layer

TRIANGLE = [[1, 1], [30, 1], [1, 30]]
KIT = "kit_lamp"


def a_frame_loop(project: Kiripix, region: list[list[int]] | None = TRIANGLE, lamp_layer: bool = True) -> Path:
    if lamp_layer:
        folder = room_with_a_lamp_layer(project)
    else:  # a room that a refit can rebuild without a Runner call
        folder = built_room(project)
        project.json("run", ROOM, "masks")
        project.json("run", ROOM, "palette")
    declare(project, form="frames")
    if region is not None:
        decide(project, "polygon", {"loop": LOOP, "points": region})
    return folder


def write_kit(project: Kiripix, frames: int = 3, *extra: str, expect: int = 0) -> dict[str, object]:
    return project.json("loop", "kit", ROOM, LOOP, KIT, "--frames", str(frames), *extra, expect=expect)


def painted(project: Kiripix, number: int, size: tuple[int, int] | None = None, name: str | None = None) -> Path:
    """Frame `number` of the kit with one pixel painted a palette colour (or a blank image of `size`)."""
    path = project.cwd / KIT / (name or f"frame_{number:03d}.png")
    if size is not None:
        Image.new("RGBA", size, (255, 255, 255, 255)).save(path)
        return path
    frame = rgba(project.cwd / KIT / "frame_000.png")
    frame[number, number] = frame[number + 3, number + 3]  # a pixel of another place in the room: still the palette
    Image.fromarray(frame, "RGBA").save(path)
    return path


def kit_decisions(folder: Path) -> list[dict[str, object]]:
    lines = (folder / "decisions" / "loops.jsonl").read_text("utf-8").splitlines()
    return [json.loads(line) for line in lines if json.loads(line).get("decision") == "kit"]


def reason(project: Kiripix) -> str:
    return str(project.json("next", ROOM)["data"]["reason"])


def refit(project: Kiripix) -> None:
    project.json("set", ROOM, "fit", "offset_x=2")
    for stage in ("fit", "layers", "masks", "palette"):
        project.json("run", ROOM, stage)
    project.json("run", ROOM, "looks")


# loop kit


def test_loop_kit_writes_the_frames_the_palette_and_a_readme(project: Kiripix) -> None:
    folder = a_frame_loop(project)

    written = write_kit(project, 3)["data"]

    assert written["box"] == [1, 1, 30, 30] and written["frames"] == 3  # type: ignore[index]
    kit = project.cwd / KIT
    assert sorted(p.name for p in kit.iterdir()) == [
        "README.txt", "frame_000.png", "frame_001.png", "frame_002.png", "kit.json", "palette.gpl", "palette.png"]
    room = rgba(folder / "work" / "palette" / "palette.png")[1:31, 1:31]
    frame0 = rgba(kit / "frame_000.png")
    assert frame0.shape[:2] == (30, 30)
    inside = frame0[..., 3] > 0
    assert inside[0, 0] and inside[5, 5] and not inside[29, 29], "transparent outside the region"
    assert (frame0[inside] == room[inside]).all(), "frame 0 is the room inside the region"
    assert not frame0[~inside].any()
    for name in ("frame_001.png", "frame_002.png"):
        assert (kit / name).read_bytes() == (kit / "frame_000.png").read_bytes()
    assert len((kit / "README.txt").read_text("utf-8").splitlines()) == 3
    gpl = (kit / "palette.gpl").read_text("utf-8").splitlines()
    swatches = rgba(kit / "palette.png")
    assert gpl[0] == "GIMP Palette" and swatches.shape[0] == 8 and swatches.shape[1] == 8 * (len(gpl) - 3)


def test_a_second_kit_in_the_same_folder_is_refused_without_force(project: Kiripix) -> None:
    a_frame_loop(project)
    write_kit(project, 3)
    painted(project, 1)
    before = (project.cwd / KIT / "frame_001.png").read_bytes()

    refused = write_kit(project, 3, expect=1)
    assert refused["findings"][0]["code"] == "loop.kit_exists"  # type: ignore[index]
    assert (project.cwd / KIT / "frame_001.png").read_bytes() == before

    write_kit(project, 2, "--force")
    kit = project.cwd / KIT
    assert not (kit / "frame_002.png").exists(), "frames of a larger kit don't stay behind"
    assert (kit / "frame_001.png").read_bytes() == (kit / "frame_000.png").read_bytes()


def test_loop_kit_refuses_what_it_cannot_cut(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    unknown = write_kit(project, 3, expect=1)["findings"][0]  # type: ignore[index]
    assert unknown["code"] == "loop.kit_unknown" and unknown["fix"] and "frames" in unknown["fix"]

    declare(project, form="frames")
    assert write_kit(project, 3, expect=1)["findings"][0]["code"] == "loop.kit_no_region"  # type: ignore[index]

    decide(project, "polygon", {"loop": LOOP, "points": TRIANGLE})
    assert write_kit(project, 1, expect=1)["findings"][0]["code"] == "loop.kit_frames"  # type: ignore[index]
    assert not (project.cwd / KIT).exists()


def test_loop_kit_refuses_a_cycle_loop(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    declare(project)
    decide(project, "polygon", {"loop": LOOP, "points": TRIANGLE})

    assert write_kit(project, 3, expect=1)["findings"][0]["code"] == "loop.kit_not_frames"  # type: ignore[index]


def test_a_kit_of_a_loop_on_a_layer_is_cut_to_the_layers_alpha(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    declare(project, form="frames", layer="lamp")
    decide(project, "polygon", {"loop": LOOP, "points": [[1, 1], [30, 1], [30, 30], [1, 30]]})

    box = write_kit(project, 2)["data"]["box"]  # type: ignore[index]

    layer = next((folder / "work" / "layers").glob("*lamp*.png"))
    alpha = rgba(layer)[..., 3] > 0
    x, y, width, height = box
    frame0 = rgba(project.cwd / KIT / "frame_000.png")
    assert ((frame0[..., 3] > 0) == alpha[y:y + height, x:x + width]).all()


# import --loop


def test_importing_painted_frames_records_them(project: Kiripix) -> None:
    folder = a_frame_loop(project)
    write_kit(project, 3)
    one, two = painted(project, 1), painted(project, 2)

    result = project.json("import", ROOM, one, two, "--loop", LOOP)

    data = result["data"]
    assert data["loop"] == LOOP and len(data["loop_frames"]) == 2 and data["created"] is True
    stored = sorted(p.name for p in (folder / "src" / "loops" / LOOP).iterdir())
    assert stored == sorted(f"{name}.png" for name in data["loop_frames"])
    (record,) = kit_decisions(folder)
    kit = json.loads((project.cwd / KIT / "kit.json").read_text("utf-8"))
    assert record["data"] == {"loop": LOOP, "box": [1, 1, 30, 30], "frames": data["loop_frames"], "fit": kit["fit"],
                              "palette": kit["palette"]}
    names = (folder / "imported.jsonl").read_text("utf-8")
    assert "frame_001.png" in names and "frame_002.png" in names, "the names the frames were imported with are kept"
    assert stage_status(project, ROOM)["source"] == "done"
    undone = project.json("undo", ROOM, "loops")
    assert undone["ok"]


def test_frame_zero_among_the_files_is_skipped_with_an_info_finding(project: Kiripix) -> None:
    a_frame_loop(project)
    write_kit(project, 3)
    one = painted(project, 1)

    result = project.json("import", ROOM, project.cwd / KIT / "frame_000.png", one, "--loop", LOOP)

    assert len(result["data"]["loop_frames"]) == 1 and len(result["data"]["skipped"]) == 1
    (finding,) = result["findings"]
    assert finding["code"] == "import.frame_zero_skipped" and finding["severity"] == "info"


def test_a_frame_of_the_wrong_size_is_refused_and_nothing_is_stored(project: Kiripix) -> None:
    folder = a_frame_loop(project)
    write_kit(project, 3)
    good = painted(project, 1)
    bad = painted(project, 2, size=(29, 30), name="frame_002.png")

    refused = project.json("import", ROOM, good, bad, "--loop", LOOP, expect=1)

    assert refused["findings"][0]["code"] == "import.size_mismatch" and "30x30" in refused["findings"][0]["message"]
    assert not (folder / "src" / "loops").exists() and not kit_decisions(folder)


def test_import_loop_needs_a_declared_frame_loop_and_frames_to_import(project: Kiripix) -> None:
    a_frame_loop(project)
    write_kit(project, 3)

    other = project.json("import", ROOM, painted(project, 1), "--loop", "nope", expect=1)
    assert other["findings"][0]["code"] == "import.loop_unknown" and other["findings"][0]["fix"]

    only_zero = project.json("import", ROOM, project.cwd / KIT / "frame_000.png", "--loop", LOOP, expect=1)
    assert only_zero["findings"][0]["code"] == "import.loop_no_frames"

    more = project.json("import", ROOM, painted(project, 1), painted(project, 2), expect=1)
    assert more["findings"][0]["code"] == "import.frames_need_loop"

    both = project.json("import", ROOM, painted(project, 1), "--loop", LOOP, "--look", "door", expect=1)
    assert both["findings"][0]["code"] == "import.loop_takes_images"


def test_a_region_that_moved_since_the_kit_was_written_is_refused(project: Kiripix) -> None:
    a_frame_loop(project)
    write_kit(project, 3)
    one = painted(project, 1)
    decide(project, "polygon", {"loop": LOOP, "points": [[0, 0], [31, 0], [31, 1]]})  # the box grows by a row and a column

    refused = project.json("import", ROOM, one, "--loop", LOOP, expect=1)

    assert refused["findings"][0]["code"] in ("import.loop_region_changed", "import.size_mismatch")


# staleness, and `next`


def test_a_frame_loop_with_no_frames_has_next_suggest_a_kit(project: Kiripix) -> None:
    a_frame_loop(project)
    project.json("run", ROOM, "looks")

    data = project.json("next", ROOM)["data"]

    assert data["stage"] == "loops" and data["command"] == f"kiripix loop kit {ROOM} {LOOP} kits/{LOOP} --frames 4"
    assert project.json("run", ROOM, "loops", expect=3)["ok"] is False


def test_a_refit_puts_the_kit_frames_in_needs_input_and_a_palette_change_keeps_them(project: Kiripix) -> None:
    a_frame_loop(project, lamp_layer=False)
    write_kit(project, 3)
    project.json("import", ROOM, painted(project, 1), painted(project, 2), "--loop", LOOP)
    decide(project, "frames", {"loop": LOOP, "source": "kit"})
    project.json("run", ROOM, "looks")
    project.json("run", ROOM, "loops")
    assert stage_status(project, ROOM)["loops"] == "done"

    path = project.cwd / "style" / "palette.gpl"
    path.write_bytes(path.read_bytes() + b" 12  34  56\tother\n")
    project.json("run", ROOM, "palette")
    project.json("run", ROOM, "looks")
    project.json("run", ROOM, "loops", expect=3)
    assert stage_status(project, ROOM)["loops"] == "needs-review", "a palette change keeps the kit, remapped (0194)"

    refit(project)
    project.json("run", ROOM, "loops", expect=3)
    assert stage_status(project, ROOM)["loops"] == "needs-input"
    assert "painted on another fit" in reason(project)


def test_frames_painted_before_a_refit_are_stale_when_imported_after_it(project: Kiripix) -> None:
    a_frame_loop(project, lamp_layer=False)
    write_kit(project, 3)
    one = painted(project, 1)
    decide(project, "frames", {"loop": LOOP, "source": "kit"})
    refit(project)

    project.json("import", ROOM, one, "--loop", LOOP)

    project.json("run", ROOM, "loops", expect=3)
    assert "painted on another fit" in reason(project), "the kit remembers the fit it was written on"


def test_a_kit_is_ignored_while_the_loop_takes_its_frames_from_an_op(project: Kiripix) -> None:
    a_frame_loop(project, lamp_layer=False)
    write_kit(project, 3)
    project.json("import", ROOM, painted(project, 1), "--loop", LOOP)
    decide(project, "frames", {"loop": LOOP, "source": "op", "op": "shimmer"})
    refit(project)

    project.json("run", ROOM, "loops")

    assert stage_status(project, ROOM)["loops"] == "done"


def test_the_kit_decision_is_described(project: Kiripix) -> None:
    result = project.json("describe", "room", "--stage", "loops")
    text = json.dumps(result["data"])

    assert '"kit"' in text and "painted on" in text
