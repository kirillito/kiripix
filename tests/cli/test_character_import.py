"""Importing for a character: Models as Variants, animation files, the rigged file, and the [character] settings."""

import shutil
from pathlib import Path

from PIL import Image

from conftest import Kiripix

FIXTURES = Path(__file__).parent.parent / "fixtures" / "characters"
HERO = "character.hero"


def hero(project: Kiripix, *files: str) -> Path:
    project.json("new", "character", "hero")
    for name in files:
        shutil.copy(FIXTURES / name, project.cwd / name)
    return project.cwd / "assets" / "character" / "hero"


def model_hash(project: Kiripix) -> str:
    result = project("run", HERO, "model", "--json").json
    return str(result["data"]["results"][0]["input_hash"])


def first_variant(project: Kiripix) -> str:
    return str(project.json("show", HERO)["data"]["variants"][0]["name"])


def test_a_glb_imports_as_a_variant_and_is_picked(project: Kiripix) -> None:
    folder = hero(project, "rigged.glb", "no_rig.glb")

    data = project.json("import", HERO, "rigged.glb")["data"]
    again = project.json("import", HERO, "rigged.glb")["data"]
    other = project.json("import", HERO, "no_rig.glb")["data"]

    name = data["variant"]
    assert data["role"] == "variant" and data["created"] and not again["created"]
    assert data["file"] == f"assets/character/hero/src/{name}.glb"
    assert (folder / "src" / f"{name}.glb").read_bytes() == (FIXTURES / "rigged.glb").read_bytes()
    assert other["variants"] == sorted([name, other["variant"]])

    before = model_hash(project)
    project.json("pick", HERO, name)
    picked = model_hash(project)
    project.json("pick", HERO, other["variant"])
    assert len({before, picked, model_hash(project)}) == 3


def test_an_fbx_and_a_blend_import_as_variants(project: Kiripix) -> None:
    hero(project, "rigged.fbx")
    (project.cwd / "model.blend").write_bytes(b"BLENDER-v500 pretend")

    fbx = project.json("import", HERO, "rigged.fbx")["data"]
    blend = project.json("import", HERO, "model.blend")["data"]

    assert fbx["file"].endswith(".fbx") and blend["file"].endswith(".blend")
    shown = project.json("show", HERO)["data"]["variants"]
    assert {v["name"] for v in shown} == {fbx["variant"], blend["variant"]}


def test_an_image_on_a_character_is_refused_with_a_fix(project: Kiripix) -> None:
    hero(project)
    Image.new("RGBA", (4, 4), (255, 0, 77, 255)).save(project.cwd / "in.png")

    finding = project.json("import", HERO, "in.png", expect=1)["findings"][0]

    assert finding["code"] == "import.image_needs_room_or_prop"
    assert "character" in finding["message"] and finding["fix"] == "kiripix new prop hero"
    assert not list((project.cwd / "assets" / "character" / "hero" / "src").glob("*.png"))


def test_a_model_on_a_room_or_prop_is_refused_with_a_fix(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("new", "prop", "bench")
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "rigged.glb")

    room = project.json("import", "room.alley", "rigged.glb", expect=1)["findings"][0]
    prop = project.json("import", "prop.bench", "rigged.glb", expect=1)["findings"][0]

    assert room["code"] == prop["code"] == "import.model_needs_character"
    assert room["fix"] == "kiripix new character alley" and prop["fix"] == "kiripix new character bench"


