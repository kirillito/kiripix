"""The `npc` Kind and its `choose` Stage (ticket 0356, ADR 0015, spec §6.3): a base body, Wearables rendered on it and a named
colour choice per part, and `kiripix.toml`'s `[[character.ramps]]` `choices`. On the fake Blender; the base and the Wearables are
built through `sheet`."""

import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_ramp_table import BLACK, DUSK, NIGHT, STONE, row, table
from test_wearable import BODY, FIXTURES, hair, stage_state

HAIR, COAT, NPC = "wearable.hair", "wearable.coat", "npc.guard"
CHOICES = ('choices = { auburn = [[0, 0, 0], [29, 43, 83]], blond = ["#5f574f", "#83769c"] }',)


def ramps(project: Kiripix, extra: str = CHOICES[0]) -> None:
    """The ramp table: `hair` and `top`, two steps each, `hair` with two named choices (one written as hex text)."""
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8") + "\n[[character.ramps]]\nname = \"hair\"\nlength = 2\n" + extra +
                    "\n\n[[character.ramps]]\nname = \"top\"\nlength = 2\nchoices = { red = [[95, 87, 79], [131, 118, 156]] }\n",
                    encoding="utf-8")


def build_wearable(project: Kiripix, wearable: str) -> None:
    project.json("new", "wearable", wearable.split(".")[1], "--body", BODY)
    shutil.copy(FIXTURES / "rigged.glb", project.cwd / "part.glb")
    project.json("pick", wearable, project.json("import", wearable, "part.glb")["data"]["variant"])
    project.json("set", wearable, "palette", "colors=4")
    for stage in ("model", "rig", "render", "palette", "finish", "sheet"):
        project.json("run", wearable, stage)


def built(project: Kiripix, wearables: tuple[str, ...] = (HAIR,)) -> None:
    """character.zed built through `sheet`, and each Wearable on it (the first is wearable.hair)."""
    ramps(project)
    hair(project)
    project.json("set", BODY, "palette", "colors=4")
    for stage in ("palette", "finish", "sheet"):
        project.json("run", BODY, stage)
    project.json("set", HAIR, "palette", "colors=4")
    for stage in ("render", "palette", "finish", "sheet"):
        project.json("run", HAIR, stage)
    for wearable in wearables[1:]:
        build_wearable(project, wearable)


def choose(project: Kiripix, wearables: str = "", colours: str = "", expect: int = 0) -> dict[str, Any]:
    project.json("new", "npc", "guard", "--base", BODY)
    for name, value in (("wearables", wearables), ("colours", colours)):
        if value:
            project.json("set", NPC, "choose", f"{name}={value}")
    return project.json("run", NPC, "choose", expect=expect)


def npc_json(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / "assets" / "npc" / "guard" / "work" / "choose" / "npc.json").read_text("utf-8"))
    return value


def codes(result: dict[str, Any]) -> list[str]:
    return [f["code"] for f in result["findings"]]


def test_describe_lists_the_kind_and_its_choice_parameters(project: Kiripix) -> None:
    kind = project.json("describe", "npc")["data"]["kinds"][0]

    assert kind["recipe"] == ["choose", "export"]
    assert [(p["name"], p["required"]) for p in kind["params"]] == [("base", True)]
    assert [p["name"] for p in kind["stages"][0]["params"]] == ["wearables", "colours"]
    assert "npc" in {k["name"] for k in project.json("describe", "project")["data"]["kinds"]}
    assert "npc" in project("new", "--help").stdout


def test_an_npc_with_two_wearables_and_a_choice_per_part_builds_npc_json(project: Kiripix) -> None:
    built(project, (HAIR, COAT))
    project.json("set", COAT, "sheet", "order=5")
    project.json("run", COAT, "sheet")

    result = choose(project, f"{HAIR},{COAT}", "top=red,hair=blond")

    assert result["ok"] and result["findings"] == []
    assert npc_json(project) == {
        "schema_version": 1, "base": BODY,
        "wearables": [{"id": COAT, "order": 5}, {"id": HAIR, "order": 10}],  # each Wearable's own `order`, the coat first
        "colours": {"hair": {"choice": "blond", "rgb": [STONE, DUSK]},  # in the ramp table's row order, hex as [r, g, b]
                    "top": {"choice": "red", "rgb": [STONE, DUSK]}}}
    assert stage_state(project, NPC, "choose")["status"] == "done"
    assert str(project.cwd / ".kiripix") not in (project.cwd / "assets" / "npc" / "guard" / "asset.toml").read_text("utf-8")


def test_an_order_after_the_id_is_this_npcs_own(project: Kiripix) -> None:
    built(project, (HAIR, COAT))

    choose(project, f"{HAIR}@1,{COAT}@2")

    assert [w["id"] for w in npc_json(project)["wearables"]] == [HAIR, COAT]
    assert [w["order"] for w in npc_json(project)["wearables"]] == [1, 2]


