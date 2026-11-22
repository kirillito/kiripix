"""The Project check `style.light_angle_differs` (ticket 0361, spec §6.3): every character is lit from the Project's most common
`light_angle`, read from its `render` camera preset. A setting, so no Blender is needed."""

import shlex
from typing import Any

from conftest import Kiripix

CODE = "style.light_angle_differs"


def presets(project: Kiripix, *angles: tuple[str, float]) -> None:
    path = project.cwd / "kiripix.toml"
    extra = "".join(f"\n[character.camera.{name}]\nlight_angle = {angle}\n" for name, angle in angles)
    path.write_text(path.read_text("utf-8") + extra, encoding="utf-8")


def character(project: Kiripix, name: str, camera: str | None = None) -> str:
    project.json("new", "character", name)
    if camera:
        project.json("set", f"character.{name}", "render", f"camera={camera}")
    return f"character.{name}"


def found(result: dict[str, Any]) -> list[dict[str, Any]]:
    return [f for f in result["findings"] if f["code"] == CODE]


def test_characters_lit_the_same_raise_nothing(project: Kiripix) -> None:
    presets(project, ("left", -45))
    character(project, "a")
    character(project, "b", "left")

    assert found(project.json("check", "--all")) == []


def test_a_third_with_another_angle_is_named_with_the_fix(project: Kiripix) -> None:
    presets(project, ("right", 60))
    character(project, "a")
    character(project, "b")
    odd = character(project, "c", "right")

    result = project.json("check", "--all")

    [finding] = found(result)
    assert finding["severity"] == "warning" and finding["position"]["asset"] == odd
    assert finding["owner_action"] is None and "light_angle 60" in finding["message"]
    command = shlex.split(finding["fix"])
    assert command == ["kiripix", "set", odd, "render", "camera=top34_8"]
    project.json(*command[1:])
    assert found(project.json("check", "--all")) == []


def test_no_majority_is_an_owner_action_on_each_character(project: Kiripix) -> None:
    presets(project, ("right", 60))
    character(project, "a")
    character(project, "b", "right")

    result = project.json("check", "--all")

    assert sorted(f["position"]["asset"] for f in found(result)) == ["character.a", "character.b"]
    assert all(f["fix"] is None and f["owner_action"] for f in found(result))


def test_a_wearable_is_named_in_its_bodys_finding_not_on_its_own(project: Kiripix) -> None:
    presets(project, ("right", 60))
    character(project, "a")
    character(project, "b")
    odd = character(project, "c", "right")
    project.json("new", "wearable", "hat", "--body", odd)

    [finding] = found(project.json("check", "--all"))

    assert finding["position"]["asset"] == odd and "wearable.hat" in finding["message"]


def test_export_all_carries_the_warning_and_still_exports(project: Kiripix) -> None:
    """`export --all` runs the check as a warning: nothing is refused for it. `--match` keeps only what names a matched
    Asset, so the unbuilt odd one stays out of the export and its own finding is left out, while the hero's is kept."""
    from test_character_model import HERO
    from test_export_character import exportable_character

    presets(project, ("right", 60))  # first: a camera preset added later makes the built render stale
    exportable_character(project)
    character(project, "odd", "right")  # one each way: no majority, so each character is named with an owner_action

    result = project.json("export", "--all", "--match", HERO)  # exit 0: a warning

    assert result["ok"] and [f["position"]["asset"] for f in found(result)] == [HERO]
    [finding] = found(result)
    assert finding["severity"] == "warning" and finding["owner_action"]
