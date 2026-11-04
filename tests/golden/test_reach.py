"""The reach Ops, called directly: walkable from `solid` and the Body's footprint, compared pixel-exactly with golden
PNGs (a walkable pixel is white, the rest black)."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import Gap, Island, narrowest_gaps, reachable, walkable, walkable_islands

EXPECTED = Path(__file__).parent / "expected"


def as_image(mask: np.ndarray) -> np.ndarray:
    grey = np.where(mask, 255, 0).astype(np.uint8)
    return np.dstack([grey, grey, grey, np.full_like(grey, 255)])


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        EXPECTED.mkdir(exist_ok=True)
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def corner() -> np.ndarray:
    """48 x 32: a solid block filling the room's top right, so the floor turns a corner around it."""
    solid = np.zeros((32, 48), dtype=np.bool_)
    solid[:16, 24:] = True
    return solid


def gap(width: int) -> np.ndarray:
    """48 x 32: a solid wall across the room at x 20 to 23, with a gap `width` pixels wide from y 12."""
    solid = np.zeros((32, 48), dtype=np.bool_)
    solid[:, 20:24] = True
    solid[12:12 + width, 20:24] = False
    return solid


def test_walkable_for_a_12_by_8_footprint_around_a_corner(request: pytest.FixtureRequest) -> None:
    assert_golden(request, as_image(walkable(corner(), (12, 8))), "walkable_corner.png")


def test_walkable_through_a_gap_narrower_than_the_footprint(request: pytest.FixtureRequest) -> None:
    # A 12 x 8 footprint needs 8 rows free to cross the wall, and the gap has 7: the two sides stay apart.
    assert_golden(request, as_image(walkable(gap(7), (12, 8))), "walkable_narrow_gap.png")


def test_the_footprint_is_centred_with_the_extra_pixel_up_and_left_of_the_spot() -> None:
    # Worked by hand: a 12 x 8 footprint at spot (x, y) covers x - 6 to x + 5 and y - 4 to y + 3.
    result = walkable(np.zeros((32, 48), dtype=np.bool_), (12, 8))

    assert result[4, 6] and result[28, 42]
    assert not result[3, 6] and not result[4, 5]  # the footprint would cross the top or left edge
    assert not result[29, 42] and not result[28, 43]  # or the bottom or right edge


def test_a_single_solid_pixel_blocks_exactly_the_spots_whose_footprint_covers_it() -> None:
    solid = np.zeros((9, 9), dtype=np.bool_)
    solid[4, 4] = True

    result = walkable(solid, (3, 3))

    expected = np.zeros((9, 9), dtype=np.bool_)
    expected[1:8, 1:8] = True  # a 3 x 3 footprint fits from 1 to 7
    expected[3:6, 3:6] = False  # and touches the pixel from 3 to 5
    assert (result == expected).all()


def test_a_gap_exactly_as_wide_as_the_footprint_is_walkable_one_row_narrower_is_not() -> None:
    wide, narrow = walkable(gap(8), (12, 8)), walkable(gap(7), (12, 8))

    assert wide[:, 21].any()
    assert not narrow[:, 21].any()


def test_a_footprint_larger_than_the_room_fits_nowhere() -> None:
    assert not walkable(np.zeros((4, 4), dtype=np.bool_), (5, 2)).any()


def test_the_input_is_not_modified_and_bad_input_is_refused() -> None:
    solid = corner()
    before = solid.copy()
    walkable(solid, (12, 8))
    assert (solid == before).all()

    with pytest.raises(ValueError, match="footprint"):
        walkable(solid, (0, 8))
    with pytest.raises(ValueError, match="Mask"):
        walkable(np.zeros((4, 4), dtype=np.uint8), (2, 2))


# the flood. BODY covers x - 6 to x + 5 and y - 4 to y + 3, so a wall at x 20 to 23 blocks the spots x 15 to 29: walkable
# is x 6 to 14 on the left and x 30 to 42 on the right, y 4 to 28 on both.

BODY = (12, 8)
LEFT = (10, 16)
RIGHT = (36, 16)
NO_SOLID = np.zeros((32, 48), dtype=np.bool_)


def split() -> np.ndarray:
    """48 x 32: a solid wall from top to bottom at x 20 to 23."""
    return gap(0)


def left_side() -> np.ndarray:
    expected = np.zeros((32, 48), dtype=np.bool_)
    expected[4:29, 6:15] = True
    return expected


