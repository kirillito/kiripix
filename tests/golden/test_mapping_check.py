"""The mapping-error Op and its Check, called directly."""

import numpy as np

from kiripix.checks import check_mapping_error
from kiripix.ops import mapping_error


def solid(rgb: tuple[int, int, int], alpha: int = 255) -> np.ndarray:
    image = np.zeros((2, 2, 4), dtype=np.uint8)
    image[..., :3], image[..., 3] = rgb, alpha
    return image


def test_mapping_error_is_the_mean_oklab_distance_over_opaque_pixels() -> None:
    assert mapping_error(solid((10, 20, 30)), solid((10, 20, 30))) == 0.0
    assert mapping_error(solid((0, 0, 0)), solid((255, 255, 255))) > 0.9
    assert mapping_error(solid((0, 0, 0), 0), solid((255, 255, 255))) == 0.0  # no pixel is opaque in both


def test_a_high_error_is_a_warning_with_a_fix_and_a_low_one_is_not() -> None:
    assert check_mapping_error(0.01, "palette.png", fix="kiripix op palette-suggest x") == []
    (finding,) = check_mapping_error(0.02, "palette.png", fix="kiripix op palette-suggest x")
    assert (finding.code, finding.severity, finding.fix) == ("palette.mapping_error", "warning",
                                                            "kiripix op palette-suggest x")
