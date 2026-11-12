"""The character's `finish` Stage (ticket 0111, spec §6.3). The CLI tests run on the fake Blender's flat, fully opaque frames; the
ones about the outline first put a transparent border round each palette frame, as a real render has."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix, stage_status
from PIL import Image
from test_character_model import HERO
from test_character_palette import built, frames, project_palette

PALETTE_PARAMS = ("colors=3",)


def finished(project: Kiripix, *params: str, border: int = 0) -> Path:
    """Build to `palette`, optionally shrink the opaque part to leave `border` transparent px, then run `finish`."""
    folder = built(project, *PALETTE_PARAMS)
    if border:
        for path in frames(folder, "palette") + frames(folder, "render", "normal"):  # as a render's alpha is
            image = np.array(Image.open(path))
            image[:border], image[-border:], image[:, :border], image[:, -border:] = 0, 0, 0, 0
            Image.fromarray(image, "RGBA").save(path)
    if params:
        project.json("set", HERO, "finish", *params)
    project.json("run", HERO, "finish")
    return folder


def read(path: Path) -> np.ndarray:
    return np.array(Image.open(path))


def test_the_stage_declares_its_parameters_and_checks(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "finish")["data"]["kinds"]

    [stage] = kind["stages"]

    by_name = {p["name"]: p for p in stage["params"]}
    assert set(by_name) == {"outline", "outline_colour", "placement", "normal_levels", "watch_parts", "part_min_pixels"}
    assert by_name["outline"]["default"] is True and by_name["placement"]["default"] == "outside"
    assert [c["code"] for c in stage["checks"]] == ["normal.size_mismatch", "palette.off_palette", "sheet.part_vanishes"]


def test_run_writes_both_images_per_frame_in_renders_layout(project: Kiripix) -> None:
    folder = finished(project)

    colour, normal = frames(folder, "finish"), frames(folder, "finish", "normal")
    assert len(colour) == len(normal) == 8 * 14
    rendered = frames(folder, "render", "color")
    assert [p.relative_to(folder / "work" / "finish") for p in colour] == [
        p.relative_to(folder / "work" / "render") for p in rendered]
    assert (folder / "work" / "finish" / "render.json").read_bytes() == (folder / "work" / "palette" / "render.json").read_bytes()
    drawn = json.loads((folder / "work" / "finish" / "finish.json").read_text("utf-8"))
    assert drawn["normal_levels"] == 8 and drawn["outline"]["placement"] == "outside"


def test_every_colour_is_on_the_palette_and_every_normal_is_its_colour_frames_size_and_alpha(project: Kiripix) -> None:
    folder = finished(project, border=3)

    palette = {tuple(int(v) for v in c) for c in project_palette(project)}
    for path in frames(folder, "finish"):
        colour = read(path)
        normal = read(folder / "work" / "finish" / "normal" / path.relative_to(folder / "work" / "finish" / "color"))
        assert colour.shape == normal.shape == (78, 78, 4)
        assert (colour[..., 3] == normal[..., 3]).all()
        assert {tuple(int(v) for v in p[:3]) for p in colour[colour[..., 3] == 255]} <= palette
    assert project.json("check", HERO)["findings"] == []


def test_the_outline_is_one_ring_in_the_chosen_colour_and_its_normal_faces_the_camera(project: Kiripix) -> None:
    folder = finished(project, "outline_colour=1", border=3)

    rgb = tuple(int(v) for v in project_palette(project)[1])
    path = folder / "work" / "finish" / "color" / "idle" / "s" / "000.png"
    colour, mapped = read(path), read(folder / "work" / "palette" / "color" / "idle" / "s" / "000.png")
    assert (colour[2, 3:-3, 3] == 255).all() and (colour[2, 3:-3, :3] == rgb).all(), "the ring is outside the silhouette"
    assert (colour[1] == 0).all() and (colour[3:-3, 3:-3] == mapped[3:-3, 3:-3]).all()
    normal = read(folder / "work" / "finish" / "normal" / "idle" / "s" / "000.png")
    assert (normal[2, 3:-3] == (128, 128, 255, 255)).all()
    assert (normal[1] == 0).all()


def test_edge_placement_paints_the_silhouettes_own_edge_pixels(project: Kiripix) -> None:
    folder = finished(project, "placement=edge", "outline_colour=1", border=3)

    colour = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    assert (colour[2] == 0).all() and (colour[3, 4:-4, 3] == 255).all()


def test_without_an_outline_the_colour_frame_is_the_palette_frame(project: Kiripix) -> None:
    folder = finished(project, "outline=false", border=3)

    for path in frames(folder, "finish"):
        assert (read(path) == read(folder / "work" / "palette" / path.relative_to(folder / "work" / "finish"))).all()


def test_normals_are_quantised_to_their_levels_not_palette_mapped(project: Kiripix) -> None:
    folder = finished(project, "normal_levels=1")

    normal = read(folder / "work" / "finish" / "normal" / "idle" / "s" / "000.png")
    assert {tuple(int(v) for v in p) for p in normal.reshape(-1, 4)} == {(128, 128, 255, 255)}


def test_changing_outline_colour_rebuilds_finish_down_not_palette(project: Kiripix) -> None:
    finished(project)
    status = stage_status(project, HERO)
    assert status["palette"] == "done" and status["finish"] == "done"

    project.json("set", HERO, "finish", "outline_colour=2")

    status = stage_status(project, HERO)
    assert status["render"] == "done" and status["palette"] == "done" and status["finish"] == "stale"
    assert status["sheet"] != "done"
    result = project.json("run", HERO, "finish")
    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("finish", "done")]
    assert project.json("run", HERO, "finish")["data"]["results"][0]["outcome"] == "skipped"


def test_an_outline_colour_outside_the_palette_fails_with_the_valid_range_and_a_fix(project: Kiripix) -> None:
    finished(project)
    project.json("set", HERO, "finish", "outline_colour=999")

    result = project.json("run", HERO, "finish", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "finish.outline_colour_unknown"]
    assert "999" in finding["message"] and "indexes 0 to" in finding["message"]
    assert finding["fix"] == f"kiripix set {HERO} finish outline_colour=0"


def test_a_normal_of_another_size_is_reported_on_its_frame(project: Kiripix) -> None:
    folder = finished(project)
    bad = folder / "work" / "finish" / "normal" / "hit" / "e" / "002.png"
    Image.new("RGBA", (10, 12), (128, 128, 255, 255)).save(bad)

    project.json("check", HERO, expect=2)
    result: dict[str, Any] = project.json("check", HERO, expect=2)
    [finding] = [f for f in result["findings"] if f["code"] == "normal.size_mismatch"]
    assert finding["position"]["field"] == "hit/e/2" and "10 x 12" in finding["message"]
    assert finding["fix"] == f"kiripix run {HERO} finish --force"


@pytest.mark.parametrize("levels", [0, 257])
def test_normal_levels_outside_1_to_256_are_refused(project: Kiripix, levels: int) -> None:
    finished(project)

    project.json("set", HERO, "finish", f"normal_levels={levels}", expect=1)