def test_a_role_other_than_variant_is_for_a_character(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    shutil.copy(FIXTURES / "rigged.fbx", project.cwd / "rigged.fbx")

    finding = project.json("import", "prop.bench", "rigged.fbx", "--role", "rigged", expect=1)["findings"][0]

    assert finding["code"] == "import.role_needs_character" and finding["fix"]


def test_a_file_that_is_not_a_model_is_refused(project: Kiripix) -> None:
    hero(project)
    (project.cwd / "notes.txt").write_text("hello", encoding="utf-8")

    finding = project.json("import", HERO, "notes.txt", expect=1)["findings"][0]

    assert finding["code"] == "import.not_a_model" and finding["owner_action"] and finding["fix"] is None
    assert project.json("import", HERO, "missing.glb", expect=1)["findings"][0]["code"] == "import.not_found"


def test_clip_sources_and_the_rigged_file_are_added_and_shown(project: Kiripix) -> None:
    folder = hero(project, "rigged.fbx", "no_rig.fbx")
    shutil.copy(FIXTURES / "no_rig.fbx", project.cwd / "Standing Idle.fbx")

    walk = project.json("import", HERO, "rigged.fbx", "--role", "clip-source")["data"]
    idle = project.json("import", HERO, "Standing Idle.fbx", "--role", "clip-source")["data"]
    again = project.json("import", HERO, "Standing Idle.fbx", "--role", "clip-source")["data"]
    rigged = project.json("import", HERO, "rigged.fbx", "--role", "rigged")["data"]

    assert walk["clip_source"] == "rigged" and idle["clip_source"] == "Standing Idle" and not again["created"]
    assert idle["clip_sources"] == ["Standing Idle", "rigged"]
    assert rigged["rigged"] and rigged["role"] == "rigged" and rigged["variants"] == []
    assert (folder / rigged["file"].removeprefix("assets/character/hero/")).is_file()

    shown = project.json("show", HERO)["data"]
    assert [c["name"] for c in shown["clip_sources"]] == ["Standing Idle", "rigged"]
    assert shown["rigged"]["file"] == rigged["file"] and shown["variants"] == []
    assert "clip source Standing Idle" in project("show", HERO).stdout


def test_a_clip_source_with_new_content_replaces_the_old(project: Kiripix) -> None:
    hero(project, "rigged.fbx", "no_rig.fbx")
    project.json("import", HERO, "rigged.fbx", "--role", "clip-source")
    (project.cwd / "rigged.fbx").write_bytes((FIXTURES / "no_rig.fbx").read_bytes())

    changed = project.json("import", HERO, "rigged.fbx", "--role", "clip-source")["data"]

    assert changed["created"] and changed["clip_sources"] == ["rigged"]
    assert len(list((project.cwd / "assets/character/hero/src/clips").glob("*.fbx"))) == 1
    project.json("import", HERO, "no_rig.fbx", "--role", "rigged")
    project.json("import", HERO, "rigged.fbx", "--role", "rigged")
    assert len(list((project.cwd / "assets/character/hero/src/rigged").glob("*"))) == 1


def test_next_and_describe_say_what_to_import(project: Kiripix) -> None:
    hero(project, "rigged.glb")

    first = project.json("next", HERO)["data"]
    project.json("import", HERO, "rigged.glb")
    second = project.json("next", HERO)["data"]
    stages = {s["name"]: s for s in project.json("describe", "character")["data"]["kinds"][0]["stages"]}

    assert first["stage"] == "model" and first["command"] == f"kiripix import {HERO} <file>"
    assert second["command"] == f"kiripix pick {HERO} {first_variant(project)}"
    assert "kiripix import" in stages["model"]["owner_input"]
    assert "--role rigged" in stages["rig"]["owner_input"] and "--role clip-source" in stages["clips"]["owner_input"]


def test_an_old_settings_file_migrates_in_memory_and_the_stage_takes_a_height(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    old = 'schema_version = 1\n[project]\nname = "x"\n'
    path.write_text(old, encoding="utf-8")
    hero(project)

    assert project.json("status")["ok"]
    assert path.read_text(encoding="utf-8") == old
    render = {s["name"]: s for s in project.json("describe", "character")["data"]["kinds"][0]["stages"]}["render"]
    assert {p["name"] for p in render["params"]} == {"height", "camera", "bands", "shadow"}
    project.json("set", HERO, "render", "height=40")
    assert project.json("show", HERO)["data"]["stages"][3]["params"]["height"] == 40


def test_a_version_2_settings_file_migrates_in_memory_and_gets_the_default_light(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")
    assert "schema_version = 3" in text  # ticket 0105 added the key light to the camera presets
    old = text.replace("schema_version = 3", "schema_version = 2")
    for key in ("light_angle", "light_tilt"):
        old = "\n".join(line for line in old.splitlines() if not line.startswith(key)) + "\n"
    path.write_text(old, encoding="utf-8")
    hero(project)

    assert project.json("status")["ok"]
    assert path.read_text(encoding="utf-8") == old  # migrated in memory only; the file is the Owner's


def test_the_character_settings_are_written_by_init_and_checked(project: Kiripix) -> None:
    hero(project)
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")
    assert "[character]\nheight = 52" in text and "[character.camera.top34_8]" in text

    path.write_text(text.replace("height = 52", "height = 64"), encoding="utf-8")
    assert project.json("status")["ok"]
    path.write_text(text.replace("height = 52", "hieght = 52"), encoding="utf-8")
    finding = project.json("status", expect=1)["findings"][0]
    assert finding["code"] == "config.unknown_key" and finding["position"]["field"] == "character.hieght"
    path.write_text(text.replace("elevation = 30", "elevation = 0"), encoding="utf-8")
    assert project.json("status", expect=1)["findings"][0]["code"] == "config.invalid"


def test_show_gives_each_file_its_imported_name_and_size(project: Kiripix) -> None:
    folder = hero(project, "rigged.fbx")
    shutil.copy(FIXTURES / "rigged.fbx", project.cwd / "hero_v2.fbx")
    expected = (FIXTURES / "rigged.fbx").stat().st_size
    project.json("import", HERO, "hero_v2.fbx")
    project.json("import", HERO, "rigged.fbx", "--role", "clip-source")
    project.json("import", HERO, "hero_v2.fbx", "--role", "rigged")

    data = project.json("show", HERO)["data"]
    assert [(v["imported_as"], v["size"]) for v in data["variants"]] == [("hero_v2.fbx", expected)]
    assert [(c["name"], c["imported_as"], c["size"]) for c in data["clip_sources"]] == [("rigged", "rigged.fbx", expected)]
    assert (data["rigged"]["imported_as"], data["rigged"]["size"]) == ("hero_v2.fbx", expected)
    assert not (folder / "src" / "imported.jsonl").exists()

    # the same content under a new name records the newer name, and nothing is rebuilt for it
    before = model_hash(project)
    shutil.copy(FIXTURES / "rigged.fbx", project.cwd / "hero_old.fbx")
    assert not project.json("import", HERO, "hero_old.fbx")["data"]["created"]
    assert project.json("show", HERO)["data"]["variants"][0]["imported_as"] == "hero_old.fbx"
    assert model_hash(project) == before


def test_a_project_from_before_the_record_gives_null(project: Kiripix) -> None:
    folder = hero(project, "rigged.fbx")
    project.json("import", HERO, "rigged.fbx")
    (folder / "imported.jsonl").unlink()

    result = project.json("show", HERO)["data"]["variants"][0]
    assert result["imported_as"] is None and result["size"] > 0


def test_an_image_variant_has_its_imported_name(project: Kiripix) -> None:
    project.json("new", "prop", "crate")
    Image.new("RGBA", (8, 8), (200, 0, 0, 255)).save(project.cwd / "crate_v3.png")
    project.json("import", "prop.crate", "crate_v3.png")

    variant = project.json("show", "prop.crate")["data"]["variants"][0]
    assert variant["imported_as"] == "crate_v3.png" and variant["size"] > 0