def test_the_same_choice_builds_the_same_bytes(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR, "hair=auburn")
    first = (project.cwd / "assets" / "npc" / "guard" / "work" / "choose" / "npc.json").read_bytes()

    project.json("run", NPC, "choose", "--force")

    assert (project.cwd / "assets" / "npc" / "guard" / "work" / "choose" / "npc.json").read_bytes() == first


def test_a_choice_is_a_parameter_and_changes_the_input_hash(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR, "hair=auburn")

    project.json("set", NPC, "choose", "colours=hair=blond")

    assert stage_state(project, NPC, "choose")["status"] == "stale"
    project.json("run", NPC, "choose")
    assert npc_json(project)["colours"]["hair"]["choice"] == "blond"


def test_a_re_render_of_the_base_makes_the_npc_stale(project: Kiripix) -> None:
    built(project, ())
    choose(project)
    assert stage_state(project, NPC, "choose")["status"] == "done"

    project.json("set", BODY, "palette", "colors=5")
    waiting = stage_state(project, NPC, "choose")
    assert waiting["status"] == "needs-input" and BODY in waiting["reason"]  # the base's sheet isn't built for the new inputs
    for stage in ("palette", "finish", "sheet"):
        project.json("run", BODY, stage)

    assert stage_state(project, NPC, "choose")["status"] == "stale"
    project.json("run", NPC, "choose")
    assert stage_state(project, NPC, "choose")["status"] == "done"


def test_a_re_render_of_a_wearable_makes_the_npc_stale_and_its_order_is_read_again(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR)
    assert npc_json(project)["wearables"] == [{"id": HAIR, "order": 10}]

    project.json("set", HAIR, "sheet", "order=40")
    project.json("run", HAIR, "sheet")

    assert stage_state(project, NPC, "choose")["status"] == "stale"
    project.json("run", NPC, "choose")
    assert npc_json(project)["wearables"] == [{"id": HAIR, "order": 40}]


def test_the_npc_waits_for_a_wearable_that_is_not_built(project: Kiripix) -> None:
    built(project)
    project.json("new", "wearable", "cap", "--body", BODY)
    project.json("new", "npc", "guard", "--base", BODY)
    project.json("set", NPC, "choose", "wearables=wearable.cap")

    state = stage_state(project, NPC, "choose")

    assert state["status"] == "needs-input" and "wearable.cap" in state["reason"]


def test_each_wrong_base_is_npc_base_unknown(project: Kiripix) -> None:
    built(project)
    project.json("new", "character", "twin", "--base", BODY)
    project.json("new", "sprite", "mage")
    cases = {"character.nobody": "no such Asset", HAIR: "wearable", "sprite.mage": "sprite", "character.twin": "made from",
             "npc.guard": "it is a npc", "nonsense": "not an Asset ID"}
    project.json("new", "npc", "guard", "--base", BODY)

    for base, why in cases.items():
        result = project.json("new", "npc", "other", "--base", base, expect=1)
        assert codes(result) == ["npc.base_unknown"], (base, result["findings"])
        finding = result["findings"][0]
        assert why in finding["message"] and finding["fix"] and not finding["owner_action"]
        assert not (project.cwd / "assets" / "npc" / "other").exists()


def test_an_npc_needs_a_base(project: Kiripix) -> None:
    result = project.json("new", "npc", "guard", expect=1)

    assert codes(result) == ["asset.param_required"]


def test_a_base_edited_into_a_wearable_is_refused_when_it_is_read(project: Kiripix) -> None:
    built(project)
    project.json("new", "npc", "guard", "--base", BODY)
    path = project.cwd / "assets" / "npc" / "guard" / "asset.toml"
    path.write_text(path.read_text("utf-8").replace(BODY, HAIR), encoding="utf-8")

    result = project.json("status", expect=1)

    finding = next(f for f in result["findings"] if f["code"] == "npc.base_unknown")
    assert finding["owner_action"] and not finding["fix"]


def test_a_bad_choice_is_refused_with_its_own_code(project: Kiripix) -> None:
    built(project)
    project.json("new", "npc", "guard", "--base", BODY)
    cases = [("wearables", "wearable.nobody", "npc.wearable_unknown"), ("wearables", BODY, "npc.wearable_unknown"),
             ("wearables", f"{HAIR},{HAIR}", "npc.wearable_twice"), ("wearables", f"{HAIR}@x", "npc.wearable_order"),
             ("colours", "hair=purple", "npc.choice_unknown"), ("colours", "feet=red", "npc.part_unknown"),
             ("colours", "hair", "npc.colours_invalid"), ("colours", "hair=auburn,hair=blond", "npc.colours_invalid")]

    for name, value, code in cases:
        project.json("set", NPC, "choose", f"{name}={value}")
        state = stage_state(project, NPC, "choose")
        result = project.json("run", NPC, "choose", expect=3)
        assert state["status"] == "needs-input", (value, state)
        assert code in codes(result), (value, result["findings"])
        finding = next(f for f in result["findings"] if f["code"] == code)
        assert (finding["fix"] is None) != (finding["owner_action"] is None)
        project.json("set", NPC, "choose", f"{name}=")


