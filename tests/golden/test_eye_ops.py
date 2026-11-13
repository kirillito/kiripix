"""The eye Ops (ticket 0203): `plan_eyes`, `fill_from_neighbours` and `paint_eyes`, called directly on small fixed inputs.

The expected values are written out here and not kept as PNGs: the outputs are a few pixels and a few numbers, which read
better in the test than in an image.
"""

import numpy as np

from kiripix.ops import EyeAnchor, EyeStamp, fill_from_neighbours, paint_eyes, plan_eyes

SKIN, SHADE, DARK, WHITE = (220, 180, 140), (170, 130, 100), (30, 30, 40), (250, 250, 240)


def eye(x: float, y: float = 10.0, width: float = 2.2, turn: float = 0.0, facing: float = 1.0, seen: bool = True) -> EyeAnchor:
    return EyeAnchor(x, y, width, 2.0, turn, facing, seen)


def pair(shift: float = 0.0) -> list[EyeAnchor]:
    return [eye(8.5 + shift), eye(11.8 + shift)]


def test_two_eyes_facing_the_camera_get_a_white_each_and_pupils_toward_each_other() -> None:
    [stamps] = plan_eyes([pair()])

    assert stamps == [EyeStamp(left=8, top=9, columns=2, rows=2, pupil=1), EyeStamp(left=11, top=9, columns=2, rows=2, pupil=0)]


def test_a_sway_of_less_than_a_pixel_does_not_move_the_eyes_and_a_bigger_one_moves_both_together() -> None:
    plans = plan_eyes([pair(), pair(0.3), pair(-0.3), pair(0.4), pair(1.2), pair(0.7)])

    lefts = [[s.left for s in stamps if s is not None] for stamps in plans]
    assert lefts == [[8, 11], [8, 11], [8, 11], [8, 11], [9, 12], [9, 12]]


def test_a_narrow_eye_and_an_eye_without_whites_are_one_column() -> None:
    [narrow] = plan_eyes([[eye(8.5, width=1.2), eye(11.8, width=1.2)]])
    [plain] = plan_eyes([pair()], whites=False)

    assert [s.columns for s in narrow if s] == [1, 1] and [s.columns for s in plain if s] == [1, 1]
    assert [s.left for s in plain if s] == [8, 11], "the pupils stay where the eyes are"


def test_on_a_turned_face_the_far_eye_is_one_column_and_both_pupils_lead() -> None:
    turned = [eye(8.5, turn=-0.5, facing=0.8), eye(10.9, turn=-0.6, facing=0.6)]

    [stamps] = plan_eyes([turned])

    assert [(s.columns, s.pupil) for s in stamps if s] == [(2, 0), (1, 0)]


def test_an_eye_that_faces_away_in_most_frames_is_never_drawn_and_one_hidden_in_a_frame_is_left_out_of_it() -> None:
    away = [[eye(8.5), eye(11.8, facing=-0.5)]] * 3
    hidden = [pair(), [eye(8.5), eye(11.8, seen=False)], pair()]

    assert [stamps[1] for stamps in plan_eyes(away)] == [None, None, None]
    drawn = plan_eyes(hidden)
    assert drawn[1][1] is None and drawn[0][1] is not None and drawn[2][1] is not None
    assert drawn[1][0] is not None, "the other eye is still there"


def test_no_eyes_is_no_plan() -> None:
    assert plan_eyes([[], []]) == [[], []]
    assert plan_eyes([]) == []


def face() -> tuple[np.ndarray, np.ndarray]:
    """A 5 x 6 face: skin on the left half, shade on the right, a transparent row on top, and an eye of 2 x 2 in the middle."""
    colour = np.zeros((5, 6, 4), dtype=np.uint8)
    colour[1:, :3] = (*SKIN, 255)
    colour[1:, 3:] = (*SHADE, 255)
    mask = np.zeros((5, 6), dtype=bool)
    mask[2:4, 2:4] = True
    colour[mask] = (*DARK, 255)
    return colour, mask


def test_fill_gives_each_eye_pixel_the_skin_next_to_it() -> None:
    colour, mask = face()

    filled = fill_from_neighbours(colour, mask)

    assert (filled[2:4, 2, :3] == SKIN).all() and (filled[2:4, 3, :3] == SHADE).all()
    assert (filled[~mask] == colour[~mask]).all() and (filled[0] == 0).all()


def test_fill_leaves_a_mask_with_nothing_round_it_as_it_is() -> None:
    colour, _ = face()

    assert (fill_from_neighbours(colour, np.ones((5, 6), dtype=bool)) == colour).all()


def test_paint_puts_the_pupil_and_the_white_on_opaque_pixels_only() -> None:
    colour, mask = face()
    filled = fill_from_neighbours(colour, mask)

    open_eye = paint_eyes(filled, [EyeStamp(left=2, top=0, columns=2, rows=3, pupil=1), None], DARK, WHITE)

    assert (open_eye[0] == 0).all(), "the row above the face stays transparent"
    assert (open_eye[1:3, 2, :3] == WHITE).all() and (open_eye[1:3, 3, :3] == DARK).all()
    assert (open_eye[3:] == filled[3:]).all()


def test_a_closed_eye_is_a_line_on_its_bottom_row() -> None:
    colour, mask = face()
    filled = fill_from_neighbours(colour, mask)

    closed = paint_eyes(filled, [EyeStamp(left=2, top=2, columns=2, rows=2, pupil=1)], DARK, WHITE, closed=True)

    assert (closed[3, 2:4, :3] == DARK).all() and (closed[2] == filled[2]).all()


def test_without_a_white_every_column_is_the_pupils_colour() -> None:
    colour, mask = face()

    painted = paint_eyes(colour, [EyeStamp(left=2, top=2, columns=2, rows=1, pupil=0)], DARK, None)

    assert (painted[2, 2:4, :3] == DARK).all()
