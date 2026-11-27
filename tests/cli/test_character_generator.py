"""A Model built from a parameter file by the Project's generator (ticket 0224).

On the fake Blender of `kiripix_test_recipes.py`, which runs a Project's script with this Python in place of Blender's, by
the same protocol: `<script> -- <args.json> <result.json>`. The generator here is a fake one, written into the test's
Project: it reads the parameter file (TOML) and its library, writes a Model the fake Blender can read (JSON: the bones of the
library and the Model's own height) and says what a real one says: the materials, the parts, the eye materials and the
Model's height over its base body's. Keys of the parameter file make it fail (`fail`), write no Model (`no_model`) or no
JSON (`no_json`), or say something else (`[says]`)."""

import json
import shutil
from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status
from test_character_base import BODY, BONES, body, stage
from test_character_clips import IDLE
from test_character_model import FIXTURES, HERO, calls, picked_hero
from test_character_render import render_json

ELDER = "character.elder"
GENERATOR = '''
import json
import sys
import tomllib
from pathlib import Path

separator = sys.argv.index("--")
args = json.loads(Path(sys.argv[separator + 1]).read_text("utf-8"))
said = tomllib.loads(Path(args["parameters"]).read_text("utf-8"))
library = json.loads(Path(args["library"][0]).read_text("utf-8"))
print("building", said.get("name"))
if said.get("fail"):
    for number in range(30):
        print("line", number)
    sys.exit(3)
if not said.get("no_model"):
    model = {"bones": library["bones"], "source_height": 1.8 * said.get("height", 1.0)}
    Path(args["model"]).write_text(json.dumps(model), "utf-8")
if not said.get("no_json"):
    result = {"materials": ["cloth", "skin"], "parts": "cloth,skin", "eyes": ["skin"], "height": said.get("height", 1.0)}
    result.update(said.get("says", {}))
    Path(sys.argv[separator + 2]).write_text(json.dumps(result), "utf-8")
'''


def add_settings(project: Kiripix, text: str) -> None:
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8") + "\n" + text, encoding="utf-8")


def chargen(project: Kiripix, name: str = "chargen") -> Path:
    """The fake generator in the Project, with a library of one file and one folder, and its settings."""
    folder = project.cwd / name
    (folder / "parts").mkdir(parents=True)
    (folder / "generate.py").write_text(GENERATOR, encoding="utf-8")
    (folder / "library.json").write_text(json.dumps({"bones": BONES}), encoding="utf-8")
    (folder / "parts" / "hat.txt").write_text("a hat", encoding="utf-8")
    add_settings(project, f'[character.generators.{name}]\nscript = "{name}/generate.py"\n'
                          f'library = ["{name}/library.json", "{name}/parts"]\n')
    return folder


def parameter_file(project: Kiripix, text: str = 'name = "elder"\nheight = 0.9\n', name: str = "elder.toml") -> Path:
    path = project.cwd / name
    path.write_text(text, encoding="utf-8")
    return path


def elder(project: Kiripix, text: str = 'name = "elder"\nheight = 0.9\n', *more: str) -> Path:
    parameter_file(project, text)
    project.json("new", "character", "elder", "--from-parameters", "elder.toml", *more)
    return project.cwd / "assets" / "character" / "elder"


