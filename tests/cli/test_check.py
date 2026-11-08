"""`check` (a Probe) and `preview` (spec §10.5): they look at what is built and write nothing the Project keeps."""

import json
from pathlib import Path

from PIL import Image

from conftest import Kiripix, make_demo, make_sketch, save_image
from test_layers_stage import ROOM as LAYERED, accept, built_room, click, lift
from test_locks import finish, start_holding
from test_room import ROOM, make_room


def _snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
            if p.is_file() and ".kiripix" not in p.relative_to(root).parts}


def _built_room(project: Kiripix, width: int = 480, height: int = 272) -> Path:
    folder = make_room(project)
    project.json("set", ROOM, "brief", f"width={width}", f"height={height}")
    project.json("run", ROOM, "brief", expect=0 if width % 16 == 0 and height % 16 == 0 else 2)
    return folder


# check


def test_check_on_a_room_with_a_bad_brief_exits_2_and_lists_the_finding_with_a_fix(project: Kiripix) -> None:
    _built_room(project, 481, 272)

    result = project.json("check", ROOM, expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "brief.size_not_tiles"
    assert finding["fix"] == f"kiripix set {ROOM} brief width=496 height=272" and finding["owner_action"] is None
    assert finding["position"]["asset"] == ROOM and finding["position"]["stage"] == "brief"
    assert result["ok"] is False and result["data"]["stages"] == [f"{ROOM} brief"]


def test_check_on_a_clean_room_exits_0_with_no_findings(project: Kiripix) -> None:
    _built_room(project)

    result = project.json("check", ROOM)

    assert result["ok"] is True and result["findings"] == []
    assert result["data"]["stages"] == [f"{ROOM} brief"]


def test_check_skips_stages_without_an_output(project: Kiripix) -> None:
    make_room(project)

    result = project.json("check", ROOM)

    assert result["data"]["stages"] == [] and result["findings"] == []


def test_check_writes_nothing_to_the_project(project: Kiripix) -> None:
    _built_room(project, 481, 272)
    before = _snapshot(project.cwd)

    project.json("check", ROOM, expect=2)

    assert _snapshot(project.cwd) == before


def test_check_runs_while_the_asset_lock_is_held(project: Kiripix) -> None:
    make_demo(project)
    holder, folder = start_holding(project)
    try:
        result = project.json("check", "demo.a")

        assert result["ok"] is True
    finally:
        (folder / "hold").unlink(missing_ok=True)
        finish(holder)


def test_a_stage_check_finding_carries_its_pixel_position(project: Kiripix) -> None:
    folder = make_demo(project)
    (folder / "src" / "input.txt").write_text("bad", encoding="utf-8")
    project.json("run", "demo.a", "copy", expect=2)

    finding = project.json("check", "demo.a", expect=2)["findings"][0]

    assert finding["code"] == "demo.bad_text"
    assert finding["position"] == {"asset": "demo.a", "stage": "copy", "file": "out.txt", "line": None, "x": 1,
                                   "y": 2, "width": None, "height": None, "field": None}


def test_check_needs_an_asset_or_all(project: Kiripix) -> None:
    assert project.json("check", expect=1)["findings"][0]["code"] == "input.invalid"
    assert project.json("check", ROOM, "--all", expect=1)["findings"][0]["code"] == "input.invalid"


def test_check_of_an_unknown_asset_is_an_error(project: Kiripix) -> None:
    assert project.json("check", "room.nope", expect=1)["findings"][0]["code"] == "asset.not_found"


# check: out of date


def test_check_names_the_checked_stages_that_are_out_of_date_and_still_exits_0(project: Kiripix) -> None:
    _built_room(project)
    assert project.json("check", ROOM)["data"]["out_of_date"] == []

    project.json("set", ROOM, "brief", "width=496", "height=272")  # the built output is now behind its inputs
    result = project.json("check", ROOM)

    [late] = result["data"]["out_of_date"]
    assert (late["asset"], late["stage"], late["status"]) == (ROOM, "brief", "stale") and late["reason"]
    assert result["ok"] is True and result["findings"] == []
    text = project("check", ROOM)
    assert "1 out of date: brief" in text.stdout


def test_check_all_names_out_of_date_stages_of_every_asset(project: Kiripix) -> None:
    _built_room(project)
    project.json("set", ROOM, "brief", "width=496", "height=272")

    result = project.json("check", "--all")

    assert [(o["asset"], o["stage"], o["status"]) for o in result["data"]["out_of_date"]] == [(ROOM, "brief", "stale")]


def test_check_names_the_built_stages_after_a_layers_stage_in_needs_review(project: Kiripix) -> None:
    built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    accept(project)
    project.json("decide", LAYERED, "place", "--decision",  # a Layer needs a y-sort line or "always above"
                 json.dumps({"decision": "above", "data": {"layer": "lamp", "above": True}}))
    project("run", LAYERED, "--json")  # builds the Stages after layers; reach waits for a Spawn
    before = project.json("check", LAYERED)
    assert before["data"]["out_of_date"] == [] and f"{LAYERED} place" in before["data"]["stages"]

    click(project, "crate", 40, 24)
    lift(project)  # layers is now in needs-review; the Stages after it are built from the accepted lift
    result = project.json("check", LAYERED)

    late = {o["stage"]: o for o in result["data"]["out_of_date"]}
    assert "layers" in late and late["layers"]["status"] == "needs-review"
    assert {"place"} <= set(late) and all(o["status"] != "done" and o["reason"] for o in late.values())
    assert result["ok"] is True and not [f for f in result["findings"] if f["severity"] == "error"]


# check --all


def test_check_all_checks_every_asset_and_lists_each_finding(project: Kiripix) -> None:
    _built_room(project, 481, 272)
    folder = make_demo(project)
    (folder / "src" / "input.txt").write_text("bad", encoding="utf-8")
    project.json("run", "demo.a", "copy", expect=2)

    result = project.json("check", "--all", expect=2)

    assert sorted(result["data"]["assets"]) == ["demo.a", ROOM]
    assert sorted(f["code"] for f in result["findings"]) == ["brief.size_not_tiles", "demo.bad_text"]


def test_check_all_on_a_clean_project_is_ok(project: Kiripix) -> None:
    _built_room(project)

    result = project.json("check", "--all")

    assert result["findings"] == [] and result["data"]["project_checks"] is True


def test_check_all_runs_the_registered_project_checks(project: Kiripix) -> None:
    make_demo(project, "a")
    make_demo(project, "b")

    assert project.json("check", "demo.a")["findings"] == []
    result = project.json("check", "--all", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "demo.too_many" and finding["fix"] is None and finding["owner_action"]


# preview


def _picked_source(project: Kiripix, size: tuple[int, int] = (4, 4)) -> None:
    make_room(project)
    project.json("set", ROOM, "brief", "width=480", "height=272")
    save_image(project.cwd / "made.png", size=size)
    name = project.json("import", ROOM, "made.png")["data"]["variant"]
    project.json("pick", ROOM, name)
    project.json("run", ROOM, "brief")
    project.json("run", ROOM, "source")


def test_preview_of_source_is_the_sources_size_times_the_zoom(project: Kiripix) -> None:
    _picked_source(project, (6, 3))

    data = project.json("preview", ROOM, "--stage", "source", "--zoom", "3")["data"]

    with Image.open(project.cwd / data["path"]) as image:
        assert image.size == (18, 9) and image.convert("RGBA").getpixel((17, 8)) == (255, 0, 77, 255)
    assert data["path"].startswith(".kiripix/previews/") and data["path"].endswith(".png")
    assert (data["width"], data["height"], data["zoom"], data["stage"]) == (18, 9, 3, "source")


def test_preview_without_a_stage_uses_the_last_done_stage_with_an_image(project: Kiripix) -> None:
    _picked_source(project)

    data = project.json("preview", ROOM)["data"]

    assert data["stage"] == "source" and data["zoom"] == 4 and (data["width"], data["height"]) == (16, 16)


def test_preview_of_a_stage_that_is_not_built_says_what_to_run(project: Kiripix) -> None:
    make_room(project)

    finding = project.json("preview", ROOM, "--stage", "source", expect=1)["findings"][0]

    assert finding["code"] == "preview.not_built" and finding["fix"] == f"kiripix run {ROOM} source"


def test_preview_with_nothing_built_says_what_is_next(project: Kiripix) -> None:
    make_room(project)

    finding = project.json("preview", ROOM, expect=1)["findings"][0]

    assert finding["code"] == "preview.nothing_built" and finding["fix"] == f"kiripix next {ROOM}"


def test_preview_of_a_stage_without_an_image_is_refused(project: Kiripix) -> None:
    _built_room(project)

    finding = project.json("preview", ROOM, "--stage", "brief", expect=1)["findings"][0]

    assert finding["code"] == "preview.no_image"


def test_preview_rejects_a_zoom_below_1(project: Kiripix) -> None:
    _picked_source(project)

    assert project.json("preview", ROOM, "--zoom", "0", expect=1)["findings"][0]["code"] == "input.invalid"


def test_preview_overlay_masks_without_masks_says_to_run(project: Kiripix) -> None:
    _picked_source(project)

    finding = project.json("preview", ROOM, "--overlay", "masks", expect=1)["findings"][0]

    assert finding["code"] == "preview.no_masks" and finding["fix"] == f"kiripix run {ROOM}"


def test_preview_overlay_masks_tints_each_mask_over_the_image(project: Kiripix) -> None:
    """The tint on a hand-placed `masks` output; test_masks.py does it with the built Stage (ticket 0016)."""
    _picked_source(project)
    masks = project.cwd / "assets" / "room" / "alley" / "work" / "masks"
    masks.mkdir(parents=True)
    solid = Image.new("1", (4, 4), 0)
    solid.putpixel((1, 2), 1)
    solid.save(masks / "solid.png")
    (masks / ".stage.json").write_text(json.dumps({"stage": "masks", "input_hash": "x"}), encoding="utf-8")

    data = project.json("preview", ROOM, "--overlay", "masks", "--zoom", "2")["data"]

    assert data["masks"] == ["solid"] and data["path"].endswith("room.alley.source.masks.x2.png")
    with Image.open(project.cwd / data["path"]) as image:
        rgba = image.convert("RGBA")
        assert rgba.size == (8, 8)
        assert rgba.getpixel((2, 4)) == rgba.getpixel((3, 5)) == (255, 0, 38, 255)  # half way from (255,0,77) to red
        assert rgba.getpixel((0, 0)) == (255, 0, 77, 255)


def test_preview_works_on_the_sketch_kind(project: Kiripix) -> None:
    make_sketch(project)
    project.json("run", "sketch.a")

    data = project.json("preview", "sketch.a", "--stage", "draw", "--zoom", "1")["data"]

    assert (data["width"], data["height"]) == (4, 4)
