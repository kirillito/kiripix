"""The character's `palette` Stage (ticket 0110, spec §6.3). The CLI tests run on the fake Blender's frames (two colours that
differ by frame). The marked test runs the real Blender 5.2 on the fixture walk, through toon shading and palette, and
checks sizes, one shared subset and untouched passes, never pixels (ADR 0010)."""

import json
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix, stage_status
from PIL import Image
from test_character_clips import clip, real_hero
from test_character_model import HERO
from test_character_render import ready, render_json

from kiripix.ops import parse_gpl


def palette_json(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work" / "palette" / "palette.json").read_text("utf-8"))
    return document


def frames(folder: Path, stage: str, name: str = "color") -> list[Path]:
    return sorted((folder / "work" / stage / name).rglob("*.png"))


def project_palette(project: Kiripix) -> np.ndarray:
    return parse_gpl((project.cwd / "style" / "palette.gpl").read_text("utf-8")).rgb()


def palette_findings(project: Kiripix, **kwargs: Any) -> list[dict[str, Any]]:
    result = project.json("check", HERO, **kwargs)
    return [f for f in result["findings"] if f["code"].startswith("palette.")]


def built(project: Kiripix, *params: str) -> Path:
    folder = ready(project)
    project.json("run", HERO, "render")
    for param in params:
        project.json("set", HERO, "palette", param)
    project.json("run", HERO, "palette")
    return folder


def test_the_stage_declares_the_room_parameters_and_colors(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "palette")["data"]["kinds"]

    [stage] = kind["stages"]

    by_name = {p["name"]: p for p in stage["params"]}
    assert set(by_name) == {"colors", "dither", "strength", "orphan_size"}
    assert by_name["colors"]["default"] == 16 and by_name["colors"]["minimum"] == 1
    assert [c["code"] for c in stage["checks"]] == ["palette.off_palette"]


def test_run_maps_every_frame_to_one_subset_of_the_palette(project: Kiripix) -> None:
    folder = built(project, "colors=3")

    document = palette_json(folder)
    assert document["schema_version"] == 1
    colours = document["colors"]
    palette = project_palette(project)
    assert len(colours) == 3 and [c["index"] for c in colours] == sorted(c["index"] for c in colours)
    for colour in colours:
        assert palette[colour["index"]].tolist() == colour["rgb"]
        assert colour["hex"] == "#%02x%02x%02x" % tuple(colour["rgb"])
    allowed = {tuple(c["rgb"]) for c in colours}
    mapped, rendered = frames(folder, "palette"), frames(folder, "render", "color")
    assert len(mapped) == len(rendered) == 8 * 14
    assert [p.relative_to(folder / "work" / "palette") for p in mapped] == [
        p.relative_to(folder / "work" / "render") for p in rendered]
    used: set[tuple[int, ...]] = set()
    for path, source in zip(mapped, rendered, strict=True):
        image = np.array(Image.open(path))
        assert image.shape == np.array(Image.open(source)).shape == (78, 78, 4)
        assert set(np.unique(image[..., 3])) <= {0, 255}
        used |= {tuple(int(v) for v in pixel) for pixel in image[image[..., 3] == 255][:, :3]}
    assert used <= allowed and len(used) >= 2


def test_every_frame_uses_the_subset_not_its_own_nearest_colours(project: Kiripix) -> None:
    folder = built(project, "colors=2")

    allowed = {tuple(c["rgb"]) for c in palette_json(folder)["colors"]}

    for path in frames(folder, "palette"):
        image = np.array(Image.open(path))
        assert {tuple(int(v) for v in p) for p in image[..., :3].reshape(-1, 3)[image[..., 3].reshape(-1) == 255]} <= allowed


def test_the_other_passes_are_not_mapped_and_the_frame_list_goes_on(project: Kiripix) -> None:
    folder = built(project)

    out = folder / "work" / "palette"
    assert not (out / "normal").exists() and not (out / "depth").exists() and not (out / "mask").exists()
    assert (out / "render.json").read_bytes() == (folder / "work" / "render" / "render.json").read_bytes()
    assert render_json(folder)["clips"][0]["directions"]["s"][0]["files"]["color"] == "color/hit/s/000.png"
    assert (out / "color" / "hit" / "s" / "000.png").is_file()


def test_the_check_is_clean_after_a_run_and_names_the_frame_when_one_is_off(project: Kiripix) -> None:
    folder = built(project)
    assert palette_findings(project) == []

    bad = folder / "work" / "palette" / "color" / "idle" / "se" / "003.png"
    image = np.array(Image.open(bad))
    image[0, 0] = (1, 2, 3, 255)
    Image.fromarray(image, "RGBA").save(bad)

    project.json("check", HERO, expect=2)
    [finding] = palette_findings(project, expect=2)
    assert "idle" in finding["message"] and "se" in finding["message"] and "frame 3" in finding["message"]
    assert finding["position"]["file"] == "color/idle/se/003.png"
    assert finding["fix"] == f"kiripix run {HERO} palette --force"


def test_changing_the_project_palette_makes_palette_stale_and_leaves_render(project: Kiripix) -> None:
    built(project)
    status = stage_status(project, HERO)
    assert status["render"] == "done" and status["palette"] == "done"

    palette = project.cwd / "style" / "palette.gpl"
    palette.write_text(palette.read_text(encoding="utf-8") + "  1   2   3\textra\n", encoding="utf-8")

    status = stage_status(project, HERO)
    assert status["render"] == "done" and status["clips"] == "done"
    assert status["palette"] == "stale"
    assert all(status[name] != "done" for name in ("finish", "sheet", "export"))


def test_changing_orphan_size_rebuilds_only_palette(project: Kiripix) -> None:
    built(project)

    project.json("set", HERO, "palette", "orphan_size=2")

    status = stage_status(project, HERO)
    assert status["render"] == "done" and status["palette"] == "stale"
    result = project.json("run", HERO, "palette")
    assert [(r["stage"], r["outcome"]) for r in result["data"]["results"]] == [("palette", "done")]
    assert project.json("run", HERO, "palette")["data"]["results"][0]["outcome"] == "skipped"


def test_a_palette_with_fewer_colours_than_asked_gives_the_whole_palette(project: Kiripix) -> None:
    folder = built(project, "colors=500")

    assert len(palette_json(folder)["colors"]) == len(project_palette(project))


def test_the_same_inputs_give_the_same_frames(project: Kiripix) -> None:
    folder = built(project, "colors=4", "dither=bayer4")
    first = [p.read_bytes() for p in frames(folder, "palette")]

    project.json("run", HERO, "palette", "--force")

    assert [p.read_bytes() for p in frames(folder, "palette")] == first


@pytest.mark.blender
def test_the_walk_fixture_through_palette_has_one_subset_and_untouched_passes(project: Kiripix) -> None:
    folder = real_hero(project, "rigged.fbx")
    clip(project, {"name": "walk", "source": "walk", "start": 1, "end": 25, "fps": 3, "loop": True}, test_recipes=False)
    project.json("run", HERO, "clips", test_recipes=False, timeout=900)
    project.json("set", HERO, "render", "height=26", test_recipes=False)
    project.json("run", HERO, "render", "--cpu", test_recipes=False, timeout=1800)
    project.json("set", HERO, "palette", "colors=8", test_recipes=False)

    result = project.json("run", HERO, "palette", test_recipes=False, timeout=900)

    assert result["findings"] == []
    colours = palette_json(folder)["colors"]
    allowed = {tuple(c["rgb"]) for c in colours}
    assert 1 <= len(colours) <= 8
    mapped = frames(folder, "palette")
    assert len(mapped) == len(frames(folder, "render", "color")) >= 16
    used: set[tuple[int, ...]] = set()
    for path in mapped:
        image = np.array(Image.open(path))
        assert image.shape == (40, 40, 4) and set(np.unique(image[..., 3])) <= {0, 255}
        used |= {tuple(int(v) for v in p) for p in image[image[..., 3] == 255][:, :3]}
        source = np.array(Image.open(folder / "work" / "render" / path.relative_to(folder / "work" / "palette")))
        assert ((image[..., 3] == 255) == (source[..., 3] == 255)).all()  # the silhouette is the render's
    assert used <= allowed
    assert palette_findings(project, test_recipes=False) == []
