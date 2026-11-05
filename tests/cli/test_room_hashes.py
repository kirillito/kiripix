"""Moving what rooms and props share out of `room.py` (ticket 0050) changed no room's input hashes: these are the hashes
the room Stages had before the move, on a fixed room. A change to a Stage's inputs, parameters or defaults changes them
on purpose, and then the Owner's rooms go stale: update them only for that."""

import json

from conftest import Kiripix
from test_fit import ROOM, art, room_from, upscaled

# brief, source, fit and palette as built before the move, from `art(48, 32)` imported at 2x, `fit scale=2`.
HASHES = {
    "brief": (
        "dac8482ae1544a39d75ea3b9856247459f8c4743fd14f9c9c196917c385e53cc"
    ),
    "source": (
        "191a517da8a0a2780c72ce966c6e04c650dd9f10e0f1280789ec0f2d0d381056"
    ),
    "fit": (
        "3f6bbcade137c4ca931606bad20184b1c720cf32f04199c848182daab9014515"
    ),
    # Changed on purpose through its upstream `layers`: its inputs and `grow` (0043), then `difference` (0044).
    "palette": (
        "3c9cd0a9bb8ebda3ddfb4c67af342b8bc38d3d9e81412dd56f1d0485ee9d3279"
    ),
}


def test_a_rooms_input_hashes_are_those_before_the_shared_code_moved(project: Kiripix) -> None:
    folder = room_from(project, upscaled(art(48, 32), 2), 48, 32)
    project.json("set", ROOM, "fit", "scale=2")
    project.json("run", ROOM, expect=3)

    built = {stage: json.loads((folder / "work" / stage / ".stage.json").read_text(encoding="utf-8"))["input_hash"]
             for stage in HASHES}

    assert built == HASHES
