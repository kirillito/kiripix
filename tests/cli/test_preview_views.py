"""`preview --region`, `--grid` and `--overlay walkable|reachable` (spec §10.5): a closer look, a ruler, and where the Body fits."""

from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_masks import HEIGHT, ROOM, WIDTH, built_room, decide
from test_place import place, walled_room
from test_reachability import LEFT, split_room


def preview(project: Kiripix, *args: str, expect: int = 0) -> dict[str, Any]:
    return project.json("preview", ROOM, "--stage", "layers", *args, expect=expect)


def pixels(project: Kiripix, data: dict[str, Any]) -> np.ndarray:
    with Image.open(project.cwd / data["data"]["path"]) as image:
        return np.asarray(image.convert("RGBA")).copy()


# --region


def test_a_region_has_the_right_size_and_matches_the_same_area_of_the_full_preview(project: Kiripix) -> None:
    built_room(project)
    full = pixels(project, preview(project, "--zoom", "3"))

    data = preview(project, "--zoom", "3", "--region", "10,5,20,12")

    assert data["data"]["region"] == {"x": 10, "y": 5, "width": 20, "height": 12}
    assert (data["data"]["width"], data["data"]["height"]) == (60, 36)
    assert (pixels(project, data) == full[15:51, 30:90]).all()


def test_regions_and_grids_and_overlays_get_their_own_file_names(project: Kiripix) -> None:
    built_room(project)
    paths = {preview(project)["data"]["path"], preview(project, "--region", "0,0,8,8")["data"]["path"],
             preview(project, "--region", "0,0,8,9")["data"]["path"], preview(project, "--grid", "4")["data"]["path"]}

    assert len(paths) == 4


def test_a_region_outside_the_image_is_refused_with_a_fix(project: Kiripix) -> None:
    built_room(project)

    finding = preview(project, "--region", "40,0,10,10", expect=1)["findings"][0]

    assert finding["code"] == "preview.region_outside" and f"{WIDTH}x{HEIGHT}" in finding["message"]
    assert finding["fix"] == f"kiripix preview {ROOM} --region 0,0,{WIDTH},{HEIGHT}"


def test_a_region_that_is_not_four_whole_numbers_is_refused(project: Kiripix) -> None:
    built_room(project)

    for text in ("1,2,3", "a,b,c,d", "0,0,0,4", "-1,0,4,4"):
        assert preview(project, "--region", text, expect=1)["findings"][0]["code"] == "preview.region_invalid"


# --grid


def line_columns(base: np.ndarray, gridded: np.ndarray) -> list[int]:
    return [int(x) for x in np.flatnonzero((base[1:2] != gridded[1:2]).any(axis=(0, 2)))]


def test_a_grid_lines_up_with_target_pixels_at_any_zoom(project: Kiripix) -> None:
    built_room(project)
    for zoom in (1, 3):
        base = pixels(project, preview(project, "--zoom", str(zoom)))
        gridded = pixels(project, preview(project, "--zoom", str(zoom), "--grid", "8"))

        assert line_columns(base, gridded) == [x * zoom for x in range(0, WIDTH, 8)]
        assert np.flatnonzero((base[:, 1:2] != gridded[:, 1:2]).any(axis=(1, 2))).tolist() == [y * zoom for y in range(0, HEIGHT, 8)]


def test_a_grid_in_a_region_is_measured_from_the_rooms_origin_and_not_the_crops(project: Kiripix) -> None:
    built_room(project)
    region = ("--zoom", "2", "--region", "3,5,20,12")
    base = pixels(project, preview(project, *region))
    gridded = pixels(project, preview(project, *region, "--grid", "8"))

    # target columns 8 and 16 are in 3..22: they are at (8 - 3) * 2 and (16 - 3) * 2
    assert line_columns(base, gridded) == [10, 26]
    assert np.flatnonzero((base[:, 1:2] != gridded[:, 1:2]).any(axis=(1, 2))).tolist() == [6, 22]  # rows 8 and 16 less 5, times 2


def test_every_fifth_grid_line_is_stronger(project: Kiripix) -> None:
    built_room(project)
    base = pixels(project, preview(project, "--zoom", "1"))
    gridded = pixels(project, preview(project, "--zoom", "1", "--grid", "2"))

    def change(x: int) -> int:  # on a row of the plate whose pixels the lines don't cross
        return int(np.abs(gridded[1, x, :3].astype(int) - base[1, x, :3].astype(int)).sum())

    assert change(0) > change(2) and change(10) > change(8) and change(2) == change(4)


# --overlay walkable and reachable


def test_the_walkable_overlay_tints_walkable_ground_and_not_solid_or_a_pit(project: Kiripix) -> None:
    walled_room(project)
    decide(project, "brush", {"mask": "pit", "erase": False, "radius": 1, "points": [[38, 24], [38, 24]]})
    place(project, "spawn.main", "spawn")
    project.json("run", ROOM, expect=3)
    plain = pixels(project, preview(project, "--zoom", "1"))

    data = preview(project, "--overlay", "walkable", "--zoom", "1")

    assert data["data"]["overlay"] == "walkable" and data["data"]["path"].endswith(".walkable.x1.png")
    tinted = pixels(project, data)
    assert tuple(tinted[16, 30]) != tuple(plain[16, 30])  # walkable floor
    assert tuple(tinted[16, 30, 3:]) == tuple(plain[16, 30, 3:])  # the tint never touches alpha
    assert tuple(tinted[16, 10]) == tuple(plain[16, 10])  # solid (the wall)
    assert tuple(tinted[24, 38]) == tuple(plain[24, 38])  # the Pit


def test_the_reachable_overlay_leaves_out_an_unreachable_island(project: Kiripix) -> None:
    split_room(project)
    place(project, "spawn.main", "spawn", LEFT)
    project("run", ROOM)
    plain = pixels(project, preview(project, "--zoom", "1"))

    reached = pixels(project, preview(project, "--zoom", "1", "--overlay", "reachable"))
    walkable = pixels(project, preview(project, "--zoom", "1", "--overlay", "walkable"))

    assert tuple(reached[16, 23]) != tuple(plain[16, 23])  # where the Body can get to
    assert tuple(reached[16, 41]) == tuple(plain[16, 41])  # the island beyond the wall
    assert tuple(walkable[16, 41]) != tuple(plain[16, 41])  # but it is walkable


def test_an_overlay_from_an_out_of_date_stage_is_drawn_with_a_warning_naming_the_run(project: Kiripix) -> None:
    walled_room(project)
    place(project, "spawn.main", "spawn")
    project.json("run", ROOM, expect=3)
    assert preview(project, "--overlay", "walkable")["findings"] == []
    decide(project, "brush", {"mask": "pit", "erase": False, "radius": 1, "points": [[38, 24], [38, 24]]})

    result = preview(project, "--overlay", "walkable")

    assert result["ok"] is True
    finding = result["findings"][0]
    assert finding["code"] == "preview.overlay_out_of_date" and finding["severity"] == "warning"
    assert finding["fix"] == f"kiripix run {ROOM} place"


def test_the_reachable_overlay_without_reach_built_says_to_run_it(project: Kiripix) -> None:
    built_room(project)

    finding = preview(project, "--overlay", "reachable", expect=1)["findings"][0]

    assert finding["code"] == "preview.not_built" and finding["fix"] == f"kiripix run {ROOM} reach"
