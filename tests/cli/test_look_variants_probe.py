"""`show` lists a Look's edit Variants, and the Probe `look-difference` previews a `difference` (ticket 0205, ADR 0009)."""

import json
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_layers_stage import ROOM, SCALE
from test_looks_build import (
    LOOK,
    decide,
    edited,
    import_and_pick,
    look_record,
    room_with_a_lamp_layer,
    run_looks,
)

BOX = "0,0,20,20"


def runs_mask(answer: dict[str, Any], height: int, width: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=bool)
    for y, x, length in answer["runs"]:
        mask[y, x:x + length] = True
    return mask


def probe(project: Kiripix, *args: str, expect: int = 0) -> dict[str, Any]:
    return project.json("probe", "look-difference", ROOM, *args, expect=expect)


def test_show_lists_each_looks_edit_variants_and_the_pick(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    first = import_and_pick(project, edited())
    Image.fromarray(np.repeat(np.repeat(edited(), SCALE, axis=0), SCALE, axis=1) // 2, "RGBA").save(
        project.cwd / "other.png")
    second = str(project.json("import", ROOM, "other.png", "--look", LOOK)["data"]["variant"])
    assert first != second

    looks = project.json("show", ROOM)["data"]["looks"]

    assert [entry["look"] for entry in looks] == [LOOK]
    assert sorted(v["name"] for v in looks[0]["variants"]) == sorted([first, second])
    assert looks[0]["picked"] == first
    assert all(v["file"].endswith(f"src/looks/{LOOK}/{v['name']}.png") for v in looks[0]["variants"])


def test_a_room_with_no_looks_shows_an_empty_list(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    assert project.json("show", ROOM)["data"]["looks"] == []


def test_a_look_with_edits_and_no_pick_shows_null(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    Image.fromarray(np.repeat(np.repeat(edited(), SCALE, axis=0), SCALE, axis=1), "RGBA").save(project.cwd / "e.png")
    project.json("import", ROOM, "e.png", "--look", LOOK)
    looks = project.json("show", ROOM)["data"]["looks"]
    assert looks[0]["picked"] is None and len(looks[0]["variants"]) == 1


def test_the_probe_answers_the_region_the_looks_stage_builds(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    decide(project, "difference", {"look": LOOK, "x0": 0, "y0": 0, "x1": 20, "y1": 20, "specks": 4})
    run_looks(project)
    record = look_record(folder)
    built = np.zeros((20, 20), dtype=bool)
    x, y, width, height = record["box"]
    for entry in [*record["layers"], *([{"file": record["plate"]}] if record["plate"] else [])]:
        piece = np.asarray(Image.open(folder / "work" / "looks" / entry["file"]).convert("RGBA"))[..., 3] > 0
        built[y:y + height, x:x + width] |= piece

    answer = probe(project, LOOK, BOX, "4", "4")["data"]["result"]

    assert answer["pixels"] == int(built.sum()) > 0
    assert (runs_mask(answer, answer["height"], answer["width"])[:20, :20] == built).all()
    assert answer["box"] == {"x": x, "y": y, "width": width, "height": height}


def test_the_probe_uses_the_defaults_and_summary_leaves_out_the_runs(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    full = probe(project, LOOK, BOX, "--summary")["data"]["result"]
    assert "runs" not in full and full["pixels"] >= 0 and set(full) == {"width", "height", "pixels", "box"}
    assert json.dumps(full)  # plain data


def test_the_probe_on_a_look_with_no_pick_is_refused_with_a_fix(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    result = probe(project, LOOK, BOX, expect=1)
    finding = result["findings"][0]
    assert finding["code"].startswith("probe.") and "pick" in finding["fix"]


def test_the_probe_before_fit_is_built_is_refused_with_a_fix(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", "width=48", "height=32")
    project.json("set", ROOM, "fit", f"scale={SCALE}")
    Image.fromarray(np.repeat(np.repeat(edited(), SCALE, axis=0), SCALE, axis=1), "RGBA").save(project.cwd / "s.png")
    project.json("pick", ROOM, str(project.json("import", ROOM, "s.png")["data"]["variant"]))
    import_and_pick(project, edited())  # an edit is picked, but nothing is built

    result = probe(project, LOOK, BOX, expect=1)

    assert "run" in result["findings"][0]["fix"]


def test_another_look_waiting_for_its_edit_does_not_stop_the_probe(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    import_and_pick(project, edited())
    run_looks(project)
    decide(project, "polygon", {"look": "other", "points": [[0, 0], [5, 0], [5, 5]]})  # a second Look, no edit yet

    answer = probe(project, LOOK, BOX)["data"]["result"]

    assert answer["pixels"] > 0
