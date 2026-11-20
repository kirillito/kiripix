"""A portrait set's export (ticket 0244, spec §9): `<id>.png` for the neutral and each emotion and `portrait.json` under
`portraits/<name>/`, all in the Manifest, no scene; and the emotion IDs frozen once exported."""

import json
from pathlib import Path
from typing import Any

from conftest import Kiripix
from PIL import Image
from test_export import godot_project, set_target
from test_portrait_stages import PORTRAIT, build, declare, make_set, moved, neutral, with_face

FOLDER = "game/kiripix/portraits/sanjay"
RES = "res://kiripix/portraits/sanjay"
MANIFEST = "game/kiripix/manifest/portrait.sanjay.json"
GAMES = b"the game's own\n"


def exportable_portrait(project: Kiripix) -> Path:
    base = neutral()
    folder = make_set(project, {"happy": with_face(moved(base, 1.01, 2.4, -1.8), 11),
                                "sad": with_face(moved(base, 0.99, -2.2, 1.9), 12)})
    godot_project(project)
    set_target(project)
    build(project, "finish")
    project.json("run", PORTRAIT)
    return folder


def manifest(project: Kiripix) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((project.cwd / MANIFEST).read_text("utf-8"))
    return value


def remove(project: Kiripix, emotion: str, expect: int = 0) -> dict[str, Any]:
    entry = json.dumps({"decision": "emotion_remove", "data": {"id": emotion}})
    return project.json("decide", PORTRAIT, "source", "--decision", entry, expect=expect)


def test_the_stage_leaves_an_image_per_emotion_and_the_record(project: Kiripix) -> None:
    folder = exportable_portrait(project)

    out = folder / "out" / "export"

    assert json.loads((out / "portrait.json").read_text("utf-8")) == {
        "schema_version": 1, "asset": PORTRAIT, "canvas": [192, 240], "anchor": [96, 239], "fallback": "neutral",
        "emotions": [{"id": "neutral", "file": "neutral.png"}, {"id": "happy", "file": "happy.png"},
                     {"id": "sad", "file": "sad.png"}]}
    assert sorted(p.name for p in out.iterdir() if p.name != ".stage.json") == [
        "happy.png", "neutral.png", "portrait.json", "sad.png"]
    assert (out / "neutral.png").read_bytes() == (folder / "work" / "finish" / "finish.png").read_bytes()
    assert (out / "happy.png").read_bytes() == (folder / "work" / "finish" / "emotions" / "happy.png").read_bytes()
    with Image.open(out / "sad.png") as image:
        assert image.size == (192, 240)


def test_export_writes_the_images_and_the_record_lists_the_emotions_and_a_second_export_writes_nothing(project: Kiripix) -> None:
    folder = exportable_portrait(project)

    data = project.json("export", PORTRAIT)["data"]

    files = [f"{RES}/{name}" for name in ("happy.png", "neutral.png", "portrait.json", "sad.png")]
    assert sorted(data["written"]) == files and data["counter"] == 1
    assert (project.cwd / FOLDER / "happy.png").read_bytes() == (folder / "out" / "export" / "happy.png").read_bytes()
    assert (project.cwd / FOLDER / "portrait.json").read_bytes() == (folder / "out" / "export" / "portrait.json").read_bytes()
    assert not list((project.cwd / "game" / "kiripix").glob("**/*.tscn")), "no scene"
    record = manifest(project)
    assert record["asset"] == PORTRAIT and record["exported"] is True and sorted(record["files"]) == files
    assert record["ids"]["emotions"] == ["happy", "sad"]
    before = (project.cwd / MANIFEST).read_bytes()

    again = project.json("export", PORTRAIT)["data"]

    assert again["written"] == [] and again["counter"] == 1 and (project.cwd / MANIFEST).read_bytes() == before
    assert project.json("export", "--all")["data"]["written"] == []


def test_an_exported_emotion_can_not_be_removed_or_renamed_but_a_new_one_can_be_added(project: Kiripix) -> None:
    exportable_portrait(project)
    project.json("export", PORTRAIT)

    refused = remove(project, "sad", expect=1)
    rename = json.dumps({"decision": "emotion_rename", "data": {"id": "happy", "to": "glad"}})
    renamed = project.json("decide", PORTRAIT, "source", "--decision", rename, expect=1)

    for result, emotion in ((refused, "sad"), (renamed, "happy")):
        assert [f["code"] for f in result["findings"]] == ["export.id_frozen"]
        assert f"'{emotion}'" in result["findings"][0]["message"] and result["findings"][0]["owner_action"]
    declare(project, "angry", with_face(moved(neutral(), 1.0, 1.0, 1.0), 13))  # adding is fine
    build(project, "finish")
    project.json("run", PORTRAIT)

    assert project.json("export", PORTRAIT)["data"]["counter"] == 2
    assert manifest(project)["ids"]["emotions"] == ["happy", "sad", "angry"]


def test_a_file_the_game_changed_is_refused_naming_it_and_force_backs_it_up(project: Kiripix) -> None:
    exportable_portrait(project)
    project.json("export", PORTRAIT)
    (project.cwd / FOLDER / "happy.png").write_bytes(GAMES)

    refused = project.json("export", PORTRAIT, expect=3)

    assert refused["findings"][0]["code"] == "export.file_changed" and f"{RES}/happy.png" in refused["findings"][0]["message"]
    assert (project.cwd / FOLDER / "happy.png").read_bytes() == GAMES
    project.json("export", PORTRAIT, "--force")
    assert (project.cwd / FOLDER / "happy.png").read_bytes() != GAMES
    assert list((project.cwd / ".kiripix" / "backups").glob("*/game/kiripix/portraits/sanjay/happy.png"))
