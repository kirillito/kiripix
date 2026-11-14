"""The room's `loops` Stage (ticket 0189): colour cycles cut to a region. Frame 0 is the room, pixel for pixel; the strips,
the index, `loops.json`, the Checks and the staleness rules, on the `layers` test room (a lamp lifted into a Layer)."""

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from test_layers_stage import ROOM, built_room, rgba
from test_looks_build import LAMP_BOX, room_with_a_lamp_layer

LOOP = "lamp_glow"
WHOLE = [[1, 1], [30, 1], [30, 30], [1, 30]]  # the lamp, its Layer, and the floor round them


def hexed(pixel: Any) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(int(v) for v in pixel[:3]))


def decide(project: Kiripix, decision: str, data: dict[str, Any], expect: int = 0) -> dict[str, Any]:
    return project.json("decide", ROOM, "loops", "--decision", json.dumps({"decision": decision, "data": data}),
                        expect=expect)


def out(folder: Path) -> Path:
    return folder / "work" / "loops"


def record(folder: Path, loop: str = LOOP) -> dict[str, Any]:
    built = json.loads((out(folder) / "loops.json").read_text("utf-8"))
    return next(entry for entry in built["loops"] if entry["id"] == loop)


def findings(project: Kiripix, prefix: str = "loop.") -> list[dict[str, Any]]:
    return [f for f in project("check", ROOM, "--json").json["findings"] if f["code"].startswith(prefix)]


def codes(project: Kiripix) -> list[str]:
    return [f["code"] for f in findings(project)]


