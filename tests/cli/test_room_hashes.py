"""Moving what rooms and props share out of `room.py` (ticket 0050) changed no room's input hashes: these are the hashes
the room Stages had before the move, on a fixed room. A change to a Stage's inputs, parameters or defaults changes them
on purpose, and then the Owner's rooms go stale: update them only for that."""

import json

from conftest import Kiripix
from test_fit import ROOM, art, room_from, upscaled

# brief, source, fit and palette as built before the move, from `art(48, 32)` imported at 2x, `fit scale=2`.
# Re-pinned for ticket 0278's hash form (a parameter at its default left out, the Stage's `version` in): a stamp in
# the old form still reads as current through `legacy_input_hash`, so the Owner's rooms don't go stale.
HASHES = {
    "brief": (
        "c294ea790a4de3efd147f64a8b65a8b930e2ae25eb0b95117342fec069dc98e4"
    ),
    "source": (
        "823e484d44671d25562d656b67f0d6fbbf3ff39c5bafb8ffc55588f381f8a173"
    ),
    "fit": (
        "7859d88010ea4b9930ea2840c0b955279abdff1ee1cda9113eed83f3828362fd"
    ),
    # Changed on purpose through its upstream `layers`: its inputs and `grow` (0043), then `difference` (0044), then
    # `min_piece` (0087).
    "palette": (
        "83a6116736fe45e416bc3b718ef5bc596e52cb74539a520068bc015e4c712f46"
    ),
}


def test_a_rooms_input_hashes_are_those_before_the_shared_code_moved(project: Kiripix) -> None:
    folder = room_from(project, upscaled(art(48, 32), 2), 48, 32)
    project.json("set", ROOM, "fit", "scale=2")
    project.json("run", ROOM, expect=3)

    built = {stage: json.loads((folder / "work" / stage / ".stage.json").read_text(encoding="utf-8"))["input_hash"]
             for stage in HASHES}

    assert built == HASHES
