"""init, new, describe, and the data files (`kiripix.toml`, `asset.toml`)."""

import tomllib
from pathlib import Path

from conftest import Kiripix


def test_init_creates_the_documented_layout(kpx: Kiripix) -> None:
    data = kpx.json("init")["data"]

    root = kpx.cwd
    for path in ["kiripix.toml", "style/palette.gpl", "style/bible.md", "style/refs", "style/prompts", "assets"]:
        assert (root / path).exists(), path
    assert "kiripix.toml" in data["created"]
    attributes = (root / ".gitattributes").read_text(encoding="utf-8")
    assert "*.png filter=lfs diff=lfs merge=lfs -text" in attributes
    assert "history.jsonl merge=union text eol=lf" in attributes
    assert "**/decisions/*.jsonl merge=union text eol=lf" in attributes
    ignored = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "work/" in ignored and ".kiripix/" in ignored


def test_init_writes_defaults_that_load(kpx: Kiripix) -> None:
    kpx.json("init")
    settings = tomllib.loads((kpx.cwd / "kiripix.toml").read_text(encoding="utf-8"))

    assert settings["schema_version"] == 1
    assert settings["project"]["tile"] == 16
    assert settings["project"]["palette"] == "style/palette.gpl"
    assert settings["body"]["size"] == [12, 8]
    assert set(settings["masks"]) == {"top", "side"}
    assert kpx.json("status")["ok"]


def test_init_into_a_named_folder(kpx: Kiripix) -> None:
    kpx.json("init", "my-game-assets")

    assert (kpx.cwd / "my-game-assets" / "kiripix.toml").is_file()


def test_init_refuses_an_existing_project(project: Kiripix) -> None:
    (project.cwd / "kiripix.toml").write_text('schema_version = 1\n[project]\nname = "mine"\n', encoding="utf-8")

    result = project.json("init", expect=1)

    assert [f["code"] for f in result["findings"]] == ["project.exists"]
    assert 'name = "mine"' in (project.cwd / "kiripix.toml").read_text(encoding="utf-8")


