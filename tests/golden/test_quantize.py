"""Golden tests for the palette and quantise Ops: fixed inputs and palettes, expected PNGs compared pixel-exactly.

The Ops are pure functions, so this seam calls them directly. `--update-golden` rewrites the expected images; review
them by eye before committing.
"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.checks import check_palette
from kiripix.ops import conformance, nearest_index, parse_gpl, parse_hex, quantize

HERE = Path(__file__).parent
INPUTS = HERE / "inputs"
EXPECTED = HERE / "expected"


def load(path: Path) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("RGBA"), dtype=np.uint8)


def palette_rgb() -> np.ndarray:
    return parse_gpl((INPUTS / "palette.gpl").read_text(encoding="utf-8")).rgb()


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        EXPECTED.mkdir(exist_ok=True)
        Image.fromarray(actual, "RGBA").save(path)
    expected = load(path)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


@pytest.mark.parametrize(("dither", "name"), [(0, "strict.png"), (2, "bayer2.png"), (4, "bayer4.png"),
                                              (8, "bayer8.png")])
def test_quantize_gradient(request: pytest.FixtureRequest, dither: int, name: str) -> None:
    result = quantize(load(INPUTS / "gradient.png"), palette_rgb(), dither)  # type: ignore[arg-type]

    assert_golden(request, result, name)
    assert conformance(result, palette_rgb()).off_palette == 0


def test_dithering_differs_from_strict() -> None:
    image, palette = load(INPUTS / "gradient.png"), palette_rgb()

    assert (quantize(image, palette, 4) != quantize(image, palette, 0)).any()
    assert (quantize(image, palette, 4, strength=0.0) == quantize(image, palette, 0)).all()


def test_transparent_pixels_stay_transparent(request: pytest.FixtureRequest) -> None:
    image = load(INPUTS / "transparent.png")

    result = quantize(image, palette_rgb(), 0)

    assert_golden(request, result, "transparent.png")
    clear = image[..., 3] == 0
    assert (result[clear] == 0).all()
    assert (result[~clear][:, 3] == 255).all()


def test_partial_alpha_is_refused() -> None:
    image = load(INPUTS / "partial_alpha.png")

    report = conformance(image, palette_rgb())
    assert report.partial_alpha == 1 and report.first_partial_alpha == [(7, 5)]
    with pytest.raises(ValueError, match="partially transparent"):
        quantize(image, palette_rgb(), 0)


def test_an_image_on_the_palette_is_unchanged() -> None:
    palette = palette_rgb()
    image = np.full((4, len(palette), 4), 255, dtype=np.uint8)
    image[..., :3] = palette[None, :, :]

    assert (quantize(image, palette, 0) == image).all()
    assert conformance(image, palette).off_palette == 0


def test_ties_go_to_the_earlier_palette_colour() -> None:
    colour = np.array([[0.5, 0.0, 0.0]])
    darker, lighter = [0.4, 0.0, 0.0], [0.6, 0.0, 0.0]

    assert nearest_index(colour, np.array([darker, lighter]))[0] == 0
    assert nearest_index(colour, np.array([lighter, darker]))[0] == 0


def test_a_palette_with_duplicates_fails_its_check() -> None:
    palette = parse_gpl((INPUTS / "duplicates.gpl").read_text(encoding="utf-8"))

    findings = check_palette(palette, "duplicates.gpl")

    assert [f.code for f in findings] == ["palette.duplicate_colour"]
    assert findings[0].position is not None and findings[0].position.line == 6


def test_palette_alpha_and_empty_fail_their_checks() -> None:
    assert [f.code for f in check_palette(parse_hex("FF0000\n00FF0080\n"), "p.hex")] == ["palette.alpha"]
    assert [f.code for f in check_palette(parse_hex(""), "p.hex")] == ["palette.empty"]


def test_hex_import_matches_gpl() -> None:
    gpl = parse_gpl((INPUTS / "palette.gpl").read_text(encoding="utf-8"))
    hex_text = "\n".join(e.hex for e in gpl.entries)

    assert (parse_hex(hex_text).rgb() == gpl.rgb()).all()
