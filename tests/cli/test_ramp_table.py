"""The Project ramp table (ticket 0167, spec §6.3): `[[character.ramps]]` in kiripix.toml, the owner-only `ramps-add` that fills
it from a character's built `palette.json`, and the Project check `palette.parts_differ`. On the fake Blender, whose materials
are `cloth` and `skin` (see test_character_ramps.py)."""

import json
import shutil
from pathlib import Path

from conftest import Kiripix
from test_character_clips import IDLE, rigged_hero
from test_character_model import FIXTURES, HERO
from test_character_ramps import split
from test_clips_copy import TWIN

BLACK, NIGHT, STONE, DUSK = [0, 0, 0], [29, 43, 83], [95, 87, 79], [131, 118, 156]  # the default palette's first colours


def table(project: Kiripix, *rows: str) -> None:
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8") + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def row(name: str, length: int, rgb: list[list[int]] | None = None) -> str:
    colours = f"\nrgb = {json.dumps(rgb)}" if rgb is not None else ""
    return f'[[character.ramps]]\nname = "{name}"\nlength = {length}{colours}\n'


def build(project: Kiripix, asset: str, parts: str) -> Path:
    project.json("set", asset, "palette", f"parts={parts}")
    project.json("run", asset, "render")
    project.json("run", asset, "palette")
    return project.cwd / "assets" / "character" / asset.split(".")[1]


def hero(project: Kiripix, parts: str = "cloth,skin") -> Path:
    split(project)
    rigged_hero(project)
    project.json("decide", HERO, "clips", "--decision", json.dumps({"decision": "clip", "data": IDLE}))
    project.json("run", HERO, "clips")
    return build(project, HERO, parts)


def twin(project: Kiripix, parts: str) -> Path:
    project.json("new", "character", "twin")
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "twin.glb")
    project.json("pick", TWIN, project.json("import", TWIN, "twin.glb")["data"]["variant"])
    project.json("run", TWIN, "model")
    project.json("run", TWIN, "rig")
    project.json("decide", TWIN, "clips", "--decision", json.dumps({"decision": "clip", "data": IDLE}))
    project.json("run", TWIN, "clips")
    return build(project, TWIN, parts)


def codes(result: dict[str, object]) -> list[str]:
    findings = result["findings"]
    assert isinstance(findings, list)
    return [f["code"] for f in findings]


