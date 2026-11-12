"""Golden tests for the per-part palette ramps (ticket 0149): `part_ramps`, `quantize_by_part`,
`remove_orphans_by_part` and the `ramp_shared` Check, called directly.

Materials: 1 hair, 2 boots, 3 skin, 4 eye, 5 jacket. Hair and boots are the parts; the rest are fixed.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.checks import check_ramp_shared
from kiripix.ops import lightness_breaks, part_ramps, quantize_by_part, remove_orphans_by_part

EXPECTED = Path(__file__).parent / "expected"

PALETTE = np.array(
    [
        [28, 13, 8],  # 0 near black brown: the hair, and the boots just as well
        [64, 32, 20],  # 1 dark brown
        [120, 70, 45],  # 2 mid brown
        [235, 190, 160],  # 3 skin
        [20, 20, 20],  # 4 eye / outline
        [90, 90, 110],  # 5 jacket grey
        [200, 60, 60],  # 6 red
    ],
    dtype=np.uint8,
)
HAIR, BOOTS, SKIN, EYE, JACKET = 1, 2, 3, 4, 5


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


def build(rows: list[list[int]], colours: dict[int, tuple[int, int, int]]) -> tuple[np.ndarray, np.ndarray]:
    """A frame and its material labels from a grid of materials; material 0 is transparent."""
    frame = np.zeros((len(rows), len(rows[0]), 4), dtype=np.uint8)
    labels = np.zeros(frame.shape[:2], dtype=np.int32)
    for y, row in enumerate(rows):
        for x, material in enumerate(row):
            if material:
                frame[y, x] = (*colours[material], 255)
                labels[y, x] = material
    return frame, labels


PARTS = {"hair": [HAIR], "boots": [BOOTS]}


def test_near_identical_parts_get_disjoint_ramps(request: pytest.FixtureRequest) -> None:
    # Hair (28, 13, 8) and boots (31, 13, 8): both best fit palette 0. The hair has more pixels, so it loses more
    # by being denied it; the boots take the next best colour, 4.
    frame, labels = build(
        [[1, 1, 1, 1, 2, 2], [1, 1, 1, 1, 2, 2], [1, 1, 3, 3, 0, 0]],
        {1: (28, 13, 8), 2: (31, 13, 8), 3: (235, 190, 160)},
    )
    ramps = part_ramps([frame], [labels], PARTS, PALETTE, {"hair": 1, "boots": 1}, PALETTE[[3]])

    assert ramps["hair"].tolist() == [[28, 13, 8]]
    assert ramps["boots"].tolist() == [[20, 20, 20]]
    assert part_ramps([frame, frame], [labels, labels], PARTS, PALETTE, {"hair": 1, "boots": 1}, PALETTE[[3]])[
        "boots"
    ].tolist() == ramps["boots"].tolist()
    mapped = quantize_by_part(frame, labels, PARTS, ramps, PALETTE[[3]])
    assert_golden(request, mapped, "part_ramps_disjoint.png")
    assert set(map(tuple, mapped[labels == HAIR][:, :3].tolist())) == {(28, 13, 8)}
    assert set(map(tuple, mapped[labels == BOOTS][:, :3].tolist())) == {(20, 20, 20)}


def test_the_part_that_loses_least_gives_way_whichever_is_listed_first() -> None:
    frame, labels = build([[1, 1, 1, 1, 2, 2]], {1: (28, 13, 8), 2: (31, 13, 8)})
    reversed_parts = {"boots": [BOOTS], "hair": [HAIR]}
    ramps = part_ramps([frame], [labels], reversed_parts, PALETTE, {"hair": 1, "boots": 1}, PALETTE[[4]])
    assert ramps["hair"].tolist() == [[28, 13, 8]]
    assert ramps["boots"].tolist() == [[64, 32, 20]]


def test_reserved_colours_are_never_in_a_ramp_and_a_textured_part_gets_all_its_steps() -> None:
    # A hair of three browns, and 0 reserved as the outline colour.
    frame, labels = build([[1, 1, 1, 1, 1, 1]], {1: (28, 13, 8)})
    frame[0, 2, :3], frame[0, 3, :3], frame[0, 4, :3], frame[0, 5, :3] = (64, 32, 20), (64, 32, 20), (120, 70, 45), (120, 70, 45)
    ramps = part_ramps([frame], [labels], {"hair": [HAIR]}, PALETTE, {"hair": 3}, PALETTE[[0]])

    assert len(ramps["hair"]) == 3
    assert [28, 13, 8] not in ramps["hair"].tolist()
    lightness = [c.sum() for c in ramps["hair"].astype(int)]
    assert lightness == sorted(lightness)  # dark to light
    assert PALETTE[1].tolist() in ramps["hair"].tolist() and PALETTE[2].tolist() in ramps["hair"].tolist()


def test_a_part_that_cannot_get_its_colours_is_named() -> None:
    frame, labels = build([[1, 2]], {1: (28, 13, 8), 2: (31, 13, 8)})
    with pytest.raises(ValueError, match="needs 4 colours"):
        part_ramps([frame], [labels], PARTS, PALETTE, {"hair": 4, "boots": 4}, PALETTE[[3]])
    with pytest.raises(ValueError, match="both part"):
        part_ramps([frame], [labels], {"a": [1], "b": [1]}, PALETTE, {"a": 1, "b": 1}, PALETTE[:0])


def test_a_dithered_pixel_stays_inside_its_parts_ramp() -> None:
    frame, labels = build([[1] * 8] * 8 + [[3] * 8] * 8, {1: (50, 25, 15), 3: (235, 190, 160)})
    ramps = {"hair": PALETTE[[0, 1, 2]], "boots": PALETTE[[6]]}
    mapped = quantize_by_part(frame, labels, {"hair": [HAIR]}, ramps, PALETTE[[3, 5]], dither=4, strength=1.0)

    assert {tuple(c) for c in mapped[labels == HAIR][:, :3].tolist()} <= {tuple(c) for c in PALETTE[[0, 1, 2]].tolist()}
    assert len({tuple(c) for c in mapped[labels == HAIR][:, :3].tolist()}) > 1  # it did dither
    assert {tuple(c) for c in mapped[labels == SKIN][:, :3].tolist()} <= {tuple(c) for c in PALETTE[[3, 5]].tolist()}


def test_an_orphan_on_a_part_boundary_takes_its_own_parts_colour(request: pytest.FixtureRequest) -> None:
    # Left: hair (mid brown); right: boots (dark brown). One hair-material pixel, painted near black, sits in the
    # boots' edge with three boots neighbours and one hair neighbour: plain `remove_orphans` would paint it boots
    # brown, which would put a boots colour in the hair.
    a, b, c = (120, 70, 45), (28, 13, 8), (64, 32, 20)
    frame, labels = build([[1, 1, 2, 2, 2]] * 3, {1: a, 2: c})
    frame[1, 2, :3] = b
    labels[1, 2] = HAIR
    cleaned = remove_orphans_by_part(frame, labels, PARTS, 1)

    # The speck is hair, so it takes the hair colour from its hair neighbour, not the boots' colour that surrounds it.
    assert cleaned[1, 2, :3].tolist() == list(a)
    assert cleaned[0, 2, :3].tolist() == list(c)
    assert_golden(request, np.concatenate([frame, cleaned], axis=1), "part_ramps_orphan_boundary.png")


def test_a_detail_that_is_a_material_of_its_own_is_kept_and_a_shading_speck_is_cleaned(
    request: pytest.FixtureRequest,
) -> None:
    skin, dark, eye = (235, 190, 160), (120, 70, 45), (20, 20, 20)
    frame, labels = build(
        [
            [3, 3, 3, 3, 3, 3, 3],
            [3, 3, 4, 3, 3, 3, 3],  # the eye: 1 px, a material of its own, surrounded by skin
            [3, 3, 3, 3, 3, 3, 3],
            [3, 3, 3, 3, 3, 3, 3],
            [3, 3, 3, 3, 3, 3, 3],
        ],
        {3: skin, 4: eye},
    )
    frame[3, 5, :3] = dark  # a shading speck: skin material, a darker skin colour, 1 px
    cleaned = remove_orphans_by_part(frame, labels, {"skin": [SKIN]}, 1)

    assert cleaned[1, 2, :3].tolist() == list(eye)  # kept
    assert cleaned[3, 5, :3].tolist() == list(skin)  # cleaned
    # The eye is a material of its own, so even listed as a part it stays apart from the skin around it.
    assert (cleaned[labels == SKIN][:, :3] == skin).all()
    assert_golden(request, np.concatenate([frame, cleaned], axis=1), "part_ramps_eye_and_speck.png")
    # With no materials grouped, the ordinary rule paints the eye over; this one doesn't.
    from kiripix.ops import remove_orphans

    assert remove_orphans(frame, 1)[1, 2, :3].tolist() == list(skin)


def test_ramp_shared_names_both_parts_and_the_first_pixel() -> None:
    frame, labels = build([[1, 1, 2, 2]], {1: (28, 13, 8), 2: (64, 32, 20)})
    ramps = {"hair": PALETTE[[0, 1]], "boots": PALETTE[[2]]}
    findings = check_ramp_shared(frame, labels, PARTS, ramps, "f.png", fix="kiripix run x palette")
    (finding,) = findings  # the boots pixels are colour 1, which is hair's ramp
    assert finding.code == "palette.ramp_shared"
    assert "boots" in finding.message and "hair" in finding.message
    assert (finding.position.x, finding.position.y) == (2, 0)  # type: ignore[union-attr]

    shared = {"hair": PALETTE[[0, 1]], "boots": PALETTE[[1, 2]]}
    clean = np.zeros((1, 1, 4), dtype=np.uint8)
    (pair,) = check_ramp_shared(clean, np.zeros((1, 1), dtype=np.int32), PARTS, shared, "f.png", fix="x")
    assert "hair" in pair.message and "boots" in pair.message and "#402014" in pair.message


def test_ramp_shared_is_silent_for_disjoint_ramps_and_flags_fixed_pixels() -> None:
    frame, labels = build([[1, 2, 3]], {1: (28, 13, 8), 2: (120, 70, 45), 3: (28, 13, 8)})
    ramps = {"hair": PALETTE[[0]], "boots": PALETTE[[2]]}
    findings = check_ramp_shared(frame, labels, PARTS, ramps, "f.png", fix="x")
    assert [f.message.split(" at ")[0].split("a pixel of ")[-1] for f in findings] == ["fixed colours"]
    ok, ok_labels = build([[1, 2, 3]], {1: (28, 13, 8), 2: (120, 70, 45), 3: (235, 190, 160)})
    assert check_ramp_shared(ok, ok_labels, PARTS, ramps, "f.png", fix="x") == []


# A part whose colours the Project's ramp table gives (ticket 0168): mapped by lightness order, not by nearest colour.
GIVEN = np.array([[64, 32, 20], [120, 70, 45], [235, 190, 160]], dtype=np.uint8)  # dark to light


def shaded(shades: list[tuple[int, int, int]]) -> tuple[np.ndarray, np.ndarray]:
    """A 3-band toon-shaded skin (material 3, one band per shade, the lit band widest) beside a fixed jacket (material 5)."""
    return build(
        [[3, 3, 3, 3, 3, 3, 5], [3, 3, 3, 3, 3, 3, 5], [3, 3, 3, 3, 3, 3, 5], [3, 3, 3, 3, 3, 3, 5]],
        {3: shades[0], 5: (90, 90, 110)},
    )


def bands(frame: np.ndarray, shades: list[tuple[int, int, int]]) -> np.ndarray:
    """The skin painted in three vertical bands, dark on the left: 1, 2 and 3 columns wide."""
    out = frame.copy()
    for (x0, x1), shade in zip(((0, 1), (1, 3), (3, 6)), shades, strict=True):
        out[:, x0:x1, :3] = shade
    return out


@pytest.mark.parametrize(("texture", "golden"), [
    ([(150, 110, 90), (190, 150, 125), (250, 225, 205)], "lightness_lighter.png"),  # lighter than the given ramp's middle
    ([(30, 15, 10), (55, 32, 22), (85, 52, 36)], "lightness_darker.png"),  # darker: nearest would put it all on the dark step
])
def test_a_lighter_and_a_darker_texture_both_use_every_step_of_a_given_ramp(
        request: pytest.FixtureRequest, texture: list[tuple[int, int, int]], golden: str) -> None:
    frame, labels = shaded(texture)
    frame = bands(frame, texture)
    parts = {"skin": [SKIN]}

    breaks = lightness_breaks([frame], [labels], [SKIN], 3)
    mapped = quantize_by_part(frame, labels, parts, {"skin": GIVEN}, PALETTE[[5]], breaks={"skin": breaks})

    assert_golden(request, mapped, golden)
    skin = mapped[labels == SKIN][:, :3]
    assert {tuple(c) for c in skin.tolist()} == {tuple(c) for c in GIVEN.tolist()}
    assert mapped[0, 0, :3].tolist() == GIVEN[0].tolist() and mapped[0, 5, :3].tolist() == GIVEN[2].tolist()  # dark to dark
    assert {tuple(c) for c in mapped[labels == JACKET][:, :3].tolist()} == {(90, 90, 110)}


def test_lightness_breaks_spread_fewer_shades_than_steps_over_the_ramp_and_count_every_frame() -> None:
    frame, labels = shaded([(30, 15, 10)])
    lit = frame.copy()
    lit[..., :3] = np.where((labels == SKIN)[..., None], np.array([250, 225, 205], dtype=np.uint8), lit[..., :3])

    breaks = lightness_breaks([frame, lit], [labels, labels], [SKIN], 3)

    assert len(breaks) == 2
    dark = quantize_by_part(frame, labels, {"skin": [SKIN]}, {"skin": GIVEN}, PALETTE[[5]], breaks={"skin": breaks})
    light = quantize_by_part(lit, labels, {"skin": [SKIN]}, {"skin": GIVEN}, PALETTE[[5]], breaks={"skin": breaks})
    assert {tuple(c) for c in dark[labels == SKIN][:, :3].tolist()} == {tuple(GIVEN[0].tolist())}
    assert {tuple(c) for c in light[labels == SKIN][:, :3].tolist()} == {tuple(GIVEN[2].tolist())}
    with pytest.raises(ValueError, match="at least 1"):
        lightness_breaks([frame], [labels], [SKIN], 0)
