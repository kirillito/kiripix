"""A frame Loop's strips hold only the pixels that differ from frame 0 (ticket 0403): clear wherever a frame equals the
room, RGBA-exactly, on the Plate's piece and on the piece cut for a foreground Layer the region crosses; the Loop's own
numbers and findings are those of the whole frames."""

import re

import numpy as np
from conftest import Kiripix, stage_status
from test_layers_stage import ROOM, rgba
from test_loop_frame_ops import frames_of
from test_loops import LOOP, WHOLE, build, codes, declare, decide, findings, record
from test_looks_build import room_with_a_lamp_layer


def test_a_shimmer_across_a_layer_cuts_every_piece_clear_where_a_frame_equals_the_room(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    declare(project, form="frames")
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "frames", {"loop": LOOP, "op": "shimmer"})
    build(project)

    loop = record(folder)
    x, y, width, height = loop["box"]
    room = rgba(folder / "work" / "palette" / "palette.png")[y:y + height, x:x + width]
    lamp = rgba(folder / "work" / "layers" / "layer.lamp.png")[y:y + height, x:x + width, 3] > 0
    assert loop["plate"] and [e["id"] for e in loop["layers"]] == ["lamp"]
    moving = np.zeros(room.shape[:2], dtype=bool)
    for key, cut in (("plate", ~lamp), ("layer", lamp)):
        _, pieces = frames_of(project, folder, key)
        assert (pieces[0] == 0).all(), "frame 0 is the room: clear"
        for piece in pieces[1:]:
            kept = piece[..., 3] > 0
            assert not (kept & ~cut).any(), "cut by the piece's own alpha"
            assert (piece[kept] != room[kept]).any(axis=1).all(), "a kept pixel differs from the room"
            assert (piece[~kept] == 0).all()
            moving |= kept
    assert moving.any() and int(moving.sum()) == loop["moving"], "the strips keep exactly the pixels that move"
    assert stage_status(project, ROOM)["loops"] == "done"
    assert [f for f in findings(project) if f["severity"] == "error"] == []
    assert "loop.frame0" not in codes(project) and "loop.still" not in codes(project)


HEAD_FINDINGS = [("loop.texture", "info")]  # what this room gave before ticket 0403, read from a build of the code before it
HEAD_TEXTURE_BYTES = 723  # and the size of its strips then, which the message names


def test_a_rebuild_gives_the_same_loop_findings_as_before_with_smaller_strips(project: Kiripix) -> None:
    folder = room_with_a_lamp_layer(project)
    declare(project, form="frames")
    decide(project, "polygon", {"loop": LOOP, "points": WHOLE})
    decide(project, "frames", {"loop": LOOP, "op": "shimmer"})
    build(project)
    before = sorted((f["code"], f["severity"], f["message"]) for f in findings(project))
    assert [(code, severity) for code, severity, _ in before] == HEAD_FINDINGS, "the checks read whole frames, as before"
    [texture] = [message for code, _, message in before if code == "loop.texture"]
    match = re.search(r"in (\d+) bytes", texture)
    assert match is not None and int(match.group(1)) < HEAD_TEXTURE_BYTES, "a strip that holds only the changes is smaller"
    first = record(folder)

    project.json("run", ROOM, "loops", "--force")

    assert sorted((f["code"], f["severity"], f["message"]) for f in findings(project)) == before
    assert record(folder) == first
