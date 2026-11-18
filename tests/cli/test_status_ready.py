"""Ticket 0233: `status` reads a `todo` Stage whose inputs are all there as work to run, not as a question."""

from conftest import Kiripix, make_demo, stage_status


def test_status_names_the_command_for_a_todo_stage_that_is_ready_and_json_keeps_the_status(project: Kiripix) -> None:
    make_demo(project)

    text = project("status").stdout
    stages = stage_status(project, "demo.a")

    assert stages["copy"] == "todo"
    assert "copy       todo (ready: kiripix run demo.a)" in text
    assert text.count("(ready:") == 1, "only the first open Stage is ready; the later ones wait on it"
    first = project.json("status")["data"]["assets"][0]["stages"][0]
    assert first["status"] == "todo" and "ready" not in str(first), "the JSON keeps the plain status"


def test_status_names_no_command_for_a_stage_that_is_done(project: Kiripix) -> None:
    make_demo(project)
    project.json("run", "demo.a", "copy")

    text = project("status").stdout

    assert stage_status(project, "demo.a")["copy"] == "done"
    assert "copy       done\n" in text or "copy       done  (" in text
    assert "copy       done (ready" not in text
