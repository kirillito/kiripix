"""`kiripix note`: a hand-over note on a Stage, live until the Stage has a newer Decision or an accept (ticket 0326)."""

import json
from pathlib import Path

from conftest import MARK, Kiripix, in_review, make_demo, sketched


def notes_of(project: Kiripix, asset: str, stage: str) -> list[dict[str, object]]:
    stages = project.json("show", asset)["data"]["stages"]
    [found] = [s for s in stages if s["stage"] == stage]
    return list(found["notes"])


def stage_hashes(project: Kiripix, asset: str) -> list[tuple[str, str]]:
    return [(s["stage"], s["status"]) for s in project.json("status")["data"]["assets"][0]["stages"]]


def test_a_note_is_live_after_run_and_not_after_a_decision(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")

    written = project.json("note", "demo.a", "choose", "the bench's solid may be 16 px long")["data"]["note"]
    assert written["live"] is True and written["stage"] == "choose" and written["input_hash"]
    project.json("run", "demo.a", "--force")
    [listed] = notes_of(project, "demo.a", "choose")
    assert listed["id"] == written["id"] and listed["live"] is True and listed["text"].startswith("the bench")

    project.json("decide", "demo.a", "choose", "--decision", MARK)
    assert [n["live"] for n in notes_of(project, "demo.a", "choose")] == [False]
    project.json("note", "demo.a", "choose", "later")
    assert [n["live"] for n in notes_of(project, "demo.a", "choose")] == [False, True]
    assert notes_of(project, "demo.a", "copy") == []


def test_a_note_on_another_stage_is_not_ended_by_a_decision_here(project: Kiripix) -> None:
    make_demo(project)
    project.json("note", "demo.a", "copy", "copy note")

    project.json("decide", "demo.a", "choose", "--decision", MARK)

    assert [n["live"] for n in notes_of(project, "demo.a", "copy")] == [True]


def test_a_note_is_not_live_after_an_accept(project: Kiripix) -> None:
    in_review(project)
    project.json("note", "sketch.a", "draw", "waiting for you")
    assert [n["live"] for n in notes_of(project, "sketch.a", "draw")] == [True]

    project("accept", "sketch.a", "draw", "--json", owner=True)

    assert [n["live"] for n in notes_of(project, "sketch.a", "draw")] == [False]


def test_undo_does_not_reach_a_note(project: Kiripix) -> None:
    make_demo(project)
    project.json("decide", "demo.a", "choose", "--decision", MARK)
    project.json("note", "demo.a", "choose", "kept")

    project.json("undo", "demo.a", "choose")

    [kept] = notes_of(project, "demo.a", "choose")
    assert kept["text"] == "kept" and kept["live"] is True  # an undo isn't a newer Decision: the note stays live
    project.json("redo", "demo.a", "choose")
    assert [n["live"] for n in notes_of(project, "demo.a", "choose")] == [True]
    project.json("undo", "demo.a", "choose")
    project.json("undo", "demo.a", "choose", expect=1)  # the note was never a Decision to undo


def test_the_file_is_append_only_and_a_note_changes_no_status_or_hash(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("run", "demo.a")
    before = stage_hashes(project, "demo.a")
    hash_before = project.json("note", "demo.a", "choose", "one")["data"]["note"]["input_hash"]

    first = (folder / "notes.jsonl").read_bytes()
    hash_after = project.json("note", "demo.a", "choose", "two")["data"]["note"]["input_hash"]
    second = (folder / "notes.jsonl").read_bytes()

    assert stage_hashes(project, "demo.a") == before and hash_before == hash_after
    assert second.startswith(first) and b"\r" not in second
    lines = second.decode("utf-8").splitlines()
    assert len(lines) == 2
    entry = json.loads(lines[0])
    assert set(entry) == {"schema_version", "id", "stage", "text", "input_hash"} and entry["schema_version"] == 1
    assert json.loads(lines[1])["id"] > entry["id"]


def test_a_note_over_2000_characters_is_refused(project: Kiripix) -> None:
    folder = make_demo(project)

    refused = project.json("note", "demo.a", "choose", "x" * 2001, expect=1)

    [finding] = refused["findings"]
    assert finding["code"] == "note.too_long" and finding["fix"] and finding["owner_action"] is None
    assert not (folder / "notes.jsonl").exists()
    assert project.json("note", "demo.a", "choose", "x" * 2000)["ok"] is True


def test_an_unknown_stage_or_empty_text_is_refused(project: Kiripix) -> None:
    make_demo(project)

    assert project.json("note", "demo.a", "nope", "text", expect=1)["ok"] is False
    assert project.json("note", "demo.a", "choose", "  ", expect=1)["findings"][0]["code"] == "note.empty"


def test_an_unknown_key_in_notes_jsonl_is_an_error(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("note", "demo.a", "choose", "ok")
    with (folder / "notes.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps({"schema_version": 1, "id": "Z", "stage": "choose", "text": "t", "input_hash": "h",
                                 "extra": 1}) + "\n")

    result = project.json("show", "demo.a", expect=1)

    assert result["findings"][0]["code"] == "note.invalid"
