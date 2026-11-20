"""What the review of held things found in core (ticket 0312): a base's things, one rule for "a thing exists", one current
Variant, unnamed `.glb` materials counted as Blender counts them, and a base's rig checked at `decide`."""

import json
import os
from pathlib import Path
from typing import Any

from conftest import Kiripix, stage_status
from test_character_base import BODY, GUARD, WAVE, body, decide, guard
from test_character_clips import HIT, clip, clips_json, rigged_hero
from test_character_model import HERO
from test_character_render import render_calls
from test_clip_attach import SOCKET, add_thing, attached, held
from test_held_things import thing_file, things


def test_a_character_made_from_a_base_builds_clips_with_the_bases_thing_and_lists_it(project: Kiripix) -> None:
    zed = body(project)
    add_thing(zed, "phone")
    decide(project, BODY, "clip", attached(held("phone"), base=WAVE))
    folder = guard(project)
    for name in ("model", "rig"):
        project.json("run", GUARD, name)

    result = project.json("run", GUARD, "clips")

    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("clips", "done")]
    wave = next(c for c in clips_json(folder)["clips"] if c["name"] == "wave")
    assert wave["attach"] == [{"thing": "phone", "socket": SOCKET}]
    shown = project.json("show", GUARD)["data"]["things"]
    assert [(t["thing"], t["from_base"], t["attached_by"]) for t in shown] == [("phone", True, ["wave"])]
    assert shown[0]["variants"][0]["file"].startswith("assets/character/zed/src/things/phone/")
    assert not (folder / "src" / "things").exists(), "nothing is copied"
    assert "thing phone, current model (base), held by wave" in project("show", GUARD).stdout


def test_the_characters_own_thing_of_the_same_id_wins_the_bases_and_render_draws_the_bases_others(project: Kiripix) -> None:
    zed = body(project)
    add_thing(zed, "phone", b"theirs")
    add_thing(zed, "stick", b"stick")
    decide(project, BODY, "clip", attached(held("phone"), held("stick"), base=WAVE))
    folder = guard(project)
    add_thing(folder, "phone", b"mine")
    (project.cwd / "blender-bones").write_text(json.dumps(["root", SOCKET]), encoding="utf-8")
    for name in ("model", "rig", "clips", "render"):
        project.json("run", GUARD, name)

    shown = {t["thing"]: t for t in project.json("show", GUARD)["data"]["things"]}

    assert [(t["thing"], t["from_base"]) for t in project.json("show", GUARD)["data"]["things"]] == [
        ("phone", False), ("stick", True)], "the base's order, the character's own in the base's place"
    assert shown["phone"]["variants"][0]["file"].startswith("assets/character/guard/")
    [args] = [c["args"] for c in render_calls(project)]
    files = {t["id"]: Path(t["file"]).resolve() for t in args["things"]}
    assert files["phone"].parent == (folder / "src" / "things" / "phone").resolve()
    assert files["stick"].parent == (zed / "src" / "things" / "stick").resolve()


def test_a_re_import_on_the_base_makes_a_based_characters_render_stale_and_draws_the_new_current(project: Kiripix) -> None:
    zed = body(project)
    target = zed / "src" / "things" / "phone"
    target.mkdir(parents=True)
    (target / "aaaa.glb").write_bytes(b"first")
    (target / "bbbb.glb").write_bytes(b"second")  # no journal: the last by name, bbbb, is current
    decide(project, BODY, "clip", attached(held("phone"), base=WAVE))
    guard(project)
    (project.cwd / "blender-bones").write_text(json.dumps(["root", SOCKET]), encoding="utf-8")
    for name in ("model", "rig", "clips", "render"):
        project.json("run", GUARD, name)
    assert stage_status(project, GUARD)["render"] == "done"

    with (zed / "imported.jsonl").open("a", encoding="utf-8", newline="\n") as journal:  # aaaa imported again, now the newest
        journal.write(json.dumps({"schema_version": 1, "file": "src/things/phone/aaaa.glb", "imported_as": "phone.glb"}) + "\n")

    assert stage_status(project, GUARD)["render"] == "stale", "the base's journal is an input (ADR 0012)"
    project.json("run", GUARD, "render")
    args = render_calls(project)[-1]["args"]
    assert [Path(t["file"]).stem for t in args["things"]] == ["aaaa"]
    assert project.json("show", GUARD)["data"]["things"][0]["current"] == "aaaa"


