"""The portrait Kind (ticket 0242, spec §6.7): `new portrait`, `[portrait]` in kiripix.toml, the brief, and the `source` Stage's
emotions: `emotion` Decisions, `import --emotion` and `pick --emotion`. The Stages after `source` are 0243."""

import json
import tomllib
from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status
from PIL import Image

PORTRAIT = "portrait.sanjay"


def image(project: Kiripix, name: str, colour: tuple[int, int, int]) -> str:
    Image.new("RGBA", (8, 12), (*colour, 255)).save(project.cwd / name)
    return name


def declare(project: Kiripix, emotion: str, expect: int = 0) -> dict[str, Any]:
    entry = json.dumps({"decision": "emotion", "data": {"id": emotion}})
    return project.json("decide", PORTRAIT, "source", "--decision", entry, expect=expect)


def with_neutral(project: Kiripix, colour: tuple[int, int, int] = (200, 100, 50)) -> str:
    """A portrait with its neutral Source imported and picked; returns the Variant."""
    if not (project.cwd / "assets" / "portrait" / "sanjay").is_dir():
        project.json("new", "portrait", "sanjay")
    variant = project.json("import", PORTRAIT, image(project, "neutral.png", colour))["data"]["variant"]
    project.json("pick", PORTRAIT, variant)
    project.json("run", PORTRAIT, "brief")
    return str(variant)


def emotion_picked(project: Kiripix, emotion: str, colour: tuple[int, int, int]) -> str:
    declare(project, emotion)
    variant = project.json("import", PORTRAIT, image(project, f"{emotion}.png", colour), "--emotion", emotion)["data"]["variant"]
    project.json("pick", PORTRAIT, variant, "--emotion", emotion)
    return str(variant)


def two_emotions(project: Kiripix) -> str:
    neutral = with_neutral(project)
    emotion_picked(project, "happy", (10, 200, 10))
    emotion_picked(project, "angry", (200, 10, 10))
    return neutral


def test_a_set_with_a_neutral_source_and_two_emotions_shows_them_and_builds_source(project: Kiripix) -> None:
    neutral = two_emotions(project)

    shown = project.json("show", PORTRAIT)["data"]
    project.json("run", PORTRAIT, "source")

    assert shown["picked"] == neutral and shown["variants"][0]["name"] == neutral
    assert [e["emotion"] for e in shown["emotions"]] == ["happy", "angry"]
    for emotion in shown["emotions"]:
        assert emotion["picked"] and emotion["made_on"] == neutral and emotion["current"]
        assert [v["name"] for v in emotion["variants"]] == [emotion["picked"]]
        assert emotion["variants"][0]["file"] == f"assets/portrait/sanjay/src/emotions/{emotion['emotion']}/{emotion['picked']}.png"
    assert stage_status(project, PORTRAIT)["source"] == "done"
    work = project.cwd / "assets" / "portrait" / "sanjay" / "work" / "source"
    assert (work / "source.png").is_file() and (work / "emotions" / "happy.png").is_file()
    assert json.loads((work / "emotions.json").read_text("utf-8")) == {
        "schema_version": 1, "neutral": "neutral", "emotions": ["happy", "angry"]}
    assert "emotion happy" in project("show", PORTRAIT).stdout


def test_a_new_neutral_source_puts_every_emotion_in_needs_input(project: Kiripix) -> None:
    with_neutral(project)
    emotion_picked(project, "happy", (10, 200, 10))
    emotion_picked(project, "angry", (200, 10, 10))
    project.json("run", PORTRAIT, "source")

    again = project.json("import", PORTRAIT, image(project, "neutral2.png", (20, 40, 60)))["data"]["variant"]
    project.json("pick", PORTRAIT, again)

    status = stage_status(project, PORTRAIT)
    assert status["source"] == "needs-input"
    shown = project.json("show", PORTRAIT)["data"]
    assert shown["picked"] == again and [e["current"] for e in shown["emotions"]] == [False, False]
    refused = project.json("run", PORTRAIT, "source", expect=3)
    [finding] = refused["findings"]
    assert finding["code"] == "portrait.emotion_unpicked"
    assert "the edit was made on another Source" in finding["message"]
    assert "happy" in finding["owner_action"] and "angry" in finding["owner_action"]

    # remaking the emotions from the new Source clears it
    for emotion, colour in (("happy", (11, 200, 10)), ("angry", (201, 10, 10))):
        variant = project.json("import", PORTRAIT, image(project, f"{emotion}2.png", colour), "--emotion", emotion)["data"]["variant"]
        project.json("pick", PORTRAIT, variant, "--emotion", emotion)
    project.json("run", PORTRAIT, "source")
    assert stage_status(project, PORTRAIT)["source"] == "done"


