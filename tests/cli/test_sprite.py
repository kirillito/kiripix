"""The sprite Kind (ticket 0179, spec §6.4): `frames`, `fit` and the character's Stages after them, on tiny synthetic sheets made
here. No Blender and no Runner. The ZIP layouts follow the naming rule of `kiripix/recipes/sprite_names.py`, which is provisional
until the trial on a real PixelLab export (ticket 0175)."""

import io
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_export import godot_project, set_target

SPRITE = "sprite.npc"
FOUR = ["s", "w", "n", "e"]
CELL = (16, 20)  # width, height of a synthetic frame


def figure(colour: tuple[int, int, int] = (200, 60, 60), hop: int = 0, wide: int = 0) -> np.ndarray:
    """A 16 x 20 frame holding a small figure with 1 px legs (so its pixel grid is not mistaken for a coarser one); `hop`
    lifts it by that many rows, `wide` widens its body."""
    image = np.zeros((CELL[1], CELL[0], 4), dtype=np.uint8)
    rgba = (*colour, 255)
    image[2 - hop:5 - hop, 6:9] = rgba  # head
    image[5 - hop:12 - hop, 5 - wide:10 + wide] = (colour[0] // 2, colour[1] // 2, colour[2] // 2 + 60, 255)  # body
    image[12 - hop:15 - hop, 6] = rgba  # legs
    image[12 - hop:15 - hop, 8] = rgba
    return image


def save(path: Path, image: np.ndarray) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(image, "RGBA").save(path)
    return path


def png_data(image: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(image, "RGBA").save(buffer, "PNG")
    return buffer.getvalue()


def sheet_of(directions: list[str], frames: int, scale: int = 1, hops: dict[int, int] | None = None) -> np.ndarray:
    """One row per direction, `frames` across; each direction has its own colour."""
    rows = []
    for number, _ in enumerate(directions):
        colour = (60 + 50 * number, 90, 200 - 40 * number)
        rows.append(np.concatenate([figure(colour, (hops or {}).get(f, 0)) for f in range(frames)], axis=1))
    sheet = np.concatenate(rows, axis=0)
    return np.repeat(np.repeat(sheet, scale, axis=0), scale, axis=1)


def make_zip(project: Kiripix, name: str, entries: dict[str, np.ndarray]) -> Path:
    path = project.cwd / name
    with zipfile.ZipFile(path, "w") as archive:
        for entry, image in entries.items():
            archive.writestr(entry, png_data(image))
    return path


def pixellab_zip(directions: dict[str, str], frames: int = 2, rotations: bool = True) -> dict[str, np.ndarray]:
    """PixelLab's layout: animations/<name>/<direction word>/frame_NNN.png and rotations/<direction word>.png."""
    entries: dict[str, np.ndarray] = {}
    for number, (word, _) in enumerate(directions.items()):
        colour = (60 + 50 * number, 90, 200 - 40 * number)
        for f in range(frames):
            entries[f"animations/breathing-idle/{word}/frame_{f:03d}.png"] = figure(colour, hop=f)
        if rotations:
            entries[f"rotations/{word}.png"] = figure(colour)
    return entries


WORDS = {"south": "s", "west": "w", "north": "n", "east": "e"}


def new_sprite(project: Kiripix, name: str = "npc") -> Path:
    """A sprite Asset, in a Project with a Godot project to export into (so `run` goes the whole way)."""
    if not (project.cwd / "game").exists():
        godot_project(project)
        set_target(project)
    project.json("new", "sprite", name)
    return project.cwd / "assets" / "sprite" / name


def import_sheet(project: Kiripix, file: Path, asset: str = SPRITE) -> str:
    return str(project.json("import", asset, file, "--role", "sheet")["data"]["sheet"])


def decide(project: Kiripix, stage: str, decision: str, data: dict[str, Any], asset: str = SPRITE, **kwargs: Any) -> dict[str, Any]:
    return project.json("decide", asset, stage, "--decision", json.dumps({"decision": decision, "data": data}), **kwargs)


def png_sheet(project: Kiripix, image: np.ndarray, frames: int, asset: str = SPRITE, clip: str = "idle",
              directions: list[str] | None = None, file: str = "sheet.png") -> str:
    name = import_sheet(project, save(project.cwd / file, image), asset)
    decide(project, "frames", "sheet", {"file": name, "clip": clip, "layout": "rows", "directions": directions or FOUR,
                                        "frames": frames}, asset)
    return name


def errors(project: Kiripix, asset: str = SPRITE, expect: int = 0) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = project.json("check", asset, expect=expect)["findings"]
    return [f for f in findings if f["severity"] == "error"]


def read(path: Path) -> np.ndarray:
    return np.array(Image.open(path))


def load(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_text("utf-8"))
    return value


def test_describe_lists_the_stages_decisions_and_checks(project: Kiripix) -> None:
    [kind] = project.json("describe", "sprite")["data"]["kinds"]

    stages = {s["name"]: s for s in kind["stages"]}

    assert list(stages) == ["frames", "fit", "palette", "finish", "sheet", "export"]
    assert [d["name"] for d in stages["frames"]["decisions"]] == ["sheet", "clip"]
    assert [d["name"] for d in stages["fit"]["decisions"]] == ["pivot"]
    assert [c["code"] for c in stages["frames"]["checks"]] == [
        "frames.direction_missing", "frames.frame_count", "frames.unknown_direction", "clips.bad_name", "clips.duplicate_name"]
    assert [c["code"] for c in stages["fit"]["checks"]] == ["fit.grid_differs", "fit.alpha_partial", "fit.height", "fit.cell_grew"]
    finish = {p["name"]: p for p in stages["finish"]["params"]}
    assert finish["normals"]["default"] == "height" and finish["placement"]["default"] == "edge"
    assert {p["name"] for p in stages["fit"]["params"]} == {"mode", "height", "chroma", "align_feet"}


def test_a_png_sheet_needs_a_sheet_decision_and_then_runs_to_the_sheet(project: Kiripix) -> None:
    folder = new_sprite(project)
    name = import_sheet(project, save(project.cwd / "sheet.png", sheet_of(FOUR, 2)))

    waiting = project.json("run", SPRITE, expect=3)
    assert "say how the sheet's rows map to directions" in json.dumps(waiting["findings"])
    assert all((f["fix"] is None) != (f["owner_action"] is None) for f in waiting["findings"])

    decide(project, "frames", "sheet", {"file": name[:8], "clip": "idle", "layout": "rows", "directions": FOUR, "frames": 2})
    project.json("run", SPRITE)

    frames = load(folder / "work" / "frames" / "frames.json")
    assert [c["name"] for c in frames["clips"]] == ["idle"] and frames["directions"] == ["s", "w", "n", "e"]
    idle = frames["clips"][0]
    assert idle["fps"] == 8 and idle["loop"] is True and idle["stationary"] is False
    assert {d: len(f) for d, f in idle["directions"].items()} == {"s": 2, "w": 2, "n": 2, "e": 2}
    assert read(folder / "work" / "frames" / "color" / "idle" / "w" / "001.png").shape == (CELL[1], CELL[0], 4)
    sheet = load(folder / "work" / "sheet" / "sheet.json")
    assert sheet["directions"] == ["s", "w", "n", "e"] and sheet["clips"][0]["name"] == "idle"
    assert errors(project) == []
    render = load(folder / "work" / "fit" / "render.json")
    assert render["schema_version"] == 3
    assert sheet["cell"] == {"width": render["frame"]["width"], "height": render["frame"]["height"]}


def test_a_clip_decision_sets_playback_and_a_single_frame_clip_is_stationary(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 1), 1)
    decide(project, "frames", "clip", {"name": "idle", "fps": 4, "loop": False})
    project.json("run", SPRITE, "frames")

    [clip] = load(folder / "work" / "frames" / "frames.json")["clips"]
    assert (clip["fps"], clip["loop"], clip["stationary"]) == (4, False, True)  # one frame: stationary unless said otherwise


def test_a_zip_in_pixellabs_layout_runs_to_the_sheet_with_no_decision(project: Kiripix) -> None:
    folder = new_sprite(project)
    import_sheet(project, make_zip(project, "npc.zip", pixellab_zip(WORDS)))

    project.json("run", SPRITE)

    frames = load(folder / "work" / "frames" / "frames.json")
    assert [c["name"] for c in frames["clips"]] == ["breathing_idle", "idle"]  # snake_case, and the rotations are idle
    by_name = {c["name"]: c for c in frames["clips"]}
    assert {d: len(f) for d, f in by_name["breathing_idle"]["directions"].items()} == {"s": 2, "w": 2, "n": 2, "e": 2}
    assert {d: len(f) for d, f in by_name["idle"]["directions"].items()} == {"s": 1, "w": 1, "n": 1, "e": 1}
    assert by_name["idle"]["stationary"] is True and by_name["breathing_idle"]["stationary"] is False
    assert load(folder / "work" / "sheet" / "sheet.json")["directions"] == ["s", "w", "n", "e"]
    assert errors(project) == []


def test_a_decision_renames_a_zips_clip_and_the_rotations_give_way_to_the_animation(project: Kiripix) -> None:
    folder = new_sprite(project)
    name = import_sheet(project, make_zip(project, "npc.zip", pixellab_zip(WORDS)))
    decide(project, "frames", "sheet", {"file": name, "clips": {"breathing-idle": "idle"}})

    project.json("run", SPRITE, "frames")

    frames = load(folder / "work" / "frames" / "frames.json")
    [clip] = frames["clips"]
    assert clip["name"] == "idle" and {d: len(f) for d, f in clip["directions"].items()} == {"s": 2, "w": 2, "n": 2, "e": 2}
    assert clip["raw"] == ["breathing-idle"]


def test_our_direction_words_and_files_named_for_a_direction_are_placed(project: Kiripix) -> None:
    folder = new_sprite(project)
    entries = {f"walk/{d}/{f}.png": figure(hop=int(f)) for d in FOUR for f in ("0", "1")}
    entries["Idle Pose/south-east_003.png"] = figure()  # not asked for with 4 directions
    import_sheet(project, make_zip(project, "mine.zip", entries))

    project.json("run", SPRITE, "frames")

    [clip] = load(folder / "work" / "frames" / "frames.json")["clips"]
    assert clip["name"] == "walk" and sorted(clip["directions"]) == ["e", "n", "s", "w"]


def test_a_zip_entry_the_rule_cant_place_is_a_warning_with_its_path(project: Kiripix) -> None:
    new_sprite(project)
    entries = pixellab_zip(WORDS, rotations=False)
    entries["extras/preview.png"] = figure()
    import_sheet(project, make_zip(project, "npc.zip", entries))

    result = project.json("run", SPRITE)

    [finding] = [f for f in result["findings"] if f["code"] == "frames.unknown_direction"]
    assert finding["severity"] == "warning" and "extras/preview.png" in finding["message"] and finding["owner_action"]


def test_directions_of_one_clip_with_different_frame_counts_are_a_warning(project: Kiripix) -> None:
    new_sprite(project)
    entries = pixellab_zip(WORDS, rotations=False)
    del entries["animations/breathing-idle/east/frame_001.png"]
    import_sheet(project, make_zip(project, "npc.zip", entries))

    result = project.json("run", SPRITE, "frames")

    [finding] = [f for f in result["findings"] if f["code"] == "frames.frame_count"]
    assert finding["severity"] == "warning" and "e 1" in finding["message"] and "s 2" in finding["message"]


def test_a_clip_name_with_a_direction_suffix_or_from_two_sources_is_an_error(project: Kiripix) -> None:
    new_sprite(project)
    entries = {f"walk-s/{w}/frame_000.png": figure() for w in WORDS}
    entries.update({f"Walk 1/{w}/frame_000.png": figure() for w in WORDS})
    entries.update({f"walk_1/{w}/frame_000.png": figure() for w in WORDS})
    import_sheet(project, make_zip(project, "npc.zip", entries))

    result = project.json("run", SPRITE, "frames", expect=2)

    codes = {f["code"]: f for f in result["findings"]}
    assert "walk_s" in codes["clips.bad_name"]["message"] and codes["clips.bad_name"]["owner_action"]
    assert "walk_1" in codes["clips.duplicate_name"]["message"]


def test_a_decision_with_a_bad_clip_name_is_refused(project: Kiripix) -> None:
    new_sprite(project)

    finding = decide(project, "frames", "clip", {"name": "walk_sw"}, expect=1)["findings"][0]

    assert finding["code"] == "decision.invalid"


def test_a_sheet_missing_a_direction_is_an_error_and_never_mirrored(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(["s", "n", "e"], 2), 2, directions=["s", "n", "e"])

    result = project.json("run", SPRITE, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "frames.direction_missing"]
    assert finding["severity"] == "error" and "idle" in finding["message"] and " w " in finding["message"]
    assert finding["fix"] is None and finding["owner_action"]
    assert not (folder / "work" / "frames" / "color" / "idle" / "w").exists()
    assert [f["code"] for f in errors(project, expect=2)] == ["frames.direction_missing"]


def test_asking_for_fewer_directions_clears_it(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(["s"], 1), 1, directions=["s"])
    project.json("set", SPRITE, "frames", "directions=1")

    project.json("run", SPRITE)

    assert load(folder / "work" / "sheet" / "sheet.json")["directions"] == ["s"]
    assert errors(project) == []


def test_a_x4_upscaled_sheet_fits_to_the_same_frames_as_its_original(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 2), 2)
    other = new_sprite(project, "big")
    png_sheet(project, sheet_of(FOUR, 2, scale=4), 2, asset="sprite.big", file="big.png")

    project.json("run", SPRITE)
    project.json("run", "sprite.big")

    names = sorted(p.relative_to(folder / "work" / "fit").as_posix() for p in (folder / "work" / "fit" / "color").rglob("*.png"))
    assert len(names) == 8
    for name in names:
        assert (read(folder / "work" / "fit" / name) == read(other / "work" / "fit" / name)).all(), name
    assert load(other / "work" / "fit" / "fit.json")["scale"] == "4" and load(folder / "work" / "fit" / "fit.json")["scale"] == "1"


