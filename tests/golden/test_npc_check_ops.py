"""Unit tests for the NPC Checks (ticket 0357): `npc.wearable_body`, `npc.colour_choice`, `npc.part_unset` and `npc.stack`, called
directly on small fixed inputs."""

import numpy as np

from kiripix.checks import (
    Finding,
    LayerFrame,
    buried_by_order,
    check_colour_choice,
    check_npc_stack,
    check_part_unset,
    check_wearable_body,
)

NPC, BASE = "npc.guard", "character.zed"
AUBURN, BLOND = [[0, 0, 0], [29, 43, 83]], [[95, 87, 79], [131, 118, 156]]


def one(findings: list[Finding], code: str) -> Finding:
    assert [f.code for f in findings] == [code]
    assert (findings[0].fix is None) != (findings[0].owner_action is None)
    return findings[0]


def test_a_wearable_of_another_body_is_an_error_naming_it() -> None:
    found = check_wearable_body(NPC, BASE, [("wearable.hair", BASE), ("wearable.cap", "character.twin"), ("wearable.x", None)],
                                {"wearable.hair": "keep", "wearable.cap": "kiripix set npc.guard choose wearables=wearable.hair"})

    finding = one(found, "npc.wearable_body")
    assert finding.severity == "error" and finding.fix == "kiripix set npc.guard choose wearables=wearable.hair"
    assert finding.position is not None and finding.position.field == "wearables/wearable.cap"
    assert finding.data == {"wearable": "wearable.cap", "body": "character.twin", "base": BASE}
    assert check_wearable_body(NPC, BASE, [("wearable.hair", BASE)], {"wearable.hair": ""}) == []


def test_a_colour_that_is_no_choice_now_names_the_part_and_its_choices() -> None:
    table = {"hair": {"auburn": AUBURN, "blond": BLOND}, "top": {"red": BLOND}, "boots": {}}
    without = {"hair": "set-hair", "top": "set-top", "eyes": "set-eyes", "boots": "set-boots"}

    cases = {
        "choice_gone": {"hair": ("purple", AUBURN)},
        "part_gone": {"eyes": ("green", AUBURN)},
        "choice_changed": {"top": ("red", AUBURN)},
    }
    for reason, built in cases.items():
        finding = one(check_colour_choice(NPC, built, table, without, "rebuild"), "npc.colour_choice")
        assert finding.severity == "error" and finding.data["reason"] == reason
        assert finding.fix == ("rebuild" if reason == "choice_changed" else without[next(iter(built))])
    gone = check_colour_choice(NPC, cases["choice_gone"], table, without, "rebuild")[0]
    assert "auburn, blond" in gone.message and gone.data["choices"] == ["auburn", "blond"] and gone.data["part"] == "hair"


def test_a_colour_that_is_still_a_choice_passes() -> None:
    table = {"hair": {"auburn": AUBURN}}

    assert check_colour_choice(NPC, {"hair": ("auburn", [[0, 0, 0], [29, 43, 83]])}, table, {}, "rebuild") == []
    assert check_colour_choice(NPC, {}, table, {}, "rebuild") == []


def test_a_part_with_choices_left_as_built_is_info() -> None:
    table = {"hair": {"auburn": AUBURN}, "top": {"red": BLOND}, "boots": {}}

    found = check_part_unset(NPC, ["hair"], table, {"top": "set-top", "hair": "set-hair"})

    finding = one(found, "npc.part_unset")
    assert finding.severity == "info" and finding.data == {"part": "top", "choices": ["red"]} and finding.fix == "set-top"
    assert check_part_unset(NPC, ["hair", "top"], table, {}) == []  # a Part without choices is nothing to set


def layer(box: tuple[int, int, int, int], depth: int) -> tuple[np.ndarray, np.ndarray]:
    x0, x1, y0, y1 = box
    frame = np.zeros((6, 8, 4), dtype=np.uint8)
    frame[y0:y1, x0:x1] = (200, 100, 50, 255)
    z = np.full((6, 8), 65535, dtype=np.uint16)
    z[y0:y1, x0:x1] = depth
    return frame, z


def test_the_pixels_the_order_buries_but_the_depth_shows_are_counted_per_layer() -> None:
    body, body_z = layer((0, 6, 0, 6), 100)
    coat, coat_z = layer((0, 4, 0, 6), 50)  # in front of the body, above it by order: nothing buried
    pack, pack_z = layer((2, 6, 0, 4), 10)  # the nearest of all, but under the coat by order where they meet

    plain = buried_by_order([body, coat], [body_z, coat_z])
    stacked = buried_by_order([body, pack, coat], [body_z, pack_z, coat_z])

    assert plain == [(36, 0), (24, 0)]
    assert stacked == [(36, 0), (16, 8), (24, 0)]  # the pack: 2 columns by 4 rows under the coat
    assert buried_by_order([body, coat], [body_z, np.full((6, 8), 200, dtype=np.uint16)])[1] == (24, 0)
    assert buried_by_order([body, coat], [coat_z, body_z])[0] == (36, 24)  # swap the depths: the body is in front of the coat


def frame(wearable: str, index: int, opaque: int, buried: int) -> LayerFrame:
    return LayerFrame(wearable=wearable, clip="idle", direction="s", index=index, opaque=opaque, buried=buried)


def test_a_wearable_buried_in_most_of_its_frames_is_a_warning() -> None:
    frames = [frame("wearable.pack", i, 40, 30 if i < 3 else 0) for i in range(4)]
    frames += [frame("wearable.hair", i, 40, 4 if i == 0 else 0) for i in range(4)]  # one frame of four, and 10 % of the pixels

    finding = one(check_npc_stack(NPC, frames, lambda w: f"kiripix set npc.guard choose wearables={w}@99"), "npc.stack")

    assert finding.severity == "warning" and finding.fix == "kiripix set npc.guard choose wearables=wearable.pack@99"
    assert finding.position is not None and finding.position.field == "wearables/wearable.pack"
    assert finding.data["wearable"] == "wearable.pack" and finding.data["frames"] == 4 and finding.data["buried_frames"] == 3
    assert [w["frame"] for w in finding.data["worst"]] == [0, 1, 2]


def test_half_the_frames_is_not_most_and_a_frame_without_pixels_is_not_counted() -> None:
    half = [frame("wearable.pack", i, 40, 30 if i < 2 else 0) for i in range(4)]
    empty = [frame("wearable.pack", 0, 40, 30), frame("wearable.pack", 1, 0, 0), frame("wearable.pack", 2, 0, 0)]

    assert check_npc_stack(NPC, half, lambda w: "fix") == []
    assert [f.data["frames"] for f in check_npc_stack(NPC, empty, lambda w: "fix")] == [1]