def model_json(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work" / "model" / "model.json").read_text("utf-8"))
    return document


def to_render(project: Kiripix, asset: str = ELDER) -> None:
    (project.cwd / "blender-material-split").write_text("", encoding="utf-8")  # both materials have pixels
    project.json("run", asset, "model")
    project.json("run", asset, "rig")
    project.json("decide", asset, "clips", "--decision", json.dumps({"decision": "clip", "data": IDLE}))
    project.json("run", asset, "clips")
    project.json("run", asset, "render")


def test_a_character_with_a_parameter_file_reaches_render_with_no_pick(project: Kiripix) -> None:
    chargen(project)
    parameter_file(project)

    created = project.json("new", "character", "elder", "--from-parameters", "elder.toml")["data"]

    folder = project.cwd / "assets" / "character" / "elder"
    assert "assets/character/elder/src/parameters/elder.toml" in created["created"]
    assert (folder / "src" / "parameters" / "elder.toml").read_text("utf-8") == 'name = "elder"\nheight = 0.9\n'
    assert stage_status(project, ELDER)["model"] == "todo", "the parameter file is the Source: nothing is picked"
    assert project.json("next", ELDER)["data"]["command"] == f"kiripix run {ELDER}"

    to_render(project)

    document = model_json(folder)
    assert document["source"] == "elder.toml" and document["generator"] == "chargen"
    assert document["generated"] == {"parts": "cloth,skin", "eyes": "skin", "height": 0.9, "materials": ["cloth", "skin"]}
    assert (folder / "work" / "model" / "generated.glb").is_file()
    generate, normalise = calls(project)[:2]
    assert generate["script"] == "generate.py" and set(generate["args"]) == {"parameters", "library", "model"}
    assert [Path(p).name for p in generate["args"]["library"]] == ["library.json", "parts"]
    assert normalise["script"] == "normalise_model" and Path(normalise["args"]["input"]).name == "generated.glb"
    render = render_json(folder)
    assert render["height"] == 47, "the Project's 52 px times the generator's 0.9"
    assert render["eyes"] == ["skin"] and render["generated"]["parts"] == "cloth,skin"

    project.json("run", ELDER, "palette")

    palette = json.loads((folder / "work" / "palette" / "palette.json").read_text("utf-8"))
    assert [p["name"] for p in palette["parts"]] == ["cloth", "skin"]
    shown = project.json("show", ELDER)["data"]
    assert shown["parameters"]["name"] == "elder.toml" and shown["variants"] == [] and shown["picked"] is None
    assert stage(project, ELDER, "render")["params"]["eyes"] == "skin"
    assert stage(project, ELDER, "render")["param_sources"]["eyes"] == "generated"
    assert stage(project, ELDER, "palette")["params"]["parts"] == "cloth,skin"
    assert stage(project, ELDER, "palette")["param_sources"]["parts"] == "generated"
    assert "parts=cloth,skin (generated)" in project("show", ELDER).stdout


def test_a_value_set_by_hand_wins_the_generators(project: Kiripix) -> None:
    chargen(project)
    folder = elder(project)
    to_render(project)

    project.json("set", ELDER, "render", "eyes=", "height=40")
    project.json("set", ELDER, "palette", "parts=skin")

    assert stage_status(project, ELDER)["render"] == "stale"
    assert stage(project, ELDER, "render")["param_sources"]["eyes"] == "asset"
    project.json("run", ELDER, "render")
    project.json("run", ELDER, "palette")
    render = render_json(folder)
    assert render["height"] == 40 and "eyes" not in render, "an empty `eyes` set by hand means none, not the generator's"
    palette = json.loads((folder / "work" / "palette" / "palette.json").read_text("utf-8"))
    assert [p["name"] for p in palette["parts"]] == ["skin"]


def test_editing_the_parameter_file_the_library_or_the_script_makes_model_stale(project: Kiripix) -> None:
    generator = chargen(project)
    folder = elder(project)
    project.json("run", ELDER, "model")
    assert stage_status(project, ELDER)["model"] == "done"

    (folder / "src" / "parameters" / "elder.toml").write_text('name = "elder"\nheight = 0.8\n', encoding="utf-8")

    assert stage_status(project, ELDER)["model"] == "stale"
    project.json("run", ELDER, "model")
    assert model_json(folder)["generated"]["height"] == 0.8

    (generator / "parts" / "hat.txt").write_text("another hat", encoding="utf-8")

    assert stage_status(project, ELDER)["model"] == "stale", "a file under a library folder is an input"
    project.json("run", ELDER, "model")

    (generator / "parts" / "__pycache__").mkdir()
    (generator / "parts" / "__pycache__" / "hat.cpython-312.pyc").write_bytes(b"cache")

    assert stage_status(project, ELDER)["model"] == "done", "what running the script leaves behind is not an input"

    (generator / "generate.py").write_text(GENERATOR + "# changed\n", encoding="utf-8")

    assert stage_status(project, ELDER)["model"] == "stale"
    project.json("run", ELDER, "model")

    (generator / "parts" / "scarf.txt").write_text("a scarf", encoding="utf-8")

    assert stage_status(project, ELDER)["model"] == "stale", "so is a file added to it"


def test_an_imported_models_stages_do_not_depend_on_the_projects_generators(project: Kiripix) -> None:
    picked_hero(project)
    project.json("run", HERO, "model")
    before = project.json("run", HERO, "model")["data"]["results"][0]

    generator = chargen(project)
    (generator / "parts" / "hat.txt").write_text("another hat", encoding="utf-8")

    after = project.json("run", HERO, "model")["data"]["results"][0]
    assert after["outcome"] == "skipped" and after["input_hash"] == before["input_hash"]


def test_a_generator_that_fails_names_the_script_and_shows_its_last_lines(project: Kiripix) -> None:
    chargen(project)
    folder = elder(project, 'name = "elder"\nfail = true\n')

    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]

    assert finding["code"] == "model.generator_failed" and finding["fix"] is None
    assert "chargen/generate.py" in finding["message"] and "exit 3" in finding["message"]
    lines = finding["message"].splitlines()[1:]
    assert lines == [f"line {number}" for number in range(10, 30)], "its last 20 lines"
    assert "elder.toml" in finding["owner_action"] and f"kiripix run {ELDER} model" in finding["owner_action"]
    assert stage_status(project, ELDER)["model"] == "failed" and not (folder / "work" / "model").exists()


