"""Golden test for a sprite's palette by parts (ticket 0319): `colour_regions` and `region_labels` group a made-up figure's
colours into parts by hue, then the body's part Ops (`part_ramps`, `quantize_by_part`) give each part `shades` colours, dark to
light, as the sprite's `palette` does. Called directly; the golden is the mapped frame, enlarged for review."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops import colour_regions, inner_lines, part_ramps, quantize_by_part, region_labels

EXPECTED = Path(__file__).parent / "expected"
SCALE = 8
HUES = {"red": (1.0, 0.25, 0.2), "green": (0.3, 1.0, 0.35), "blue": (0.25, 0.4, 1.0)}
SHADES = 4


def ramp(tint: tuple[float, float, float], count: int) -> list[tuple[int, int, int]]:
    """`count` shades of one hue, dark to light."""
    return [tuple(int(round(c * (40 + 200 * k / (count - 1)))) for c in tint) for k in range(count)]  # type: ignore[misc]


def figure() -> np.ndarray:
    """Three bands of 9 x 3 px, one per hue, each a gradient of 9 shades, with a transparent column round them."""
    frame = np.zeros((9, 11, 4), dtype=np.uint8)
    for band, tint in enumerate(HUES.values()):
        for x, colour in enumerate(ramp(tint, 9)):
            frame[band * 3:band * 3 + 3, x + 1] = (*colour, 255)
    return frame


def palette() -> np.ndarray:
    return np.array([c for tint in HUES.values() for c in ramp(tint, 12)], dtype=np.uint8)


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    big = np.kron(actual, np.ones((SCALE, SCALE, 1), dtype=np.uint8))
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        EXPECTED.mkdir(exist_ok=True)
        Image.fromarray(big, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert big.shape == expected.shape
    different = np.argwhere((big != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def test_three_hues_of_many_shades_come_out_with_shades_per_hue(request: pytest.FixtureRequest) -> None:
    frame = figure()
    regions = colour_regions([frame])
    assert regions.names == ["red", "green", "blue"]
    labels = region_labels(frame, regions)
    parts = {name: [number] for number, name in enumerate(regions.names, start=1)}

    ramps = part_ramps([frame], [labels], parts, palette(), {n: SHADES for n in parts}, np.zeros((0, 3), dtype=np.uint8))
    mapped = quantize_by_part(frame, labels, parts, ramps, np.zeros((0, 3), dtype=np.uint8))

    assert_golden(request, mapped, "sprite_parts_three_hues.png")
    for number, name in enumerate(regions.names, start=1):
        used = {tuple(c) for c in mapped[labels == number][:, :3].tolist()}
        assert len(used) == SHADES  # every hue keeps its own ramp of 4, dark to light
        assert used == {tuple(c) for c in ramps[name].tolist()}


def test_greys_are_one_region_and_a_hue_word_twice_is_numbered_by_size() -> None:
    frame = np.zeros((3, 8, 4), dtype=np.uint8)
    frame[0, :] = (90, 90, 96, 255)  # grey
    frame[1, :2] = (150, 150, 158, 255)  # a lighter grey, the same region
    frame[1, 2:] = (220, 60, 40, 255)  # red, 6 px
    frame[2, :3] = (220, 40, 90, 255)  # a cooler red, OKLab hue 12 against 31: its own region at hue_gap 10, 3 px
    frame[2, 3:] = (0, 0, 0, 0)

    regions = colour_regions([frame], hue_gap=10.0)

    assert regions.names == ["red_2", "red", "grey"]  # by mean hue; the larger red is plain; grey last
    assert regions.pixels == [3, 6, 10]
    labels = region_labels(frame, regions)
    assert len(set(labels[0].tolist())) == 1 and labels[0, 0] == labels[1, 0]
    assert labels[2, 5] == 0
    unseen = np.array([[[222, 62, 42, 255]]], dtype=np.uint8)  # a colour the regions didn't see goes to its nearest
    assert region_labels(unseen, regions)[0, 0] == labels[1, 2]


def test_an_inner_line_where_two_parts_meet_and_none_round_a_skipped_part(request: pytest.FixtureRequest) -> None:
    # A sprite has no depth: every pixel ties, so the line is the lower (or right) pixel of each border (ticket 0320).
    frame = np.zeros((8, 10, 4), dtype=np.uint8)
    frame[1:4, 1:9] = (200, 60, 50, 255)  # red, the upper part
    frame[4:7, 1:9] = (50, 80, 200, 255)  # blue, the lower part
    frame[2:6, 6:9] = (60, 170, 70, 255)  # green, across both, skipped
    regions = colour_regions([frame])
    assert regions.names == ["red", "green", "blue"]
    red, green, blue = 1, 2, 3
    labels = region_labels(frame, regions)

    lines = inner_lines(labels, np.zeros(labels.shape), [green])

    expected = np.zeros(labels.shape, dtype=bool)
    expected[4, 1:6] = True  # the 1 px line on the blue side of the red-blue border, up to the green part
    assert (lines == expected).all()
    assert not inner_lines(labels, np.zeros(labels.shape), [(red, blue), green]).any()
    out = frame.copy()
    out[lines] = (24, 24, 40, 255)
    assert_golden(request, out, "sprite_parts_inner_lines.png")