def run_loops(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    project.json("run", ROOM, "masks")
    project.json("run", ROOM, "palette")
    return project.json("run", ROOM, "looks")  # `loops` is built on it


def build(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    run_loops(project)
    return project.json("run", ROOM, "loops", expect=expect)


def colours(folder: Path) -> dict[str, str]:
    """The room's mapped colours: the floor, the lamp, the wall and the crate."""
    palette = rgba(folder / "work" / "palette" / "palette.png")
    return {"floor": hexed(palette[20, 20]), "lamp": hexed(palette[8, 8]), "wall": hexed(palette[20, 1]),
            "crate": hexed(palette[24, 40])}


def declare(project: Kiripix, **fields: Any) -> None:
    decide(project, "loop", {"loop": LOOP, **fields})


def tiles(path: Path, box: list[int], frames: int, columns: int) -> list[np.ndarray]:
    strip = rgba(path)
    width, height = box[2], box[3]
    return [strip[(n // columns) * height:(n // columns + 1) * height, (n % columns) * width:(n % columns + 1) * width]
            for n in range(frames)]


def a_rotating_loop(project: Kiripix, timing: dict[str, Any] | None = None, region: list[list[int]] = WHOLE) -> Path:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project)
    decide(project, "polygon", {"loop": LOOP, "points": region})
    decide(project, "cycle", {"loop": LOOP, "colours": [c["floor"], c["lamp"], c["wall"]]})
    if timing is not None:
        decide(project, "timing", {"loop": LOOP, **timing})
    return folder


def test_a_rotating_loop_gives_strips_that_start_on_the_room_and_step_the_colours(project: Kiripix) -> None:
    folder = a_rotating_loop(project, {"ticks": 6})
    build(project)

    loop = record(folder)
    c = colours(folder)
    assert loop["form"] == "cycle" and loop["mode"] == "rotate" and loop["frames"] == 3
    assert loop["sequence"] == [[0, 6], [1, 6], [2, 6]] and loop["ticks"] == 18
    assert loop["colours"] == [c["floor"], c["lamp"], c["wall"]] and loop["layer"] == "plate" and loop["phase"] == 0
    assert loop["box"] == [1, 1, 30, 30]
    composite = rgba(folder / "work" / "palette" / "palette.png")
    box = loop["box"]
    room = composite[1:31, 1:31]
    strips = [(loop["plate"], None)] + [(entry["file"], entry["id"]) for entry in loop["layers"]]
    assert loop["plate"] == f"{LOOP}/plate.png" and [e["id"] for e in loop["layers"]] == ["lamp"]
    first = np.zeros_like(room)
    for file, _ in strips:
        piece = tiles(out(folder) / file, box, 3, loop["columns"])
        shown = piece[0][..., 3] > 0
        first[shown] = piece[0][shown]
        assert ((piece[1][..., 3] > 0) == shown).all(), "every frame has the piece's own shape"
    assert (first == room).all(), "frame 0 of the pieces together is the room inside the region"
    moved = tiles(out(folder) / loop["plate"], box, 3, loop["columns"])
    floor = np.array([int(c["floor"][i:i + 2], 16) for i in (1, 3, 5)])
    floors = (room[..., :3] == floor).all(axis=2) & (moved[0][..., 3] > 0)
    assert floors.any() and (moved[1][floors][:, :3] == [int(c["lamp"][i:i + 2], 16) for i in (1, 3, 5)]).all()
    index = rgba(out(folder) / loop["index"])  # an 8-bit image, read as RGBA
    assert set(np.unique(index[..., 0])) <= {0, 1, 2, 3}
    assert stage_status(project, ROOM)["loops"] == "done"
    assert [f for f in findings(project) if f["severity"] == "error"] == []


def test_a_loop_on_a_layer_is_cut_to_the_layers_alpha_and_gives_that_piece_only(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project, layer="lamp")
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "cycle", {"loop": LOOP, "colours": [c["lamp"], c["crate"]]})
    build(project)

    loop = record(folder)
    alpha = rgba(folder / "work" / "layers" / "layer.lamp.png")[..., 3] > 0
    assert loop["plate"] is None and [e["id"] for e in loop["layers"]] == ["lamp"]
    x, y, width, height = loop["box"]
    piece = tiles(out(folder) / loop["layers"][0]["file"], loop["box"], loop["frames"], loop["columns"])
    assert ((piece[0][..., 3] > 0) == alpha[y:y + height, x:x + width]).all()


def test_a_flood_finds_the_lamp_and_a_region_can_be_undone(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project)
    decide(project, "flood", {"loop": LOOP, "x": 8, "y": 8})
    decide(project, "cycle", {"loop": LOOP, "colours": [c["lamp"], c["crate"]]})
    build(project)
    assert record(folder)["box"] == [6, 5, 5, 7] and record(folder)["pixels"] == 35

    decide(project, "polygon", {"loop": LOOP, "points": [[40, 20], [44, 20], [44, 28], [40, 28]]})
    build(project)
    assert record(folder)["box"][0] == 6 and record(folder)["pixels"] > 35

    project.json("undo", ROOM, "loops")
    build(project)
    assert record(folder)["pixels"] == 35
    assert stage_status(project, ROOM)["loops"] == "done"


def test_a_pulse_loop_keeps_to_the_palette_and_reports_a_region_far_from_its_colours(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project)
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "cycle", {"loop": LOOP, "mode": "pulse", "colours": [c["wall"], c["crate"]], "depth": 2, "steps": 4})
    build(project)

    loop = record(folder)
    assert loop["mode"] == "pulse" and loop["frames"] == 4 and loop["emissive"] is True and loop["depth"] == 2
    assert loop["moving"] > 0 and loop["pulse_spill"] > 0
    [spill] = findings(project, "loop.pulse_spills")
    assert spill["severity"] == "info" and spill["owner_action"]
    assert "loop.off_palette" not in codes(project) and "loop.frame0" not in codes(project)


def test_a_flicker_timing_is_seeded_and_sums_to_its_length(project: Kiripix) -> None:
    folder = a_rotating_loop(project, {"flicker": {"seed": 7, "mean_ticks": 10, "length_ticks": 200}})
    build(project)
    first = record(folder)["sequence"]
    assert sum(ticks for _, ticks in first) == 200 and first[0][0] == 0

    project.json("run", ROOM, "loops", "--force")
    assert record(folder)["sequence"] == first, "the same seed gives the same sequence"
    decide(project, "timing", {"loop": LOOP, "flicker": {"seed": 8, "mean_ticks": 10, "length_ticks": 200}})
    build(project)
    assert record(folder)["sequence"] != first


def test_a_timing_with_flicker_and_ticks_is_refused(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    declare(project)
    result = project.json("decide", ROOM, "loops", "--decision", json.dumps(
        {"decision": "timing", "data": {"loop": LOOP, "ticks": 4, "flicker": {"seed": 1}}}), expect=1)
    assert "flicker" in json.dumps(result)


# the Checks


def test_a_cycle_that_wraps_with_a_jump_has_a_seam_warning_whose_fix_sets_pingpong(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project)
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "cycle", {"loop": LOOP, "colours": ["#000000", "#1d2b53", "#5f574f", "#83769c", "#c2c3c7", "#fff1e8"]})
    build(project)
    ratio = record(folder)["seam"]
    assert ratio is not None and ratio > 3, ratio
    [seam] = findings(project, "loop.seam")
    assert seam["severity"] == "warning" and '"pingpong": true' in seam["fix"]
    decide(project, "timing", {"loop": LOOP, "pingpong": True})
    build(project)
    assert "loop.seam" not in codes(project)


def test_pingpong_has_no_seam(project: Kiripix) -> None:
    folder = a_rotating_loop(project, {"ticks": 6, "pingpong": True})
    build(project)
    assert record(folder)["sequence"] == [[0, 6], [1, 6], [2, 6], [1, 6]]
    assert "loop.seam" not in codes(project)


def test_a_loop_that_changes_nothing_is_still(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project)
    decide(project, "polygon", {"loop": LOOP, "points": [[6, 5], [10, 5], [10, 11], [6, 11]]})
    decide(project, "cycle", {"loop": LOOP, "colours": [c["crate"], c["wall"]]})  # neither colour is in the region
    build(project)
    [still] = findings(project, "loop.still")
    assert still["severity"] == "warning" and record(folder)["moving"] == 0


def test_a_cycle_colour_off_the_palette_is_an_error(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project)
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "cycle", {"loop": LOOP, "colours": [c["floor"], "#123456"]})
    build(project, expect=2)
    listed = findings(project, "loop.off_palette")
    [off] = [f for f in listed if "#123456" in f["message"] and f["owner_action"]]
    assert off["severity"] == "error" and any("pixels off the palette" in f["message"] for f in listed)
    assert project("check", ROOM, "--json").code == 2


