"""Ticket 0367: a Stage's Check findings are kept until something the Check reads changes (spec §5, ADR 0005).

The demo Check counts its calls in `.kiripix/check-calls.txt`, which the Check cache doesn't read. The cache holds findings, never a
status, and deleting `.kiripix/` loses nothing but time."""

import json
from pathlib import Path

import pytest

from conftest import Kiripix, make_demo

ASSET = "demo.a"


def calls(project: Kiripix) -> int:
    path = project.cwd / ".kiripix" / "check-calls.txt"
    return len(path.read_text(encoding="utf-8").splitlines()) if path.is_file() else 0


def built(project: Kiripix, text: str = "bad input") -> Path:
    folder = make_demo(project, "a")
    (folder / "src" / "input.txt").write_text(text, encoding="utf-8")
    project.json("run", ASSET, "copy", expect=2 if "bad" in text else 0)
    return folder


def findings(project: Kiripix) -> list[dict[str, object]]:
    found: list[dict[str, object]] = project("check", ASSET, "--json").json["findings"]  # a warning exits 0, an error 2
    return found


def test_a_second_check_does_not_run_the_stages_check_again_and_says_the_same(project: Kiripix) -> None:
    built(project)
    first = findings(project)
    after_first = calls(project)
    assert after_first >= 1

    second = findings(project)

    assert calls(project) == after_first
    assert second == first and first[0]["code"] == "demo.bad_text"


def test_queue_goes_through_the_same_cache(project: Kiripix) -> None:
    built(project)
    project.json("queue")
    after_first = calls(project)

    again = project.json("queue")

    assert calls(project) == after_first
    assert again["data"]["agent_fixable"][0]["fixes"][0]["command"] == f"kiripix set {ASSET} concat sep=-"
    findings(project)  # `check` reads what `queue` kept
    assert calls(project) == after_first


def test_a_rebuild_of_the_stage_runs_the_check_again(project: Kiripix) -> None:
    folder = built(project)
    findings(project)
    kept = calls(project)

    (folder / "src" / "input.txt").write_text("fine", encoding="utf-8")
    project.json("run", ASSET, "copy")
    assert project.json("check", ASSET)["findings"] == []

    assert calls(project) > kept


def test_a_forced_rebuild_with_the_same_inputs_runs_the_check_again(project: Kiripix) -> None:
    built(project)
    findings(project)
    kept = calls(project)
    findings(project)
    assert calls(project) == kept

    project.json("run", ASSET, "copy", "--force", expect=2)
    findings(project)

    assert calls(project) > kept


def test_a_change_to_the_stages_version_runs_the_check_again(project: Kiripix, monkeypatch: pytest.MonkeyPatch) -> None:
    built(project)
    findings(project)
    kept = calls(project)

    monkeypatch.setenv("KIRIPIX_TEST_COPY_VERSION", "2")
    findings(project)

    assert calls(project) > kept


def test_a_change_to_a_file_the_check_reads_in_the_asset_runs_it_again(project: Kiripix) -> None:
    folder = built(project)
    assert findings(project)[0]["code"] == "demo.bad_text"
    kept = calls(project)

    (folder / "src" / "note.txt").write_text("loud", encoding="utf-8")
    now = findings(project)

    assert calls(project) > kept and now[0]["code"] == "demo.loud_note"
    kept = calls(project)
    assert findings(project) == now and calls(project) == kept


def test_a_change_to_a_file_the_check_declares_outside_the_asset_runs_it_again(project: Kiripix) -> None:
    built(project)
    findings(project)
    kept = calls(project)

    (project.cwd / "style-note.txt").write_text("loud", encoding="utf-8")
    now = findings(project)

    assert calls(project) > kept and now[0]["code"] == "demo.loud_style"
    kept = calls(project)
    (project.cwd / "style-note.txt").write_text("quiet", encoding="utf-8")
    assert findings(project)[0]["code"] == "demo.bad_text" and calls(project) > kept


def test_a_change_to_the_settings_runs_the_check_again(project: Kiripix) -> None:
    built(project)
    findings(project)
    kept = calls(project)

    toml = project.cwd / "kiripix.toml"
    text = toml.read_text(encoding="utf-8")
    assert "size = [12, 8]" in text
    toml.write_text(text.replace("size = [12, 8]", "size = [14, 8]", 1), encoding="utf-8")
    findings(project)

    assert calls(project) > kept


def test_the_cache_holds_findings_and_never_a_status(project: Kiripix) -> None:
    built(project)
    findings(project)

    document = json.loads((project.cwd / ".kiripix" / "derived-cache.json").read_text(encoding="utf-8"))

    [name] = [n for n in document if n.startswith("check:")]
    assert name == f"check:{ASSET}:copy"
    stored = json.dumps(document[name][1])
    assert "demo.bad_text" in stored and '"status"' not in stored


def test_an_entry_that_is_not_a_finding_is_a_miss_not_an_error(project: Kiripix) -> None:
    built(project)
    first = findings(project)
    kept = calls(project)
    path = project.cwd / ".kiripix" / "derived-cache.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    name = f"check:{ASSET}:copy"
    document[name][1]["findings"] = [{"code": "demo.bad_text", "no_such_key": 1}]
    path.write_text(json.dumps(document), encoding="utf-8")

    assert findings(project) == first
    assert calls(project) > kept


def test_deleting_the_state_folder_loses_nothing_but_time(project: Kiripix) -> None:
    built(project)
    first = findings(project)
    (project.cwd / ".kiripix" / "derived-cache.json").unlink()
    kept = calls(project)

    assert findings(project) == first
    assert calls(project) > kept


def test_an_output_edited_by_hand_without_a_rebuild_is_a_miss(project: Kiripix) -> None:
    built(project, "fine")
    assert findings(project) == []
    kept = calls(project)
    assert findings(project) == [] and calls(project) == kept

    (project.cwd / "assets" / "demo" / "a" / "work" / "copy" / "out.txt").write_text("bad!", encoding="utf-8")
    now = findings(project)

    assert now[0]["code"] == "demo.bad_text" and calls(project) > kept
