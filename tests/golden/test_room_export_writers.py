"""Golden text files for the room's Godot scene writer (ticket 0316): the scene from a small fixed `room.json` dict, a room with
no Look and one whose Looks change `solid`, add a light and navigate. Byte-compared, so a change to the output shows in the game
repo's diffs only when it is real. `uv run pytest tests/golden --update-golden` rewrites them; review the diff before committing."""

from pathlib import Path
from typing import Any

import pytest

from kiripix.export.godot import room_ids, room_scene

EXPECTED = Path(__file__).parent / "expected" / "room_export"
BASE = "res://kiripix/room/yard"


def _square(x: int, y: int, size: int = 16) -> list[list[int]]:
    return [[x, y], [x + size, y], [x + size, y + size], [x, y + size]]


def _navigation(x: int) -> dict[str, Any]:
    return {"vertices": [[x, 0], [x + 16, 0], [x + 16, 16], [x, 16]], "polygons": [[0, 1, 2, 3]],
            "outlines": [[[x, 0], [x + 16, 0], [x + 16, 16], [x, 16]]]}


def _light(marker_id: str, x: int) -> dict[str, Any]:
    return {"id": marker_id, "type": "light", "x": x, "y": 8, "radius": 24.0, "colour": "#ffcc88", "energy": 1.5}


def room() -> dict[str, Any]:
    return {
        "schema_version": 12, "asset": "room.yard", "size": [64, 32],
        "collision": {"pit": [], "solid": [_square(0, 0), _square(16, 0)]},
        "navigation": _navigation(32),
        "markers": [{"id": "spawn.main", "type": "spawn", "x": 40, "y": 8}, _light("lamp", 4)],
        "links": [], "layers": [], "masks": {"solid": "masks/solid.png"}, "loops": [],
        "looks": [],
        "scene": {"solid": [_square(0, 0), _square(16, 0)], "cleared": {}, "shared": []},
    }


def with_looks() -> dict[str, Any]:
    def look(name: str, shapes_added: list[Any], cleared: list[Any], markers: list[Any]) -> dict[str, Any]:
        return {
            "id": name, "condition": None, "file": None, "box": None, "pieces": [], "markers": markers,
            "solid": f"masks/{name}.solid.png", "collision": {"solid": []}, "navigation": _navigation(48),
            "added": {"file": f"masks/{name}.added.png", "collision": shapes_added},
            "cleared": {"file": f"masks/{name}.cleared.png", "collision": cleared},
        }

    built = room()
    built["looks"] = [
        look("gate_open", [], [_square(0, 0), _square(16, 0)], [_light("gate.glow", 20)]),
        look("gate_wide", [_square(48, 16)], [_square(16, 0)], []),
    ]
    built["scene"] = {"solid": [], "cleared": {"gate_open": [_square(0, 0)], "gate_wide": []},
                      "shared": [{"looks": ["gate_open", "gate_wide"], "collision": [_square(16, 0)]}]}
    return built


def assert_golden(request: pytest.FixtureRequest, actual: str, name: str) -> None:
    assert "\r" not in actual and actual.endswith("\n")
    path = EXPECTED / name
    if request.config.getoption("--update-golden"):
        path.write_bytes(actual.encode("utf-8"))
    assert actual == path.read_bytes().decode("utf-8")


def test_a_room_with_no_look_collides_as_before(request: pytest.FixtureRequest) -> None:
    text = room_scene(room(), "yard", f"{BASE}/plate.png", f"{BASE}/room.json")
    assert "LookSolids" not in text and "LookNavigation" not in text and "LookMarkers" not in text
    assert_golden(request, text, "yard.tscn")


def test_a_room_with_looks_that_clear_solid(request: pytest.FixtureRequest) -> None:
    text = room_scene(with_looks(), "yard", f"{BASE}/plate.png", f"{BASE}/room.json")
    assert_golden(request, text, "yard_looks.tscn")


def test_the_manifest_ids_name_a_looks_markers_under_the_look() -> None:
    ids = room_ids(with_looks())
    assert ids.markers == ["lamp", "spawn.main"] and ids.look_markers == ["gate_open/gate.glow"]
