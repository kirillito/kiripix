"""Growing the palette from an image (ticket 0077): `op palette-suggest` proposes, the owner-only `palette-add` appends."""

import json
import shutil
from pathlib import Path

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_fit import ROOM
from test_fit import upscaled
from test_palette import fitted_room, off_palette_art

COLOURS = [(10, 200, 210), (230, 120, 240), (140, 200, 10)]  # far from anything in the default palette


def painted(project: Kiripix, name: str = "ref.png") -> Path:
    """A reference with three flat blocks of colours the default palette lacks."""
    pixels = np.full((60, 90, 4), 255, dtype=np.uint8)
    for i, colour in enumerate(COLOURS):
        pixels[:, i * 30 : (i + 1) * 30, :3] = colour
    path = project.cwd / name
    Image.fromarray(pixels, "RGBA").save(path)
    return path


def palette_bytes(project: Kiripix) -> bytes:
    return (project.cwd / "style" / "palette.gpl").read_bytes()


def suggest(project: Kiripix, *extra: str) -> dict[str, object]:
    painted(project)
    data: dict[str, object] = project.json("op", "palette-suggest", "ref.png", "--add", "5", "--scale", "1", *extra)["data"]
    return data


def test_suggest_proposes_colours_and_leaves_the_palette_and_every_status_alone(project: Kiripix) -> None:
    fitted_room(project)
    project.json("run", ROOM, expect=3)
    before_status = project.json("status")["data"]
    before = palette_bytes(project)

    data = suggest(project)

    assert palette_bytes(project) == before
    assert project.json("status")["data"] == before_status
    assert len(data["colours"]) == 3 and data["error_after"] < data["error_before"]  # type: ignore[arg-type]
    for key in ("proposal", "swatch", "mapped_before", "mapped_after"):
        assert (project.cwd / str(data[key])).is_file()
        assert str(data[key]).startswith(".kiripix/")
    proposal = json.loads((project.cwd / str(data["proposal"])).read_text(encoding="utf-8"))
    assert proposal["schema_version"] == 1 and proposal["colours"] == data["colours"]
    assert {"image_hash", "palette_hash"} <= set(proposal)


def test_a_palette_that_fits_adds_no_colours_and_says_so(project: Kiripix) -> None:
    pixels = np.full((20, 20, 4), 255, dtype=np.uint8)
    pixels[..., :3] = (255, 0, 77)  # "red" in the default palette
    Image.fromarray(pixels, "RGBA").save(project.cwd / "fits.png")

    result = project.json("op", "palette-suggest", "fits.png", "--add", "8", "--scale", "1")

    assert result["ok"] is True and result["data"]["colours"] == [] and result["data"]["proposal"] is None
    assert "already fits" in result["data"]["note"]


def test_add_appends_to_the_end_and_keeps_every_existing_line(project: Kiripix) -> None:
    before = palette_bytes(project)
    data = suggest(project)

    result = project.json("palette-add", str(data["proposal"]), owner=True)

    after = palette_bytes(project)
    assert after.startswith(before)
    new_lines = after[len(before) :].decode("utf-8").splitlines()
    assert len(new_lines) == 3 and new_lines[0].endswith("\tadded-01") and new_lines[2].endswith("\tadded-03")
    assert result["data"]["colours_total"] > 3
    again = project.json("op", "palette-suggest", "ref.png", "--add", "5", "--scale", "1")
    assert again["data"]["colours"] == []  # the palette now fits the image, and the file passes its Checks


def test_the_prefix_names_the_new_colours(project: Kiripix) -> None:
    data = suggest(project)

    project.json("palette-add", str(data["proposal"]), "--name", "subway", owner=True)

    assert b"\tsubway-01" in palette_bytes(project)


def test_add_without_the_owner_exits_3_and_writes_nothing(project: Kiripix) -> None:
    data = suggest(project)
    before = palette_bytes(project)

    result = project.json("palette-add", str(data["proposal"]), expect=3)

    assert result["findings"][0]["code"] == "owner.required"
    assert palette_bytes(project) == before


