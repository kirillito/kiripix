"""The stage graph: derived status, run, next, history and atomic outputs (ADR 0005)."""

import json
import shutil

from conftest import Kiripix, make_demo, stage_status

ALL_DONE = {"copy": "done", "concat": "done", "hold": "done", "fail": "done", "choose": "done"}


def history(project: Kiripix, name: str = "a") -> list[dict[str, object]]:
    text = (project.cwd / "assets" / "demo" / name / "history.jsonl").read_bytes().decode("utf-8")
    assert "\r" not in text
    return [json.loads(line) for line in text.splitlines()]


def test_a_new_asset_is_todo(project: Kiripix) -> None:
    make_demo(project)

    assert stage_status(project, "demo.a") == {"copy": "todo", "concat": "todo", "hold": "todo", "fail": "todo",
                                                    "choose": "todo"}


def test_run_builds_every_stage_in_order(project: Kiripix) -> None:
    folder = make_demo(project)

    data = project.json("run", "demo.a")["data"]

    assert [(r["stage"], r["outcome"]) for r in data["results"]] == [
        ("copy", "done"), ("concat", "done"), ("hold", "done"), ("fail", "done"),
        ("choose", "done"),
    ]
    assert (folder / "work" / "concat" / "out.txt").read_text(encoding="utf-8") == "input+extra+GIMP Palette"
    assert stage_status(project, "demo.a") == ALL_DONE