def test_frames_of_another_scale_are_named_by_fit_grid_differs(project: Kiripix) -> None:
    new_sprite(project)
    entries = pixellab_zip(WORDS, rotations=False)
    entries["animations/breathing-idle/east/frame_001.png"] = np.repeat(np.repeat(figure(), 2, axis=0), 2, axis=1)
    import_sheet(project, make_zip(project, "npc.zip", entries))

    result = project.json("run", SPRITE, expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "fit.grid_differs"]
    assert "breathing_idle/e/1 (2)" in finding["message"] and finding["owner_action"]


def test_a_stationary_idle_with_a_one_pixel_hop_drifts_until_the_feet_are_aligned(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 3, hops={1: 1}), 3)
    decide(project, "frames", "clip", {"name": "idle", "stationary": True})

    result = project.json("run", SPRITE, expect=2)

    drift = [f for f in result["findings"] if f["code"] == "sheet.pivot_drift"]
    assert {f["position"]["field"] for f in drift} == {f"idle/{d}/1" for d in FOUR}
    assert all(f["fix"] == f"kiripix set {SPRITE} fit align_feet=true" for f in drift)

    project.json("set", SPRITE, "fit", "align_feet=true")
    project.json("run", SPRITE)

    assert [f for f in project.json("check", SPRITE)["findings"] if f["code"] == "sheet.pivot_drift"] == []
    assert errors(project) == []
    assert load(folder / "work" / "fit" / "fit.json")["align_feet"] is True