def test_a_version_3_project_migrates_in_memory_to_an_empty_table(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")
    assert "schema_version = 5" in text
    old = text.replace("schema_version = 5", "schema_version = 3")
    path.write_text(old, encoding="utf-8")

    described = project.json("describe", "project")

    assert described["ok"] and described["data"]["ramps"] == []
    assert path.read_text(encoding="utf-8") == old  # the file is the Owner's until a writing Command saves it


def test_describe_shows_the_table_and_an_example(project: Kiripix) -> None:
    table(project, row("skin", 3, [BLACK, NIGHT, STONE]), row("top", 2))

    data = project.json("describe", "project")["data"]

    assert data["ramps"] == [{"name": "skin", "length": 3, "rgb": [BLACK, NIGHT, STONE]},
                             {"name": "top", "length": 2, "rgb": None}]
    assert "ramps-add" in data["ramps_example"]
    schema = project.json("schema")["data"]["commands"]["ramps-add"]
    assert "ramps-add" in json.dumps(schema["input"]) and schema["kind"] == "owner-only"


def test_each_bad_table_fails_to_load_with_its_own_finding_code(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    good = path.read_text(encoding="utf-8")
    cases = {
        "ramps.name_twice": [row("skin", 2), row("skin", 3)],
        "ramps.rgb_length": [row("skin", 3, [BLACK, NIGHT])],
        "ramps.colour_not_in_palette": [row("skin", 2, [BLACK, [1, 2, 3]])],
        "ramps.colour_shared": [row("skin", 2, [BLACK, NIGHT]), row("hair", 2, [NIGHT, STONE])],
        "config.invalid": [row("skin", 1)],
    }

    for code, rows in cases.items():
        path.write_text(good, encoding="utf-8")
        table(project, *rows)
        result = project.json("status", expect=1)
        assert code in codes(result), (code, result["findings"])
        finding = next(f for f in result["findings"] if f["code"] == code)
        assert (finding["fix"] is None) != (finding["owner_action"] is None)
    path.write_text(good, encoding="utf-8")
    table(project, row("Skin Tone", 3))
    assert codes(project.json("status", expect=1)) == ["config.invalid"]


def test_ramps_add_needs_the_owner_and_a_built_palette(project: Kiripix) -> None:
    hero(project)
    before = (project.cwd / "kiripix.toml").read_text(encoding="utf-8")

    refused = project.json("ramps-add", HERO, "--parts", "skin", expect=3)

    assert codes(refused) == ["owner.required"]
    assert (project.cwd / "kiripix.toml").read_text(encoding="utf-8") == before
    project.json("new", "character", "bare")
    unbuilt = project.json("ramps-add", "character.bare", "--parts", "skin", owner=True, expect=1)
    assert codes(unbuilt) == ["ramps.palette_not_built"]
    assert unbuilt["findings"][0]["fix"] == "kiripix run character.bare palette"
    unknown = project.json("ramps-add", HERO, "--parts", "hair", owner=True, expect=1)
    assert codes(unknown) == ["ramps.part_unknown"] and "cloth, skin" in unknown["findings"][0]["message"]


def test_ramps_add_writes_the_table_from_palette_json_and_a_repeat_writes_nothing(project: Kiripix) -> None:
    folder = hero(project)
    parts = {p["name"]: p for p in json.loads((folder / "work/palette/palette.json").read_text("utf-8"))["parts"]}
    path = project.cwd / "kiripix.toml"
    before = path.read_text(encoding="utf-8")

    dry = project.json("ramps-add", HERO, "--parts", "cloth,skin", "--colours", "--dry-run", owner=True)

    assert dry["data"]["wrote"] is False and dry["data"]["dry_run"] is True
    assert [r["name"] for r in dry["data"]["table"]] == ["cloth", "skin"]
    assert path.read_text(encoding="utf-8") == before
    done = project.json("ramps-add", HERO, "--parts", "cloth,skin", "--colours", owner=True)
    assert done["data"]["wrote"] is True and done["data"]["added"] == ["cloth", "skin"]
    text = path.read_text(encoding="utf-8")
    assert text.startswith(before) and "# The ramp table" in text  # the Owner's comments stay
    shown = project.json("describe", "project")["data"]["ramps"]
    assert shown == [{"name": n, "length": len(parts[n]["rgb"]), "rgb": parts[n]["rgb"]} for n in ("cloth", "skin")]

    again = project.json("ramps-add", HERO, "--parts", "cloth,skin", "--colours", owner=True)

    assert again["data"]["wrote"] is False and again["data"]["unchanged"] == ["cloth", "skin"]
    assert path.read_text(encoding="utf-8") == text
    assert project.json("check", "--all", expect=0)["findings"] == []


def test_a_part_already_in_the_table_is_refused_when_its_length_or_colours_differ(project: Kiripix) -> None:
    hero(project)
    path = project.cwd / "kiripix.toml"
    before = path.read_text(encoding="utf-8")
    project.json("ramps-add", HERO, "--parts", "skin", owner=True)
    text = path.read_text(encoding="utf-8")

    with_colours = project.json("ramps-add", HERO, "--parts", "skin", "--colours", owner=True, expect=1)
    assert codes(with_colours) == ["ramps.part_differs"] and "rgb" in with_colours["findings"][0]["message"]
    path.write_text(before, encoding="utf-8")  # with the table, a length of the hero's own is refused (ticket 0168)
    build(project, HERO, "skin:4")
    path.write_text(text, encoding="utf-8")
    longer = project.json("ramps-add", HERO, "--parts", "skin", owner=True, expect=1)

    assert codes(longer) == ["ramps.part_differs"]
    assert "length is 3 in the table and 4" in longer["findings"][0]["message"]
    assert longer["findings"][0]["owner_action"] and not longer["findings"][0]["fix"]
    assert path.read_text(encoding="utf-8") == text


def test_two_characters_that_disagree_on_a_part_raise_palette_parts_differ(project: Kiripix) -> None:
    hero(project)
    twin(project, "skin,cloth")  # skin is row 0 here and row 1 on the hero
    project.json("ramps-add", HERO, "--parts", "cloth,skin", owner=True)

    result = project.json("check", "--all", expect=2)

    findings = result["findings"]  # one per character and part: the twin's skin and cloth are both in the wrong row
    assert sorted(f["position"]["field"] for f in findings) == ["parts.cloth.row", "parts.skin.row"]
    for finding in findings:
        assert finding["code"] == "palette.parts_differ" and finding["fix"] == f"kiripix run {TWIN} palette"
        assert finding["owner_action"] is None and finding["position"]["asset"] == TWIN
    assert any("row is 0, the table's is 1" in f["message"] for f in findings)


def test_a_different_length_is_named(project: Kiripix) -> None:
    hero(project)
    twin(project, "cloth,skin:4")  # built before the table: with it, a length of the twin's own is refused (ticket 0168)
    project.json("ramps-add", HERO, "--parts", "cloth,skin", owner=True)

    result = project.json("check", "--all", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "palette.parts_differ" and finding["position"]["field"] == "parts.skin.length"
    assert "length is 4, the table's is 3" in finding["message"] and finding["fix"] == f"kiripix run {TWIN} palette"


def test_shared_colours_that_differ_are_named(project: Kiripix) -> None:
    hero(project)
    table(project, row("cloth", 3, [BLACK, NIGHT, STONE]))

    findings = project.json("check", "--all", expect=2)["findings"]

    [finding] = [f for f in findings if f["position"]["field"].startswith("parts.cloth")]  # skin isn't in the table at all
    assert finding["code"] == "palette.parts_differ" and finding["position"]["asset"] == HERO
    assert finding["position"]["field"] == "parts.cloth.rgb"


def test_a_part_the_table_lacks_asks_the_owner_to_add_it(project: Kiripix) -> None:
    hero(project)
    table(project, row("skin", 3))

    findings = project.json("check", "--all", expect=2)["findings"]

    [finding] = [f for f in findings if "'cloth'" in f["message"]]
    assert finding["owner_action"] and "ramps-add" in finding["owner_action"] and finding["fix"] is None


def test_an_empty_table_checks_nothing(project: Kiripix) -> None:
    hero(project)

    assert project.json("check", "--all")["findings"] == []


def test_the_exported_character_json_is_checked_too(project: Kiripix) -> None:
    folder = hero(project)
    table(project, row("cloth", 3), row("skin", 3))
    assert project.json("check", "--all")["findings"] == []
    export = folder / "out" / "export"
    export.mkdir(parents=True)
    parts = [{"name": "skin", "materials": ["skin"], "indexes": [1, 2, 3], "rgb": [BLACK, NIGHT, STONE]},
             {"name": "cloth", "materials": ["cloth"], "indexes": [4, 5, 6], "rgb": [BLACK, NIGHT, STONE, DUSK]}]
    (export / "character.json").write_text(json.dumps({"schema_version": 2, "parts": parts}), encoding="utf-8")

    findings = project.json("check", "--all", expect=2)["findings"]

    assert {f["position"]["field"] for f in findings} == {"parts.skin.row", "parts.cloth.length,row"}
    assert all(f["code"] == "palette.parts_differ" and f["fix"] == f"kiripix run {HERO} export" for f in findings)
    assert all(f["position"]["file"] == "character.json" for f in findings)