def test_a_proposal_made_before_the_palette_changed_is_stale(project: Kiripix) -> None:
    data = suggest(project)
    path = project.cwd / "style" / "palette.gpl"
    path.write_bytes(path.read_bytes() + b"  1   2   3\tother\n")
    before = palette_bytes(project)

    result = project.json("palette-add", str(data["proposal"]), owner=True, expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "palette.proposal_stale"
    assert finding["fix"].startswith("kiripix op palette-suggest ref.png --add 5")
    assert palette_bytes(project) == before


def test_a_proposal_for_another_palette_is_refused_and_the_fix_suggests_for_the_projects(project: Kiripix) -> None:
    shutil.copy(project.cwd / "style" / "palette.gpl", project.cwd / "other.gpl")
    data = suggest(project, "--palette", "other.gpl")  # the same bytes, so only the path tells them apart
    before = palette_bytes(project)

    result = project.json("palette-add", str(data["proposal"]), owner=True, expect=1)

    finding = result["findings"][0]
    assert finding["code"] == "palette.proposal_other_palette"
    assert "--palette" not in finding["fix"]
    assert palette_bytes(project) == before


def test_a_proposal_with_an_unknown_key_is_refused(project: Kiripix) -> None:
    data = suggest(project)
    path = project.cwd / str(data["proposal"])
    path.write_text(json.dumps({**json.loads(path.read_text(encoding="utf-8")), "extra": 1}), encoding="utf-8")

    result = project.json("palette-add", str(data["proposal"]), owner=True, expect=1)

    assert result["findings"][0]["code"] == "palette.proposal_invalid"


def test_different_arguments_make_different_proposals(project: Kiripix) -> None:
    first = suggest(project)
    second = suggest(project, "--min-distance", "0.05")

    assert first["proposal"] != second["proposal"]
    assert (project.cwd / str(first["proposal"])).is_file()


def test_a_second_add_of_the_same_proposal_is_refused(project: Kiripix) -> None:
    data = suggest(project)
    project.json("palette-add", str(data["proposal"]), owner=True)
    after = palette_bytes(project)

    result = project.json("palette-add", str(data["proposal"]), owner=True, expect=1)

    assert result["findings"][0]["code"] == "palette.proposal_stale"
    assert palette_bytes(project) == after


def test_after_an_add_the_rooms_palette_and_later_stages_are_stale_and_run_rebuilds_them(project: Kiripix) -> None:
    fitted_room(project)
    project.json("run", ROOM, expect=3)
    assert stage_status(project, ROOM)["palette"] == "done"
    data = suggest(project)

    result = project.json("palette-add", str(data["proposal"]), owner=True)

    assert result["data"]["assets_made_stale"] == [ROOM]
    states = stage_status(project, ROOM)
    assert states["palette"] == "stale" and states["place"] == "stale"
    assert "needs-review" not in states.values()
    project.json("run", ROOM, expect=3)
    assert stage_status(project, ROOM)["palette"] == "done"


def test_suggest_from_a_room_matches_the_old_path_on_a_crop_at_the_rooms_scale(project: Kiripix) -> None:
    pixels = off_palette_art(48, 32)
    fitted_room(project, source=pixels)
    project.json("run", ROOM, "brief")
    project.json("run", ROOM, "source")
    project.json("run", ROOM, "fit")
    x, y, w, h = 8, 4, 20, 16
    crop = upscaled(pixels, 2)[2 * y : 2 * (y + h), 2 * x : 2 * (x + w)]
    Image.fromarray(crop, "RGBA").save(project.cwd / "crop.png")

    old = project.json("op", "palette-suggest", "crop.png", "--add", "5", "--scale", "2")["data"]
    new = project.json("op", "palette-suggest", "--asset", ROOM, "--box", f"{x},{y},{w},{h}", "--add", "5")["data"]
    whole = project.json("op", "palette-suggest", "--asset", ROOM, "--add", "5")["data"]

    assert new["colours"] == old["colours"] and new["error_before"] == old["error_before"]
    assert new["box"] == [x, y, w, h] and new["scale"] == 2.0 and (new["width"], new["height"]) == (w, h)
    assert whole["box"] == [0, 0, 48, 32] and (whole["width"], whole["height"]) == (48, 32)
    proposal = json.loads((project.cwd / str(new["proposal"])).read_text(encoding="utf-8"))
    assert proposal["asset"] == ROOM and proposal["box"] == [x, y, w, h]
    assert (project.cwd / str(new["proposal"])) != (project.cwd / str(whole["proposal"]))


def test_suggest_from_a_room_needs_fit_and_a_box_inside_the_room(project: Kiripix) -> None:
    fitted_room(project)

    refused = project.json("op", "palette-suggest", "--asset", ROOM, "--add", "5", expect=1)
    assert refused["findings"][0]["code"] == "palette.suggest_needs_fit"
    assert refused["findings"][0]["fix"] == f"kiripix run {ROOM} fit"

    project.json("run", ROOM, "brief")
    project.json("run", ROOM, "source")
    project.json("run", ROOM, "fit")
    bad = project.json("op", "palette-suggest", "--asset", ROOM, "--box", "40,0,20,10", "--add", "5", expect=1)
    assert bad["findings"][0]["code"] == "palette.box_invalid"
    both = project.json("op", "palette-suggest", "x.png", "--asset", ROOM, "--add", "5", expect=1)
    assert both["findings"][0]["code"] == "palette.suggest_input"


def test_an_asset_proposal_goes_stale_when_the_fit_changes_and_the_fix_keeps_the_box(project: Kiripix) -> None:
    pixels = off_palette_art(48, 32)
    fitted_room(project, source=pixels)
    project.json("run", ROOM, "brief")
    project.json("run", ROOM, "source")
    project.json("run", ROOM, "fit")
    made = project.json("op", "palette-suggest", "--asset", ROOM, "--box", "8,4,20,16", "--add", "3")["data"]

    project.json("set", ROOM, "fit", "scale=2", "offset_x=2")
    project.json("run", ROOM, "fit")
    stale = project.json("palette-add", str(made["proposal"]), owner=True, expect=1)

    finding = stale["findings"][0]
    assert finding["code"] == "palette.proposal_stale"
    assert f"--asset {ROOM} --box 8,4,20,16" in finding["fix"]


def test_a_malformed_box_and_a_kind_without_fit_are_refused(project: Kiripix) -> None:
    fitted_room(project)
    project.json("run", ROOM, "brief")
    project.json("run", ROOM, "source")
    project.json("run", ROOM, "fit")
    for box in ("1,2,3", "a,b,c,d", "1,2,3,4,5"):
        result = project.json("op", "palette-suggest", "--asset", ROOM, "--box", box, "--add", "2", expect=1)
        assert result["findings"][0]["code"] == "palette.box_invalid"
    project.json("new", "character", "hero")
    other = project.json("op", "palette-suggest", "--asset", "character.hero", "--add", "2", expect=1)
    assert other["findings"][0]["code"] == "palette.suggest_input"
