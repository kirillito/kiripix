"""Golden and unit tests for the sel-out Ops (ticket 0382): an outline, or an inner line, in the colour of the part it borders; where
it borders two parts, the darker one's. The goldens are shown enlarged (12x, nearest) and captioned; the comparison is pixel-exact."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from kiripix.ops import inner_lines, sel_out_outline, sel_out_paint

EXPECTED = Path(__file__).parent / "expected"
SCALE = 12
SKIN, COAT, HAIR = (230, 170, 140), (60, 90, 160), (120, 70, 40)
# each part's darkest ramp colour, which its lines take; the coat's is the darkest of the three
LINES = {1: (150, 90, 70), 2: (20, 30, 70), 3: (60, 30, 15)}


def fixture() -> tuple[np.ndarray, np.ndarray]:
    """A 9 x 12 frame: skin (1) as a head over a coat (2) with hair (3) on top, and a notch in the top edge at column 6
    between the hair (left) and the coat's collar (right), so the outline pixel in it borders two parts."""
    rows = [
        "..333.2222..",
        "..333..222..",
        "..3311122...",
        "..1111111...",
        "..1111111...",
        "...22222....",
        "..222222222.",
        "..222222222.",
        "............",
    ]
    labels = np.array([[0 if c == "." else int(c) for c in r] for r in rows], dtype=np.uint8)
    rgba = np.zeros((*labels.shape, 4), dtype=np.uint8)
    for label, colour in ((1, SKIN), (2, COAT), (3, HAIR)):
        rgba[labels == label] = (*colour, 255)
    return rgba, labels


def drawn(image: np.ndarray, caption: str) -> np.ndarray:
    h, w = image.shape[:2]
    rgb = np.where(image[..., 3:4] > 0, image[..., :3], 255).astype(np.uint8)
    big = np.kron(rgb, np.ones((SCALE, SCALE, 1), dtype=np.uint8))
    canvas = Image.new("RGB", (w * SCALE, h * SCALE + 18), (255, 255, 255))
    canvas.paste(Image.fromarray(big, "RGB"), (0, 0))
    ImageDraw.Draw(canvas).text((2, h * SCALE + 3), caption, fill=(0, 0, 0))
    return np.asarray(canvas.convert("RGBA"), dtype=np.uint8)


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        Image.fromarray(actual, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def test_each_outline_pixel_takes_the_part_it_touches_and_the_darker_where_it_touches_two(request: pytest.FixtureRequest) -> None:
    rgba, labels = fixture()

    out = sel_out_outline(rgba, labels, LINES, (255, 0, 255))

    assert tuple(out[0, 1]) == (*LINES[3], 255)  # left of the hair: the hair's colour
    assert tuple(out[1, 5]) == (*LINES[3], 255)  # the notch's floor touches the hair only
    assert tuple(out[3, 1]) == (*LINES[1], 255)  # beside the skin
    assert tuple(out[8, 4]) == (*LINES[2], 255)  # under the coat
    assert (out[labels > 0] == rgba[labels > 0]).all(), "the part's own pixels are not changed"
    assert_golden(request, drawn(out, "outline, own parts"), "sel_out_outline.png")


def test_a_pixel_between_two_parts_takes_the_darker_part(request: pytest.FixtureRequest) -> None:
    rgba, labels = fixture()
    # the notch in the top edge: (0, 5) is transparent with the hair (3) on its left and the coat (2) on its right
    assert labels[0, 5] == 0 and labels[0, 4] == 3 and labels[0, 6] == 2

    out = sel_out_outline(rgba, labels, LINES, (255, 0, 255))

    assert tuple(out[0, 5]) == (*LINES[2], 255)  # the coat's line colour is darker than the hair's
    swapped = sel_out_outline(rgba, labels, {**LINES, 2: (250, 250, 250)}, (255, 0, 255))
    assert tuple(swapped[0, 5]) == (*LINES[3], 255)  # with the coat's the lighter one, the hair's wins
    assert_golden(request, drawn(out, "notch: darker (coat)"), "sel_out_notch.png")


def test_inner_lines_take_the_darker_of_the_two_parts_across_the_border(request: pytest.FixtureRequest) -> None:
    rgba, labels = fixture()
    lines = inner_lines(labels, np.zeros(labels.shape, dtype=np.float32), [])

    out = sel_out_paint(rgba, labels, lines, LINES)

    assert tuple(out[3, 4]) == tuple(rgba[3, 4])  # inside the skin, no border: unchanged
    on = np.argwhere(lines)
    for y, x in on:  # every line pixel is one of its own and its neighbours' colours: the darkest of them
        near = {int(labels[y, x])} | {int(labels[y + dy, x + dx]) for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
                                      if 0 <= y + dy < labels.shape[0] and 0 <= x + dx < labels.shape[1]}
        near.discard(0)
        darkest = min(near, key=lambda m: (sum(c * w for c, w in zip(LINES[m], (0.2126, 0.7152, 0.0722), strict=True)), m))
        assert tuple(out[y, x, :3]) == LINES[darkest]
    assert_golden(request, drawn(out, "inner: darker of two"), "sel_out_lines.png")


def test_a_pixel_with_no_known_part_takes_the_fallback_or_stays() -> None:
    rgba, labels = fixture()

    kept = sel_out_outline(rgba, labels, {}, (1, 2, 3))
    none = sel_out_paint(rgba, labels, labels == 0, {})

    assert tuple(kept[0, 1]) == (1, 2, 3, 255)
    assert (none == rgba).all()


def test_the_input_is_not_changed_and_a_wrong_size_is_refused() -> None:
    rgba, labels = fixture()
    before = rgba.copy()

    sel_out_outline(rgba, labels, LINES, (0, 0, 0), "edge")

    assert (rgba == before).all()
    with pytest.raises(ValueError):
        sel_out_paint(rgba, labels[:-1], labels[:-1] == 0, LINES)
