"""Pinned Runner calls (spec §5, ADR 0002) and click-to-segment in masks, with the fake Runner: `run` never calls a Runner,
`run --rerun` does and lands in needs-review, and a rebuild uses the committed result."""

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, make_demo, stage_status
from PIL import Image
from test_locks import finish, start_holding
from test_masks import FLOOR, HEIGHT, ROOM, WIDTH, built_room, decide, plate, read_mask
from test_place import findings

RERUN = f"kiripix run {ROOM} masks --rerun"
NOT_RUN = "Runner not run yet"
CHANGED = "Runner input changed"


def click(project: Kiripix, x: int = 30, y: int = 10, positive: bool = True, mask: str = "solid") -> None:
    decide(project, "click", {"x": x, "y": y, "mask": mask, "positive": positive})


def rerun(project: Kiripix, *flags: str, expect: int = 3) -> dict[str, Any]:
    return project.json("run", ROOM, "masks", "--rerun", *flags, expect=expect)


def accept(project: Kiripix, stage: str = "masks") -> None:
    project.json("accept", ROOM, stage, owner=True)


def calls(project: Kiripix) -> list[dict[str, Any]]:
    path = project.cwd / "runner-calls.jsonl"
    return [json.loads(line) for line in path.read_text("utf-8").splitlines()] if path.exists() else []


def pinned(folder: Path) -> list[Path]:
    return sorted((folder / "pinned").glob("*.png"))


def box(top: int, bottom: int, left: int, right: int) -> np.ndarray:
    """A Mask of the room's size with the given rows and columns set, both ends included."""
    expected = np.zeros((HEIGHT, WIDTH), dtype=np.bool_)
    expected[top:bottom + 1, left:right + 1] = True
    return expected


def repick(project: Kiripix, name: str = "source2.png") -> None:
    """A new Source of the same size, picked."""
    image = plate()
    image[0:4, 40:48] = (120, 80, 60, 255)
    Image.fromarray(image, "RGBA").save(project.cwd / name)
    project.json("pick", ROOM, str(project.json("import", ROOM, name)["data"]["variant"]))


# `run` never calls a Runner


def test_a_click_makes_masks_needs_input_and_next_names_the_rerun(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)

    result = project.json("run", ROOM, expect=3)

    assert calls(project) == [] and pinned(folder) == []
    assert stage_status(project, ROOM)["masks"] == "needs-input"
    assert result["data"]["results"][-1]["outcome"] == "needs-input" and result["data"]["results"][-1]["message"] == NOT_RUN
    [finding] = findings(result, "stage.needs_input")
    assert finding["fix"] == RERUN and finding["owner_action"] is None
    advice = project.json("next", ROOM)["data"]
    assert (advice["stage"], advice["status"], advice["reason"], advice["command"]) == ("masks", "needs-input", NOT_RUN,
                                                                                        RERUN)


# the acceptance path


def test_rerun_pins_a_result_that_lands_in_needs_review_and_accept_makes_it_done(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)

    result = rerun(project)

    assert len(calls(project)) == 1 and len(pinned(folder)) == 1
    assert stage_status(project, ROOM)["masks"] == "needs-review"
    assert result["data"]["results"][-1]["outcome"] == "needs-review"
    [finding] = findings(result, "stage.needs_review")
    assert finding["fix"] is None and f"kiripix accept {ROOM} masks" in finding["owner_action"]
    # The room is 48 wide, so the fake's square reaches 6 px around the click's Source pixel.
    assert (read_mask(folder) == box(4, 16, 24, 36)).all()

    accept(project)

    assert stage_status(project, ROOM)["masks"] == "done"
    assert len(calls(project)) == 1


def test_a_plain_run_after_deleting_work_rebuilds_from_the_pinned_result(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)
    project.json("run", ROOM, expect=3)  # on down to reach, which has no Spawn or Exit
    shutil.rmtree(folder / "work")

    project.json("run", ROOM, expect=3)

    assert len(calls(project)) == 1, "a rebuild never calls the Runner"
    assert stage_status(project, ROOM)["masks"] == "done"
    assert (read_mask(folder) == box(4, 16, 24, 36)).all()


