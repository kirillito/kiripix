"""Frame Loops built by an Op (ticket 0192): `sway` on a Layer carries its own alpha, on the Plate it is `loop.no_fill`;
`shimmer` and `scroll` stay inside their region; the seam Check is quiet on the periodic Ops."""

import json
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from test_layers_stage import ROOM, rgba
from test_loops import (
    LOOP,
    WHOLE,
    build,
    codes,
    declare,
    decide,
    findings,
    out,
    record,
    run_loops,
    tiles,
)
from test_looks_build import room_with_a_lamp_layer


def frames_of(project: Kiripix, folder: Any, file_key: str = "plate") -> tuple[dict[str, Any], list[np.ndarray]]:
    loop = record(folder)
    file = loop["plate"] if file_key == "plate" else loop["layers"][0]["file"]
    return loop, tiles(out(folder) / file, loop["box"], loop["frames"], loop["columns"])


def test_a_sway_on_a_layer_builds_frames_that_carry_their_own_alpha(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    declare(project, form="frames", layer="lamp")
    decide(project, "frames", {"loop": LOOP, "op": "sway", "params": {"amplitude": 2}})
    build(project)

    loop, pieces = frames_of(project, folder, "layer")
    assert loop["form"] == "frames" and loop["op"] == "sway" and loop["source"] == "op"
    assert loop["frames"] == 4 and len(loop["sequence"]) == 4 and loop["plate"] is None
    alpha = rgba(folder / "work" / "layers" / "layer.lamp.png")
    x, y, width, height = loop["box"]
    assert (pieces[0] == np.where((alpha[y:y + height, x:x + width, 3] > 0)[..., None],
                                  rgba(folder / "work" / "palette" / "palette.png")[y:y + height, x:x + width], 0)).all()
    assert any(((p[..., 3] > 0) != (pieces[0][..., 3] > 0)).any() for p in pieces[1:]), "the shape moves"
    assert loop["moving"] > 0 and set(np.unique(np.concatenate([p[..., 3].ravel() for p in pieces]))) <= {0, 255}
    assert stage_status(project, ROOM)["loops"] == "done"
    assert [f for f in findings(project) if f["severity"] == "error"] == []
    assert "loop.seam" not in codes(project)


def test_a_sway_on_the_plate_is_no_fill(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    declare(project, form="frames")
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "frames", {"loop": LOOP, "op": "sway"})
    build(project, expect=2)  # the Stage's own Checks fail it

    [finding] = findings(project, "loop.no_fill")
    assert finding["severity"] == "error" and finding["fix"] is None and "layers" in finding["owner_action"]
    assert "loop.no_region" not in codes(project)


def test_a_shimmer_keeps_to_its_region_and_the_wrap_is_quiet(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    declare(project, form="frames")
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "frames", {"loop": LOOP, "op": "shimmer"})
    decide(project, "timing", {"loop": LOOP, "ticks": [4, 4, 4, 4, 4, 8]})
    build(project)

    loop = record(folder)
    assert loop["frames"] == 6 and loop["ticks"] == 28
    palette = rgba(folder / "work" / "palette" / "palette.png")
    x, y, width, height = loop["box"]
    room = palette[y:y + height, x:x + width]
    seen: list[np.ndarray] = []
    for file in [loop["plate"]] + [e["file"] for e in loop["layers"]]:
        pieces = tiles(out(folder) / file, loop["box"], 6, loop["columns"])
        shown = pieces[0][..., 3] > 0
        for piece in pieces:
            assert ((piece[..., 3] > 0) == shown).all()
        seen.append(shown)
        assert (pieces[0][shown] == room[shown]).all()
    assert [f for f in findings(project) if f["severity"] == "error"] == []
    assert "loop.seam" not in codes(project)


def test_a_scroll_has_the_period_of_its_wrap_as_frames(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    declare(project, form="frames")
    decide(project, "polygon", {"loop": LOOP, "points": [[2, 2], [9, 2], [9, 5], [2, 5]]})
    decide(project, "frames", {"loop": LOOP, "op": "scroll", "params": {"dx": 1}})
    build(project)

    loop = record(folder)
    assert loop["frames"] == loop["box"][2] and loop["op"] == "scroll"
    assert loop["params"] == {"dx": 1}


def test_a_timing_of_the_wrong_length_or_a_bad_op_parameter_is_refused(project: Kiripix) -> None:
    room_with_a_lamp_layer(project)
    declare(project, form="frames", layer="lamp")
    decide(project, "frames", {"loop": LOOP, "op": "sway"})
    decide(project, "timing", {"loop": LOOP, "ticks": [4, 4, 4]})
    run_loops(project)
    assert "timing" in json.dumps(project.json("run", ROOM, "loops", expect=3))
    refused = decide(project, "frames", {"loop": LOOP, "op": "sway", "params": {"dx": 1}}, expect=1)
    assert "sway takes" in json.dumps(refused)
    refused = decide(project, "frames", {"loop": LOOP, "op": "scroll", "params": {}}, expect=1)
    assert "dx or a dy" in json.dumps(refused)


def test_the_frames_decision_is_described(project: Kiripix) -> None:
    described = json.dumps(project.json("describe", "room", "--stage", "loops"))
    assert "sway" in described and "nearest" in described
