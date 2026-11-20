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
        return [{"index": i, "rect": _rect(i, row), "offset": {"x": 0, "y": 0}} for i in range(count)]

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


def wide() -> dict[str, object]:
    """`character()` with its `attack` clip on its own larger cell (24 x 20, pivot 12, 17): the body's clips are padded to it."""
    value = character()
    own = {"cell": {"width": 24, "height": 20}, "pivot": {"x": 12, "y": 17}}
    clips = [{**clip, **(own if clip["name"] == "attack" else {"cell": value["cell"], "pivot": value["pivot"]})}
             for clip in value["clips"]]  # type: ignore[attr-defined]
    for clip in clips:
        if clip["name"] == "attack":  # its frames fill its own cell
            for listed in clip["directions"].values():
                for frame in listed:
                    frame["rect"] = {**frame["rect"], "width": 24, "height": 20}
    return {**value, "clips": clips}


def trimmed() -> dict[str, object]:
    """`wide()` with every frame cut to its opaque box (ticket 0308): a smaller `rect` and the `offset` of the box in its clip's
    cell. One frame's box is its whole cell, which takes no margin when its clip's cell is the logical cell."""
    value = wide()
    for clip in value["clips"]:  # type: ignore[attr-defined]
        for listed in clip["directions"].values():
            for frame in listed:
                whole = clip["name"] == "attack" and frame["index"] == 2
                width, height = (24, 20) if whole else (10, 12)
                frame["rect"] = {**frame["rect"], "width": width, "height": height}
                frame["offset"] = {"x": 0, "y": 0} if whole else {"x": 3 + frame["index"], "y": 2}
    return value


def test_the_sprite_frames_of_a_clip_with_its_own_cell_pad_every_frame_to_one_logical_cell(request: pytest.FixtureRequest) -> None:
    assert_golden(request, character_frames(wide(), f"{BASE}/texture.tres"), "frames_wide.tres")


def test_the_sprite_frames_of_trimmed_frames_pad_each_back_to_the_logical_cell(request: pytest.FixtureRequest) -> None:
    assert_golden(request, character_frames(trimmed(), f"{BASE}/texture.tres"), "frames_trimmed.tres")


def test_the_scene_of_a_clip_with_its_own_cell_is_offset_by_the_logical_pivot(request: pytest.FixtureRequest) -> None:
    assert_golden(request, character_scene(wide(), "hero", f"{BASE}/frames.tres"), "hero_wide.tscn")


def test_the_canvas_texture(request: pytest.FixtureRequest) -> None:
    assert_golden(request, character_texture(f"{BASE}/color.png", f"{BASE}/normal.png"), "texture.tres")


def test_the_frozen_ids_are_each_clip_in_each_direction() -> None:
    ids = character_ids(character())

    assert ids.clips == ["attack_e", "attack_s", "idle_e", "idle_s"]
    assert ids.markers == ids.layers == ids.masks == []


def test_the_ramps_image_is_padded_to_the_longest_row_of_the_table_even_one_the_character_lacks() -> None:
    import io

    from PIL import Image

    from kiripix.export.character import ramp_rows, ramps_png

    character = {"parts": [{"name": "skin", "rgb": [[1, 2, 3], [4, 5, 6]]}],
                 "rows": [{"name": "skin", "length": 2}, {"name": "hair", "length": 4}]}
    rows = ramp_rows(character)
    image = Image.open(io.BytesIO(ramps_png(character, rows))).convert("RGBA")

    assert rows == ["skin", "hair"] and image.size == (4, 2)
    assert [list(image.getpixel((x, 0))) for x in range(4)] == [[1, 2, 3, 255], [4, 5, 6, 255], [0, 0, 0, 0], [0, 0, 0, 0]]
    assert [list(image.getpixel((x, 1))) for x in range(4)] == [[0, 0, 0, 0]] * 4