def test_a_flood_stays_on_its_side_of_a_wall(request: pytest.FixtureRequest) -> None:
    result = reachable(walkable(split(), BODY), [LEFT], BODY)

    assert (result == left_side()).all()
    assert_golden(request, as_image(result), "reach_split.png")


def test_a_flood_from_both_sides_of_a_wall_reaches_both() -> None:
    ground = walkable(split(), BODY)

    assert (reachable(ground, [LEFT, RIGHT], BODY) == ground).all()


def test_a_gap_one_pixel_narrower_than_the_footprint_stops_the_flood(request: pytest.FixtureRequest) -> None:
    result = reachable(walkable(gap(7), BODY), [LEFT], BODY)

    assert (result == left_side()).all()
    assert_golden(request, as_image(result), "reach_narrow_gap.png")


def test_a_gap_exactly_as_wide_as_the_footprint_lets_the_flood_through_from_any_seed() -> None:
    ground = walkable(gap(8), BODY)

    for seed in (LEFT, (11, 17), (9, 5)):
        assert (reachable(ground, [seed], BODY) == ground).all()


def test_a_dash_crosses_a_pit_as_wide_as_the_dash(request: pytest.FixtureRequest) -> None:
    ground = walkable(split(), BODY)  # the same shape as the wall, but as a pit: no walking on it, and no solid

    result = reachable(ground, [LEFT], BODY, dash=4, solid=NO_SOLID)

    assert (result == ground).all()  # from x 14 over the pit to x 30: 4 px of pit, plus the Body's own 12
    assert_golden(request, as_image(result), "reach_dash.png")


def test_a_dash_one_pixel_shorter_than_the_pit_does_not_cross() -> None:
    assert (reachable(walkable(split(), BODY), [LEFT], BODY, dash=3, solid=NO_SOLID) == left_side()).all()


def test_a_dash_uses_the_footprint_along_the_way_it_goes() -> None:
    pit = np.zeros((32, 48), dtype=np.bool_)
    pit[14:18, :] = True  # a band across the room, 4 rows high; BODY is 8 high, so it blocks the spots y 11 to 21
    ground = walkable(pit, BODY)

    assert (reachable(ground, [(24, 6)], BODY, dash=4, solid=NO_SOLID) == ground).all()
    assert not reachable(ground, [(24, 6)], BODY, dash=3, solid=NO_SOLID)[22:].any()


def test_a_dash_never_crosses_solid_however_long_it_is() -> None:
    assert (reachable(walkable(split(), BODY), [LEFT], BODY, dash=48, solid=split()) == left_side()).all()


def test_a_dash_crosses_a_pit_only_where_the_footprint_clears_the_solid_beside_it() -> None:
    ground = walkable(split(), BODY)  # the pit, from top to bottom
    solid = np.zeros((32, 48), dtype=np.bool_)

    solid[8:25, 20:24] = True  # BODY at y 4 covers y 0 to 7, so it can still cross at the top
    assert (reachable(ground, [LEFT], BODY, dash=4, solid=solid) == ground).all()

    solid[7, 20:24] = True  # and now there is nowhere it can
    assert (reachable(ground, [LEFT], BODY, dash=4, solid=solid) == left_side()).all()


def test_a_seed_off_walkable_ground_or_outside_the_room_floods_nothing() -> None:
    ground = walkable(split(), BODY)

    assert not reachable(ground, [(21, 16), (480, 16), (16, 320)], BODY).any()
    assert not reachable(ground, [], BODY).any()


def test_a_longer_step_gives_a_whole_region_without_crossing_a_wall() -> None:
    ground = walkable(split(), BODY)

    assert (reachable(ground, [LEFT], BODY, step=4) == left_side()).all()


def test_a_step_longer_than_a_wall_does_not_jump_it() -> None:
    ground = np.ones((5, 20), dtype=np.bool_)
    ground[:, 5] = False

    result = reachable(ground, [(0, 0)], (1, 1), step=8)

    assert result[:, :5].all() and not result[:, 5:].any()


def test_a_step_stopped_short_by_a_wall_lands_against_it() -> None:
    ground = np.ones((1, 7), dtype=np.bool_)
    ground[0, 6] = False

    assert reachable(ground, [(0, 0)], (1, 1), step=4)[0, 5]


