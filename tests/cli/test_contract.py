"""The JSON contract, for every Command in the registry: `--help`, one JSON object, and output that validates against
`schema`. A new Command without a sample here fails `test_every_command_has_a_sample`."""

import shutil
from collections.abc import Callable
from pathlib import Path

import jsonschema
import pytest
from PIL import Image

from conftest import MARK, Kiripix, in_review, make_demo, sketched
from test_export import exportable_room, godot_project, set_target
from test_manifest_merge import git, manifest_text, sides


def _image(project: Kiripix) -> None:
    Image.new("RGBA", (4, 4), (255, 0, 77, 255)).save(project.cwd / "in.png")  # "red" in the default palette


def _proposal(project: Kiripix) -> None:
    """A palette proposal for a colour the default palette lacks, copied to a path the sample can name."""
    Image.new("RGBA", (4, 4), (10, 200, 210, 255)).save(project.cwd / "in.png")
    made = project.json("op", "palette-suggest", "in.png", "--add", "2", "--scale", "1")["data"]["proposal"]
    shutil.copy(project.cwd / made, project.cwd / ".kiripix" / "palette-proposals" / "in-proposal.json")


def _decided(project: Kiripix) -> None:
    make_demo(project)
    project.json("decide", "demo.a", "choose", "--decision", MARK)


def _undone(project: Kiripix) -> None:
    _decided(project)
    project.json("undo", "demo.a", "choose")


def _room_image(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    _image(project)


def _imported(project: Kiripix) -> str:
    """Import in.png into room.alley (once; importing again is a no-op) and return the Variant's name."""
    if not (project.cwd / "in.png").exists():
        _room_image(project)
    return str(project.json("import", "room.alley", "in.png")["data"]["variant"])


def _game_repo(project: Kiripix) -> None:
    """A Godot project that is a git repository, as the target."""
    if shutil.which("git") is None:
        pytest.skip("git isn't installed")
    game = godot_project(project)
    set_target(project)
    git(game, "init", "-b", "main")


# Each sample prepares the Project, then gives the arguments of one successful call.
SAMPLES: dict[str, Callable[[Kiripix], list[str]]] = {
    "init": lambda p: ["init", "sub"],
    "new": lambda p: ["new", "prop", "bench"],
    "describe": lambda p: ["describe", "room"],
    "schema": lambda p: ["schema", "run"],
    "status": lambda p: (make_demo(p), ["status"])[1],
    "next": lambda p: (make_demo(p), ["next", "demo.a"])[1],
    "run": lambda p: (make_demo(p), ["run", "demo.a"])[1],
    "set": lambda p: (make_demo(p), ["set", "demo.a", "concat", "sep=-"])[1],
    "decide": lambda p: (make_demo(p), ["decide", "demo.a", "choose", "--decision", MARK])[1],
    "undo": lambda p: (_decided(p), ["undo", "demo.a", "choose"])[1],
    "redo": lambda p: (_undone(p), ["redo", "demo.a", "choose"])[1],
    "override": lambda p: (sketched(p), ["override", "sketch.a", "draw", "fix.png"])[1],
    "accept": lambda p: (in_review(p), ["accept", "sketch.a", "draw"])[1],
    "import": lambda p: (_room_image(p), ["import", "room.alley", "in.png"])[1],
    "mask-import": lambda p: (_room_image(p), ["mask-import", "room.alley", "in.png"])[1],
    "plate-import": lambda p: (_room_image(p), ["plate-import", "room.alley", "in.png"])[1],
    "pick": lambda p: (_imported(p), ["pick", "room.alley", _imported(p)])[1],
    "check": lambda p: (make_demo(p), ["check", "demo.a"])[1],
    "show": lambda p: (make_demo(p), ["show", "demo.a"])[1],
    "preview": lambda p: (sketched(p), ["preview", "sketch.a", "--stage", "draw", "--region", "0,0,4,4", "--grid", "2"])[1],
    "export": lambda p: (exportable_room(p), ["export", "room.alley"])[1],
    "probe": lambda p: (make_demo(p), ["probe", "echo", "demo.a", "x"])[1],
    "op quantize": lambda p: (_image(p), ["op", "quantize", "in.png", "out.png"])[1],
    "op conformance": lambda p: (_image(p), ["op", "conformance", "in.png"])[1],
    "op palette-suggest": lambda p: (_image(p), ["op", "palette-suggest", "in.png", "--add", "2", "--scale", "1"])[1],
    "palette-add": lambda p: (_proposal(p), ["palette-add", ".kiripix/palette-proposals/in-proposal.json"])[1],
    "runners list": lambda p: ["runners", "list"],
    "runners pull": lambda p: ["runners", "pull", "sam2.1-small"],
    "runners rm": lambda p: ["runners", "rm", "sam2.1-small"],
    "manifest merge": lambda p: sides(p.cwd, manifest_text(1), manifest_text(2)),
    "manifest install": lambda p: (_game_repo(p), ["manifest", "install"])[1],
    "manifest repair": lambda p: (godot_project(p), set_target(p), ["manifest", "repair"])[2],
}


@pytest.fixture(scope="module")
def schemas(tmp_path_factory: pytest.TempPathFactory) -> dict[str, dict[str, object]]:
    runner = Kiripix(tmp_path_factory.mktemp("schema"))
    data = runner.json("schema")["data"]
    assert data["api_version"] == 1
    commands: dict[str, dict[str, object]] = data["commands"]
    return commands


def test_every_command_has_a_sample(schemas: dict[str, object]) -> None:
    assert set(schemas) == set(SAMPLES)


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_help_exists(kpx: Kiripix, name: str) -> None:
    result = kpx(*name.split(), "--help")

    assert result.code == 0
    assert "--json" in result.stdout


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_json_output_validates_against_the_schema(project: Kiripix, schemas: dict[str, dict[str, object]],
                                                  name: str) -> None:
    arguments = SAMPLES[name](project)

    result = project.json(*arguments, owner=schemas[name]["kind"] == "owner-only")

    assert result["api_version"] == 1 and result["ok"] is True and result["findings"] == []
    jsonschema.validate(result, schemas[name]["output"])


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_input_schema_lists_the_options(schemas: dict[str, dict[str, object]], name: str) -> None:
    schema = schemas[name]["input"]
    assert isinstance(schema, dict) and schema["type"] == "object"


def test_an_error_result_validates_too(project: Kiripix, schemas: dict[str, dict[str, object]]) -> None:
    result = project.json("new", "dragon", "x", expect=1)

    jsonschema.validate(result, schemas["new"]["output"])
    finding = result["findings"][0]
    assert set(finding) == {"code", "severity", "message", "position", "fix", "owner_action"}


def test_schema_for_an_unknown_command(kpx: Kiripix) -> None:
    finding = kpx.json("schema", "paint", expect=1)["findings"][0]

    assert finding["code"] == "command.unknown"
    assert "op quantize" in finding["message"]


def test_a_usage_error_is_exit_1_with_one_json_object(kpx: Kiripix) -> None:
    result = kpx("new", "--json")

    assert result.code == 1
    assert result.json["ok"] is False
    assert result.json["findings"][0]["code"] == "input.invalid"


def test_text_mode_prints_findings_on_stderr(kpx: Kiripix) -> None:
    result = kpx("status")

    assert result.code == 1
    assert result.stdout == ""
    assert "project.not_found" in result.stderr and "fix: kiripix init" in result.stderr


def test_kpx_is_an_alias(tmp_path: Path) -> None:
    scripts = Path(__import__("sys").executable).parent
    assert any((scripts / name).exists() for name in ("kpx", "kpx.exe"))
