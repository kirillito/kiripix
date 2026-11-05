"""The prop Recipe from brief to palette (ticket 0050, spec §6.2, ADR 0004): chroma key and matting on the full-size Source,
the fit and palette Stages with binary alpha, and the Checks, on small fixture images with the fake matter."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_matter import calls, pinned
from test_palette import palette_colours
from test_fit import read

PROP = "prop.bench"
KEY = (0, 255, 0)
SUBJECT = (250, 10, 70)  # near the palette's red, and on no palette
SIZE, TARGET = 32, 8  # a 32 x 32 Source, fitted 4:1 to the 8 x 8 brief


def source_image(size: int = SIZE) -> np.ndarray:
    """The key colour with a subject in the middle half."""
    rgba = np.full((size, size, 4), 255, dtype=np.uint8)
    rgba[..., :3] = KEY
    quarter = size // 4
    rgba[quarter:size - quarter, quarter:size - quarter, :3] = SUBJECT
    return rgba


def built_prop(project: Kiripix, source: np.ndarray | None = None, **fit: str) -> Path:
    """A prop with an 8 x 8 brief and `source` picked, fitted at scale 4 (flat areas give grid detection nothing)."""
    project.json("new", "prop", "bench")
    project.json("set", PROP, "brief", f"width={TARGET}", f"height={TARGET}")
    project.json("set", PROP, "fit", "scale=4", *[f"{k}={v}" for k, v in fit.items()])
    Image.fromarray(source_image() if source is None else source, "RGBA").save(project.cwd / "source.png")
    project.json("import", PROP, "source.png")
    [variant] = sorted((project.cwd / "assets" / "prop" / "bench" / "src").glob("*.png"))
    project.json("pick", PROP, variant.stem)
    return project.cwd / "assets" / "prop" / "bench"


def work(folder: Path, stage: str, name: str) -> Path:
    return folder / "work" / stage / name


STAGES = ("brief", "source", "cutout", "fit", "palette")


def upto(project: Kiripix, stage: str) -> None:
    """Run the Stages before `stage`, each of which must be done: `run <stage>` wants its upstream built."""
    for earlier in STAGES[:STAGES.index(stage)]:
        project.json("run", PROP, earlier)


def no_runner_call(project: Kiripix) -> bool:
    return calls(project) == []


# chroma


def test_chroma_runs_to_the_palette_with_binary_alpha_on_the_palette_and_no_runner_call(project: Kiripix) -> None:
    folder = built_prop(project)

    project.json("run", PROP, expect=3)  # stops at `footprint`, which waits for the Owner

    status = stage_status(project, PROP)
    assert [status[s] for s in ("brief", "source", "cutout", "fit", "palette")] == ["done"] * 5
    assert status["finish"] == "done" and status["footprint"] == "needs-input"
    cutout = read(work(folder, "cutout", "cutout.png"))
    assert cutout.shape == (SIZE, SIZE, 4) and (cutout[0, 0] == 0).all() and cutout[16, 16, 3] == 255
    fitted = read(work(folder, "fit", "fit.png"))
    assert fitted.shape == (TARGET, TARGET, 4)
    mapped = read(work(folder, "palette", "palette.png"))
    assert mapped.shape == (TARGET, TARGET, 4)
    assert set(np.unique(mapped[..., 3])) == {0, 255}
    assert (mapped[2:6, 2:6, 3] == 255).all() and (mapped[:2, :, 3] == 0).all() and (mapped[:, :2, 3] == 0).all()
    assert (mapped[mapped[..., 3] == 0] == 0).all()
    opaque = {tuple(int(c) for c in p) for p in mapped[mapped[..., 3] == 255][:, :3]}
    assert opaque <= palette_colours(project) and (255, 0, 77) in opaque, "mapped to the nearest palette colour"
    assert no_runner_call(project) and not (folder / "pinned").exists()
    assert project.json("check", PROP)["findings"] == []


def test_chroma_needs_no_pinned_result_and_is_never_waiting_on_a_runner(project: Kiripix) -> None:
    built_prop(project)
    upto(project, "cutout")

    project.json("run", PROP, "cutout")

    assert stage_status(project, PROP)["cutout"] == "done"
    assert project.json("run", PROP, "cutout", "--rerun")["ok"] and no_runner_call(project)


def test_a_chroma_cutout_that_keys_nothing_points_to_matting(project: Kiripix) -> None:
    built_prop(project)
    project.json("set", PROP, "cutout", "chroma=#FF00FF")
    upto(project, "cutout")

    result = project.json("run", PROP, "cutout", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "cutout.chroma_keyed_nothing"
    assert finding["fix"] == f"kiripix set {PROP} cutout method=matting"
    assert finding["position"]["asset"] == PROP and finding["position"]["stage"] == "cutout"


def test_a_chroma_cutout_that_keys_nearly_everything_is_a_finding(project: Kiripix) -> None:
    solid = np.full((SIZE, SIZE, 4), 255, dtype=np.uint8)
    solid[..., :3] = KEY
    solid[0, 0, :3] = SUBJECT
    built_prop(project, solid)
    upto(project, "cutout")

    result = project.json("run", PROP, "cutout", expect=2)

    assert [f["code"] for f in result["findings"]] == ["cutout.chroma_keyed_everything"]


def test_a_fringe_of_near_key_pixels_is_a_warning_that_points_to_matting(project: Kiripix) -> None:
    source = source_image()
    source[8:24, 7, :3] = (20, 235, 20)  # an antialiased column left of the subject, close to the key
    built_prop(project, source)
    upto(project, "cutout")

    result = project.json("run", PROP, "cutout")  # a warning: exit 0

    [finding] = result["findings"]
    assert finding["code"] == "cutout.chroma_fringe" and finding["severity"] == "warning"
    assert finding["position"]["x"] == 7 and finding["fix"] == f"kiripix set {PROP} cutout method=matting"


def test_an_invalid_chroma_colour_fails_the_stage_with_the_fix(project: Kiripix) -> None:
    built_prop(project)
    project.json("set", PROP, "cutout", "chroma=green")
    upto(project, "cutout")

    result = project.json("run", PROP, "cutout", expect=1)

    assert result["findings"][0]["code"] == "stage.failed" and "#RRGGBB" in result["findings"][0]["message"]


# matting, with the fake matter: its alpha ramps from 0 at the left column to 255 at the right one


def test_matting_waits_for_a_rerun_pins_it_into_review_and_accept_makes_it_done(project: Kiripix) -> None:
    folder = built_prop(project)
    project.json("set", PROP, "cutout", "method=matting")

    waiting = project.json("run", PROP, expect=3)
    assert no_runner_call(project) and pinned(folder) == []
    cutout = next(s for s in project.json("status")["data"]["assets"][0]["stages"] if s["stage"] == "cutout")
    assert cutout["status"] == "needs-input" and cutout["reason"] == "Runner not run yet"
    assert waiting["findings"][0]["fix"] == f"kiripix run {PROP} cutout --rerun"
    assert project.json("next", PROP)["data"]["command"] == f"kiripix run {PROP} cutout --rerun"

    project.json("run", PROP, "cutout", "--rerun", expect=3)

    assert len(calls(project)) == 1 and calls(project)[0]["params"] == {"max_size": 1536}
    assert stage_status(project, PROP)["cutout"] == "needs-review"
    [path] = pinned(folder)
    assert json.loads(path.with_suffix(".json").read_text("utf-8"))["stage"] == "cutout"
    cut = read(work(folder, "cutout", "cutout.png"))
    assert cut.shape == (SIZE, SIZE, 4) and 0 < cut[16, 15, 3] < 255, "the matte's partial alpha reaches the cutout"

    project.json("accept", PROP, "cutout", owner=True)
    project.json("run", PROP, expect=3)

    status = stage_status(project, PROP)
    assert status["cutout"] == "done" and status["fit"] == "done" and status["palette"] == "done"
    assert len(calls(project)) == 1, "a rebuild makes no second call"


def test_matting_gives_the_fit_a_binary_alpha_by_majority_vote(project: Kiripix) -> None:
    folder = built_prop(project)
    project.json("set", PROP, "cutout", "method=matting")
    upto(project, "cutout")
    project.json("run", PROP, "cutout", "--rerun", expect=3)
    project.json("accept", PROP, "cutout", owner=True)

    project.json("run", PROP, expect=3)

    fitted = read(work(folder, "fit", "fit.png"))
    alpha = fitted[0, :, 3]
    assert set(np.unique(fitted[..., 3])) <= {0, 255}
    assert alpha[0] == 0 and alpha[-1] == 255, "the ramp is clear on the left, opaque on the right"
    assert (np.diff(alpha.astype(int)) >= 0).all(), "one step across the ramp"
    mapped = read(work(folder, "palette", "palette.png"))
    assert set(np.unique(mapped[..., 3])) == {0, 255}
    assert project.json("check", PROP)["findings"] == []


def source_pad() -> np.ndarray:
    return np.pad(source_image(), ((0, 0), (0, 2368), (0, 0)), constant_values=255)


def test_a_capped_matte_is_laid_over_the_full_size_source(project: Kiripix) -> None:
    folder = built_prop(project, source_pad())
    project.json("set", PROP, "brief", "width=600", "height=8")
    project.json("set", PROP, "cutout", "method=matting")
    upto(project, "cutout")

    project.json("run", PROP, "cutout", "--rerun", expect=3)

    cut = read(work(folder, "cutout", "cutout.png"))
    assert cut.shape == (SIZE, SIZE + 2368, 4), "the cutout has the Source's size, though the call was capped"
    [path] = pinned(folder)
    with Image.open(path) as pinned_image:
        assert pinned_image.size == (1536, 20)
    keep = cut[..., 3] > 0
    assert keep.any() and (cut[keep][:, :3] == source_pad()[keep][:, :3]).all(), "the Source's own colours"


def test_a_matter_with_another_id_is_runner_input_changed(project: Kiripix) -> None:
    folder = built_prop(project)
    project.json("set", PROP, "cutout", "method=matting")
    upto(project, "cutout")
    project.json("run", PROP, "cutout", "--rerun", expect=3)
    project.json("accept", PROP, "cutout", owner=True)
    [path] = pinned(folder)
    record = json.loads(path.with_suffix(".json").read_text("utf-8"))
    path.with_suffix(".json").write_text(json.dumps({**record, "runner": "an-older-matter"}), "utf-8")
    path.unlink()

    step: dict[str, Any] = project.json("next", PROP)["data"]

    assert step["stage"] == "cutout" and step["reason"] == "Runner input changed"
    assert step["command"] == f"kiripix run {PROP} cutout --rerun"
    rerun = project.json("run", PROP, "cutout", "--rerun")
    assert rerun["data"]["results"][0]["outcome"] == "skipped"
    assert stage_status(project, PROP)["cutout"] == "done", "the same result as the Owner accepted: nothing to review"
    assert len(calls(project)) == 2


def test_choosing_chroma_after_matting_needs_no_pinned_result(project: Kiripix) -> None:
    built_prop(project)
    project.json("set", PROP, "cutout", "method=matting")
    upto(project, "cutout")
    project.json("run", PROP, "cutout", "--rerun", expect=3)
    project.json("set", PROP, "cutout", "method=chroma")

    project.json("run", PROP, "cutout")

    assert stage_status(project, PROP)["cutout"] == "done" and len(calls(project)) == 1


# fit and palette


def test_the_fit_is_the_briefs_exact_size_and_a_mismatch_is_a_finding_with_a_fix(project: Kiripix) -> None:
    built_prop(project)
    project.json("set", PROP, "brief", "width=16", "height=16")
    upto(project, "fit")

    result = project.json("run", PROP, "fit", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "fit.size_mismatch" and finding["fix"] == f"kiripix set {PROP} fit scale=2"


def test_downscale_fit_keeps_alpha_binary_and_the_brief_size(project: Kiripix) -> None:
    folder = built_prop(project, mode="downscale")

    project.json("run", PROP, expect=3)

    fitted = read(work(folder, "fit", "fit.png"))
    assert fitted.shape == (TARGET, TARGET, 4) and set(np.unique(fitted[..., 3])) == {0, 255}


def test_a_partial_alpha_painted_over_the_fit_is_a_finding(project: Kiripix) -> None:
    folder = built_prop(project)
    upto(project, "fit")
    project.json("run", PROP, "fit")
    painted = read(work(folder, "fit", "fit.png")).copy()
    painted[3, 3, 3] = 120
    Image.fromarray(painted, "RGBA").save(project.cwd / "fix.png")
    project.json("override", PROP, "fit", "fix.png")

    result = project.json("run", PROP, "fit", expect=2)

    assert [f["code"] for f in result["findings"]] == ["image.partial_alpha"]
    assert result["findings"][0]["owner_action"]


def test_palette_keeps_transparent_pixels_and_every_opaque_one_is_on_the_palette(project: Kiripix) -> None:
    folder = built_prop(project)
    project.json("set", PROP, "palette", "orphan_size=0")
    upto(project, "palette")
    project.json("run", PROP, "palette")

    mapped = read(work(folder, "palette", "palette.png"))

    assert (mapped[..., 3] == read(work(folder, "fit", "fit.png"))[..., 3]).all(), "transparent pixels stay"
    assert project.json("check", PROP)["findings"] == []


# the brief


def test_the_default_prop_brief_is_32_px_and_a_brief_over_the_resolution_is_a_finding_with_a_fix(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    project.json("run", PROP, "brief")
    brief = project.cwd / "assets" / "prop" / "bench" / "work" / "brief" / "brief.json"
    assert json.loads(brief.read_text("utf-8")) == {"width": 32, "height": 32, "angle": "top34"}

    project.json("set", PROP, "brief", "width=700", "height=360")
    result = project.json("run", PROP, "brief", expect=2)

    [finding] = result["findings"]
    assert finding["code"] == "brief.larger_than_resolution"
    assert finding["fix"] == f"kiripix set {PROP} brief width=640 height=360"
    project.json("set", PROP, "brief", "width=640", "height=360")
    assert project.json("run", PROP, "brief")["findings"] == []


# the way through


def test_next_gives_a_command_or_an_owner_action_at_every_prop_stage(project: Kiripix) -> None:
    folder = built_prop(project)
    project.json("new", "prop", "lamp")
    for stage in ("brief", "source"):
        project.json("run", "prop.lamp", stage, expect=0 if stage == "brief" else 3)

    step = project.json("next", "prop.lamp")["data"]
    assert step["stage"] == "source" and step["command"] == "kiripix import prop.lamp <file>"

    seen = []
    project.json("set", PROP, "cutout", "method=matting")
    for _ in range(12):
        step = project.json("next", PROP)["data"]
        if step["done"]:
            break
        assert (step["command"] is None) != (step["owner_action"] is None), step
        seen.append(step["stage"])
        if step["command"] and step["stage"] == "cutout":
            project.json("run", PROP, "cutout", "--rerun", expect=3)
            project.json("accept", PROP, "cutout", owner=True)
        elif step["command"]:
            project.json("run", PROP, step["stage"], expect=0)
        else:
            break
    assert "cutout" in seen
    step = project.json("next", PROP)["data"]
    assert step["stage"] == "footprint" and step["command"] is None and "footprint" in step["owner_action"]
    assert folder.is_dir()


# finish and footprint (ticket 0051)


def to_finish(project: Kiripix, **finish: str) -> Path:
    folder = built_prop(project)
    if finish:
        project.json("set", PROP, "finish", *[f"{k}={v}" for k, v in finish.items()])
    for stage in STAGES:
        project.json("run", PROP, stage)
    project.json("run", PROP, "finish")
    return folder


def decision(polygon: list[list[int]], origin: list[int]) -> str:
    return json.dumps({"decision": "footprint", "data": {"polygon": polygon, "origin": origin}})


def test_finish_without_an_outline_is_the_palette_image(project: Kiripix) -> None:
    folder = to_finish(project)

    assert (read(work(folder, "finish", "finish.png")) == read(work(folder, "palette", "palette.png"))).all()


def test_an_outline_is_on_the_palette_with_binary_alpha_and_grows_around_the_shape(project: Kiripix) -> None:
    folder = to_finish(project, outline="true", outline_colour="1")

    finished = read(work(folder, "finish", "finish.png"))
    mapped = read(work(folder, "palette", "palette.png"))
    assert set(np.unique(finished[..., 3])) == {0, 255}
    assert (finished[1, 2:6, 3] == 255).all() and (finished[0, :, 3] == 0).all(), "one ring, 4-adjacent"
    assert finished[1, 1, 3] == 0, "not the corner"
    assert (finished[2:6, 2:6] == mapped[2:6, 2:6]).all()
    colours = palette_colours(project)
    assert {tuple(int(c) for c in p[:3]) for p in finished[finished[..., 3] == 255]} <= colours


def test_an_outline_colour_outside_the_palette_fails_with_the_valid_range(project: Kiripix) -> None:
    built_prop(project)
    for stage in STAGES:
        project.json("run", PROP, stage)
    project.json("set", PROP, "finish", "outline=true", "outline_colour=99")

    result = project.json("run", PROP, "finish", expect=1)

    message = json.dumps(result)
    assert "99" in message and "indexes 0 to" in message


def test_no_footprint_waits_for_the_owner_then_decide_runs_to_done_and_moving_the_origin_rebuilds_from_footprint(
    project: Kiripix,
) -> None:
    folder = to_finish(project)
    project.json("run", PROP, "footprint", expect=3)
    step = project.json("next", PROP)["data"]
    assert step["stage"] == "footprint" and step["command"] is None and "kiripix decide" in step["owner_action"]

    project.json("decide", PROP, "footprint", "--decision", decision([[1, 5], [6, 5], [6, 7], [1, 7]], [3, 7]))
    project.json("run", PROP, "footprint")

    status = stage_status(project, PROP)
    assert status["footprint"] == "done"
    record = json.loads(work(folder, "footprint", "footprint.json").read_text("utf-8"))
    assert record == {"polygon": [[1, 5], [6, 5], [6, 7], [1, 7]], "origin": [3, 7]}
    assert (read(work(folder, "footprint", "sprite.png")) == read(work(folder, "finish", "finish.png"))).all()
    assert project.json("check", PROP)["findings"] == []

    finish_stamp = work(folder, "finish", "finish.png").stat().st_mtime_ns
    project.json("decide", PROP, "footprint", "--decision", decision([[1, 5], [6, 5], [6, 7], [1, 7]], [4, 7]))
    assert stage_status(project, PROP)["footprint"] != "done"
    assert stage_status(project, PROP)["finish"] == "done"
    project.json("run", PROP, "footprint")
    assert work(folder, "finish", "finish.png").stat().st_mtime_ns == finish_stamp
    record = json.loads(work(folder, "footprint", "footprint.json").read_text("utf-8"))
    assert record["origin"] == [4, 7]


def test_an_origin_outside_the_image_and_a_polygon_of_two_points_are_findings_and_an_empty_one_is_not(
    project: Kiripix,
) -> None:
    to_finish(project)
    project.json("decide", PROP, "footprint", "--decision", decision([[1, 1], [2, 2]], [8, 0]))

    result = project.json("run", PROP, "footprint", expect=2)

    assert sorted(f["code"] for f in result["findings"]) == ["prop.footprint_too_small", "prop.origin_outside"]
    assert all(f["owner_action"] for f in result["findings"])
    project.json("decide", PROP, "footprint", "--decision", decision([], [0, 7]))
    assert project.json("run", PROP, "footprint")["findings"] == []