def test_the_flood_input_is_not_modified_and_bad_input_is_refused() -> None:
    ground = walkable(split(), BODY)
    before = ground.copy()
    reachable(ground, [LEFT], BODY, step=2, dash=4, solid=NO_SOLID)
    assert (ground == before).all()

    with pytest.raises(ValueError, match="step"):
        reachable(ground, [LEFT], BODY, step=0)
    with pytest.raises(ValueError, match="dash"):
        reachable(ground, [LEFT], BODY, dash=-1)
    with pytest.raises(ValueError, match="solid"):
        reachable(ground, [LEFT], BODY, dash=4)
    with pytest.raises(ValueError, match="footprint"):
        reachable(ground, [LEFT], (0, 8))
    with pytest.raises(ValueError, match="Mask"):
        reachable(ground.astype(np.uint8), [LEFT], BODY)


# islands


def test_walkable_ground_with_nothing_reached_is_an_island_with_its_bounding_box() -> None:
    ground = walkable(split(), BODY)

    islands = walkable_islands(ground, reachable(ground, [LEFT], BODY))

    assert islands == [Island(x=30, y=4, width=13, height=25, spots=325)]


def test_ground_partly_reached_is_not_an_island_and_the_largest_island_comes_first() -> None:
    ground = np.zeros((6, 12), dtype=np.bool_)
    ground[0, 0:3] = True  # reached at one end only
    ground[2:5, 5:7] = True
    ground[0, 10] = True
    reached = np.zeros_like(ground)
    reached[0, 0] = True

    assert walkable_islands(ground, reached) == [Island(x=5, y=2, width=2, height=3, spots=6),
                                                 Island(x=10, y=0, width=1, height=1, spots=1)]


# the narrowest gaps


def test_a_gap_narrower_than_the_footprint_is_reported_with_the_width_and_its_centre() -> None:
    assert narrowest_gaps(gap(7), BODY) == [Gap(width=7, needed=8, x=21, y=15)]


def test_a_gap_the_body_fits_is_reported_too_and_the_narrowest_comes_first() -> None:
    solid = gap(9)
    solid[:, 30:34] = True
    solid[20:30, 30:34] = False  # a second wall, with a 10 px gap at y 20 to 29

    assert narrowest_gaps(solid, BODY) == [Gap(width=9, needed=8, x=21, y=16), Gap(width=10, needed=8, x=31, y=24)]


def test_a_gap_is_measured_across_whichever_way_the_body_goes_through_it() -> None:
    solid = np.zeros((48, 48), dtype=np.bool_)
    solid[20:24, :] = True
    solid[20:24, 12:22] = False  # a 10 px gap in a band across the room; the way through is downwards

    assert narrowest_gaps(solid, BODY) == [Gap(width=10, needed=12, x=16, y=21)]


def test_a_gap_can_lie_between_a_wall_and_the_room_edge() -> None:
    solid = np.zeros((32, 48), dtype=np.bool_)
    solid[7:, 20:24] = True  # a wall from the bottom edge, leaving y 0 to 6 free

    assert narrowest_gaps(solid, BODY) == [Gap(width=7, needed=8, x=21, y=3)]


def test_open_floor_a_dead_end_and_a_wide_passage_are_not_gaps() -> None:
    assert narrowest_gaps(np.zeros((32, 48), dtype=np.bool_), BODY) == []
    assert narrowest_gaps(corner(), BODY) == []
    notch = np.ones((32, 48), dtype=np.bool_)
    notch[8:32, 8:40] = False
    notch[12:16, 0:8] = False  # a notch into the wall from the room: it leads nowhere
    assert narrowest_gaps(notch, BODY) == []
    assert narrowest_gaps(gap(16), BODY) == []  # twice the Body across: wide enough not to mention


def test_a_passage_with_uneven_edges_is_one_gap_at_its_narrowest() -> None:
    solid = np.ones((40, 100), dtype=np.bool_)
    solid[:, :30] = solid[:, 70:] = False  # a room at each side, joined by two corridors
    solid[10:22, 30:70] = False  # 12 px high
    solid[10, 50:54] = True  # with a bump that makes it 11 at x 50 to 53
    solid[24:38, 30:70] = False  # 14 px high

    assert narrowest_gaps(solid, BODY) == [Gap(width=11, needed=8, x=51, y=16), Gap(width=14, needed=8, x=49, y=30)]


def test_at_most_the_limit_of_gaps_is_reported() -> None:
    solid = np.zeros((32, 96), dtype=np.bool_)
    for left in (10, 30, 50, 70):
        solid[:, left:left + 4] = True
        solid[10:10 + (left // 10 + 6), left:left + 4] = False

    assert [g.width for g in narrowest_gaps(solid, BODY, limit=2)] == [7, 9]