def test_a_fast_big_flash_is_an_error_and_its_fix_sets_a_slower_timing(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    toml = project.cwd / "kiripix.toml"
    toml.write_text(re.sub(r"resolution\s*=\s*\[.*?\]", "resolution = [40, 30]", toml.read_text("utf-8")), "utf-8")
    declare(project)
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "cycle", {"loop": LOOP, "colours": [c["floor"], "#000000"]})
    decide(project, "timing", {"loop": LOOP, "ticks": 5})
    build(project, expect=2)
    loop = record(folder)
    assert loop["flash"] > 3 and loop["flash_fix"]
    [flash] = findings(project, "loop.flash")
    assert flash["severity"] == "error" and '"ticks"' in flash["fix"]

    fixed = flash["fix"].split("--decision ", 1)[1].strip("'")
    project.json("decide", ROOM, "loops", "--decision", fixed)
    build(project)
    assert "loop.flash" not in codes(project)


def test_a_loop_over_a_look_is_a_warning(project: Kiripix) -> None:
    from test_looks_build import LOOK, decide as decide_look, import_and_pick, edited

    folder = a_rotating_loop(project)
    import_and_pick(project, edited())
    decide_look(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    build(project)
    assert record(folder)["overlaps"] and record(folder)["overlaps"][0]["look"] == LOOK
    [overlap] = findings(project, "loop.overlaps_look")
    assert overlap["severity"] == "warning"


def test_texture_is_reported_as_info(project: Kiripix) -> None:
    a_rotating_loop(project)
    build(project)
    [texture] = findings(project, "loop.texture")
    assert texture["severity"] == "info" and "3 frames" in texture["message"]


def test_a_frame_0_that_was_changed_after_the_build_is_an_error(project: Kiripix) -> None:
    folder = a_rotating_loop(project)
    build(project)
    plate = out(folder) / record(folder)["plate"]
    strip = rgba(plate)
    shown = np.argwhere(strip[..., 3] > 0)[0]
    strip[shown[0], shown[1], :3] = (1, 2, 3)
    from PIL import Image

    Image.fromarray(strip, "RGBA").save(plate)
    assert "loop.frame0" in codes(project)


def test_a_light_that_names_no_marker_is_an_error_when_export_is_built_and_a_placed_light_clears_it(
        project: Kiripix) -> None:
    from test_export import godot_project, set_target
    from test_masks import decide as decide_mask
    from test_place import line, place

    folder = a_rotating_loop(project)
    declare(project, light="lamp.glow")
    decide_mask(project, "flood", {"x": 0, "y": 0, "mask": "solid"})
    place(project, "spawn.main", "spawn")
    line(project, "lamp")
    godot_project(project)
    set_target(project)
    project.json("run", ROOM, expect=2)  # an error finding: the light
    assert record(folder)["light"] == "lamp.glow"
    [unknown] = findings(project, "loop.light_unknown")
    assert unknown["severity"] == "error" and unknown["owner_action"] and "lamp.glow" in unknown["message"]

    place(project, "lamp.glow", "light", (8, 8), colour="#FFCC88", radius=24, energy=1.5)
    project.json("run", ROOM)
    assert findings(project, "loop.light_unknown") == []


# what holds a Loop back


def test_a_decision_for_an_undeclared_loop_holds_the_stage(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    decide(project, "polygon", {"loop": "nope", "points": WHOLE})
    run_loops(project)
    result = project.json("run", ROOM, "loops", expect=3)
    assert "not declared" in json.dumps(result)


def test_a_frame_loop_with_no_frames_decision_is_held_and_a_kit_loop_asks_for_a_kit(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    declare(project, form="frames")
    run_loops(project)
    assert "frames" in json.dumps(project.json("run", ROOM, "loops", expect=3))
    decide(project, "frames", {"loop": LOOP, "source": "kit"})
    assert "loop kit" in json.dumps(project.json("run", ROOM, "loops", expect=3))


def test_a_loop_with_one_colour_rotating_or_a_timing_of_the_wrong_length_is_held(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project)
    decide(project, "cycle", {"loop": LOOP, "colours": [c["floor"]]})
    run_loops(project)
    assert "at least two" in json.dumps(project.json("run", ROOM, "loops", expect=3))
    decide(project, "cycle", {"loop": LOOP, "colours": [c["floor"], c["lamp"]]})
    decide(project, "timing", {"loop": LOOP, "ticks": [4, 4, 4]})
    assert "ticks lists 3" in json.dumps(project.json("run", ROOM, "loops", expect=3))


def test_a_loop_with_no_region_builds_nothing_and_warns(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    c = colours(folder)
    declare(project)
    decide(project, "cycle", {"loop": LOOP, "colours": [c["floor"], c["lamp"]]})
    build(project)
    assert record(folder)["box"] is None and "loop.no_region" in codes(project)


def test_a_loop_with_the_id_of_a_look_holds_the_stage(project: Kiripix) -> None:
    from test_looks_build import LOOK, decide as decide_look, import_and_pick, edited

    room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    decide_look(project, "polygon", {"look": LOOK, "points": LAMP_BOX})
    decide(project, "loop", {"loop": LOOK})
    run_loops(project)
    assert "ID of a Look" in json.dumps(project.json("run", ROOM, "loops", expect=3))


# staleness


def test_a_palette_change_rebuilds_a_flood_and_a_refit_puts_it_in_needs_review(project: Kiripix) -> None:
    folder = built_room(project)
    project.json("run", ROOM, "masks")
    project.json("run", ROOM, "palette")
    c = colours(folder)
    declare(project)
    decide(project, "flood", {"loop": LOOP, "x": 8, "y": 8})
    decide(project, "cycle", {"loop": LOOP, "colours": [c["lamp"], c["crate"]]})
    build(project)
    assert stage_status(project, ROOM)["loops"] == "done"

    project.json("set", ROOM, "palette", "dither=bayer2", "strength=1")
    assert stage_status(project, ROOM)["loops"] == "stale"
    build(project)
    assert stage_status(project, ROOM)["loops"] == "done"

    project.json("set", ROOM, "fit", "offset_x=2")
    for stage in ("fit", "layers", "masks", "palette"):
        project.json("run", ROOM, stage)
    project.json("run", ROOM, "looks")
    project.json("run", ROOM, "loops", expect=3)
    assert stage_status(project, ROOM)["loops"] == "needs-review"


def test_a_room_with_no_loops_has_a_loops_stage_that_is_done(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    build(project)
    assert stage_status(project, ROOM)["loops"] == "done"
    assert json.loads((out(folder) / "loops.json").read_text("utf-8")) == {"schema_version": 1, "loops": []}
    assert codes(project) == []


def test_describe_loops_says_what_a_loop_is(project: Kiripix) -> None:
    text = json.dumps(project.json("describe", "room", "--stage", "loops"))
    for word in ("always plays", "Look is shown by game state", "`loop` flag", "flood", "timing", "cycle"):
        assert word in text.replace("\\n", " ") or word in text, word