def test_a_generator_that_writes_no_model_or_no_json_says_which_is_missing(project: Kiripix) -> None:
    chargen(project)
    folder = elder(project, 'name = "elder"\nno_model = true\n')
    stored = folder / "src" / "parameters" / "elder.toml"

    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]

    assert finding["code"] == "model.generator_failed" and "without writing the Model" in finding["message"]

    stored.write_text('name = "elder"\nno_json = true\n', encoding="utf-8")
    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]

    assert finding["code"] == "model.generator_failed" and "without writing its JSON" in finding["message"]
    assert "building elder" in finding["message"]

    stored.write_text('name = "elder"\n[says]\nheight = "tall"\n', encoding="utf-8")
    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]

    assert finding["code"] == "model.generator_failed" and "`height` is not a number" in finding["message"]


def test_without_a_generator_or_with_several_the_stage_waits_for_the_owner(project: Kiripix) -> None:
    elder(project)

    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]

    assert finding["code"] == "stage.needs_input" and "no generator" in finding["message"]
    assert "[character.generators.<name>]" in finding["owner_action"]

    chargen(project)
    chargen(project, "other")
    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]

    assert "several generators (chargen, other)" in finding["message"]
    assert f"kiripix set {ELDER} model generator=<name>" in finding["owner_action"]

    project.json("set", ELDER, "model", "generator=other")
    project.json("run", ELDER, "model")

    assert model_json(project.cwd / "assets" / "character" / "elder")["generator"] == "other"
    project.json("set", ELDER, "model", "generator=nobody")
    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]
    assert "no generator nobody" in finding["message"]


def test_a_generator_whose_script_is_not_in_the_project_waits_for_the_owner(project: Kiripix) -> None:
    generator = chargen(project)
    elder(project)
    (generator / "generate.py").unlink()

    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]

    assert finding["code"] == "stage.needs_input" and "chargen/generate.py" in finding["message"]
    assert "[character.generators.chargen]" in finding["owner_action"]


def test_a_character_has_a_parameter_file_or_imported_models_never_both(project: Kiripix) -> None:
    chargen(project)
    folder = elder(project)
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "rigged.glb")

    [finding] = project.json("import", ELDER, "rigged.glb", expect=1)["findings"]

    assert finding["code"] == "import.model_or_parameters" and "elder.toml" in finding["message"]
    assert not list((folder / "src").glob("*.glb"))

    picked_hero(project)
    [finding] = project.json("import", HERO, "elder.toml", "--role", "parameters", expect=1)["findings"]

    assert finding["code"] == "import.model_or_parameters"
    assert not (project.cwd / "assets" / "character" / "hero" / "src" / "parameters").exists()

    shutil.copy(FIXTURES / "rigged.glb", folder / "src" / "0123456789abcdef.glb")  # put there by hand
    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]
    assert finding["code"] == "stage.needs_input" and "a parameter file and an imported Model" in finding["message"]