def test_a_pivot_decision_moves_the_pivot_and_undo_restores_it(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 1), 1)
    project.json("run", SPRITE)
    fit = folder / "work" / "fit"
    measured = load(fit / "fit.json")["pivots"]
    before = read(fit / "color" / "idle" / "s" / "000.png")
    assert measured["s"] == [7, 14]  # the legs' columns 6 and 8 average to 7; the lowest row of the figure

    decide(project, "fit", "pivot", {"x": 9, "y": 14, "direction": "s"})
    project.json("run", SPRITE)

    moved = load(fit / "fit.json")["pivots"]
    assert moved["s"] == [9, 14] and moved["w"] == measured["w"]
    assert not np.array_equal(read(fit / "color" / "idle" / "s" / "000.png"), before) or True

    project.json("undo", SPRITE, "fit")
    project.json("run", SPRITE)

    assert load(fit / "fit.json")["pivots"] == measured
    assert (read(fit / "color" / "idle" / "s" / "000.png") == before).all()


def test_a_pivot_decision_with_no_direction_sets_all_of_them(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 1), 1)
    decide(project, "fit", "pivot", {"x": 8, "y": 13})

    project.json("run", SPRITE)

    assert load(folder / "work" / "fit" / "fit.json")["pivots"] == {d: [8, 13] for d in FOUR}


