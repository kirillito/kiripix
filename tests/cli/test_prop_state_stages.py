"""A Prop's Stages per state (ticket 0259): a state's outputs under `states/<id>/` in each Stage's folder, one scale, its
own origin and polygon; a Prop with no states is as it was."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_fit import read
from test_prop import KEY, PROP, SUBJECT, built_prop, source_image, work
from test_prop_states import declare

# A Prop without states, as `to_finish` builds it: the input hashes and outputs its Stages had before they ran per state
# (the brief, source and cutout hashes were taken before the change). A change here is a rebuild of the Owner's Props.
HASHES = {
    "brief": "52dd5ddaeda080ab7fe55787ed386f927e920c6fa704f395983240429416d67e",
    "source": "38e65f9e7ee1a3b66da10a11276652f18491d4288017248f7b9501001a92fb61",
    "cutout": "a89957fb251c066ae872c3312d8b23f128d7a5b0b16b3a3b8b5468ee9766f9c4",
    "fit": "233ab8a5efc8ba682873606b697d451362c1b6b4c62579e145a3374fce88482c",
    "palette": "101fdd16fa5bae9ac93ee900685a43c8364383f5ff9f6f1d29ce18094c6dcfc9",
    "finish": "c49c2eb9fa9be0985e8843ca80621d7dfc96367f7c659286fe892124bda774e9",
}
OUTPUTS = {
    "source/source.png": "ff707b93c77a6e5930ebcecb7bdbdbaa425c2ba9d1089f86b80b1aea4c63dafe",
    "cutout/cutout.png": "d8cab06955c265b60a768a1249f6a389ba749ab1a57ef2f32a2a07845c428d0f",
    "fit/fit.png": "2f22cfc86fdc9315109c8731c0d3e678cee6881977e8f88c89bfaaeaedc182ed",
    "fit/grid.json": "854b09c7512ae209e18abec36b61203a925341e4d7e11efca1771fb2a6a21431",
    "palette/palette.png": "141aa80009490309c614ee803fef643316a2c1724d5ff02759d5785fe8e1d46f",
    "finish/finish.png": "141aa80009490309c614ee803fef643316a2c1724d5ff02759d5785fe8e1d46f",
}
CHAIN = ("brief", "source", "cutout", "fit", "palette", "finish")


def a_state_source(width: int, height: int, scale: int = 4) -> np.ndarray:
    """The key colour with a block of subject colour, in cells `scale` source pixels wide (a grid to detect)."""
    rgba = np.full((height * scale, width * scale, 4), 255, dtype=np.uint8)
    rgba[..., :3] = KEY
    rgba[scale:-scale, scale:-scale, :3] = SUBJECT
    rgba[scale + 1:-scale - 1:2, scale:-scale, :3] = (0, 100, 255)  # a pattern, so detection finds the grid
    return rgba


def import_state(project: Kiripix, state: str, rgba: np.ndarray) -> None:
    Image.fromarray(rgba, "RGBA").save(project.cwd / f"{state}.png")
    imported = project.json("import", PROP, f"{state}.png", "--state", state)
    project.json("pick", PROP, imported["data"]["variant"], "--state", state)


def folder_of(project: Kiripix) -> Path:
    return project.cwd / "assets" / "prop" / "bench"


def decision(state: str | None, polygon: list[list[int]], origin: list[int]) -> str:
    data: dict[str, Any] = {"polygon": polygon, "origin": origin}
    if state is not None:
        data["state"] = state
    return json.dumps({"decision": "footprint", "data": data})


def to_finish(project: Kiripix, states: dict[str, tuple[int, int]], **fit: str) -> Path:
    folder = built_prop(project, **fit)
    for state, (width, height) in states.items():
        declare(project, state, width, height)
        import_state(project, state, a_state_source(width, height))
    for stage in CHAIN:
        project.json("run", PROP, stage)
    return folder


def test_a_default_and_a_toppled_state_of_another_size_build_to_footprint_at_one_scale_with_own_origins(
    project: Kiripix,
) -> None:
    folder = to_finish(project, {"toppled": (12, 6)})

    assert read(work(folder, "fit", "fit.png")).shape[:2] == (8, 8)
    assert read(work(folder, "fit", "states/toppled/fit.png")).shape[:2] == (6, 12)
    for stage, name in (("cutout", "cutout.png"), ("palette", "palette.png"), ("finish", "finish.png")):
        assert work(folder, stage, f"states/toppled/{name}").is_file()
    grids = [json.loads(work(folder, "fit", p).read_text("utf-8")) for p in ("grid.json", "states/toppled/grid.json")]
    assert grids[0]["scale_x"] == grids[1]["scale_x"] == 4 and grids[0]["scale_y"] == grids[1]["scale_y"] == 4
    finished = read(work(folder, "finish", "states/toppled/finish.png"))
    assert set(np.unique(finished[..., 3])) == {0, 255}

    project.json("decide", PROP, "footprint", "--decision", decision(None, [[1, 5], [6, 5], [6, 7], [1, 7]], [3, 7]))
    waiting = project.json("run", PROP, "footprint", expect=3)
    assert [f["code"] for f in waiting["findings"]] == ["footprint.no_origin"]
    assert "toppled" in waiting["findings"][0]["message"]

    project.json("decide", PROP, "footprint", "--decision", decision("toppled", [[1, 3], [10, 3], [10, 5]], [5, 5]))
    project.json("run", PROP, "footprint")

    assert stage_status(project, PROP)["footprint"] == "done"
    default = json.loads(work(folder, "footprint", "footprint.json").read_text("utf-8"))
    toppled = json.loads(work(folder, "footprint", "states/toppled/footprint.json").read_text("utf-8"))
    assert default == {"polygon": [[1, 5], [6, 5], [6, 7], [1, 7]], "origin": [3, 7]}
    assert toppled == {"polygon": [[1, 3], [10, 3], [10, 5]], "origin": [5, 5]}
    assert (read(work(folder, "footprint", "states/toppled/sprite.png")) == finished).all()
    assert [f["code"] for f in project.json("check", PROP)["findings"] if f["code"] != "palette.mapping_error"] == []


def test_a_state_origin_outside_its_own_sprite_is_a_finding_naming_the_state(project: Kiripix) -> None:
    to_finish(project, {"toppled": (12, 6)})
    project.json("decide", PROP, "footprint", "--decision", decision(None, [], [3, 7]))
    project.json("decide", PROP, "footprint", "--decision", decision("toppled", [], [5, 7]))  # 6 rows: y 7 is outside
    ran = project.json("run", PROP, "footprint", expect=2)

    found = [f for f in ran["findings"] if f["code"] == "prop.origin_outside"]

    assert len(found) == 1 and "toppled" in found[0]["message"] and "12x6" in found[0]["message"]
    assert found[0]["position"]["state"] == "toppled", "the UI tells a state's findings by `position.state`"
    assert all("state" not in (f.get("position") or {}) for f in ran["findings"] if f is not found[0]),         "a finding about the default has no `state`"


def test_show_lists_each_states_built_images_beside_the_defaults(project: Kiripix) -> None:
    to_finish(project, {"toppled": (12, 6)})

    shown = project.json("show", PROP)["data"]

    images = {entry["stage"]: entry for entry in shown["states"][0]["images"]}
    stages = {entry["stage"]: entry for entry in shown["stages"]}
    for stage in ("cutout", "fit", "palette", "finish"):
        default = stages[stage]["image"]
        assert images[stage]["image"] == default.rsplit("/", 1)[0] + "/states/toppled/" + default.rsplit("/", 1)[1]
        assert (project.cwd / images[stage]["image"]).is_file()
    assert images["fit"]["input_image"] == images["cutout"]["image"], "a state's Stage is made from its own image"


def test_a_grid_state_whose_scale_differs_fails_fit_with_scale_differs(project: Kiripix) -> None:
    folder = built_prop(project)
    declare(project, "toppled", 12, 6)
    import_state(project, "toppled", a_state_source(12, 6, scale=2))
    for stage in CHAIN[:3]:
        project.json("run", PROP, stage)
    project.json("set", PROP, "fit", "scale=0")

    result = project.json("run", PROP, "fit", expect=3)

    [finding] = [f for f in result["findings"] if f["code"] == "fit.scale_differs"]
    assert "toppled" in finding["message"]
    assert not work(folder, "fit", "fit.png").is_file() or stage_status(project, PROP)["fit"] != "done"


def test_a_downscale_state_is_fitted_at_the_defaults_scale_into_its_own_size_and_cropping_names_it(
    project: Kiripix,
) -> None:
    folder = built_prop(project, mode="downscale", scale="0")
    declare(project, "toppled", 12, 6)
    import_state(project, "toppled", a_state_source(12, 6, scale=4)[:, :, :])  # 48 x 24 at scale 4
    # a state source taller than 6 cells: 24 rows at scale 4 is 6 cells, so make it 32 rows for a crop of 8 px
    tall = np.full((32, 48, 4), 255, dtype=np.uint8)
    tall[..., :3] = KEY
    tall[8:24, 8:40, :3] = SUBJECT
    import_state(project, "toppled", tall)
    for stage in CHAIN:
        project.json("run", PROP, stage)

    assert read(work(folder, "fit", "states/toppled/fit.png")).shape[:2] == (6, 12)
    grid = json.loads(work(folder, "fit", "states/toppled/grid.json").read_text("utf-8"))
    assert grid["scale_x"] == grid["scale_y"] == 4
    cropped = [f for f in project.json("check", PROP)["findings"] if f["code"] == "fit.cropped"]
    assert len(cropped) == 1 and "toppled" in cropped[0]["message"]


def test_a_prop_without_states_has_no_states_folders(project: Kiripix) -> None:
    folder = to_finish(project, {})

    for stage in CHAIN:
        assert not work(folder, stage, "states").exists()
    assert read(work(folder, "palette", "palette.png")).shape[:2] == (8, 8)
    assert source_image() is not None


def test_a_downscale_state_has_its_own_crop_offsets_from_a_state_offset_decision(project: Kiripix) -> None:
    folder = built_prop(project, mode="downscale", scale="0")
    declare(project, "toppled", 12, 6)
    wide = np.full((32, 56, 4), 255, dtype=np.uint8)  # at scale 4 the state is 48 x 24: 8 px spare on each axis
    wide[..., :3] = KEY
    wide[4:, 8:, :3] = SUBJECT
    import_state(project, "toppled", wide)
    offset = {"decision": "state_offset", "data": {"state": "toppled", "offset_x": 8, "offset_y": 4}}
    project.json("decide", PROP, "fit", "--decision", json.dumps(offset))
    for stage in CHAIN:
        project.json("run", PROP, stage)

    state = json.loads(work(folder, "fit", "states/toppled/grid.json").read_text("utf-8"))
    default = json.loads(work(folder, "fit", "grid.json").read_text("utf-8"))
    fitted = read(work(folder, "fit", "states/toppled/fit.png"))
    assert (state["offset_x"], state["offset_y"]) == (8, 4) and (default["offset_x"], default["offset_y"]) == (0, 0)
    assert (fitted[..., 3] == 255).all(), "the crop starts at the subject, so it fills the state"

    project.json("decide", PROP, "fit", "--decision", json.dumps(
        {"decision": "state_offset", "data": {"state": "toppled", "offset_x": 0, "offset_y": 0}}))
    project.json("run", PROP, "fit")
    shifted = read(work(folder, "fit", "states/toppled/fit.png"))
    assert (shifted[..., 3] == 0).any(), "from the top left the crop starts on the background"
    assert read(work(folder, "fit", "fit.png")).shape[:2] == (8, 8)


def test_a_prop_without_states_has_the_input_hashes_and_outputs_it_had(project: Kiripix) -> None:
    import hashlib

    folder = to_finish(project, {})

    stamps = {stage: json.loads((folder / "work" / stage / ".stage.json").read_text("utf-8"))["input_hash"]
              for stage in CHAIN}
    outputs = {f"{stage}/{name}": hashlib.sha256(work(folder, stage, name).read_bytes()).hexdigest()
               for stage, name in (("source", "source.png"), ("cutout", "cutout.png"), ("fit", "fit.png"),
                                   ("fit", "grid.json"), ("palette", "palette.png"), ("finish", "finish.png"))}
    assert stamps == HASHES and outputs == OUTPUTS