def test_importing_a_parameter_file_replaces_the_one_before_and_other_files_are_refused(project: Kiripix) -> None:
    chargen(project)
    folder = elder(project)
    parameter_file(project, 'name = "elder"\nheight = 1.1\n', "taller.toml")

    data = project.json("import", ELDER, "taller.toml", "--role", "parameters")["data"]

    assert data["role"] == "parameters" and data["parameters"] == "taller.toml" and data["created"]
    assert data["file"] == "assets/character/elder/src/parameters/taller.toml"
    assert [p.name for p in (folder / "src" / "parameters").iterdir()] == ["taller.toml"]
    assert not project.json("import", ELDER, "taller.toml", "--role", "parameters")["data"]["created"]
    assert project.json("show", ELDER)["data"]["parameters"]["imported_as"] == "taller.toml"

    (project.cwd / "notes.txt").write_text("hello", encoding="utf-8")
    [finding] = project.json("import", ELDER, "notes.txt", "--role", "parameters", expect=1)["findings"]
    assert finding["code"] == "import.not_parameters"

    project.json("new", "room", "alley", "--view", "top")
    [finding] = project.json("import", "room.alley", "taller.toml", "--role", "parameters", expect=1)["findings"]
    assert finding["code"] == "import.role_needs_character"


def test_new_from_parameters_is_for_a_character_and_a_refused_file_creates_nothing(project: Kiripix) -> None:
    parameter_file(project)
    (project.cwd / "notes.txt").write_text("hello", encoding="utf-8")

    [finding] = project.json("new", "prop", "bench", "--from-parameters", "elder.toml", expect=1)["findings"]
    assert finding["code"] == "new.parameters_need_character" and finding["fix"]

    [finding] = project.json("new", "character", "elder", "--from-parameters", "notes.txt", expect=1)["findings"]
    assert finding["code"] == "import.not_parameters"

    [finding] = project.json("new", "character", "elder", "--from-parameters", "missing.toml", expect=1)["findings"]
    assert finding["code"] == "import.not_found"
    assert not (project.cwd / "assets" / "prop").exists() and not (project.cwd / "assets" / "character").exists()


def test_a_generators_paths_stay_inside_the_project_and_one_library_path_may_be_text(project: Kiripix) -> None:
    add_settings(project, '[character.generators.chargen]\nscript = "chargen/generate.py"\nlibrary = "chargen/parts"\n')

    assert project.json("status")["ok"]

    path = project.cwd / "kiripix.toml"
    text = path.read_text("utf-8")
    for bad in ('"../chargen/generate.py"', '"/chargen/generate.py"'):
        path.write_text(text.replace('"chargen/generate.py"', bad), encoding="utf-8")

        [finding] = project.json("status", expect=1)["findings"]

        assert finding["code"] == "config.invalid" and "inside the Project" in finding["message"]


def test_a_version_5_settings_file_migrates_in_memory_to_no_generators(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text("utf-8")
    assert "schema_version = 15" in text
    old = text.replace("schema_version = 15", "schema_version = 5")
    path.write_text(old, encoding="utf-8")
    elder(project)

    [finding] = project.json("run", ELDER, "model", expect=3)["findings"]

    assert "no generator" in finding["message"]
    assert path.read_text("utf-8") == old  # migrated in memory only; the file is the Owner's


def test_a_generated_character_made_from_a_base_takes_the_generators_values_before_the_bases(project: Kiripix) -> None:
    body(project)
    project.json("set", BODY, "render", "height=60", "eyes=cloth", "shadow=0.7")
    project.json("set", BODY, "palette", "parts=skin")
    chargen(project)
    folder = elder(project, 'name = "elder"\nheight = 0.9\n', "--base", BODY)

    to_render(project)

    render = render_json(folder)
    assert render["height"] == 54, "the base's 60 px times the generator's 0.9"
    assert render["eyes"] == ["skin"] and render["toon"]["shadow"] == 0.7, "the generator's eyes, and the base's shadow"
    assert [c["name"] for c in render["clips"]] == ["idle", "walk", "wave"], "the base's clips, and its own idle over the base's"
    project.json("run", ELDER, "palette")
    palette = json.loads((folder / "work" / "palette" / "palette.json").read_text("utf-8"))
    assert [p["name"] for p in palette["parts"]] == ["cloth", "skin"]
    assert stage(project, ELDER, "palette")["param_sources"]["parts"] == "generated"
    assert stage(project, ELDER, "render")["param_sources"]["shadow"] == "base"

    project.json("set", ELDER, "palette", "parts=skin")

    assert stage_status(project, ELDER)["palette"] == "stale"