def test_changing_the_source_makes_masks_needs_input_with_runner_input_changed(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)

    repick(project)
    result = project.json("run", ROOM, expect=3)

    assert stage_status(project, ROOM)["masks"] == "needs-input"
    assert result["data"]["results"][-1]["message"] == CHANGED
    advice = project.json("next", ROOM)["data"]
    assert advice["reason"] == CHANGED and advice["command"] == RERUN
    assert len(calls(project)) == 1

    rerun(project)
    assert stage_status(project, ROOM)["masks"] == "needs-review"
    assert len(calls(project)) == 2 and len(pinned(folder)) == 2
    accept(project)
    assert stage_status(project, ROOM)["masks"] == "done"


def test_other_weights_for_the_runner_make_masks_needs_input_with_runner_input_changed(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)

    (project.cwd / "fake-weights-v2").write_text("", encoding="utf-8")

    advice = project.json("next", ROOM)["data"]
    assert (advice["status"], advice["reason"], advice["command"]) == ("needs-input", CHANGED, RERUN)
    rerun(project)
    assert stage_status(project, ROOM)["masks"] == "needs-review" and len(pinned(folder)) == 2
    accept(project)
    assert stage_status(project, ROOM)["masks"] == "done"


def test_a_click_pinned_by_another_runner_is_input_changed(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)
    [path] = pinned(folder)
    record = json.loads(path.with_suffix(".json").read_text("utf-8"))
    path.with_suffix(".json").write_text(json.dumps({**record, "runner": "an-older-segmenter"}), "utf-8")
    path.unlink()

    assert project.json("next", ROOM)["data"]["reason"] == CHANGED


def test_a_rerun_with_nothing_stale_calls_no_runner_and_needs_no_review(project: Kiripix) -> None:
    built_room(project)
    click(project)
    rerun(project)
    accept(project)

    project.json("run", ROOM, "masks", "--rerun")

    assert len(calls(project)) == 1 and stage_status(project, ROOM)["masks"] == "done"


def test_a_rerun_that_makes_the_result_already_accepted_says_so(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)
    shutil.rmtree(folder / "pinned")

    result = project.json("run", ROOM, "masks", "--rerun", "--cpu")

    assert len(calls(project)) == 2 and len(pinned(folder)) == 1
    [row] = result["data"]["results"]
    assert row["outcome"] == "skipped" and "same result" in row["message"]
    assert stage_status(project, ROOM)["masks"] == "done"


def test_rerun_works_at_every_scope(project: Kiripix) -> None:
    built_room(project)
    click(project)

    project.json("run", ROOM, "--rerun", expect=3)
    assert len(calls(project)) == 1 and stage_status(project, ROOM)["masks"] == "needs-review"

    click(project, 10, 20)
    project.json("run", "--all", "--rerun", expect=3)
    assert len(calls(project)) == 2 and stage_status(project, ROOM)["masks"] == "needs-review"


# what a call is