def test_a_stray_file_or_a_sidecar_is_no_thing_at_decide(project: Kiripix) -> None:
    folder = rigged_hero(project)
    stray = folder / "src" / "things" / "note"
    stray.mkdir(parents=True)
    (stray / "readme.txt").write_text("not a mesh", encoding="utf-8")
    sidecar = folder / "src" / "things" / "ghost"
    sidecar.mkdir(parents=True)
    (sidecar / "abcd.materials.json").write_text('{"materials": ["a"]}', encoding="utf-8")

    for thing in ("note", "ghost"):
        refused = clip(project, attached(held(thing), base=HIT), expect=1)
        assert refused["findings"][0]["code"] == "clips.unknown_thing", thing
    assert things(project) == {}

    add_thing(folder, "note")  # a mesh in the folder makes it a thing
    clip(project, attached(held("note"), base=HIT))


def test_two_hand_laid_variants_give_the_same_current_file_in_show_and_render(project: Kiripix) -> None:
    folder = rigged_hero(project)
    (project.cwd / "blender-bones").write_text(json.dumps(["root", SOCKET]), encoding="utf-8")
    target = folder / "src" / "things" / "phone"
    target.mkdir(parents=True)
    (target / "bbbb.glb").write_bytes(b"older by name, newer file")
    (target / "aaaa.glb").write_bytes(b"newer by name, older file")
    now = os.stat(target / "bbbb.glb").st_mtime_ns
    os.utime(target / "aaaa.glb", ns=(now - 5_000_000_000, now - 5_000_000_000))  # aaaa is the older file; no journal
    clip(project, attached(held("phone")) | {"name": "hit", "source": "walk", "start": 0, "end": 6, "fps": 15, "loop": False})
    project.json("run", HERO, "clips")
    project.json("run", HERO, "render")

    [shown] = project.json("show", HERO)["data"]["things"]

    [args] = [c["args"] for c in render_calls(project)]
    assert [Path(t["file"]).stem for t in args["things"]] == [shown["current"]] == ["bbbb"], "the last by name, never by mtime"


def test_a_glb_with_two_unnamed_materials_numbers_both_as_blender_does(project: Kiripix) -> None:
    rigged_hero(project)
    project.json("import", HERO, thing_file(project, "cup.glb", "", ""), "--role", "thing", "--thing", "cup")
    project.json("import", HERO, thing_file(project, "lid.glb", "plain"), "--role", "thing", "--thing", "lid")

    shown = things(project)

    assert [(m["name"], m["number"]) for m in shown["cup"]["materials"]] == [("Material", 1), ("Material.001", 2)]
    assert [(m["name"], m["number"]) for m in shown["lid"]["materials"]] == [("plain", 3)], "the next thing's first follows"


def test_a_bad_socket_on_a_based_character_is_refused_at_decide_before_its_rig_is_built(project: Kiripix) -> None:
    zed = body(project)
    add_thing(zed, "phone")
    guard(project)
    assert stage_status(project, GUARD)["rig"] != "done"

    refused = project.json("decide", GUARD, "clips", "--decision", json.dumps(
        {"decision": "clip", "data": attached({"thing": "phone", "socket": "grip_x"}, base=WAVE)}), expect=1)

    [finding] = refused["findings"]
    assert finding["code"] == "clips.unknown_socket" and "grip_x" in finding["message"] and SOCKET in finding["message"]
    ok: dict[str, Any] = project.json("decide", GUARD, "clips", "--decision", json.dumps(
        {"decision": "clip", "data": attached(held("phone"), base=WAVE)}))
    assert ok["ok"] is True, "the base's thing and a bone of the base's rig are enough"