def test_run_appends_history(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")

    entries = history(project)

    assert [e["stage"] for e in entries] == ["copy", "concat", "hold", "fail", "choose"]
    concat = entries[1]
    assert concat["outcome"] == "done"
    assert concat["params"] == {"sep": "+"}
    assert isinstance(concat["input_hash"], str) and isinstance(concat["duration_s"], float)


def test_a_done_stage_is_skipped(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")

    data = project.json("run", "demo.a")["data"]

    assert {r["outcome"] for r in data["results"]} == {"skipped"}
    assert len(history(project)) == 5


def test_changing_an_input_makes_the_stage_and_everything_below_stale(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("run", "demo.a")

    (folder / "src" / "extra.txt").write_text("other", encoding="utf-8")

    assert stage_status(project, "demo.a") == {"copy": "done", "concat": "stale", "hold": "stale", "fail": "stale",
                                                    "choose": "done"}
    ran = project.json("run", "demo.a")["data"]["results"]
    assert [r["outcome"] for r in ran] == ["skipped", "done", "done", "done", "skipped"]
    assert stage_status(project, "demo.a") == ALL_DONE


def test_a_same_size_edit_is_seen_through_the_hash_cache(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("run", "demo.a")
    project.json("status")

    (folder / "src" / "input.txt").write_text("INPUT", encoding="utf-8")

    assert stage_status(project, "demo.a")["copy"] == "stale"


def test_a_project_setting_is_an_input(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")

    palette = project.cwd / "style" / "palette.gpl"
    palette.write_text(palette.read_text(encoding="utf-8") + "  1   2   3\textra\n", encoding="utf-8")

    assert stage_status(project, "demo.a") == {"copy": "done", "concat": "stale", "hold": "stale", "fail": "stale",
                                                    "choose": "done"}


def test_a_stage_parameter_is_an_input(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("run", "demo.a")

    asset_toml = folder / "asset.toml"
    asset_toml.write_text(asset_toml.read_text(encoding="utf-8") + '\n[stages.concat]\nsep = "-"\n',
                          encoding="utf-8")

    assert stage_status(project, "demo.a")["concat"] == "stale"
    project.json("run", "demo.a")
    assert (folder / "work" / "concat" / "out.txt").read_text(encoding="utf-8").startswith("input-extra")


def test_an_invalid_stage_parameter_is_reported(project: Kiripix) -> None:
    folder = make_demo(project)
    asset_toml = folder / "asset.toml"
    asset_toml.write_text(asset_toml.read_text(encoding="utf-8") + "\n[stages.concat]\nsep = 3\n", encoding="utf-8")

    finding = project.json("run", "demo.a", expect=1)["findings"][0]

    assert finding["code"] == "config.invalid"
    assert finding["position"]["field"] == "stages.concat.sep"


def test_status_is_never_written_to_committed_files(project: Kiripix) -> None:
    folder = make_demo(project)
    committed = [folder / "asset.toml", project.cwd / "kiripix.toml"]
    before = [path.read_bytes() for path in committed]

    project.json("run", "demo.a")
    project.json("status")

    assert [path.read_bytes() for path in committed] == before


def test_deleting_the_cache_changes_nothing(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")

    shutil.rmtree(project.cwd / ".kiripix")

    assert stage_status(project, "demo.a") == ALL_DONE


def test_a_failure_is_remembered_only_in_the_cache(project: Kiripix) -> None:
    folder = make_demo(project)
    (folder / "src" / "fail.txt").write_text("on purpose", encoding="utf-8")

    result = project.json("run", "demo.a", expect=1)

    assert result["data"]["results"][-1] == {**result["data"]["results"][-1], "stage": "fail", "outcome": "failed",
                                             "message": "on purpose"}
    finding = result["findings"][0]
    assert finding["code"] == "stage.failed" and finding["fix"] == "kiripix run demo.a fail"
    assert stage_status(project, "demo.a")["fail"] == "failed"
    assert history(project)[-1]["outcome"] == "failed"

    shutil.rmtree(project.cwd / ".kiripix")  # a fresh checkout
    assert stage_status(project, "demo.a")["fail"] == "todo"


def test_fixing_the_input_clears_the_failure(project: Kiripix) -> None:
    folder = make_demo(project)
    (folder / "src" / "fail.txt").write_text("on purpose", encoding="utf-8")
    project.json("run", "demo.a", expect=1)

    (folder / "src" / "fail.txt").unlink()

    assert stage_status(project, "demo.a")["fail"] == "todo"
    project.json("run", "demo.a")
    assert stage_status(project, "demo.a")["fail"] == "done"


def test_run_one_stage(project: Kiripix) -> None:
    make_demo(project)

    data = project.json("run", "demo.a", "copy")["data"]

    assert [(r["stage"], r["outcome"]) for r in data["results"]] == [("copy", "done")]
    assert stage_status(project, "demo.a")["concat"] == "todo"


def test_run_one_stage_needs_its_upstream_done(project: Kiripix) -> None:
    make_demo(project)

    finding = project.json("run", "demo.a", "concat", expect=1)["findings"][0]

    assert finding["code"] == "stage.upstream_not_done"
    assert finding["fix"] == "kiripix run demo.a"


def test_force_reruns_a_done_stage(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a")

    data = project.json("run", "demo.a", "copy", "--force")["data"]

    assert data["results"][0]["outcome"] == "done"
    assert len(history(project)) == 6


def test_an_unknown_stage(project: Kiripix) -> None:
    make_demo(project)

    assert project.json("run", "demo.a", "paint", expect=1)["findings"][0]["code"] == "stage.unknown"


def test_a_stage_that_needs_input_stops_the_run_with_exit_3(project: Kiripix) -> None:
    project.json("new", "character", "hero")

    result = project.json("run", "character.hero", expect=3)

    assert result["data"]["results"] == [{**result["data"]["results"][0], "stage": "model", "outcome": "needs-input"}]
    finding = result["findings"][0]
    assert finding["code"] == "stage.needs_input"
    assert finding["fix"] == "kiripix import character.hero <file>" and finding["owner_action"] is None


def test_a_stage_not_built_yet_says_until_when(project: Kiripix) -> None:
    project.json("new", "character", "hero")

    finish = next(s for s in project.json("status", "--kind", "character")["data"]["assets"][0]["stages"]
              if s["stage"] == "finish")

    assert finish == {"stage": "finish", "status": "needs-input",
                      "reason": "the character Stage 'finish' is not implemented until M3"}


def test_status_filters_by_kind(project: Kiripix) -> None:
    make_demo(project)
    project.json("new", "character", "hero")

    assets = project.json("status", "--kind", "character")["data"]["assets"]

    assert [a["asset"] for a in assets] == ["character.hero"]
    assert assets[0]["stages"][0] == {"stage": "model", "status": "needs-input",
                                      "reason": "no Source picked"}


def test_status_with_an_unknown_kind(project: Kiripix) -> None:
    assert project.json("status", "--kind", "dragon", expect=1)["findings"][0]["code"] == "kind.unknown"


def test_status_reports_a_broken_asset_and_still_shows_the_others(project: Kiripix) -> None:
    make_demo(project, "a")
    broken = make_demo(project, "b")
    (broken / "asset.toml").write_text('schema_version = 1\nkind = "demo"\ncolour = "red"\n', encoding="utf-8")

    result = project.json("status", expect=1)

    assert [a["asset"] for a in result["data"]["assets"]] == ["demo.a"]
    assert result["findings"][0]["code"] == "config.unknown_key"


def test_next_returns_a_command_or_an_owner_action(project: Kiripix) -> None:
    make_demo(project)
    project.json("new", "character", "hero")

    demo = project.json("next", "demo.a")["data"]
    character = project.json("next", "character.hero")["data"]
    project.json("run", "demo.a")
    finished = project.json("next", "demo.a")["data"]

    assert demo["stage"] == "copy" and demo["command"] == "kiripix run demo.a" and demo["owner_action"] is None
    assert character["stage"] == "model" and character["command"] == "kiripix import character.hero <file>"
    assert finished["done"] and finished["command"] is None and finished["owner_action"] is None


def test_run_all_runs_every_asset(project: Kiripix) -> None:
    make_demo(project, "a")
    make_demo(project, "b")

    data = project.json("run", "--all")["data"]

    assert {(r["asset"], r["outcome"]) for r in data["results"]} == {("demo.a", "done"), ("demo.b", "done")}


def test_run_all_carries_on_past_an_asset_that_needs_the_owner(project: Kiripix) -> None:
    project.json("new", "character", "hero")
    make_demo(project, "a")

    result = project.json("run", "--all", expect=3)

    assert stage_status(project, "demo.a") == ALL_DONE
    assert result["findings"][0]["code"] == "stage.needs_input"


def test_run_needs_an_asset_or_all(project: Kiripix) -> None:
    assert project.json("run", expect=1)["findings"][0]["code"] == "input.invalid"


def test_progress_streams_on_stderr_and_stdout_stays_one_object(project: Kiripix) -> None:
    make_demo(project)

    result = project("run", "demo.a", "--json", "--progress", "jsonl")

    assert result.code == 0 and result.json["ok"]
    events = [json.loads(line) for line in result.stderr.splitlines()]
    assert {"event", "stage", "done", "total", "message"} <= set(events[0])
    assert ("stage_start", "copy") == (events[0]["event"], events[0]["stage"])
    assert any(e["event"] == "stage_progress" and e["message"] == "held" for e in events)


def _tree(folder: object) -> dict[str, bytes]:
    from pathlib import Path
    root = Path(str(folder))
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_a_stage_sees_its_previous_output_only_on_a_rebuild(project: Kiripix) -> None:
    folder = make_demo(project)
    saw = folder / "saw-previous.txt"

    project.json("run", "demo.a")
    assert saw.read_text(encoding="utf-8") == "none"

    project.json("run", "demo.a", "hold", "--force")
    assert saw.read_text(encoding="utf-8") == "held"  # the first build's out.txt


def test_a_stage_writing_to_previous_does_not_survive_the_swap(project: Kiripix) -> None:
    folder = make_demo(project)
    project.json("run", "demo.a")
    (folder / "poke-previous").write_text("", encoding="utf-8")

    project.json("run", "demo.a", "hold", "--force")

    assert not (folder / "work" / "hold" / "poked.txt").exists()
    assert not [p for p in (folder / "work").iterdir() if p.name.startswith(".tmp")]


def test_an_interrupted_rebuild_leaves_the_old_output_byte_equal(project: Kiripix) -> None:
    from test_locks import wait_for
    folder = make_demo(project)
    project.json("run", "demo.a")
    before = _tree(folder / "work" / "hold")
    (folder / "hold").write_text("", encoding="utf-8")
    process = project.popen("run", "demo.a", "hold", "--force")
    wait_for(folder / "holding")

    process.kill()
    process.wait()

    assert _tree(folder / "work" / "hold") == before
