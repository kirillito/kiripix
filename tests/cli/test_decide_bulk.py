"""`decide` with an array, `--brief` on decide, undo and redo, and `describe <kind> --stage` (ticket 0075)."""

import json
from typing import Any

from conftest import Kiripix, make_demo
from test_decisions import current_labels, journal_lines, mark


def write_array(project: Kiripix, labels: list[Any], name: str = "many.json") -> str:
    documents = [json.loads(mark(label)) if isinstance(label, str) else label for label in labels]
    (project.cwd / name).write_text(json.dumps(documents), encoding="utf-8")
    return name


def test_brief_output_does_not_grow_with_the_journal(project: Kiripix) -> None:
    make_demo(project)
    sizes = []
    for index in range(12):
        result = project.json("decide", "demo.a", "choose", "--decision", mark(f"label-{index}"), "--brief")
        sizes.append(len(json.dumps(result["data"])))
        assert "current" not in result["data"] or result["data"]["current"] is None
        assert result["data"]["count"] == index + 1
    assert max(sizes[1:]) - min(sizes[1:]) <= 2  # the first entry has no parent; later ones differ by digits only

    undone = project.json("undo", "demo.a", "choose", "--brief")["data"]
    redone = project.json("redo", "demo.a", "choose", "--brief")["data"]

    assert undone["count"] == 11 and redone["count"] == 12
    assert undone.get("current") is None and redone.get("current") is None


def test_the_default_output_still_lists_the_current_decisions(project: Kiripix) -> None:
    make_demo(project)
    project.json("decide", "demo.a", "choose", "--decision", mark("door"))

    data = project.json("decide", "demo.a", "choose", "--decision", mark("window"))["data"]
    step = project.json("undo", "demo.a", "choose")["data"]

    assert [d["data"]["label"] for d in data["current"]] == ["door", "window"]
    assert data["count"] == 2 and data["ids"] == [data["id"]]
    assert [d["data"]["label"] for d in step["current"]] == ["door"]


def test_an_array_records_one_line_each_in_order_and_replays_like_single_calls(project: Kiripix) -> None:
    folder = make_demo(project)
    labels = [f"label-{index}" for index in range(30)]
    name = write_array(project, labels)

    data = project.json("decide", "demo.a", "choose", "--file", name, "--brief")["data"]

    lines = journal_lines(folder)
    assert [line["data"]["label"] for line in lines] == labels
    assert data["ids"] == [line["id"] for line in lines] and data["count"] == 30
    assert lines[0]["parent"] is None and all(b["parent"] == a["id"] for a, b in zip(lines, lines[1:]))
    assert lines == sorted(lines, key=lambda line: line["id"])
    bulk = current_labels(project, folder)

    other = make_demo(project, "b")
    for label in labels:
        project.json("decide", "demo.b", "choose", "--decision", mark(label), "--brief")
    project.json("run", "demo.b", "copy")
    project.json("run", "demo.b", "choose", "--force")
    output = json.loads((other / "work" / "choose" / "out.json").read_text(encoding="utf-8"))
    assert bulk == [d["data"]["label"] for d in output["decisions"]] == labels


def test_an_array_with_one_invalid_decision_records_nothing_and_names_it(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("decide", "demo.a", "choose", "--decision", mark("first"))
    before = (folder / "decisions" / "choose.jsonl").read_bytes()
    name = write_array(project, ["ok", {"decision": "mark", "data": {"label": "x", "count": "two"}}, "also ok",
                                 {"decision": "pick", "data": {}}])

    result = project.json("decide", "demo.a", "choose", "--file", name, expect=1)

    findings = result["findings"]
    assert [f["code"] for f in findings] == ["decision.invalid", "decision.unknown"]
    assert findings[0]["message"].startswith("[1]") and findings[1]["message"].startswith("[3]")
    assert all((f["fix"] is None) != (f["owner_action"] is None) for f in findings)
    assert (folder / "decisions" / "choose.jsonl").read_bytes() == before


def test_an_array_with_a_malformed_element_or_no_elements_records_nothing(project: Kiripix) -> None:
    folder = make_demo(project)
    (project.cwd / "a.json").write_text(json.dumps([json.loads(mark("ok")), {"nope": 1}]), encoding="utf-8")
    (project.cwd / "b.json").write_text("[]", encoding="utf-8")

    malformed = project.json("decide", "demo.a", "choose", "--file", "a.json", expect=1)
    empty = project.json("decide", "demo.a", "choose", "--file", "b.json", expect=1)

    assert malformed["findings"][0]["code"] == "decide.invalid" and "[1]" in malformed["findings"][0]["message"]
    assert empty["findings"][0]["code"] == "decide.invalid"
    assert journal_lines(folder) == []


def test_undo_after_an_array_undoes_only_its_last_decision(project: Kiripix) -> None:
    folder = make_demo(project)
    name = write_array(project, ["one", "two", "three"])
    ids = project.json("decide", "demo.a", "choose", "--file", name)["data"]["ids"]

    step = project.json("undo", "demo.a", "choose")["data"]

    assert step["target"] == ids[-1]
    assert [d["data"]["label"] for d in step["current"]] == ["one", "two"]
    assert len(journal_lines(folder)) == 4


def test_an_array_leaves_whole_lines_and_no_temporary_files(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("decide", "demo.a", "choose", "--decision", mark("first"))
    project.json("decide", "demo.a", "choose", "--file", write_array(project, ["a", "b"]))

    assert len(journal_lines(folder)) == 3  # journal_lines asserts LF endings and a final newline
    assert sorted(p.name for p in (folder / "decisions").iterdir() if p.suffix == ".tmp" or p.name.startswith(".choose")) == []


def test_describe_one_stage_gives_only_that_stage(project: Kiripix) -> None:
    whole = project.json("describe", "room")["data"]["kinds"][0]
    one = project.json("describe", "room", "--stage", "masks")["data"]["kinds"][0]

    assert [s["name"] for s in one["stages"]] == ["masks"]
    assert one["stages"][0] == next(s for s in whole["stages"] if s["name"] == "masks")
    assert one["recipe"] == whole["recipe"]
    assert len(json.dumps(one)) < len(json.dumps(whole))


def test_describe_an_unknown_stage_lists_the_stages(project: Kiripix) -> None:
    whole = project.json("describe", "room")["data"]["kinds"][0]

    result = project.json("describe", "room", "--stage", "nope", expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "describe.unknown_stage"
    assert all(name in finding["message"] for name in whole["recipe"])
    assert (finding["fix"] is None) != (finding["owner_action"] is None)