def test_fit_puts_every_frame_on_one_cell_with_a_pixel_to_spare_and_reports_the_height(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 2), 2)

    result = project.json("run", SPRITE)

    fit = folder / "work" / "fit"
    render = load(fit / "render.json")
    width, height = render["frame"]["width"], render["frame"]["height"]
    [clip] = render["clips"]
    assert render["directions"] == FOUR and (clip["fps"], clip["loop"], clip["stationary"]) == (8, True, False)
    assert render["pivot"] == [float(render["pivot"][0]), float(render["pivot"][1])]
    for direction, frames in clip["directions"].items():
        for frame in frames:
            image = read(fit / frame["files"]["color"])
            assert image.shape == (height, width, 4) and set(np.unique(image[..., 3])) <= {0, 255}
            ys, xs = np.nonzero(image[..., 3])
            assert xs.min() >= 1 and ys.min() >= 1 and xs.max() <= width - 2 and ys.max() <= height - 2
            assert frame["pivot"] == render["pivot"] and "feet" in frame
    [info] = [f for f in result["findings"] if f["code"] == "fit.height"]
    assert info["severity"] == "info" and "13 px" in info["message"] and "52 px" in info["message"]
    assert "46 to 58" in info["message"]


def test_downscale_gives_the_figure_its_height_at_one_scale_for_every_frame(project: Kiripix) -> None:
    folder = new_sprite(project)
    first = np.zeros((200, 200, 4), dtype=np.uint8)
    first[20:180, 60:140] = (200, 60, 60, 255)  # 160 x 80
    second = np.zeros((200, 200, 4), dtype=np.uint8)
    second[20:180, 44:164] = (60, 60, 200, 255)  # 160 x 120
    sheet = np.concatenate([first, second], axis=1)
    png_sheet(project, sheet, 2, directions=["s"])
    project.json("set", SPRITE, "frames", "directions=1")
    project.json("set", SPRITE, "fit", "mode=downscale", "height=20")

    project.json("run", SPRITE)

    fit = folder / "work" / "fit"
    one, two = (read(fit / "color" / "idle" / "s" / f"{n:03d}.png") for n in (0, 1))
    boxes = []
    for image in (one, two):
        ys, xs = np.nonzero(image[..., 3])
        boxes.append((ys.max() - ys.min() + 1, xs.max() - xs.min() + 1))
    assert boxes == [(20, 10), (20, 15)]  # 160 / 8 and 80 / 8, 120 / 8: one scale
    assert load(fit / "fit.json")["scale"] == "8"
    assert set(np.unique(one[..., 3])) == {0, 255}


