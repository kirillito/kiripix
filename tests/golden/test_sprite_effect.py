"""Golden test for a sprite effect's cell and pivot (ticket 0362): the `fit` Stage, called directly on a made-up 12 x 12 spark with
`anchor=centre` and `effect=true`. The cell is the frame's own size plus the 1 px `finish` keeps for an outline, and the pivot is
the frame's centre (one px further in). The golden is the cell, enlarged, with the pivot's pixel drawn in magenta."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from kiripix.recipes.base import StageRun
from kiripix.recipes.sprite_fit import run_sprite_fit

EXPECTED = Path(__file__).parent / "expected"
SCALE = 12
SIZE = 12


def spark(arm: int) -> np.ndarray:
    frame = np.zeros((SIZE, SIZE, 4), dtype=np.uint8)
    frame[SIZE // 2 - arm:SIZE // 2 + arm, SIZE // 2 - 1:SIZE // 2] = (240, 220, 80, 255)
    frame[SIZE // 2 - 1:SIZE // 2, SIZE // 2 - arm:SIZE // 2 + arm] = (240, 220, 80, 255)
    return frame


def build(tmp_path: Path, params: dict[str, object]) -> tuple[Path, dict[str, object]]:
    frames, out = tmp_path / "frames", tmp_path / "out"
    listed = []
    for index, arm in enumerate((2, 4, 5)):
        name = f"color/boom/s/{index:03d}.png"
        (frames / name).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(spark(arm), "RGBA").save(frames / name)
        listed.append({"index": index, "file": name, "sheet": "x", "source": "x"})
    document = {"schema_version": 1, "directions": ["s"], "sheets": ["x"], "unplaced": [], "duplicates": [],
                "clips": [{"name": "boom", "fps": 8, "loop": False, "stationary": False, "raw": ["boom"],
                           "directions": {"s": listed}}]}
    (frames / "frames.json").write_text(json.dumps(document), encoding="utf-8")
    out.mkdir()
    run_sprite_fit(StageRun(asset_id="sprite.boom", asset_dir=tmp_path, output_dir=out, files={}, upstream={"frames": frames},
                            params=params, settings={"character.height": 52}, progress=lambda done, total, message: None))
    return out, json.loads((out / "render.json").read_text(encoding="utf-8"))


def test_a_centred_effect_cell_is_its_frame_plus_a_spare_pixel_around_the_centre(
        request: pytest.FixtureRequest, tmp_path: Path) -> None:
    out, render = build(tmp_path, {"anchor": "centre", "effect": True})

    assert render["frame"] == {"width": SIZE + 2, "height": SIZE + 2} and render["pivot"] == [SIZE / 2 + 1, SIZE / 2 + 1]
    assert render["effect"] is True
    cell = np.asarray(Image.open(out / "color" / "boom" / "s" / "002.png").convert("RGBA"), dtype=np.uint8).copy()
    px, py = int(render["pivot"][0]), int(render["pivot"][1])
    big = np.kron(cell, np.ones((SCALE, SCALE, 1), dtype=np.uint8))
    big[py * SCALE:(py + 1) * SCALE, px * SCALE:(px + 1) * SCALE][::4, ::4] = (255, 0, 255, 255)  # the pivot, as dots
    path = EXPECTED / "sprite_effect_cell_pivot.png"
    if request.config.getoption("--update-golden"):
        Image.fromarray(big, "RGBA").save(path)
    with Image.open(path) as image:
        expected = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    assert big.shape == expected.shape and (big == expected).all()


def test_a_feet_anchor_keeps_the_box_cell(tmp_path: Path) -> None:
    _, render = build(tmp_path, {})

    assert "effect" not in render
    assert render["frame"]["width"] < SIZE + 2  # the box of the biggest spark, not the frame