def test_a_wearable_of_another_body_is_refused(project: Kiripix) -> None:
    built(project)
    project.json("new", "character", "twin")
    project.json("new", "wearable", "cap", "--body", "character.twin")
    project.json("new", "npc", "guard", "--base", BODY)

    project.json("set", NPC, "choose", "wearables=wearable.cap")
    result = project.json("run", NPC, "choose", expect=3)

    assert "npc.wearable_body" in codes(result)


def test_an_older_project_migrates_and_gains_empty_choices(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")
    assert "schema_version = 12" in text
    old = text.replace("schema_version = 12", "schema_version = 11")
    path.write_text(old, encoding="utf-8")
    table(project, row("hair", 2, [BLACK, NIGHT]))
    old = path.read_text(encoding="utf-8")

    described = project.json("describe", "project")

    assert described["ok"] and described["data"]["ramps"] == [
        {"name": "hair", "length": 2, "rgb": [BLACK, NIGHT], "choices": {}}]
    assert path.read_text(encoding="utf-8") == old  # the file is the Owner's until a writing Command saves it
    project.json("new", "prop", "bench")  # a writing Command that doesn't save kiripix.toml leaves it too
    assert path.read_text(encoding="utf-8") == old


def test_a_version_11_project_with_ramps_reads_its_choices(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8").replace("schema_version = 12", "schema_version = 11"), encoding="utf-8")
    ramps(project)

    shown = project.json("describe", "project")["data"]["ramps"]

    assert shown[0]["choices"] == {"auburn": [BLACK, NIGHT], "blond": [STONE, DUSK]}
    assert shown[1]["choices"] == {"red": [STONE, DUSK]}


def test_a_choice_of_the_wrong_length_or_off_the_palette_is_a_settings_finding(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    good = path.read_text(encoding="utf-8")
    cases = {
        "ramps.choice_length": 'choices = { auburn = [[0, 0, 0]] }',
        "ramps.choice_not_in_palette": 'choices = { auburn = [[0, 0, 0], [1, 2, 3]] }',
        "ramps.choice_name": 'choices = { Auburn = [[0, 0, 0], [29, 43, 83]] }',
    }

    for code, choices in cases.items():
        path.write_text(good, encoding="utf-8")
        ramps(project, choices)
        result = project.json("status", expect=1)
        assert code in codes(result), (code, result["findings"])
        finding = next(f for f in result["findings"] if f["code"] == code)
        assert (finding["fix"] is None) != (finding["owner_action"] is None)
        assert "choices" in finding["position"]["field"]


def test_the_choices_are_in_the_settings_schema(project: Kiripix) -> None:
    schema = json.dumps(project.json("schema")["data"])

    assert "choices" in schema and "npc" in schema


def test_preview_draws_the_stacked_swapped_figure_one_frame_per_direction(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR, "hair=blond")

    result = project.json("preview", NPC, "--stage", "choose")

    data = result["data"]
    image = np.asarray(Image.open(project.cwd / data["path"]).convert("RGBA"))
    assert data["stage"] == "choose" and image.shape[:2] == (data["height"], data["width"])
    sheet = json.loads((project.cwd / "assets" / "character" / "zed" / "work" / "sheet" / "sheet.json").read_text("utf-8"))
    idle = next(c for c in sheet["clips"] if c["name"] == "idle")
    assert data["width"] >= len(idle["directions"]) * sheet["cell"]["width"]
    assert Path(project.cwd / data["path"]).parent.name == "previews"


def test_preview_of_an_npc_that_is_not_built_is_refused(project: Kiripix) -> None:
    built(project)
    project.json("new", "npc", "guard", "--base", BODY)

    result = project.json("preview", NPC, "--stage", "choose", expect=1)

    assert codes(result) == ["preview.not_built"]


def test_run_all_builds_a_wearable_before_the_npc_that_reads_it(project: Kiripix) -> None:
    built(project)
    choose(project, HAIR)
    project.json("set", HAIR, "sheet", "order=40")  # "npc.guard" sorts before "wearable.hair"

    project("run", "--all", "--json")  # the Wearable first, then the NPC; its `export` is not built yet, so the exit code is not 0

    assert stage_state(project, NPC, "choose")["status"] == "done"
    assert npc_json(project)["wearables"] == [{"id": HAIR, "order": 40}]