def test_import_emotion_on_an_undeclared_emotion_fails_with_a_fix_that_declares_it(project: Kiripix) -> None:
    with_neutral(project)

    refused = project.json("import", PORTRAIT, image(project, "sad.png", (1, 2, 3)), "--emotion", "sad", expect=1)

    [finding] = refused["findings"]
    assert finding["code"] == "portrait.emotion_unknown" and finding.get("owner_action") is None
    assert finding["fix"] == f"""kiripix decide {PORTRAIT} source --decision '{json.dumps({"decision": "emotion", "data": {"id": "sad"}})}'"""
    assert not list((project.cwd / "assets" / "portrait" / "sanjay" / "src").glob("emotions/*"))
    project.json("decide", PORTRAIT, "source", "--decision", json.dumps({"decision": "emotion", "data": {"id": "sad"}}))
    project.json("import", PORTRAIT, "sad.png", "--emotion", "sad")


def test_the_neutral_is_no_emotion_and_an_id_is_declared_once(project: Kiripix) -> None:
    with_neutral(project)

    neutral = declare(project, "neutral", expect=1)
    declare(project, "happy")
    twice = declare(project, "happy", expect=1)
    pick = project.json("pick", PORTRAIT, "0123", "--emotion", "neutral", expect=1)
    bad = project.json("import", PORTRAIT, image(project, "x.png", (1, 1, 1)), "--emotion", "Very Sad", expect=1)

    assert [f["code"] for f in neutral["findings"] + twice["findings"] + pick["findings"]] == ["portrait.emotion_duplicate"] * 3
    assert all(f.get("owner_action") or f.get("fix") for f in neutral["findings"] + twice["findings"])
    assert bad["findings"][0]["code"] == "portrait.emotion_unknown" and bad["findings"][0]["owner_action"]
    assert [e["emotion"] for e in project.json("show", PORTRAIT)["data"]["emotions"]] == ["happy"]


def test_an_emotion_with_no_image_is_unpicked_and_names_what_to_do(project: Kiripix) -> None:
    with_neutral(project)
    declare(project, "worried")

    none = project.json("run", PORTRAIT, "source", expect=3)["findings"][0]
    assert none["code"] == "portrait.emotion_unpicked" and "worried" in none["message"]
    assert "--emotion worried" in none["owner_action"]

    first = project.json("import", PORTRAIT, image(project, "w1.png", (5, 5, 5)), "--emotion", "worried")["data"]["variant"]
    lone = project.json("run", PORTRAIT, "source", expect=3)["findings"][0]
    assert lone["fix"] == f"kiripix pick {PORTRAIT} {first} --emotion worried"  # a lone Variant: an agent may pick it

    project.json("import", PORTRAIT, image(project, "w2.png", (6, 6, 6)), "--emotion", "worried")
    several = project.json("run", PORTRAIT, "source", expect=3)["findings"][0]
    assert several["owner_action"].startswith("Pick one of the Variants") and not several.get("fix")  # the Owner's choice
    assert stage_status(project, PORTRAIT)["source"] == "needs-input"


def test_an_emotion_is_renamed_or_removed_before_export_and_keeps_its_image(project: Kiripix) -> None:
    with_neutral(project)
    emotion_picked(project, "happy", (10, 200, 10))
    emotion_picked(project, "angry", (200, 10, 10))
    rename = json.dumps({"decision": "emotion_rename", "data": {"id": "happy", "to": "glad"}})
    remove = json.dumps({"decision": "emotion_remove", "data": {"id": "angry"}})

    project.json("decide", PORTRAIT, "source", "--decision", rename)
    project.json("decide", PORTRAIT, "source", "--decision", remove)
    project.json("run", PORTRAIT, "source")

    shown = project.json("show", PORTRAIT)["data"]
    assert [(e["emotion"], bool(e["picked"])) for e in shown["emotions"]] == [("glad", True)]
    work = project.cwd / "assets" / "portrait" / "sanjay" / "work" / "source" / "emotions"
    assert sorted(p.name for p in work.iterdir()) == ["glad.png"]
    clash = json.dumps({"decision": "emotion_rename", "data": {"id": "glad", "to": "neutral"}})
    assert project.json("decide", PORTRAIT, "source", "--decision", clash, expect=1)["findings"][0]["code"] == "portrait.emotion_duplicate"
    gone = json.dumps({"decision": "emotion_remove", "data": {"id": "nobody"}})
    assert project.json("decide", PORTRAIT, "source", "--decision", gone, expect=1)["findings"][0]["code"] == "portrait.emotion_unknown"


