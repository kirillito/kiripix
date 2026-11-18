"""`finish` draws inner lines at part borders (ticket 0215, spec §6.3). The fake Blender's material pass is, with the file
`blender-material-frames`, one vertical band per listed material, 1 `cloth` and 2 `skin` here, so the border is the column
between the halves of a 78 px frame; its depth is the same everywhere, so on the tie the right-hand pixel gets the line."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_character_model import HERO
from test_character_palette import built, project_palette
from test_character_part_vanishes import frames_with
from test_character_render import render_json

COLUMN = 39  # the right-hand pixel of the border between two bands of a 78 px frame


def read(path: Path) -> np.ndarray:
    return np.array(Image.open(path))


def finished(project: Kiripix, *params: str, clip: str = "idle") -> tuple[np.ndarray, np.ndarray, Path]:
    """The finished and the mapped first frame of `clip`'s south direction, and the Project folder."""
    frames_with(project, {"*": [1, 2]})
    folder = built(project, "colors=3")
    project.json("set", HERO, "finish", "outline=false", *params)
    project.json("run", HERO, "finish")
    return (read(folder / "work" / "finish" / "color" / clip / "s" / "000.png"),
            read(folder / "work" / "palette" / "color" / clip / "s" / "000.png"), folder)


def drawn(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work" / "finish" / "finish.json").read_text("utf-8"))
    return document


def test_the_stage_declares_the_line_parameters(project: Kiripix) -> None:
    [kind] = project.json("describe", "character", "--stage", "finish")["data"]["kinds"]

    [stage] = kind["stages"]

    by_name = {p["name"]: p for p in stage["params"]}
    assert by_name["inner_lines"]["choices"] == ["off", "outline", "dark"] and by_name["inner_lines"]["default"] == "off"
    assert by_name["line_skip"]["default"] == "" and by_name["line_darkness"]["default"] == 0.55


def test_off_leaves_the_frames_as_palette_mapped(project: Kiripix) -> None:
    frame, mapped, folder = finished(project)

    assert (frame == mapped).all() and "inner_lines" not in drawn(folder)


def test_outline_paints_the_farther_border_pixel_in_the_outline_colour(project: Kiripix) -> None:
    frame, mapped, folder = finished(project, "inner_lines=outline", "outline_colour=1")

    palette = project_palette(project)
    changed = (frame != mapped).any(axis=-1)
    assert set(np.nonzero(changed)[1]) <= {COLUMN}  # nothing but the border column, the one pixel right of the border
    assert (frame[:, COLUMN, :3] == palette[1]).all() and (frame[:, COLUMN - 1] == mapped[:, COLUMN - 1]).all()
    assert (frame[..., 3] == mapped[..., 3]).all()
    assert drawn(folder)["inner_lines"]["mode"] == "outline" and drawn(folder)["inner_lines"]["skip"] == []


def test_dark_paints_the_colour_finish_json_lists_for_the_material(project: Kiripix) -> None:
    frame, mapped, folder = finished(project, "inner_lines=dark")

    palette = project_palette(project)
    lines = drawn(folder)["inner_lines"]
    skin = lines["colours"]["skin"]  # the right-hand pixel is skin
    assert lines["mode"] == "dark" and skin["material"] == 2
    assert tuple(skin["rgb"]) == tuple(int(v) for v in palette[skin["colour"]])
    assert (frame[:, COLUMN, :3] == np.array(skin["rgb"])).all()
    assert (frame[:, :COLUMN] == mapped[:, :COLUMN]).all() and (frame[:, COLUMN + 1:] == mapped[:, COLUMN + 1:]).all()


def test_line_skip_drops_the_named_border_and_keeps_the_others(project: Kiripix) -> None:
    (project.cwd / "blender-materials").write_text(json.dumps(["a", "b", "c"]), encoding="utf-8")
    frames_with(project, {"*": [1, 2, 3]})  # bands 0 to 25, 26 to 51 and 52 to 77: borders at the columns 26 and 52
    folder = built(project, "colors=3")
    project.json("set", HERO, "finish", "outline=false", "inner_lines=outline")
    path = folder / "work" / "finish" / "color" / "idle" / "s" / "000.png"

    def lines(*skip: str) -> set[int]:
        project.json("set", HERO, "finish", f"line_skip={','.join(skip)}")
        project.json("run", HERO, "finish")
        mapped = read(folder / "work" / "palette" / "color" / "idle" / "s" / "000.png")
        return {int(c) for c in np.nonzero((read(path) != mapped).any(axis=-1))[1]}

    assert lines() == {26, 52}
    assert lines("a+b") == {52} and lines("c+b") == {26}
    assert lines("b") == set() and lines("a") == {52}
    assert lines("a+b", "b+c") == set()
    assert drawn(folder)["inner_lines"]["skip"] == ["a+b", "b+c"]


def test_an_unknown_material_fails_with_a_finding_that_lists_the_materials(project: Kiripix) -> None:
    finished(project)
    project.json("set", HERO, "finish", "inner_lines=outline", "line_skip=dragon+cloth")

    result = project.json("run", HERO, "finish", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "finish.line_skip_unknown"]
    assert "dragon" in finding["message"] and "cloth" in finding["message"] and "skin" in finding["message"]
    assert finding["fix"] == f"kiripix set {HERO} finish line_skip="


def test_dark_with_parts_asks_for_the_line_step_and_the_fix_builds(project: Kiripix) -> None:
    frames_with(project, {"*": [1, 2]})
    built(project, "parts=skin,cloth")
    project.json("set", HERO, "finish", "inner_lines=dark", "outline=false", "outline_colour=2")  # 2 is in no ramp

    result = project.json("run", HERO, "finish", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "finish.inner_lines_with_parts"]
    assert finding["fix"] == f"kiripix set {HERO} palette part_lines=true"

    project.json("set", HERO, "palette", "part_lines=true")
    project.json("run", HERO, "palette")
    project.json("run", HERO, "finish")


def test_dark_with_parts_draws_the_first_colour_of_the_ramp_of_the_part(project: Kiripix) -> None:
    frames_with(project, {"*": [1, 2]})
    folder = built(project, "parts=skin,cloth", "part_lines=true")
    project.json("set", HERO, "finish", "inner_lines=dark", "outline=false", "outline_colour=2")
    project.json("run", HERO, "finish")

    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    mapped = read(folder / "work" / "palette" / "color" / "idle" / "s" / "000.png")
    document: dict[str, Any] = json.loads((folder / "work" / "palette" / "palette.json").read_text("utf-8"))
    ramps = {p["name"]: p for p in document["parts"]}
    assert document["part_lines"] is True and all(len(p["rgb"]) == 4 for p in ramps.values())  # bands 3, plus the line step
    skin = ramps["skin"]
    assert (frame[:, COLUMN, :3] == np.array(skin["rgb"][0])).all()  # the right-hand pixel is skin
    assert (frame[:, :COLUMN] == mapped[:, :COLUMN]).all() and (frame[:, COLUMN + 1:] == mapped[:, COLUMN + 1:]).all()
    lines = drawn(folder)["inner_lines"]["colours"]
    assert lines["skin"]["colour"] == skin["indexes"][0] and lines["cloth"]["colour"] == ramps["cloth"]["indexes"][0]
    used = {tuple(c) for p in ramps.values() for c in p["rgb"][1:]} | {tuple(c["rgb"]) for c in document["colors"]}
    for part in ramps.values():  # no frame but the line uses the first colour, and no line is in another part's ramp
        first = tuple(part["rgb"][0])
        assert first not in used and (mapped[..., :3] != np.array(first)).any(axis=-1).all()
        assert all(first not in {tuple(c) for c in other["rgb"]} for other in ramps.values() if other is not part)
    assert [f for f in project.json("check", HERO)["findings"] if f["code"].startswith("palette.")] == []


def test_the_eye_materials_get_no_line_and_a_stamped_eye_is_not_painted_over(project: Kiripix) -> None:
    frames_with(project, {"*": [1, 2]})
    folder = built(project, "colors=3")
    project.json("set", HERO, "render", "eyes=skin")
    project.json("run", HERO, "render")
    project.json("run", HERO, "palette")
    project.json("set", HERO, "finish", "eyes=stamp", "outline=false")
    project.json("run", HERO, "finish")
    stamp_only = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")

    project.json("set", HERO, "finish", "inner_lines=outline", "outline_colour=1")
    project.json("run", HERO, "finish")

    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    assert (frame == stamp_only).all()  # the border is skin's, an eye material: no line, and no stamped pixel changed
    assert render_json(folder)["eyes"] == ["skin"]


def test_line_depth_draws_a_line_inside_one_material_at_a_depth_step(project: Kiripix) -> None:
    frames_with(project, {"*": [1]})  # one material: the only border is the depth step at the frame's middle
    folder = built(project, "colors=3")
    px_per_unit = float(render_json(folder)["px_per_unit"])
    (project.cwd / "blender-depth-step").write_text(str(round(2.0 / px_per_unit / 4.0 * 65535.0)), encoding="utf-8")  # 2 px; range 4
    project.json("run", HERO, "render", "--force")
    project.json("run", HERO, "palette")
    project.json("set", HERO, "finish", "outline=false", "inner_lines=outline", "outline_colour=1")
    path = folder / "work" / "finish" / "color" / "idle" / "s" / "000.png"
    mapped = read(folder / "work" / "palette" / "color" / "idle" / "s" / "000.png")
    palette = project_palette(project)

    def changed(*params: str) -> set[int]:
        project.json("set", HERO, "finish", *params)
        project.json("run", HERO, "finish")
        return {int(c) for c in np.nonzero((read(path) != mapped).any(axis=-1))[1]}

    assert changed("line_depth=0") == set()
    assert changed("line_depth=3") == set()  # the step is 2 px
    assert changed("line_depth=1.5") == {COLUMN}
    assert (read(path)[:, COLUMN, :3] == palette[1]).all()
    assert drawn(folder)["inner_lines"]["line_depth"] == 1.5
    assert changed("line_depth=1.5", "line_skip=cloth") == set()  # a single name skips its depth lines too


def with_depth_step(project: Kiripix, *palette_params: str) -> Path:
    """A built character whose one material (1, cloth) has a 2 px depth step at the frame's middle; palette run."""
    frames_with(project, {"*": [1]})
    folder = built(project, "colors=3", *palette_params)
    px_per_unit = float(render_json(folder)["px_per_unit"])
    (project.cwd / "blender-depth-step").write_text(str(round(2.0 / px_per_unit / 4.0 * 65535.0)), encoding="utf-8")
    project.json("run", HERO, "render", "--force")
    project.json("run", HERO, "palette")
    return folder


def finish_bytes(folder: Path) -> dict[str, bytes]:
    root = folder / "work" / "finish"
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*.png"))}


def test_line_depth_0_is_byte_equal_to_a_run_without_the_parameter(project: Kiripix) -> None:
    folder = with_depth_step(project)
    project.json("set", HERO, "finish", "inner_lines=outline", "outline_colour=1")
    project.json("run", HERO, "finish", "--force")
    without = finish_bytes(folder)

    project.json("set", HERO, "finish", "line_depth=0")
    project.json("run", HERO, "finish", "--force")

    assert without and finish_bytes(folder) == without


def test_dark_with_part_lines_draws_the_depth_line_in_the_part_line_step(project: Kiripix) -> None:
    folder = with_depth_step(project, "parts=cloth", "part_lines=true")
    project.json("set", HERO, "finish", "outline=false", "inner_lines=dark", "line_depth=1.5", "outline_colour=2")
    project.json("run", HERO, "finish")

    frame = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png")
    mapped = read(folder / "work" / "palette" / "color" / "idle" / "s" / "000.png")
    document: dict[str, Any] = json.loads((folder / "work" / "palette" / "palette.json").read_text("utf-8"))
    [cloth] = [p for p in document["parts"] if p["name"] == "cloth"]
    assert set(np.nonzero((frame != mapped).any(axis=-1))[1]) == {COLUMN}
    assert (frame[:, COLUMN, :3] == np.array(cloth["rgb"][0])).all()  # the first step of the ramp, not the outline's colour
    assert drawn(folder)["inner_lines"]["colours"]["cloth"]["colour"] == cloth["indexes"][0]