def test_clicks_map_from_the_target_grid_to_the_source_and_the_mask_maps_back(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", f"width={WIDTH}", f"height={HEIGHT}")
    project.json("set", ROOM, "fit", "scale=2")
    Image.fromarray(np.repeat(np.repeat(plate(), 2, axis=0), 2, axis=1), "RGBA").save(project.cwd / "source.png")
    project.json("pick", ROOM, str(project.json("import", ROOM, "source.png")["data"]["variant"]))
    project.json("run", ROOM, expect=3)
    folder = project.cwd / "assets" / "room" / "alley"
    click(project, 10, 5)

    rerun(project)

    # Target pixel (10, 5) covers Source x 20 to 21 and y 10 to 11, with its centre at (21, 11).
    assert calls(project)[0]["params"]["points"] == [[21.0, 11.0, True]]
    # The Source is 96 wide, so the square reaches 12 px: Source x 9 to 33, y 0 to 23. A target pixel is set when at
    # least half its Source pixels are, which takes in x 4 (Source 8 and 9).
    assert (read_mask(folder) == box(0, 11, 4, 16)).all()


def test_a_click_on_a_cropped_room_is_sent_at_the_source_point_inside_the_crop(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", f"width={WIDTH}", f"height={HEIGHT}")
    project.json("set", ROOM, "fit", "mode=downscale", "offset_y=8")
    source = np.zeros((80, 96, 4), dtype=np.uint8)  # scale 2 on both axes; 16 spare rows, 8 of them above the crop
    source[8:72] = np.repeat(np.repeat(plate(), 2, axis=0), 2, axis=1)
    source[:8] = source[72:] = (1, 2, 3, 255)
    Image.fromarray(source, "RGBA").save(project.cwd / "source.png")
    project.json("pick", ROOM, str(project.json("import", ROOM, "source.png")["data"]["variant"]))
    project.json("run", ROOM, expect=3)
    folder = project.cwd / "assets" / "room" / "alley"
    click(project, 10, 5)

    rerun(project)

    # Target pixel (10, 5) covers Source x 20 to 21 and y 8 + 10 to 8 + 11, so its centre is (21, 19).
    assert calls(project)[0]["params"]["points"] == [[21.0, 19.0, True]]
    assert read_mask(folder).shape == (HEIGHT, WIDTH)


def test_a_large_source_is_capped_for_the_runner_and_its_mask_still_maps_to_the_target(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    project.json("set", ROOM, "brief", f"width={WIDTH}", f"height={HEIGHT}")
    project.json("set", ROOM, "fit", "mode=downscale")
    Image.new("RGBA", (1600, 1024), FLOOR).save(project.cwd / "source.png")
    project.json("pick", ROOM, str(project.json("import", ROOM, "source.png")["data"]["variant"]))
    project.json("run", ROOM, expect=3)
    folder = project.cwd / "assets" / "room" / "alley"
    click(project)

    rerun(project)

    [path] = pinned(folder)
    with Image.open(path) as image:
        assert image.mode == "1" and max(image.size) == calls(project)[0]["params"]["max_size"] == 1536
    solid = read_mask(folder)
    assert solid[5, 25] and solid[15, 35] and not solid[2, 30] and not solid[10, 20]


def test_a_positive_click_is_its_own_call_so_a_new_one_keeps_the_earlier_result(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, 10, 8)
    rerun(project)

    click(project, 38, 24)
    assert stage_status(project, ROOM)["masks"] == "needs-input"
    assert project.json("next", ROOM)["data"]["reason"] == NOT_RUN
    rerun(project)

    assert len(calls(project)) == 2 and len(pinned(folder)) == 2
    assert (read_mask(folder) == (box(2, 14, 4, 16) | box(18, 30, 32, 44))).all()


def test_a_negative_click_in_the_overlap_of_two_positive_clicks_takes_it_away_and_a_later_positive_adds_it_back(
        project: Kiripix) -> None:
    folder = built_room(project)
    click(project, 28, 16)
    click(project, 34, 16)
    click(project, 31, 16, positive=False)

    rerun(project)

    # Three calls, each a lone point: the negative click is its own call, segmented as a positive click would be.
    assert [c["params"]["points"] for c in calls(project)] == [[[28.5, 16.5, True]], [[34.5, 16.5, True]],
                                                                [[31.5, 16.5, True]]]
    one, two, middle = box(10, 22, 22, 34), box(10, 22, 28, 40), box(10, 22, 25, 37)
    assert (read_mask(folder) == ((one | two) & ~middle)).all()
    assert not read_mask(folder)[16, 31]
    accept(project)

    click(project, 31, 16)
    project.json("run", ROOM, "masks")  # the same call as the negative click's: pinned already

    assert len(calls(project)) == 3
    assert (read_mask(folder) == ((one | two) & ~middle) | middle).all()


def test_a_negative_click_takes_away_from_a_flood_and_a_brush_stroke(project: Kiripix) -> None:
    folder = built_room(project)
    decide(project, "flood", {"x": 30, "y": 10, "mask": "solid"})  # the rug: rows 8-13, columns 24-35
    decide(project, "brush", {"mask": "solid", "radius": 0, "points": [[40, 4], [41, 4]], "erase": False})
    click(project, 28, 10, positive=False)  # the fake's square: rows 4-16, columns 22-34

    rerun(project)

    assert len(calls(project)) == 1
    expected = box(8, 13, 24, 35) & ~box(4, 16, 22, 34)
    expected[4, 40] = expected[4, 41] = True
    assert (read_mask(folder) == expected).all()
    click(project, 40, 4, positive=False)
    rerun(project)
    expected[4, 40] = expected[4, 41] = False
    expected &= ~box(0, 10, 34, 46)  # the fake's square around (40, 4), which also reaches the rug's last column
    assert (read_mask(folder) == expected).all()


def test_a_negative_click_at_the_pixel_of_a_positive_click_reuses_its_pinned_result(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, 30, 10)
    rerun(project)
    accept(project)

    click(project, 30, 10, positive=False)
    project.json("run", ROOM, "masks")

    assert len(calls(project)) == 1 and len(pinned(folder)) == 1
    assert stage_status(project, ROOM)["masks"] == "done"
    assert not read_mask(folder).any(), "the same segment, taken away again"


def test_undo_of_a_click_needs_no_rerun_and_redo_finds_its_pin_again(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)

    project.json("undo", ROOM, "masks")
    project.json("run", ROOM, "masks")
    assert not read_mask(folder).any() and stage_status(project, ROOM)["masks"] == "done"

    project.json("redo", ROOM, "masks")
    project.json("run", ROOM, "masks")
    assert (read_mask(folder) == box(4, 16, 24, 36)).all() and len(calls(project)) == 1
    assert stage_status(project, ROOM)["masks"] == "done"


def test_a_deterministic_parameter_changes_without_rerunning_the_runner(project: Kiripix) -> None:
    built_room(project)
    click(project)
    rerun(project)
    accept(project)

    project.json("set", ROOM, "masks", "snap_cell=8")
    assert stage_status(project, ROOM)["masks"] == "stale"
    project.json("run", ROOM, "masks")

    assert len(calls(project)) == 1 and stage_status(project, ROOM)["masks"] == "done"


def test_a_changed_pinned_result_makes_masks_stale(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)
    assert stage_status(project, ROOM)["masks"] == "done"

    [path] = pinned(folder)
    with Image.open(path) as image:
        Image.new("1", image.size, 1).save(path)

    assert stage_status(project, ROOM)["masks"] == "stale"

    project.json("run", ROOM, "masks", expect=3)

    assert stage_status(project, ROOM)["masks"] == "needs-review", "the Owner accepted another result than this one"
    assert read_mask(folder).all()


def test_accepting_a_divergent_journal_does_not_accept_a_result_not_made_yet(project: Kiripix) -> None:
    folder = built_room(project)
    base = decide(project, "brush", {"mask": "solid", "erase": False, "radius": 0, "points": [[1, 1]]})["data"]["id"]
    # What merge=union of two branches leaves: both entries followed `base`.
    journal = folder / "decisions" / "masks.jsonl"
    for suffix, x in (("A", 10), ("B", 38)):
        entry = {"id": f"01JZZZZZZZZZZZZZZZZZZZZZZ{suffix}", "parent": base, "decision": "click",
                 "data": {"x": x, "y": 8, "mask": "solid", "positive": True}}
        with journal.open("a", encoding="utf-8", newline="\n") as lines:
            lines.write(json.dumps(entry) + "\n")
    assert stage_status(project, ROOM)["masks"] == "needs-review"

    accept(project)
    assert stage_status(project, ROOM)["masks"] == "needs-input"

    rerun(project)

    assert stage_status(project, ROOM)["masks"] == "needs-review"
    accept(project)
    assert stage_status(project, ROOM)["masks"] == "done"


def test_a_pin_record_a_merge_broke_does_not_stop_the_status(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    (folder / "pinned").mkdir()
    (folder / "pinned" / "broken.json").write_text("<<<<<<< ours\n", encoding="utf-8")

    assert project.json("next", ROOM)["data"]["reason"] == NOT_RUN


def test_a_deleted_pinned_result_is_input_changed_when_its_record_is_left_and_not_run_when_it_is_not(
        project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)

    [path] = pinned(folder)
    path.unlink()
    assert project.json("next", ROOM)["data"]["reason"] == CHANGED

    path.with_suffix(".json").unlink()
    assert project.json("next", ROOM)["data"]["reason"] == NOT_RUN


def test_the_pin_record_holds_what_made_the_result_and_the_key_ignores_the_device(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project, "--cpu")
    [path] = pinned(folder)
    record = json.loads(path.with_suffix(".json").read_text("utf-8"))

    assert record["schema_version"] == 2 and record["result_hash"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert record["key"] == path.stem and record["stage"] == "masks" and record["runner"] == "sam2.1-small"
    assert record["device"] == "cpu" and record["licence"] == "test"
    assert record["decisions"] == [{"x": 30, "y": 10, "positive": True}]
    assert len(record["weights_hash"]) == len(record["image_hash"]) == 64

    shutil.rmtree(folder / "pinned")
    rerun(project)
    assert pinned(folder) == [path], "the same inputs on another device give the same key"


def test_every_runner_call_is_in_the_history(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)

    rerun(project)

    entries = [json.loads(line) for line in (folder / "history.jsonl").read_text("utf-8").splitlines()]
    [entry] = [e for e in entries if "runner" in e]
    assert entry["runner"] == "sam2.1-small" and entry["stage"] == "masks" and entry["outcome"] == "done"
    assert entry["key"] == pinned(folder)[0].stem and "params" not in entry, "the params are in pinned/<key>.json"
    assert entry["time"] and entry["device"] == "cuda"


# refusals


def test_a_negative_click_with_nothing_before_it_is_allowed(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, positive=False)

    assert project.json("next", ROOM)["data"]["reason"] == NOT_RUN  # a Runner call is wanted, not the Owner's input
    rerun(project)

    assert len(calls(project)) == 1 and not read_mask(folder).any()


def test_a_click_outside_the_plate_needs_the_owner(project: Kiripix) -> None:
    built_room(project)
    click(project, 99, 0)

    rerun(project)

    assert calls(project) == []
    advice = project.json("next", ROOM)["data"]
    assert "outside" in advice["reason"] and f"kiripix undo {ROOM} masks" in advice["owner_action"]


def test_a_runner_failure_fails_the_run_and_pins_nothing(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    (project.cwd / "runner-fails").write_text("", encoding="utf-8")

    result = rerun(project, expect=1)

    [finding] = findings(result, "stage.failed")
    assert "told to fail" in finding["message"] and finding["fix"] == RERUN
    assert pinned(folder) == [] and stage_status(project, ROOM)["masks"] == "needs-input"


def test_weights_that_will_not_load_fail_the_run_rather_than_kiripix(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    weights = project.cwd / ".kiripix" / "weights" / "sam2.1-small"
    weights.mkdir(parents=True)
    for name in ("vision_encoder.onnx", "vision_encoder.onnx_data", "prompt_encoder_mask_decoder.onnx",
                 "prompt_encoder_mask_decoder.onnx_data"):
        (weights / name).write_text("not weights", encoding="utf-8")

    result = project.json("run", ROOM, "masks", "--rerun", "--cpu", expect=1, test_recipes=False)

    [finding] = findings(result, "stage.failed")
    assert "can't load SAM 2" in finding["message"] and finding["fix"] == RERUN
    assert pinned(folder) == []


# the GPU lock


def test_a_runner_needs_the_gpu_lock_unless_it_runs_on_the_cpu(project: Kiripix) -> None:
    built_room(project)
    click(project)
    make_demo(project)
    process, holder = start_holding(project)
    try:
        assert rerun(project, expect=4)["data"]["holder"]["lock"] == "gpu"
        assert calls(project) == []

        rerun(project, "--cpu")
        assert calls(project)[0]["device"] == "cpu"
    finally:
        (holder / "hold").unlink()
    assert finish(process).code == 0


def test_describe_says_masks_uses_the_gpu(kpx: Kiripix) -> None:
    room = kpx.json("describe", "room")["data"]["kinds"][0]

    assert next(s for s in room["stages"] if s["name"] == "masks")["gpu"]


# a GPU left unused


def test_a_runner_that_fell_back_to_the_cpu_says_so_once_with_the_fix(project: Kiripix) -> None:
    built_room(project)
    click(project, 10, 8)
    click(project, 38, 24)
    (project.cwd / "runner-no-gpu").write_text("", encoding="utf-8")

    [finding] = findings(rerun(project), "runner.gpu_unused")

    assert finding["severity"] == "warning" and finding["fix"] == "uv sync" and "GPU" in finding["message"]


def test_a_runner_on_the_gpu_or_asked_for_the_cpu_says_nothing(project: Kiripix) -> None:
    built_room(project)
    click(project, 10, 8)
    assert findings(rerun(project), "runner.gpu_unused") == []

    click(project, 38, 24)
    (project.cwd / "runner-no-gpu").write_text("", encoding="utf-8")
    assert findings(rerun(project, "--cpu"), "runner.gpu_unused") == []


# kiripix runners


def test_weights_are_downloaded_on_first_use_with_their_hash_and_licence_recorded(project: Kiripix) -> None:
    built_room(project)
    click(project)
    weights = project.cwd / ".kiripix" / "weights" / "sam2.1-small"
    assert not weights.exists()

    rerun(project)

    assert (weights / "fake_weights.bin").is_file()
    record = json.loads((weights / "weights.json").read_text("utf-8"))
    assert record["runner"] == "sam2.1-small" and record["licence"] == "test" and len(record["weights_hash"]) == 64


def test_runners_list_pull_and_rm(project: Kiripix) -> None:
    def row() -> dict[str, Any]:
        rows = project.json("runners", "list")["data"]["runners"]
        found: dict[str, Any] = next(r for r in rows if r["id"] == "sam2.1-small")
        return found

    assert not row()["pulled"] and row()["licence"] == "test" and row()["size"] > 0

    assert project.json("runners", "pull", "sam2.1-small")["data"]["downloaded"] == ["fake_weights.bin"]
    assert row()["pulled"]
    assert project.json("runners", "pull", "sam2.1-small")["data"]["downloaded"] == []

    assert project.json("runners", "rm", "sam2.1-small")["data"]["removed"] is True
    assert not row()["pulled"]
    assert project.json("runners", "rm", "sam2.1-small")["data"]["removed"] is False


def test_runners_rm_waits_for_the_gpu_lock_like_anything_that_could_be_using_the_weights(project: Kiripix) -> None:
    project.json("runners", "pull", "sam2.1-small")
    make_demo(project)
    process, holder = start_holding(project)
    try:
        assert project.json("runners", "rm", "sam2.1-small", expect=4)["data"]["holder"]["lock"] == "gpu"
    finally:
        (holder / "hold").unlink()
    assert finish(process).code == 0
    assert (project.cwd / ".kiripix" / "weights" / "sam2.1-small" / "fake_weights.bin").is_file()


def test_the_real_runner_is_listed_with_its_licence_without_downloading_anything(project: Kiripix) -> None:
    rows = project.json("runners", "list", test_recipes=False)["data"]["runners"]

    [sam] = [r for r in rows if r["id"] == "sam2.1-small"]
    assert sam["licence"] == "Apache-2.0" and sam["size"] > 100_000_000 and not sam["pulled"]
    assert not (project.cwd / ".kiripix" / "weights").exists()


def test_a_download_that_fails_its_hash_keeps_nothing(project: Kiripix) -> None:
    result = project.json("runners", "pull", "fake.tampered", expect=1)

    [finding] = result["findings"]
    assert finding["code"] == "runner.download_failed" and "expected" in finding["message"]
    assert finding["fix"] == "kiripix runners pull fake.tampered"
    folder = project.cwd / ".kiripix" / "weights" / "fake.tampered"
    assert not list(folder.iterdir())


def test_an_unknown_runner_lists_where_to_look(project: Kiripix) -> None:
    [finding] = project.json("runners", "pull", "sam9", expect=1)["findings"]

    assert finding["code"] == "runner.unknown" and finding["fix"] == "kiripix runners list"


# the time a Runner takes is in the Stage's duration (ticket 0089)


def masks_result(result: dict[str, Any]) -> dict[str, Any]:
    [found] = [r for r in result["data"]["results"] if r["stage"] == "masks"]
    return found


def test_a_stages_duration_covers_its_runner_load_and_calls(project: Kiripix) -> None:
    built_room(project)
    click(project)
    (project.cwd / "runner-load-seconds").write_text("0.4", encoding="utf-8")
    (project.cwd / "runner-call-seconds").write_text("0.3", encoding="utf-8")

    result = rerun(project)

    assert masks_result(result)["duration_s"] >= 0.7


def test_a_history_entry_has_load_s_only_for_the_call_that_loaded_the_runner(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    click(project, x=20, y=12)
    (project.cwd / "runner-load-seconds").write_text("0.4", encoding="utf-8")
    (project.cwd / "runner-call-seconds").write_text("0.2", encoding="utf-8")

    rerun(project)

    entries = [json.loads(line) for line in (folder / "history.jsonl").read_text("utf-8").splitlines()]
    first, second = [e for e in entries if "runner" in e]
    assert first["load_s"] >= 0.4 and "load_s" not in second, "one load serves both calls"
    assert first["duration_s"] >= 0.2 and first["duration_s"] < first["load_s"] + 0.2, "duration_s is the call alone"
    assert second["duration_s"] >= 0.2


def test_a_pinned_rebuild_makes_no_call_so_its_duration_is_the_stages_own_work(project: Kiripix) -> None:
    folder = built_room(project)
    click(project)
    rerun(project)
    accept(project)
    project.json("run", ROOM, expect=3)
    (project.cwd / "runner-load-seconds").write_text("5", encoding="utf-8")
    (project.cwd / "runner-call-seconds").write_text("5", encoding="utf-8")
    shutil.rmtree(folder / "work")

    result = project.json("run", ROOM, expect=3)

    assert len(calls(project)) == 1
    assert masks_result(result)["duration_s"] < 5
