"""Golden tests for the sound contact-sheet drawing Ops (ticket 0396): a fixed synthetic signal, drawn as a waveform and a
log-frequency spectrogram with a boxed span, compared pixel-exactly with a PNG. `--update-golden` rewrites it."""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.ops.sound_sheet import draw_box, draw_column, span_columns, spectrogram_image, waveform_image

EXPECTED = Path(__file__).parent / "expected"
RATE = 8000


def signal() -> np.ndarray:
    """0.25 s: a 500 Hz tone that decays, then a 2 kHz tone that starts at half time, and one full-scale click."""
    t = np.arange(RATE // 4) / RATE
    tone = 0.6 * np.sin(2 * np.pi * 500 * t) * np.exp(-t * 18)
    tone[len(t) // 2:] += 0.3 * np.sin(2 * np.pi * 2000 * t[len(t) // 2:]) * np.exp(-(t[len(t) // 2:] - t[len(t) // 2]) * 30)
    tone[1500] = 1.0
    return tone.astype(np.float32)


def assert_golden(request: pytest.FixtureRequest, actual: np.ndarray, name: str) -> None:
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        EXPECTED.mkdir(exist_ok=True)
        Image.fromarray(actual, "RGB").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGB"), dtype=np.uint8)
    assert actual.shape == expected.shape
    different = np.argwhere((actual != expected).any(axis=2))
    assert len(different) == 0, f"{len(different)} pixels differ from {name}, the first at (y, x) {different[0]}"


def test_a_waveform_and_a_spectrogram_with_a_boxed_span(request: pytest.FixtureRequest) -> None:
    samples = signal()
    width, height = 120, 40
    wave = waveform_image(samples, width, height)
    left, span = span_columns(500, 1200, len(samples), width)
    wave = draw_box(wave, left, 0, left + span - 1, height - 1, (90, 230, 110), 2)
    wave = draw_column(wave, 60, (255, 80, 220))
    spectrogram = spectrogram_image(samples, RATE, width, height)
    sheet = np.concatenate([wave, np.zeros((2, width, 3), dtype=np.uint8), spectrogram])

    assert_golden(request, sheet, "sound_sheet_drawing.png")


def test_the_drawing_is_the_same_each_time() -> None:
    samples = signal()
    assert np.array_equal(spectrogram_image(samples, RATE, 50, 20), spectrogram_image(samples, RATE, 50, 20))
    assert np.array_equal(waveform_image(samples, 50, 20), waveform_image(samples, 50, 20))


def test_a_span_maps_to_columns_and_is_at_least_one_wide() -> None:
    assert span_columns(0, 1000, 4000, 100) == (0, 25)
    assert span_columns(1000, 1001, 4000, 100) == (25, 1)
    assert span_columns(3999, 4000, 4000, 100)[0] == 99


def test_a_louder_waveform_is_taller_and_a_full_scale_column_is_red() -> None:
    quiet = waveform_image(np.full(100, 0.1, dtype=np.float32), 10, 41)
    loud = waveform_image(np.where(np.arange(100) % 2 == 0, 1.0, -1.0).astype(np.float32), 10, 41)
    background = waveform_image(np.zeros(0, dtype=np.float32), 10, 41)

    def painted(image: np.ndarray) -> int:
        return int((image[:, 5] != background[:, 5]).any(axis=1).sum())

    assert painted(loud) > painted(quiet)
    assert (loud[:, 5] == (255, 70, 70)).all(axis=1).any()
    assert not (quiet[:, 5] == (255, 70, 70)).all(axis=1).any()


def test_a_box_is_drawn_inside_its_bounds_and_clipped() -> None:
    image = np.zeros((6, 8, 3), dtype=np.uint8)
    boxed = draw_box(image, 2, 1, 5, 4, (9, 9, 9))
    assert int((boxed != 0).any(axis=2).sum()) == 12 and not image.any()
    assert draw_box(image, -3, -3, 20, 20, (1, 1, 1))[0, 0].tolist() == [1, 1, 1]  # clipped to the picture, not dropped