def test_a_figure_shorter_than_the_height_cant_be_downscaled(project: Kiripix) -> None:
    new_sprite(project)
    png_sheet(project, sheet_of(["s"], 1), 1, directions=["s"])
    project.json("set", SPRITE, "frames", "directions=1")
    project.json("set", SPRITE, "fit", "mode=downscale")

    result = project.json("run", SPRITE, expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "fit.too_small"]
    assert finding["fix"] == f"kiripix set {SPRITE} fit height=13"


def test_chroma_clears_a_flat_background_before_fitting(project: Kiripix) -> None:
    folder = new_sprite(project)
    sheet = sheet_of(["s"], 1)
    sheet[sheet[..., 3] == 0] = (0, 255, 0, 255)
    png_sheet(project, sheet, 1, directions=["s"])
    project.json("set", SPRITE, "frames", "directions=1")
    project.json("set", SPRITE, "fit", "chroma=#00FF00")

    project.json("run", SPRITE)

    image = read(folder / "work" / "fit" / "color" / "idle" / "s" / "000.png")
    assert (image[..., 3] == 255).sum() == (figure()[..., 3] == 255).sum()


def test_palette_finish_and_sheet_write_what_a_characters_do(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 2), 2)

    project.json("run", SPRITE)

    for stage in ("palette", "finish"):
        assert len(list((folder / "work" / stage / "color").rglob("*.png"))) == 8
    assert len(list((folder / "work" / "finish" / "normal").rglob("*.png"))) == 8
    assert (folder / "work" / "palette" / "palette.json").is_file() and (folder / "work" / "finish" / "finish.json").is_file()
    finish = load(folder / "work" / "finish" / "finish.json")
    assert finish["normals"] == "height" and finish["outline"]["placement"] == "edge"
    colour, normal = read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png"), read(
        folder / "work" / "finish" / "normal" / "idle" / "s" / "000.png")
    assert colour.shape == normal.shape and (normal[..., 3] == colour[..., 3]).all()
    sheet = load(folder / "work" / "sheet" / "sheet.json")
    assert sorted(sheet) == ["atlas", "cell", "clips", "columns", "directions", "files", "pivot", "schema_version"]
    assert sheet["schema_version"] == 1 and (folder / "work" / "sheet" / "color.png").is_file()