def test_init_keeps_an_existing_gitignore(kpx: Kiripix) -> None:
    (kpx.cwd / ".gitignore").write_text("node_modules/\n", encoding="utf-8")

    kpx.json("init")

    lines = (kpx.cwd / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "node_modules/" and "work/" in lines


def test_commands_outside_a_project_point_to_init(kpx: Kiripix) -> None:
    result = kpx.json("status", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "project.not_found"
    assert finding["fix"] == "kiripix init"


# kiripix.toml


def write_settings(project: Kiripix, text: str) -> Path:
    path = project.cwd / "kiripix.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_an_invalid_setting_names_the_field_and_the_fix(project: Kiripix) -> None:
    write_settings(project, 'schema_version = 1\n[project]\nname = "x"\n[body]\nsize = "big"\n')

    result = project.json("status", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "config.invalid"
    assert finding["position"]["field"] == "body.size"
    assert finding["position"]["file"] == "kiripix.toml"
    assert finding["fix"] is None and "body.size" in finding["owner_action"]


def test_an_unknown_key_is_an_error(project: Kiripix) -> None:
    write_settings(project, 'schema_version = 1\n[project]\nname = "x"\ntiles = 8\n')

    result = project.json("status", expect=1)

    assert result["findings"][0]["code"] == "config.unknown_key"
    assert result["findings"][0]["position"]["field"] == "project.tiles"


def test_malformed_toml_is_reported(project: Kiripix) -> None:
    write_settings(project, "[project\nname = 'x'\n")

    assert project.json("status", expect=1)["findings"][0]["code"] == "config.syntax"


def test_an_old_file_is_migrated_in_memory_and_not_rewritten(project: Kiripix) -> None:
    # Version 0: the spec §4 example, written before schema versions.
    text = '[project]\nname = "toronto-rpg"\nresolution = [480, 270]\ntile = 16\npalette = "style/palette.gpl"\n'
    path = write_settings(project, text)

    data = project.json("status")["data"]

    assert data["project"] == "toronto-rpg"
    assert path.read_text(encoding="utf-8") == text


def test_a_newer_file_is_refused(project: Kiripix) -> None:
    write_settings(project, 'schema_version = 99\n[project]\nname = "x"\n')

    finding = project.json("status", expect=1)["findings"][0]

    assert finding["code"] == "config.newer_version"
    assert finding["owner_action"]


def test_an_invalid_mask_definition_is_reported(project: Kiripix) -> None:
    write_settings(project, 'schema_version = 1\n[project]\nname = "x"\n[masks.top]\nsolid = { colour = "red" }\n')

    finding = project.json("status", expect=1)["findings"][0]

    assert finding["code"] == "config.invalid"
    assert finding["position"]["field"].startswith("masks.top")


# new


def test_new_creates_the_asset(project: Kiripix) -> None:
    data = project.json("new", "room", "queen_west_alley", "--view", "top")["data"]

    assert data["asset"] == "room.queen_west_alley"
    folder = project.cwd / "assets" / "room" / "queen_west_alley"
    assert (folder / "history.jsonl").read_bytes() == b""
    assert (folder / "decisions").is_dir()
    settings = tomllib.loads((folder / "asset.toml").read_text(encoding="utf-8"))
    assert settings == {"schema_version": 1, "kind": "room", "params": {"view": "top"}, "stages": {}}


def test_new_accepts_the_full_id(project: Kiripix) -> None:
    assert project.json("new", "prop", "prop.ttc_bench")["data"]["asset"] == "prop.ttc_bench"


def test_new_refuses_a_bad_name(project: Kiripix) -> None:
    result = project.json("new", "prop", "TTC Bench", expect=1)

    assert result["findings"][0]["code"] == "asset.invalid_id"
    assert result["findings"][0]["fix"] == "kiripix new prop ttc_bench"
    assert not (project.cwd / "assets" / "prop").exists()


def test_new_refuses_a_duplicate(project: Kiripix) -> None:
    project.json("new", "prop", "bench")

    assert project.json("new", "prop", "bench", expect=1)["findings"][0]["code"] == "asset.duplicate_id"


def test_new_refuses_an_unknown_kind_and_lists_the_kinds(project: Kiripix) -> None:
    finding = project.json("new", "dragon", "x", expect=1)["findings"][0]

    assert finding["code"] == "kind.unknown"
    assert all(kind in finding["message"] for kind in ["room", "prop", "character"])


def test_a_room_needs_a_view(project: Kiripix) -> None:
    finding = project.json("new", "room", "alley", expect=1)["findings"][0]

    assert finding["code"] == "asset.param_required"
    assert finding["fix"] == "kiripix new room alley --view top"


def test_a_view_is_refused_for_a_prop(project: Kiripix) -> None:
    assert project.json("new", "prop", "bench", "--view", "top", expect=1)["findings"][0]["code"] == \
        "asset.param_unknown"


def test_a_bad_view_is_refused(project: Kiripix) -> None:
    assert project.json("new", "room", "alley", "--view", "diagonal", expect=1)["findings"][0]["code"] == \
        "asset.param_invalid"


# describe


def test_describe_project_lists_the_kinds_and_recipes(kpx: Kiripix) -> None:
    kinds = {k["name"]: k["recipe"] for k in kpx.json("describe", "project", test_recipes=False)["data"]["kinds"]}

    assert kinds == {
        "room": ["brief", "source", "fit", "layers", "masks", "palette", "place", "reach", "export"],
        "prop": ["brief", "source", "cutout", "fit", "palette", "finish", "footprint", "export"],
        "character": ["model", "rig", "clips", "render", "palette", "finish", "sheet", "export"],
    }


def test_describe_a_kind_gives_parameters_decisions_and_checks(kpx: Kiripix) -> None:
    room = kpx.json("describe", "room")["data"]["kinds"][0]

    assert room["params"][0]["name"] == "view" and room["params"][0]["required"]
    stages = {s["name"]: s for s in room["stages"]}
    palette = stages["palette"]
    assert {p["name"]: p["default"] for p in palette["params"]} == {"dither": "none", "strength": 1.0,
                                                                     "orphan_size": 1}
    assert palette["params"][1]["minimum"] == 0 and palette["params"][1]["maximum"] == 1
    assert "palette.off_palette" in [c["code"] for c in palette["checks"]]
    assert stages["source"]["decisions"][0]["name"] == "pick"
    assert stages["source"]["decisions"][0]["entry_schema"]["required"] == ["variant"]
    assert not palette["implemented"] and palette["available_from"] == "M1"


def test_describe_an_unknown_kind(kpx: Kiripix) -> None:
    assert kpx.json("describe", "dragon", expect=1)["findings"][0]["code"] == "kind.unknown"
