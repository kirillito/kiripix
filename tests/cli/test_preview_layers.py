"""`preview --overlay layers`, `--layer` and `--brighten` (ticket 0086, spec §10.5)."""

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_layers_stage import ROOM, accept, alpha_of, built_room, click, lift

STAGE = ["--stage", "fit"]


def preview(project: Kiripix, *args: str, expect: int = 0) -> dict[str, Any]:
    return project.json("preview", ROOM, *STAGE, *args, expect=expect)


def pixels(project: Kiripix, result: dict[str, Any]) -> np.ndarray:
    with Image.open(project.cwd / result["data"]["path"]) as image:
        return np.asarray(image.convert("RGBA")).copy()


def two_layers(project: Kiripix) -> Path:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    click(project, "crate", 40, 24)
    lift(project)
    return folder


def tree_hashes(project: Kiripix) -> dict[str, str]:
    """Every file in the Project outside `.kiripix/previews/`, and the hash cache, which any Command may refresh."""
    found = {}
    for path in sorted(project.cwd.rglob("*")):
        relative = path.relative_to(project.cwd).as_posix()
        if path.is_file() and not relative.startswith(".kiripix/previews/") and ".git/" not in relative \
                and relative != ".kiripix/hash-cache.json":
            found[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def test_the_layers_overlay_differs_from_the_fit_image_exactly_where_a_layer_has_alpha(project: Kiripix) -> None:
    folder = two_layers(project)
    plain = pixels(project, preview(project, "--zoom", "1"))

    result = preview(project, "--overlay", "layers", "--zoom", "1")

    tinted = pixels(project, result)
    covered = alpha_of(folder, "lamp") | alpha_of(folder, "crate")
    assert covered.any()
    assert ((tinted != plain).any(axis=2) == covered).all()
    assert (tinted[..., 3] == plain[..., 3]).all()
    colours = {entry["id"]: entry["colour"] for entry in result["data"]["layers"]}
    assert list(colours) == ["lamp", "crate"] and colours["lamp"] != colours["crate"]
    assert result["data"]["overlay"] == "layers"


def test_a_layer_is_tinted_in_its_own_colour(project: Kiripix) -> None:
    folder = two_layers(project)
    plain = pixels(project, preview(project, "--zoom", "1"))

    result = preview(project, "--overlay", "layers", "--zoom", "1")

    tinted = pixels(project, result)
    colours = {entry["id"]: entry["colour"] for entry in result["data"]["layers"]}
    for name, colour in colours.items():
        rgb = np.array([int(colour[i:i + 2], 16) for i in (1, 3, 5)], dtype=np.float64)
        alpha = alpha_of(folder, name)
        expected = np.round(plain[alpha][:, :3] * 0.5 + rgb * 0.5).astype(np.uint8)
        assert (tinted[alpha][:, :3] == expected).all()


def test_layer_tints_only_that_layer_and_keeps_its_colour(project: Kiripix) -> None:
    folder = two_layers(project)
    plain = pixels(project, preview(project, "--zoom", "1"))
    whole = preview(project, "--overlay", "layers", "--zoom", "1")

    result = preview(project, "--overlay", "layers", "--layer", "crate", "--zoom", "1")

    tinted = pixels(project, result)
    assert ((tinted != plain).any(axis=2) == alpha_of(folder, "crate")).all()
    assert [entry["id"] for entry in result["data"]["layers"]] == ["crate"]
    assert result["data"]["layers"][0] == whole["data"]["layers"][1]
    assert result["data"]["path"] != whole["data"]["path"]


def test_an_unknown_layer_is_refused_with_the_layers_named(project: Kiripix) -> None:
    two_layers(project)

    finding = preview(project, "--overlay", "layers", "--layer", "nope", expect=1)["findings"][0]

    assert finding["code"] == "input.invalid"
    assert "lamp" in finding["message"] and "crate" in finding["message"] and finding["fix"]


def test_layer_without_the_layers_overlay_is_refused(project: Kiripix) -> None:
    two_layers(project)

    assert preview(project, "--layer", "lamp", expect=1)["findings"][0]["code"] == "input.invalid"


def test_it_works_while_layers_awaits_review_and_says_so_then_stops_saying_it(project: Kiripix) -> None:
    two_layers(project)
    assert stage_status(project, ROOM)["layers"] == "needs-review"

    waiting = preview(project, "--overlay", "layers")

    assert waiting["data"]["awaiting_review"] is True
    finding = waiting["findings"][0]
    assert finding["code"] == "preview.layers_awaiting_review" and finding["owner_action"]
    assert not finding.get("fix")
    accept(project)

    done = preview(project, "--overlay", "layers")

    assert done["data"]["awaiting_review"] is False and done["findings"] == []


def test_with_no_built_layers_the_finding_says_so_and_names_the_fix(project: Kiripix) -> None:
    built_room(project)

    finding = preview(project, "--overlay", "layers", expect=1)["findings"][0]

    assert finding["code"] == "preview.no_layers" and "no built Layers" in finding["message"]
    assert finding["fix"] == f"kiripix run {ROOM} layers"


def test_brighten_one_changes_nothing_and_more_brightens_with_clipping(project: Kiripix) -> None:
    built_room(project)
    plain = pixels(project, preview(project, "--zoom", "1"))

    same = preview(project, "--brighten", "1", "--zoom", "1")
    bright = preview(project, "--brighten", "1.8", "--zoom", "1")

    assert same["data"]["path"] == preview(project, "--zoom", "1")["data"]["path"]
    assert (pixels(project, same) == plain).all()
    lit = pixels(project, bright)
    assert bright["data"]["path"] != same["data"]["path"] and bright["data"]["brighten"] == 1.8
    expected = np.clip(np.round(plain[..., :3].astype(np.float64) * 1.8), 0, 255).astype(np.uint8)
    assert (lit[..., :3] == expected).all() and (lit[..., 3] == plain[..., 3]).all()
    assert lit[..., :3].max() == 255


def test_brighten_comes_before_the_tint(project: Kiripix) -> None:
    folder = two_layers(project)
    bright = pixels(project, preview(project, "--brighten", "1.5", "--zoom", "1"))

    result = preview(project, "--overlay", "layers", "--brighten", "1.5", "--zoom", "1")

    tinted = pixels(project, result)
    covered = alpha_of(folder, "lamp") | alpha_of(folder, "crate")
    assert (tinted[~covered] == bright[~covered]).all() and (tinted[covered] != bright[covered]).any()


def test_a_brighten_of_zero_or_less_is_refused(project: Kiripix) -> None:
    built_room(project)

    for text in ("0", "-1"):
        assert preview(project, "--brighten", text, expect=1)["findings"][0]["code"] == "input.invalid"


def test_brighten_and_the_overlay_change_nothing_outside_the_previews_folder_and_no_status(project: Kiripix) -> None:
    two_layers(project)
    before, status = tree_hashes(project), stage_status(project, ROOM)

    preview(project, "--overlay", "layers", "--brighten", "2", "--region", "0,0,20,20", "--grid", "4")
    preview(project, "--brighten", "3")

    assert tree_hashes(project) == before and stage_status(project, ROOM) == status