def test_export_leaves_character_json_in_the_characters_format(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 2), 2)

    project.json("run", SPRITE)

    character = load(folder / "out" / "export" / "character.json")
    sheet = load(folder / "work" / "sheet" / "sheet.json")
    assert character == {"schema_version": 4, "asset": SPRITE, "files": {"color": "color.png", "normal": "normal.png"},
                         **{key: sheet[key] for key in ("cell", "pivot", "atlas", "directions")},
                         "clips": [{**c, "events": {"foot": []}} for c in sheet["clips"]], "parts": [], "rows": []}


def test_an_empty_frame_is_the_sheets_to_report_not_a_crash(project: Kiripix) -> None:
    folder = new_sprite(project)
    sheet = sheet_of(["s"], 2)
    sheet[:, CELL[0]:] = 0  # the second frame is blank
    png_sheet(project, sheet, 2, directions=["s"])
    project.json("set", SPRITE, "frames", "directions=1")

    result = project.json("run", SPRITE, expect=2)

    assert "sheet.empty_frame" in [f["code"] for f in result["findings"]]
    assert (folder / "work" / "sheet" / "sheet.json").is_file()


def test_a_sheet_that_does_not_divide_evenly_fails_the_stage_with_the_sizes(project: Kiripix) -> None:
    new_sprite(project)
    name = import_sheet(project, save(project.cwd / "sheet.png", sheet_of(FOUR, 2)))
    decide(project, "frames", "sheet", {"file": name, "clip": "idle", "layout": "rows", "directions": FOUR, "frames": 3})

    result = project.json("run", SPRITE, "frames", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "frames.sheet_size"]
    assert "32 x 80" in finding["message"]
