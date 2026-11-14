"""A frame Loop built from its kit (ticket 0194, Part A): imported frames are taken as painted, an off-palette pixel takes
the nearest palette colour (`loop.off_palette`), strokes outside the region are cut away (`loop.outside_region`), on a Layer
a transparent pixel leaves the Plate's fill showing, and a palette change remaps the frames into needs-review."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_layers_stage import ROOM, rgba
from test_loop_kit import KIT, TRIANGLE, a_frame_loop, painted, write_kit
from test_loops import LOOP, WHOLE, build, codes, declare, decide, findings, out, record, tiles
from test_looks_build import room_with_a_lamp_layer


def save_frame(project: Kiripix, number: int, frame: Any) -> Path:
    path = project.cwd / KIT / f"frame_{number:03d}.png"
    Image.fromarray(frame, "RGBA").save(path)
    return path


def add_a_palette_colour(project: Kiripix) -> None:
    path = project.cwd / "style" / "palette.gpl"
    path.write_bytes(path.read_bytes() + b" 12  34  56\tother\n")


def base(project: Kiripix) -> Any:
    return rgba(project.cwd / KIT / "frame_000.png")


def strips(project: Kiripix, folder: Path, key: str = "plate") -> tuple[dict[str, Any], list[Any]]:
    loop = record(folder)
    file = loop["plate"] if key == "plate" else loop["layers"][0]["file"]
    return loop, tiles(out(folder) / file, loop["box"], loop["frames"], loop["columns"])


def test_kit_frames_build_with_an_off_palette_pixel_and_a_stray_stroke(project: Kiripix) -> None:
    folder = a_frame_loop(project, lamp_layer=False)
    write_kit(project, 3)
    first, second = base(project), base(project)
    first[10, 10] = (1, 2, 3, 255)  # a near-miss from the editor
    wall = first[5, 0].copy()
    second[5, 5] = base(project)[8, 8]  # a plain change inside the region
    for y, x in ((29, 29), (29, 28), (28, 29)):  # outside the triangle
        first[y, x] = wall
    save_frame(project, 1, first)
    save_frame(project, 2, second)
    project.json("import", ROOM, project.cwd / KIT / "frame_001.png", project.cwd / KIT / "frame_002.png", "--loop", LOOP)

    result = build(project)

    assert result["ok"]
    assert stage_status(project, ROOM)["loops"] == "done"
    loop, pieces = strips(project, folder)
    assert loop["source"] == "kit" and loop["op"] is None and loop["frames"] == 3 and loop["mode"] is None
    room = rgba(folder / "work" / "palette" / "palette.png")[1:31, 1:31]
    inside = base(project)[..., 3] > 0
    assert (pieces[0][inside] == room[inside]).all(), "frame 0 is the room"
    gpl = (project.cwd / "style" / "palette.gpl").read_text("utf-8")
    assert " 0   0   0" in gpl or "0 0 0" in gpl.replace("  ", " ")
    assert tuple(int(v) for v in pieces[1][10, 10][:3]) == (0, 0, 0), "(1, 2, 3) takes the nearest palette colour, black"
    assert pieces[1][10, 10, 3] == 255
    assert pieces[1][29, 29, 3] == 0, "the stroke outside the region is cut away"
    assert (pieces[2][5, 5] == base(project)[8, 8]).all()
    found = {f["code"]: f for f in findings(project)}
    assert found["loop.off_palette"]["severity"] == "warning"
    assert "1 pixels" in found["loop.off_palette"]["message"]
    outside = [f for f in findings(project) if f["code"] == "loop.outside_region"]
    assert len(outside) == 1 and outside[0]["severity"] == "warning"
    position = outside[0]["position"]
    assert [position["x"], position["y"], position["width"], position["height"]] == [29, 29, 2, 2]
    assert [e for e in findings(project) if e["severity"] == "error"] == []
    assert "loop.still" not in codes(project)


def test_more_than_one_percent_off_palette_is_an_error(project: Kiripix) -> None:
    a_frame_loop(project, lamp_layer=False)
    write_kit(project, 2)
    frame = base(project)
    frame[4:9, 4:9] = (1, 2, 3, 255)  # 25 pixels of about 450
    save_frame(project, 1, frame)
    project.json("import", ROOM, project.cwd / KIT / "frame_001.png", "--loop", LOOP)
    decide(project, "frames", {"loop": LOOP, "source": "kit"})

    build(project, expect=2)

    errors = [f for f in findings(project) if f["code"] == "loop.off_palette"]
    assert len(errors) == 1 and errors[0]["severity"] == "error"
    assert project("check", ROOM, "--json").code == 2


def test_a_kit_frame_on_a_layer_leaves_the_plates_fill_where_it_is_transparent(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    declare(project, form="frames", layer="lamp")
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    write_kit(project, 2)
    frame = base(project)
    solid = np.argwhere(frame[..., 3] > 0)
    y, x = (int(v) for v in solid[0])
    frame[y, x] = (0, 0, 0, 0)  # the Layer's pixel is gone in this frame
    other = tuple(int(v) for v in solid[-1])
    frame[(other[0], other[1])] = frame[(int(solid[1][0]), int(solid[1][1]))]
    save_frame(project, 1, frame)
    project.json("import", ROOM, project.cwd / KIT / "frame_001.png", "--loop", LOOP)

    build(project)

    loop, pieces = strips(project, folder, "layer")
    assert loop["plate"] is None and loop["source"] == "kit"
    assert pieces[0][y, x, 3] == 255 and pieces[1][y, x, 3] == 0, "the Plate's fill shows"
    assert set(np.unique(pieces[1][..., 3])) <= {0, 255}
    assert (pieces[1][..., 3] > 0).sum() == (pieces[0][..., 3] > 0).sum() - 1
    assert [e for e in findings(project) if e["severity"] == "error"] == []


def test_a_palette_change_remaps_the_kit_frames_into_needs_review(project: Kiripix) -> None:
    folder = a_frame_loop(project, lamp_layer=False)
    write_kit(project, 3)
    project.json("import", ROOM, painted(project, 1), painted(project, 2), "--loop", LOOP)
    project.json("run", ROOM, "looks")
    project.json("run", ROOM, "loops")
    assert stage_status(project, ROOM)["loops"] == "done"
    before = [p.copy() for p in strips(project, folder)[1]]

    add_a_palette_colour(project)
    project.json("run", ROOM, "palette")
    project.json("run", ROOM, "looks")
    reviewed = project.json("run", ROOM, "loops", expect=3)

    assert stage_status(project, ROOM)["loops"] == "needs-review"
    assert any(f["code"] == "stage.needs_review" for f in reviewed["findings"])
    assert len(strips(project, folder)[1]) == len(before) == 3, "the frames were built"

    project.json("accept", ROOM, "loops", owner=True)
    project.json("run", ROOM, "loops")
    assert stage_status(project, ROOM)["loops"] == "done"


def test_a_kit_frame_of_another_size_than_the_region_fails_the_build(project: Kiripix) -> None:
    a_frame_loop(project)
    write_kit(project, 2)
    project.json("import", ROOM, painted(project, 1), "--loop", LOOP)
    decide(project, "polygon", {"loop": LOOP, "points": [[0, 0], [31, 0], [31, 1]]})  # the box changes after import

    result = build(project, expect=1)

    assert not result["ok"] and "write a new kit" in json.dumps(result)


def test_a_kit_loop_with_no_import_asks_for_a_kit_and_timing_counts_the_frames(project: Kiripix) -> None:
    a_frame_loop(project)
    decide(project, "frames", {"loop": LOOP, "source": "kit"})
    project.json("run", ROOM, "looks")
    assert project.json("run", ROOM, "loops", expect=3)["ok"] is False
    write_kit(project, 3)
    project.json("import", ROOM, painted(project, 1), painted(project, 2), "--loop", LOOP)
    decide(project, "timing", {"loop": LOOP, "ticks": [5, 5]})

    refused = project.json("run", ROOM, "loops", expect=3)

    assert not refused["ok"], "two numbers for three frames"
    decide(project, "timing", {"loop": LOOP, "ticks": [5, 5, 5]})
    project.json("run", ROOM, "loops")
    assert stage_status(project, ROOM)["loops"] == "done"


def test_an_accepted_remap_keeps_remapping_the_frames_as_painted(project: Kiripix) -> None:
    """A palette change that moves a colour the kit was painted in: once the Owner accepts the remap, the next builds
    still remap those pixels; they are not reported off the palette."""
    folder = a_frame_loop(project, lamp_layer=False)
    write_kit(project, 3)
    project.json("import", ROOM, painted(project, 1), painted(project, 2), "--loop", LOOP)
    project.json("run", ROOM, "looks")
    project.json("run", ROOM, "loops")
    r, g, b = (int(v) for v in base(project)[4, 4][:3])  # a colour inside the region, painted in every kit frame
    path = project.cwd / "style" / "palette.gpl"
    lines = path.read_text("utf-8").splitlines()
    [at] = [i for i, line in enumerate(lines) if line.split()[:3] == [str(r), str(g), str(b)]]
    lines[at] = f"{min(255, r + 9)} {g} {b}\tmoved"
    path.write_text("\n".join(lines) + "\n", "utf-8")
    project.json("run", ROOM, "palette")
    project.json("run", ROOM, "looks")
    project.json("run", ROOM, "loops", expect=3)
    remapped = [p.copy() for p in strips(project, folder)[1]]

    project.json("accept", ROOM, "loops", owner=True)
    project.json("run", ROOM, "loops")

    assert stage_status(project, ROOM)["loops"] == "done"
    assert "loop.off_palette" not in codes(project)
    assert all((a == b).all() for a, b in zip(strips(project, folder)[1], remapped, strict=True))
    assert record(folder)["kit"]["remapped"] is True


def test_a_kit_the_loop_no_longer_uses_is_not_reviewed_after_a_palette_change(project: Kiripix) -> None:
    a_frame_loop(project, lamp_layer=False)
    write_kit(project, 3)
    project.json("import", ROOM, painted(project, 1), painted(project, 2), "--loop", LOOP)
    decide(project, "frames", {"loop": LOOP, "op": "shimmer", "params": {}})
    project.json("run", ROOM, "looks")
    project.json("run", ROOM, "loops")

    add_a_palette_colour(project)
    project.json("run", ROOM, "palette")
    project.json("run", ROOM, "looks")
    project.json("run", ROOM, "loops")

    assert stage_status(project, ROOM)["loops"] == "done"
