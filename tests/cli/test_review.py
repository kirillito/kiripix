"""`override`, `accept` and replay into needs-review (spec §5, §10.3), on the sketch Kind's `draw` and `trace` Stages."""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from conftest import Kiripix, make_demo, make_sketch, save_image, stage_status

RED = (255, 0, 77, 255)
BLUE = (41, 173, 255, 255)
CLEAR = (0, 0, 0, 0)


def journal_lines(folder: Path, stage: str = "trace") -> list[dict[str, Any]]:
    path = folder / "decisions" / f"{stage}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] if path.exists() else []


def pixels(path: Path) -> list[tuple[int, ...]]:
    with Image.open(path) as image:
        return [tuple(p) for p in np.asarray(image.convert("RGBA")).reshape(-1, 4).tolist()]


def painted(project: Kiripix, size: tuple[int, int] = (4, 4)) -> Path:
    """An Override: transparent except for a blue top-left pixel."""
    path = save_image(project.cwd / "fix.png", size, CLEAR)
    with Image.open(path) as image:
        image.putpixel((0, 0), BLUE)
        image.save(path)
    return path


# override


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_override_stores_the_png_by_hash_and_journals_it_on_the_painted_stage(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    drawn = sha256(folder / "work" / "draw" / "draw.png")

    data = project.json("override", "sketch.a", "draw", painted(project).name)["data"]

    stored = project.cwd / data["file"]
    assert stored.parent == folder / "decisions" / "overrides"
    assert stored.read_bytes() == (project.cwd / "fix.png").read_bytes()
    assert data["stage"] == "draw"
    [line] = journal_lines(folder, "draw")
    assert line["decision"] == "override" and line["data"] == {"png": stored.stem}
    assert line["image_hash"] == data["image_hash"] == drawn
    assert journal_lines(folder, "trace") == []


def test_an_override_is_part_of_the_painted_stages_output_for_every_reader(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    project.json("override", "sketch.a", "draw", painted(project).name)

    assert stage_status(project, "sketch.a") == {"draw": "stale", "trace": "stale"}
    project.json("run", "sketch.a")

    assert pixels(folder / "work" / "draw" / "draw.png") == [BLUE] + [RED] * 15
    assert pixels(folder / "work" / "trace" / "trace.png") == [BLUE] + [RED] * 15
    assert stage_status(project, "sketch.a") == {"draw": "done", "trace": "done"}


def test_undoing_an_override_rebuilds_the_unpainted_output(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    project.json("override", "sketch.a", "draw", painted(project).name)
    project.json("run", "sketch.a")

    project.json("undo", "sketch.a", "draw")
    project.json("run", "sketch.a")

    assert pixels(folder / "work" / "trace" / "trace.png") == [RED] * 16


def test_an_override_whose_size_does_not_match_the_stage_output_fails(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")

    result = project.json("override", "sketch.a", "draw", painted(project, (5, 4)).name, expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "override.size_mismatch"
    assert "5x4" in finding["message"] and "4x4" in finding["message"]
    assert journal_lines(folder, "draw") == [] and not (folder / "decisions" / "overrides").exists()


def test_an_override_needs_an_image_stage_its_output_and_a_png(project: Kiripix) -> None:
    make_sketch(project)
    make_demo(project)
    (project.cwd / "fix.txt").write_text("not an image", encoding="utf-8")

    unbuilt = project.json("override", "sketch.a", "draw", painted(project).name, expect=1)
    project.json("run", "sketch.a")
    not_png = project.json("override", "sketch.a", "draw", "fix.txt", expect=1)
    no_image = project.json("override", "demo.a", "copy", "fix.png", expect=1)

    assert unbuilt["findings"][0]["code"] == "override.no_output"
    assert unbuilt["findings"][0]["fix"] == "kiripix run sketch.a draw"
    assert not_png["findings"][0]["code"] == "image.not_png"
    assert no_image["findings"][0]["code"] == "override.not_an_image"


# replay and review


def click(project: Kiripix, x: int = 1, y: int = 2) -> dict[str, Any]:
    document = {"decision": "click", "data": {"x": x, "y": y}}
    data: dict[str, Any] = project.json("decide", "sketch.a", "trace", "--decision", json.dumps(document))["data"]
    return data


def change_input(folder: Path) -> None:
    save_image(folder / "src" / "input.png", colour=BLUE)


def test_a_click_records_the_hash_of_the_image_it_was_made_on(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    project.json("override", "sketch.a", "draw", painted(project).name)
    project.json("run", "sketch.a")

    clicked = click(project)

    [line] = journal_lines(folder)
    assert line["image_hash"] == sha256(folder / "work" / "draw" / "draw.png")  # the painted image, as shown
    assert clicked["current"][-1]["image_hash"] == line["image_hash"]


def test_a_click_before_its_image_exists_fails(project: Kiripix) -> None:
    folder = make_sketch(project)

    document = {"decision": "click", "data": {"x": 1, "y": 2}}
    result = project.json("decide", "sketch.a", "trace", "--decision", json.dumps(document), expect=1)

    assert result["findings"][0]["code"] == "decision.no_image"
    assert result["findings"][0]["fix"] == "kiripix run sketch.a draw"
    assert journal_lines(folder) == []


def test_an_unchanged_input_replays_exactly_and_is_done(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    click(project)
    project.json("run", "sketch.a")
    shutil.rmtree(folder / "work")  # a fresh checkout: work/ isn't committed

    project.json("run", "sketch.a")

    assert stage_status(project, "sketch.a") == {"draw": "done", "trace": "done"}


def test_a_changed_input_under_a_click_runs_the_stage_into_needs_review(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    click(project)
    project.json("run", "sketch.a")
    change_input(folder)

    assert stage_status(project, "sketch.a") == {"draw": "stale", "trace": "stale"}
    result = project.json("run", "sketch.a", expect=3)

    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("draw", "done"),
                                                                              ("trace", "needs-review")]
    assert pixels(folder / "work" / "trace" / "trace.png") == [BLUE] * 16  # it ran, onto the new image
    [finding] = result["findings"]
    assert finding["code"] == "stage.needs_review" and "kiripix accept sketch.a trace" in finding["owner_action"]
    states = {s["stage"]: s for s in project.json("status")["data"]["assets"][0]["stages"]}
    assert states["trace"]["status"] == "needs-review" and "changed image" in states["trace"]["reason"]
    step = project.json("next", "sketch.a")["data"]
    assert step["stage"] == "trace" and step["command"] is None
    assert "kiripix accept sketch.a trace" in step["owner_action"]


def test_an_override_on_a_changed_output_puts_the_painted_stage_in_review(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    project.json("override", "sketch.a", "draw", painted(project).name)
    project.json("run", "sketch.a")
    save_image(folder / "src" / "input.png", colour=CLEAR)

    result = project.json("run", "sketch.a", expect=3)

    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("draw", "needs-review")]
    assert pixels(folder / "work" / "draw" / "draw.png") == [BLUE] + [CLEAR] * 15  # painted onto the new output
    assert stage_status(project, "sketch.a") == {"draw": "needs-review", "trace": "stale"}
    assert "kiripix accept sketch.a draw" in project.json("next", "sketch.a")["data"]["owner_action"]


def test_a_needs_review_stage_stops_the_next_run_too(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    click(project)
    project.json("run", "sketch.a")
    change_input(folder)
    project.json("run", "sketch.a", expect=3)

    again = project.json("run", "sketch.a", expect=3)

    assert [(r["stage"], r["outcome"]) for r in again["data"]["results"]] == [("draw", "skipped"),
                                                                             ("trace", "needs-review")]


# accept


def accept(project: Kiripix, stage: str = "trace", expect: int = 0) -> dict[str, Any]:
    result = project("accept", "sketch.a", stage, "--json", owner=True)
    assert result.code == expect, result.stdout + result.stderr
    return result.json


def test_accept_rerecords_a_click_and_the_next_run_stays_done(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    first = click(project)
    project.json("run", "sketch.a")
    change_input(folder)
    project.json("run", "sketch.a", expect=3)
    before = (folder / "decisions" / "trace.jsonl").read_bytes()

    data = accept(project)["data"]

    assert (folder / "decisions" / "trace.jsonl").read_bytes().startswith(before)  # only appended to
    clicked, rerecorded = journal_lines(folder)
    assert data["recorded"] == [rerecorded["id"]] and rerecorded["replaces"] == first["id"]
    assert rerecorded["data"] == clicked["data"]
    assert rerecorded["image_hash"] == sha256(folder / "work" / "draw" / "draw.png") != clicked["image_hash"]
    assert {s["stage"]: s["status"] for s in data["stages"]} == {"draw": "done", "trace": "done"}
    rerun = project.json("run", "sketch.a")
    assert [r["outcome"] for r in rerun["data"]["results"]] == ["skipped", "skipped"]
    project.json("run", "sketch.a", "trace", "--force")
    output = json.loads((folder / "work" / "trace" / "out.json").read_text(encoding="utf-8"))
    assert output["decisions"] == [{"decision": "click", "data": {"x": 1, "y": 2}}]  # replaced, not doubled


def test_accept_rebases_an_override_onto_the_new_output(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    project.json("override", "sketch.a", "draw", painted(project).name)
    project.json("run", "sketch.a")
    save_image(folder / "src" / "input.png", colour=CLEAR)
    project.json("run", "sketch.a", expect=3)

    accept(project, "draw")

    override, rebased = journal_lines(folder, "draw")
    assert rebased["replaces"] == override["id"] and rebased["data"] == override["data"]
    assert rebased["image_hash"] == sha256(folder / "src" / "input.png")  # the new, unpainted output
    assert stage_status(project, "sketch.a") == {"draw": "done", "trace": "stale"}
    project.json("run", "sketch.a")
    assert stage_status(project, "sketch.a") == {"draw": "done", "trace": "done"}
    assert pixels(folder / "work" / "trace" / "trace.png") == [BLUE] + [CLEAR] * 15


def test_accept_of_a_stage_not_in_review_fails(project: Kiripix) -> None:
    make_sketch(project)
    project.json("run", "sketch.a")

    result = accept(project, expect=1)

    assert result["findings"][0]["code"] == "accept.not_in_review"
    assert result["findings"][0]["fix"] == "kiripix next sketch.a"


def test_accept_resolves_divergent_decisions(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    base = click(project)["id"]
    # What merge=union of two branches leaves: both entries followed `base`.
    lines = journal_lines(folder)
    for suffix, x in (("A", 0), ("B", 3)):
        lines.append({"id": f"01JZZZZZZZZZZZZZZZZZZZZZZ{suffix}", "parent": base, "decision": "click",
                      "data": {"x": x, "y": 0}})
    text = "".join(json.dumps(entry) + "\n" for entry in lines)
    (folder / "decisions" / "trace.jsonl").write_text(text, encoding="utf-8", newline="\n")
    assert stage_status(project, "sketch.a")["trace"] == "needs-review"

    accept(project)

    assert journal_lines(folder)[-1]["accept"] == ["01JZZZZZZZZZZZZZZZZZZZZZZA", "01JZZZZZZZZZZZZZZZZZZZZZZB"]
    project.json("run", "sketch.a")
    assert stage_status(project, "sketch.a") == {"draw": "done", "trace": "done"}


def test_accept_from_a_non_tty_without_the_test_variable_needs_the_owner(project: Kiripix) -> None:
    folder = make_sketch(project)
    project.json("run", "sketch.a")
    click(project)
    project.json("run", "sketch.a")
    change_input(folder)
    project.json("run", "sketch.a", expect=3)
    before = (folder / "decisions" / "trace.jsonl").read_bytes()

    result = project.json("accept", "sketch.a", "trace", expect=3)

    finding = result["findings"][0]
    assert finding["code"] == "owner.required" and finding["fix"] is None and finding["owner_action"]
    assert (folder / "decisions" / "trace.jsonl").read_bytes() == before
    assert stage_status(project, "sketch.a")["trace"] == "needs-review"


def test_accept_is_never_an_mcp_tool(kpx: Kiripix) -> None:
    accept_schema = kpx.json("schema", "accept")["data"]["commands"]["accept"]

    assert accept_schema["kind"] == "owner-only" and accept_schema["mcp"] == "owner-only"
