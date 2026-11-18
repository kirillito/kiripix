"""A Wearable's `palette` and `finish` (ticket 0292): its colours apart from its body's, and no outline."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_wearable import BODY, WEARABLE, hair, stage_state


def folder(project: Kiripix, asset: str, stage: str) -> Path:
    kind, name = asset.split(".")
    return project.cwd / "assets" / kind / name / "work" / stage


def colours(path: Path) -> set[tuple[int, ...]]:
    found: set[tuple[int, ...]] = set()
    for file in sorted(path.rglob("*.png")):
        image = np.asarray(Image.open(file).convert("RGBA"))
        found |= {tuple(int(v) for v in c[:3]) for c in image[image[..., 3] > 0]}
    return found


def worn(project: Kiripix) -> None:
    hair(project)
    project.json("set", BODY, "palette", "colors=4")  # the Project's palette has room for the Wearable's colours too
    project.json("run", BODY, "palette")
    project.json("run", BODY, "finish")  # a Wearable's `finish` reads the body's `normal_levels`
    project.json("set", WEARABLE, "palette", "colors=4")
    project.json("run", WEARABLE, "render")


def test_palette_waits_for_the_bodys_palette(project: Kiripix) -> None:
    hair(project)
    project.json("run", WEARABLE, "render")

    state = stage_state(project, WEARABLE, "palette")

    assert state["status"] == "needs-input" and BODY in state["reason"]


def test_the_wearables_colours_share_none_with_its_bodys(project: Kiripix) -> None:
    worn(project)

    result = project.json("run", WEARABLE, "palette")

    assert result["ok"] and result["findings"] == []
    mine = json.loads((folder(project, WEARABLE, "palette") / "palette.json").read_text("utf-8"))
    theirs = json.loads((folder(project, BODY, "palette") / "palette.json").read_text("utf-8"))
    ours = {i["index"] for i in mine["colors"]} | {i for p in mine["parts"] for i in p["indexes"]}
    body = {i["index"] for i in theirs["colors"]} | {i for p in theirs["parts"] for i in p["indexes"]}
    assert ours and body and not ours & body


def test_finish_draws_no_outline_and_has_no_outline_parameters(project: Kiripix) -> None:
    worn(project)
    project.json("run", WEARABLE, "palette")

    project.json("run", WEARABLE, "finish")

    done = folder(project, WEARABLE, "finish")
    assert json.loads((done / "finish.json").read_text("utf-8"))["outline"] is None
    for name in ("color",):
        for file in sorted((done / name).rglob("*.png")):
            mapped = np.asarray(Image.open(folder(project, WEARABLE, "palette") / name / file.relative_to(done / name)))
            assert (np.asarray(Image.open(file)) == mapped).all()  # not a pixel added: no outline
    names = {p["name"] for p in project.json("describe", "wearable")["data"]["kinds"][0]["stages"][4]["params"]}
    assert not names & {"outline", "outline_colour", "placement", "eyes"}
    assert (done / "normal").is_dir()


def test_a_wearable_never_has_the_body_outline_colour_swapped(project: Kiripix) -> None:
    worn(project)
    project.json("run", WEARABLE, "palette")
    project.json("run", WEARABLE, "finish")

    assert colours(folder(project, WEARABLE, "finish") / "color") <= colours(folder(project, WEARABLE, "palette") / "color")


def test_finish_quantises_normals_as_the_body_does_and_follows_it(project: Kiripix) -> None:
    worn(project)
    project.json("run", WEARABLE, "palette")
    project.json("run", WEARABLE, "finish")
    assert "normal_levels" not in {p["name"] for p in stages(project)[4]["params"]}
    assert json.loads((folder(project, WEARABLE, "finish") / "finish.json").read_text("utf-8"))["normal_levels"] == 8

    project.json("set", BODY, "finish", "normal_levels=16")
    project.json("run", BODY, "finish")

    assert stage_state(project, WEARABLE, "finish")["status"] == "stale"
    project.json("run", WEARABLE, "finish")
    assert json.loads((folder(project, WEARABLE, "finish") / "finish.json").read_text("utf-8"))["normal_levels"] == 16


def stages(project: Kiripix) -> list[Any]:
    return project.json("describe", "wearable")["data"]["kinds"][0]["stages"]
