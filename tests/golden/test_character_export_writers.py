"""Golden text files for the character's Godot writers (ticket 0113): the scene, the `SpriteFrames` and the `CanvasTexture`
from a small fixed `character.json`. Byte-compared, so a change to the output shows in the game repo's diffs only when it
is real. `uv run pytest tests/golden --update-golden` rewrites them; review the diff before committing."""

from pathlib import Path

import pytest

from kiripix.export.godot import character_frames, character_ids, character_scene, character_texture

EXPECTED = Path(__file__).parent / "expected" / "character_export"
BASE = "res://kiripix/character/hero"


def _rect(column: int, row: int) -> dict[str, int]:
    return {"x": column * 16, "y": row * 16, "width": 16, "height": 16}


def character() -> dict[str, object]:
    def frames(row: int, count: int) -> list[dict[str, object]]:
        return [{"index": i, "rect": _rect(i, row)} for i in range(count)]

    return {
        "schema_version": 1, "asset": "character.hero", "files": {"color": "color.png", "normal": "normal.png"},
        "cell": {"width": 16, "height": 16}, "pivot": {"x": 8, "y": 14}, "atlas": {"width": 48, "height": 64},
        "directions": ["s", "e"],
        "clips": [
            {"name": "attack", "fps": 10, "loop": False, "stationary": False,
             "directions": {"s": frames(0, 3), "e": frames(1, 3)}},
            {"name": "idle", "fps": 12, "loop": True, "stationary": True,
             "directions": {"s": frames(2, 1), "e": frames(3, 1)}},
        ],
    }


def assert_golden(request: pytest.FixtureRequest, actual: str, name: str) -> None:
    assert "\r" not in actual and actual.endswith("\n")
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        path.write_bytes(actual.encode("utf-8"))
    assert actual == path.read_bytes().decode("utf-8")


def test_the_scene(request: pytest.FixtureRequest) -> None:
    assert_golden(request, character_scene(character(), "hero", f"{BASE}/frames.tres"), "hero.tscn")


def test_the_scene_with_ramps_names_them_and_the_parts_in_row_order(request: pytest.FixtureRequest) -> None:
    text = character_scene(character(), "hero", f"{BASE}/frames.tres", f"{BASE}/ramps.png", ["skin", "hair"])
    assert_golden(request, text, "hero_ramps.tscn")


def test_the_ramps_image_pads_rows_and_leaves_a_part_the_character_lacks_transparent() -> None:
    import io

    from PIL import Image

    from kiripix.export.character import ramps_png

    parts = [{"name": "skin", "rgb": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]}, {"name": "hair", "rgb": [[10, 11, 12]]}]
    data = ramps_png({"parts": parts}, ["hair", "eyes", "skin"])
    image = Image.open(io.BytesIO(data)).convert("RGBA")

    assert image.size == (3, 3)
    assert [list(image.getpixel((x, 0))) for x in range(3)] == [[10, 11, 12, 255], [0, 0, 0, 0], [0, 0, 0, 0]]
    assert [list(image.getpixel((x, 1))) for x in range(3)] == [[0, 0, 0, 0]] * 3
    assert [list(image.getpixel((x, 2))) for x in range(3)] == [[1, 2, 3, 255], [4, 5, 6, 255], [7, 8, 9, 255]]
    assert ramps_png({"parts": parts}, ["hair", "eyes", "skin"]) == data


def test_the_sprite_frames(request: pytest.FixtureRequest) -> None:
    assert_golden(request, character_frames(character(), f"{BASE}/texture.tres"), "frames.tres")


def test_the_canvas_texture(request: pytest.FixtureRequest) -> None:
    assert_golden(request, character_texture(f"{BASE}/color.png", f"{BASE}/normal.png"), "texture.tres")


def test_the_frozen_ids_are_each_clip_in_each_direction() -> None:
    ids = character_ids(character())

    assert ids.clips == ["attack_e", "attack_s", "idle_e", "idle_s"]
    assert ids.markers == ids.layers == ids.masks == []