def test_emotion_options_are_for_a_portrait_and_alone(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    image(project, "p.png", (1, 2, 3))
    with_neutral(project)
    declare(project, "happy")

    on_prop = project.json("import", "prop.bench", "p.png", "--emotion", "happy", expect=1)
    mixed = project.json("import", PORTRAIT, "p.png", "--emotion", "happy", "--state", "x", expect=1)
    pick_mixed = project.json("pick", PORTRAIT, "0123", "--emotion", "happy", "--look", "x", expect=1)
    no_variant = project.json("pick", PORTRAIT, "0123", "--emotion", "happy", expect=1)

    assert on_prop["findings"][0]["code"] == "import.emotion_needs_portrait"
    assert mixed["findings"][0]["code"] == "import.emotion_takes_one_image"
    assert pick_mixed["findings"][0]["code"] == "pick.emotion_alone"
    assert no_variant["findings"][0]["code"] == "pick.unknown_variant"
    assert no_variant["findings"][0]["fix"] == f"kiripix import {PORTRAIT} <file> --emotion happy"


def test_pick_emotion_needs_a_picked_neutral_source(project: Kiripix) -> None:
    project.json("new", "portrait", "sanjay")
    declare(project, "happy")
    project.json("import", PORTRAIT, image(project, "h.png", (1, 2, 3)), "--emotion", "happy")

    refused = project.json("pick", PORTRAIT, "0123", "--emotion", "happy", expect=1)

    assert refused["findings"][0]["code"] == "pick.emotion_needs_source"


def test_the_brief_takes_the_projects_canvas_and_anchor_unless_it_sets_them(project: Kiripix) -> None:
    project.json("new", "portrait", "sanjay")
    brief = project.cwd / "assets" / "portrait" / "sanjay" / "work" / "brief" / "brief.json"

    project.json("run", PORTRAIT, "brief")
    assert json.loads(brief.read_text("utf-8")) == {"schema_version": 1, "width": 192, "height": 240, "anchor": [96, 239], "fallback": "neutral"}

    project.json("set", PORTRAIT, "brief", "width=96", "height=128", "anchor_x=10", "fallback=happy")
    project.json("run", PORTRAIT, "brief")
    assert json.loads(brief.read_text("utf-8")) == {"schema_version": 1, "width": 96, "height": 128, "anchor": [10, 127], "fallback": "happy"}

    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8").replace("canvas = [192, 240]", "canvas = [64, 80]\nanchor = [5, 6]"), encoding="utf-8")
    project.json("set", PORTRAIT, "brief", "width=0", "height=0", "anchor_x=-1", "fallback=neutral")
    project.json("run", PORTRAIT, "brief")
    assert json.loads(brief.read_text("utf-8")) == {"schema_version": 1, "width": 64, "height": 80, "anchor": [5, 6], "fallback": "neutral"}


def test_a_canvas_over_the_resolution_an_anchor_off_the_canvas_and_an_unknown_fallback_have_fixes(project: Kiripix) -> None:
    project.json("new", "portrait", "sanjay")
    project.json("set", PORTRAIT, "brief", "width=700", "anchor_y=999", "fallback=sad")

    brief = project.json("run", PORTRAIT, "brief", expect=2)["findings"]

    assert {f["code"] for f in brief} == {"brief.larger_than_resolution", "brief.anchor_outside"}
    assert all(f["fix"].startswith(f"kiripix set {PORTRAIT} brief") for f in brief)
    project.json("set", PORTRAIT, "brief", "width=0", "anchor_y=-1")
    project.json("run", PORTRAIT, "brief")
    with_neutral(project)
    project.json("run", PORTRAIT, "source", expect=2)  # the fallback `sad` names no emotion
    check = project.json("check", PORTRAIT, expect=2)["findings"]
    assert [f["code"] for f in check] == ["portrait.fallback_unknown"]
    assert check[0]["fix"] == f"kiripix set {PORTRAIT} brief fallback=neutral"
    declare(project, "sad")
    emotion_picked_after = project.json("import", PORTRAIT, image(project, "sad.png", (3, 3, 3)), "--emotion", "sad")["data"]
    project.json("pick", PORTRAIT, emotion_picked_after["variant"], "--emotion", "sad")
    project.json("run", PORTRAIT, "source")
    assert project.json("check", PORTRAIT)["findings"] == []


def test_a_project_that_wrote_the_old_canvas_keeps_it(project: Kiripix) -> None:
    """Ticket 0323: the default moved to the game's 192 x 240; a canvas the Owner wrote is the Owner's."""
    path = project.cwd / "kiripix.toml"
    path.write_text(path.read_text("utf-8").replace("canvas = [192, 240]", "canvas = [160, 224]"), encoding="utf-8")
    project.json("new", "portrait", "sanjay")

    project.json("run", PORTRAIT, "brief")

    brief = json.loads((project.cwd / "assets" / "portrait" / "sanjay" / "work" / "brief" / "brief.json").read_text("utf-8"))
    assert (brief["width"], brief["height"], brief["anchor"]) == (160, 224, [80, 223])


def test_the_project_file_at_version_8_reads_with_the_default_portrait_canvas(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8").replace("schema_version = 12", "schema_version = 8")
    lines = [line for line in text.splitlines() if not line.startswith(("[portrait]", "canvas = [192", "# anchor"))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert "portrait" not in tomllib.loads(path.read_text(encoding="utf-8"))

    project.json("new", "portrait", "sanjay")
    project.json("run", PORTRAIT, "brief")

    brief = json.loads((project.cwd / "assets" / "portrait" / "sanjay" / "work" / "brief" / "brief.json").read_text("utf-8"))
    assert (brief["width"], brief["height"]) == (192, 240)  # the default today (0323): the migration writes no canvas
    assert path.read_text(encoding="utf-8").count("schema_version = 8") == 1  # read only: a writing Command migrates the file


def test_an_unknown_portrait_key_or_an_anchor_off_the_canvas_is_an_error(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")

    path.write_text(text.replace("canvas = [192, 240]", "canvas = [192, 240]\nsize = 3"), encoding="utf-8")
    assert project("status", "--json").code == 1
    path.write_text(text.replace("canvas = [192, 240]", "canvas = [192, 240]\nanchor = [192, 0]"), encoding="utf-8")
    assert project("status", "--json").code == 1


def test_new_help_lists_portrait_and_describe_shows_the_recipe(project: Kiripix) -> None:
    assert "portrait" in project("new", "--help").stdout

    kind = project.json("describe", "portrait")["data"]["kinds"][0]

    assert kind["recipe"] == ["brief", "source", "cutout", "register", "fit", "palette", "finish", "export"]
    source = next(s for s in kind["stages"] if s["name"] == "source")
    assert {"pick", "emotion", "emotion_remove", "emotion_rename", "emotion_pick"} <= {d["name"] for d in source["decisions"]}
    assert {"portrait.emotion_unknown", "portrait.emotion_unpicked", "portrait.emotion_duplicate"} <= {
        c["code"] for c in source["checks"]}


def test_the_image_stages_are_built_and_only_export_waits_for_0244(project: Kiripix) -> None:
    two_emotions(project)
    project.json("run", PORTRAIT, "source")

    status = stage_status(project, PORTRAIT)

    assert [status[s] for s in ("brief", "source")] == ["done", "done"]
    assert [status[s] for s in ("cutout", "register", "fit", "palette", "finish")] == ["todo"] * 5
    assert status["export"] == "needs-input"


def test_the_portrait_folder_has_no_status(project: Kiripix) -> None:
    two_emotions(project)
    text = (project.cwd / "assets" / "portrait" / "sanjay" / "asset.toml").read_text("utf-8")

    assert "status" not in text and "done" not in text
    assert Path(project.cwd / "assets" / "portrait" / "sanjay" / "history.jsonl").exists()
