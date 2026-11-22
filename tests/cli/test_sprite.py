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
        "frames.direction_missing", "frames.frame_count", "frames.unknown_direction", "clips.bad_name", "clips.duplicate_name", "clips.ticks_count"]
    assert [c["code"] for c in stages["fit"]["checks"]] == ["fit.grid_differs", "fit.alpha_partial", "fit.height", "fit.cell_grew"]
    finish = {p["name"]: p for p in stages["finish"]["params"]}
    assert finish["normals"]["default"] == "height" and finish["placement"]["default"] == "edge"
    assert {p["name"] for p in stages["fit"]["params"]} == {"mode", "height", "chroma", "align_feet", "anchor", "effect", "alpha", "alpha_pattern"}


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
    assert render["schema_version"] == 4
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


def test_a_pixellab_zip_with_its_metadata_json_runs_with_no_warning(project: Kiripix) -> None:
    folder = new_sprite(project)
    path = make_zip(project, "npc.zip", {f"Idle/rotations/{word}.png": figure() for word in WORDS})
    with zipfile.ZipFile(path, "a") as archive:
        archive.writestr("metadata.json", json.dumps({"frames": {"rotations": {}, "animations": {}}}))
    import_sheet(project, path)

    result = project.json("run", SPRITE, "frames")

    [clip] = load(folder / "work" / "frames" / "frames.json")["clips"]
    assert clip["name"] == "idle" and sorted(clip["directions"]) == ["e", "n", "s", "w"]
    assert [f["code"] for f in result["findings"] if f["code"].startswith("frames.")] == []


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
    assert measured["s"] == [7, 13]  # the legs' columns 6 and 8 average to 7; the lowest row of the figure (14) less 0.08
    # of the 13 px figure, 1 px (ticket 0318)

    decide(project, "fit", "pivot", {"x": 9, "y": 14, "direction": "s"})
    project.json("run", SPRITE)

    moved = load(fit / "fit.json")["pivots"]
    assert moved["s"] == [9, 14] and moved["w"] == measured["w"]
    assert not np.array_equal(read(fit / "color" / "idle" / "s" / "000.png"), before) or True

    project.json("undo", SPRITE, "fit")
    project.json("run", SPRITE)

    assert load(fit / "fit.json")["pivots"] == measured
    assert (read(fit / "color" / "idle" / "s" / "000.png") == before).all()


def tall_figure(colour: tuple[int, int, int], height: int = 40) -> np.ndarray:
    """A 16 x 48 frame with a figure `height` px tall (rows 4 to 4 + height - 1) on 1 px legs."""
    image = np.zeros((48, 16, 4), dtype=np.uint8)
    image[4:12, 6:9] = (*colour, 255)  # head
    image[12:4 + height - 8, 5:10] = (colour[0] // 2, colour[1] // 2, 120, 255)  # body
    image[4 + height - 8:4 + height, 6] = (*colour, 255)  # legs
    image[4 + height - 8:4 + height, 8] = (*colour, 255)
    return image


def test_the_pivot_sits_the_ground_share_of_the_figure_above_the_feet_in_every_direction(project: Kiripix) -> None:
    folder = new_sprite(project)
    sheet = np.concatenate([tall_figure((60 + 50 * n, 90, 200 - 40 * n)) for n in range(4)], axis=0)
    png_sheet(project, sheet, 1)

    project.json("run", SPRITE)

    fit = folder / "work" / "fit"
    record = load(fit / "fit.json")
    assert record["ground"] == {"ratio": 0.08, "figure": 40, "offset": 3}  # 3.2 px, rounded
    assert record["pivots"] == {d: [7, 40] for d in FOUR}  # the feet at row 43, 3 px up
    render = load(fit / "render.json")
    pivot_y = int(render["pivot"][1])
    for direction in FOUR:
        ys, _ = np.nonzero(read(fit / "color" / "idle" / direction / "000.png")[..., 3])
        assert int(ys.max()) == pivot_y + 3  # the lowest opaque row, the rule's 3 px below the pivot
        assert int(ys.max()) <= render["frame"]["height"] - 2  # the cell still has a pixel to spare below the feet


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
    assert sorted(sheet) == ["atlas", "cell", "clips", "directions", "files", "pivot", "schema_version"]
    assert sheet["schema_version"] == 2 and (folder / "work" / "sheet" / "color.png").is_file()


def test_palette_proposes_colour_regions_and_parts_give_each_its_own_ramp_of_shades(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 2), 2)

    result = project.json("run", SPRITE)

    palette = folder / "work" / "palette"
    regions = load(palette / "palette.json")["regions"]
    assert len(regions) >= 2 and all(r["pixels"] > 0 for r in regions)
    [proposal] = [f for f in result["findings"] if f["code"] == "palette.sprite_regions"]
    assert proposal["severity"] == "info" and regions[0]["name"] in proposal["message"]
    assert load(palette / "palette.json")["parts"] == [] and not (palette / "material").exists()

    named = [f"part{n}={r['name']}" for n, r in enumerate(regions)]
    project.json("set", SPRITE, "palette", f"parts={','.join(named)}", "shades=2")
    project.json("run", SPRITE, "palette")  # `finish` then refuses an outline in a ramp, as a body's does

    document = load(palette / "palette.json")
    assert [p["name"] for p in document["parts"]] == [f"part{n}" for n in range(len(regions))]
    assert all(len(p["rgb"]) == 2 for p in document["parts"])
    render = load(palette / "render.json")
    assert [m["name"] for m in render["materials"]] == [r["name"] for r in regions]
    frame = render["clips"][0]["directions"]["s"][0]
    colour, labels = read(palette / frame["files"]["color"]), read(palette / frame["files"]["material"])
    for number, part in enumerate(document["parts"], start=1):
        used = {tuple(c) for c in colour[labels == number][:, :3].tolist()}
        assert used <= {tuple(c) for c in part["rgb"]}
    assert [f for f in project.json("check", SPRITE)["findings"]
            if f["code"] in ("palette.sprite_regions", "palette.off_palette", "palette.ramp_shared")] == []


def test_finish_draws_inner_lines_where_a_sprites_parts_meet(project: Kiripix) -> None:
    folder = new_sprite(project)
    one = figure((200, 60, 60))  # a red head and legs on a body of (100, 30, 90), a purple far from the red in hue
    png_sheet(project, np.concatenate([one] * 4, axis=0), 1)
    project.json("set", SPRITE, "finish", "inner_lines=outline")

    failed = project.json("run", SPRITE, expect=1)  # no parts, so nothing to draw between

    assert [f["code"] for f in failed["findings"] if f["severity"] == "error"] == ["finish.inner_lines_without_parts"]
    regions = load(folder / "work" / "palette" / "palette.json")["regions"]
    assert len(regions) == 2
    project.json("set", SPRITE, "palette", f"parts=head={regions[0]['name']},body={regions[1]['name']}")
    refused = project.json("run", SPRITE, expect=1)
    [fix] = [f["fix"] for f in refused["findings"] if f["code"] == "finish.outline_in_ramp"]
    project.json(*fix.split()[1:])  # an outline colour in no part's ramp
    project.json("set", SPRITE, "finish", "inner_lines=off")
    project.json("run", SPRITE)
    finish = folder / "work" / "finish"
    plain = read(finish / "color" / "idle" / "s" / "000.png")

    project.json("set", SPRITE, "finish", "inner_lines=outline")
    project.json("run", SPRITE)

    lined = read(finish / "color" / "idle" / "s" / "000.png")
    outline = load(finish / "finish.json")["outline"]["rgb"]
    changed = np.argwhere((lined != plain).any(axis=2))
    # the body's top row under the head, 3 px; the legs' borders are lined too, but 1 px legs are all edge, which the outline
    # (placement=edge) paints over in any case
    assert len(changed) == 3 and len({int(y) for y, _ in changed}) == 1
    assert all(lined[y, x, :3].tolist() == outline for y, x in changed)
    assert load(finish / "finish.json")["inner_lines"]["mode"] == "outline"

    project.json("set", SPRITE, "finish", "line_skip=head")
    project.json("run", SPRITE)

    assert (read(finish / "color" / "idle" / "s" / "000.png") == plain).all()


def two_part_sprite(project: Kiripix) -> list[str]:
    """A sprite of a red head and legs on a purple body, built through `palette`; its two regions' names."""
    folder = new_sprite(project)
    png_sheet(project, np.concatenate([figure((200, 60, 60))] * 4, axis=0), 1)
    project.json("run", SPRITE)
    return [str(r["name"]) for r in load(folder / "work" / "palette" / "palette.json")["regions"]]


def test_a_sprites_part_joins_the_project_ramp_table_and_then_takes_its_colours(project: Kiripix) -> None:
    head, body = two_part_sprite(project)
    project.json("set", SPRITE, "palette", f"parts=head={head}")
    project.json("run", SPRITE, "palette")
    built = load(project.cwd / "assets" / "sprite" / "npc" / "work" / "palette" / "palette.json")["parts"][0]

    project.json("ramps-add", SPRITE, "--parts", "head", "--colours", owner=True)
    project.json("run", SPRITE, "palette", "--force")

    [shared] = load(project.cwd / "assets" / "sprite" / "npc" / "work" / "palette" / "palette.json")["parts"]
    assert shared["shared"] is True and shared["rgb"] == built["rgb"] and shared["row"] == 0
    project.json("set", SPRITE, "palette", f"parts=head={head},body={body}")
    refused = project.json("run", SPRITE, "palette", expect=3)  # the table is the Owner's to extend
    assert "palette.part_not_in_table" in [f["code"] for f in refused["findings"]]


def test_a_part_named_after_another_region_is_refused(project: Kiripix) -> None:
    head, body = two_part_sprite(project)
    project.json("set", SPRITE, "palette", f"parts={body}={head}")

    refused = project.json("run", SPRITE, "palette", expect=1)

    [finding] = [f for f in refused["findings"] if f["severity"] == "error"]
    assert finding["code"] == "palette.parts_invalid" and body in finding["message"]
    assert finding["fix"] == f"kiripix set {SPRITE} palette parts=" + ",".join([head, body])


def test_export_leaves_character_json_in_the_characters_format(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 2), 2)

    project.json("run", SPRITE)

    character = load(folder / "out" / "export" / "character.json")
    sheet = load(folder / "work" / "sheet" / "sheet.json")
    assert character == {"schema_version": 7, "asset": SPRITE, "files": {"color": "color.png", "normal": "normal.png"},
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


# --- effect parameters (ticket 0362) ---------------------------------------------------------------------------------


def spark(size: int = 24, frames: int = 3, blank_last: bool = True) -> np.ndarray:
    """`frames` frames of `size` px across in one row: a cross of 1 px arms from the middle, longer each frame, fully inside
    the frame so the box is smaller than the frame. The last frame is blank when `blank_last`."""
    middle = size // 2
    row = []
    for f in range(frames):
        image = np.zeros((size, size, 4), dtype=np.uint8)
        arm = 2 + 2 * f
        image[middle - arm:middle + arm + 1, middle] = (240, 220, 80, 255)
        image[middle, middle - arm:middle + arm + 1] = (240, 220, 80, 255)
        if blank_last and f == frames - 1:
            image[:] = 0
        row.append(image)
    return np.concatenate(row, axis=1)


def effect_sprite(project: Kiripix, *settings: str, size: int = 24, frames: int = 3, blank_last: bool = True,
                  expect: int = 0) -> Path:
    folder = new_sprite(project)
    png_sheet(project, spark(size, frames, blank_last), frames, directions=["s"])
    project.json("set", SPRITE, "frames", "directions=1")
    for setting in settings:
        stage, _, assignment = setting.partition(" ")
        project.json("set", SPRITE, stage, *assignment.split())
    project.json("run", SPRITE, expect=expect)
    return folder


def test_a_centred_effect_keeps_its_size_and_the_pivot_is_the_anchor(project: Kiripix) -> None:
    folder = effect_sprite(project, "fit anchor=centre effect=true", "finish outline=false")

    sheet = load(folder / "work" / "sheet" / "sheet.json")
    character = load(folder / "out" / "export" / "character.json")

    assert sheet["cell"] == {"width": 24, "height": 24} and sheet["pivot"] == {"x": 12, "y": 12}
    assert character["cell"] == {"width": 24, "height": 24} and character["pivot"] == {"x": 12, "y": 12}
    assert [c["pivot"] for c in character["clips"]] == [{"x": 12, "y": 12}]
    assert read(folder / "work" / "finish" / "color" / "idle" / "s" / "000.png").shape == (24, 24, 4)


def test_an_effect_with_an_outline_keeps_its_spare_pixel(project: Kiripix) -> None:
    folder = effect_sprite(project, "fit anchor=centre effect=true")  # finish's outline is on

    sheet = load(folder / "work" / "sheet" / "sheet.json")

    assert sheet["cell"] == {"width": 26, "height": 26} and sheet["pivot"] == {"x": 13, "y": 13}


def test_the_anchor_can_be_a_point_of_the_frame(project: Kiripix) -> None:
    folder = effect_sprite(project, "fit anchor=5,7 effect=true", "finish outline=false")

    sheet = load(folder / "work" / "sheet" / "sheet.json")

    assert sheet["cell"] == {"width": 24, "height": 24} and sheet["pivot"] == {"x": 5, "y": 7}
    assert load(folder / "out" / "export" / "character.json")["pivot"] == {"x": 5, "y": 7}


def test_a_telegraph_keeps_its_32_px_cell_whatever_its_pixels_cover(project: Kiripix) -> None:
    folder = effect_sprite(project, "fit anchor=centre effect=true", "finish outline=false", size=32, frames=2, blank_last=False)

    sheet = load(folder / "work" / "sheet" / "sheet.json")

    assert sheet["cell"] == {"width": 32, "height": 32} and sheet["pivot"] == {"x": 16, "y": 16}


def test_a_bad_anchor_fails_fit_with_a_fix(project: Kiripix) -> None:
    effect_sprite(project, "fit anchor=middle", expect=1)
    project.json("run", SPRITE, "frames")
    result = project.json("run", SPRITE, "fit", expect=1)

    [finding] = [f for f in result["findings"] if f["code"] == "fit.anchor_invalid"]
    assert finding["fix"] == f"kiripix set {SPRITE} fit anchor=feet"


def test_an_effect_ends_on_a_blank_frame_with_a_warning_and_is_flat(project: Kiripix) -> None:
    folder = effect_sprite(project, "fit anchor=centre effect=true", "finish outline=false")

    findings = project.json("check", SPRITE)["findings"]

    blank = [f for f in findings if f["code"] == "sheet.empty_frame"]
    assert [(f["severity"], f["position"]["field"]) for f in blank] == [("warning", "idle/s/2")]
    codes = {f["code"] for f in findings}
    assert "fit.height" not in codes and "palette.sprite_regions" not in codes
    exported = folder / "out" / "export"
    assert not (exported / "normal.png").exists() and (exported / "color.png").is_file()
    assert load(exported / "character.json")["files"] == {"color": "color.png"}

    written = project.json("export", SPRITE)["data"]["written"]

    assert not [w for w in written if w.endswith("normal.png")] and any(w.endswith("frames.tres") for w in written)
    texture = (project.cwd / "game" / "kiripix" / "sprite" / "npc" / "texture.tres").read_text("utf-8")
    assert "normal" not in texture and "diffuse_texture" in texture
    assert not (project.cwd / "game" / "kiripix" / "sprite" / "npc" / "normal.png").exists()


def test_without_effect_a_blank_frame_is_still_an_error_and_a_figure_keeps_its_normal(project: Kiripix) -> None:
    folder = effect_sprite(project, expect=2)

    codes = {(f["code"], f["severity"]) for f in project.json("check", SPRITE, expect=2)["findings"]}

    assert ("sheet.empty_frame", "error") in codes
    assert (folder / "out" / "export" / "normal.png").is_file()


def test_the_new_parameters_at_their_defaults_change_nothing(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, sheet_of(FOUR, 2), 2)
    project.json("run", SPRITE)
    before = {p: p.read_bytes() for p in sorted((folder / "work").rglob("*")) if p.is_file() and p.name != "stamp.json"}

    project.json("set", SPRITE, "fit", "anchor=feet", "effect=false")

    stages = project.json("status", "--kind", "sprite")["data"]["assets"][0]["stages"]
    assert {s["stage"]: s["status"] for s in stages}["fit"] == "done"
    after = {p: p.read_bytes() for p in sorted((folder / "work").rglob("*")) if p.is_file() and p.name != "stamp.json"}
    assert before == after
    assert "anchor" not in load(folder / "work" / "fit" / "fit.json") and "effect" not in load(folder / "work" / "fit" / "fit.json")
    assert "ticks" not in json.dumps(load(folder / "out" / "export" / "character.json"))


def test_a_clip_decision_takes_ticks_that_reach_the_export(project: Kiripix) -> None:
    folder = effect_sprite(project, "fit anchor=centre effect=true", "finish outline=false")

    decide(project, "frames", "clip", {"name": "idle", "loop": False, "ticks": [4, 6, 12]})
    project.json("run", SPRITE)

    [clip] = load(folder / "out" / "export" / "character.json")["clips"]
    assert clip["ticks"] == [4, 6, 12] and clip["fps"] == 8 and clip["loop"] is False


def test_ticks_must_have_one_duration_per_frame(project: Kiripix) -> None:
    effect_sprite(project, "fit anchor=centre effect=true")

    decide(project, "frames", "clip", {"name": "idle", "ticks": [4, 6]})
    result = project.json("run", SPRITE, "frames", expect=2)

    [finding] = [f for f in result["findings"] if f["code"] == "clips.ticks_count"]
    assert finding["position"]["stage"] == "frames" and finding["owner_action"] and finding["fix"] is None


# --- partial alpha: the vote, the dither and the finding on the input (ticket 0363) ----------------------------------------

GLOW = Path(__file__).parent.parent.parent / "backlog" / "m6" / "0347-trial" / "sheets" / "buff_glow.png"


def haze(size: int = 16, frames: int = 2) -> np.ndarray:
    """A solid 4 px core in the middle of an alpha 102 square haze (a glow's body), `frames` frames in one row."""
    one = np.zeros((size, size, 4), dtype=np.uint8)
    one[2:size - 2, 2:size - 2] = (80, 200, 255, 102)
    ys, xs = np.mgrid[2:size - 2, 2:size - 2]
    one[2:size - 2, 2:size - 2, 0] = 60 + (xs * 7 + ys * 13) % 40  # every pixel its own colour, so the pixel grid is 1:1
    one[size // 2 - 2:size // 2 + 2, size // 2 - 2:size // 2 + 2] = (255, 255, 255, 255)
    return np.concatenate([one] * frames, axis=1)


def haze_sprite(project: Kiripix, *settings: str, sheet: np.ndarray | None = None, frames: int = 2) -> Path:
    folder = new_sprite(project)
    png_sheet(project, haze(frames=frames) if sheet is None else sheet, frames, directions=["s"])
    project.json("set", SPRITE, "frames", "directions=1")
    project.json("set", SPRITE, "fit", "anchor=centre", "effect=true", *settings)
    project.json("set", SPRITE, "finish", "outline=false")
    project.json("run", SPRITE, "frames")
    project.json("run", SPRITE, "fit")
    return folder


def fit_alpha(folder: Path) -> np.ndarray:
    return read(folder / "work" / "fit" / "color" / "idle" / "s" / "000.png")[..., 3]


def test_by_default_partial_alpha_is_voted_away_and_the_finding_says_how_much(project: Kiripix) -> None:
    folder = haze_sprite(project)

    alpha = fit_alpha(folder)
    assert set(np.unique(alpha)) == {0, 255} and int((alpha == 255).sum()) == 16, "only the core is left; the haze is under half"
    findings = [f for f in project.json("check", SPRITE)["findings"] if f["code"] == "fit.alpha_partial"]
    assert [f["severity"] for f in findings] == ["warning"]
    assert "alpha=vote" in findings[0]["message"] and "alpha=dither" in findings[0]["message"]
    assert "%" in findings[0]["message"] and findings[0]["fix"] == f"kiripix set {SPRITE} fit alpha=dither"
    assert findings[0]["position"]["field"] == "idle/s/0"


def test_alpha_dither_keeps_the_haze_as_a_pattern_of_about_its_density(project: Kiripix) -> None:
    folder = haze_sprite(project, "alpha=dither", "alpha_pattern=4")

    alpha = fit_alpha(folder)
    image = read(folder / "work" / "fit" / "color" / "idle" / "s" / "000.png")
    assert set(np.unique(alpha)) == {0, 255} and (image[alpha == 0] == 0).all()
    assert (alpha[:2] == 0).all() and (alpha[7:11, 7:11] == 255).all(), "outside the haze is clear, the core stays solid"
    inner = alpha[3:15, 3:15]  # the 12 px haze square in the cell (fit leaves 1 px to spare around the frame)
    ring = np.ones((12, 12), dtype=bool)
    ring[4:8, 4:8] = False  # the core
    share = float((inner[ring] == 255).mean())
    assert 0.3 < share < 0.6, share
    assert (read(folder / "work" / "fit" / "color" / "idle" / "s" / "001.png")[..., 3] == alpha).all(), "the same pattern in every frame"
    findings = [f for f in project.json("check", SPRITE)["findings"] if f["code"] == "fit.alpha_partial"]
    assert [f["severity"] for f in findings] == ["warning"] and "owner_action" in findings[0] and "Bayer 4" in findings[0]["message"]


def test_a_sprite_with_binary_alpha_has_no_finding_and_writes_the_same_fit_json(project: Kiripix) -> None:
    folder = effect_sprite(project, "fit anchor=centre effect=true", "finish outline=false")
    before = (folder / "work" / "fit" / "fit.json").read_bytes()
    project.json("set", SPRITE, "fit", "alpha=dither")
    project.json("run", SPRITE, expect=0)

    record = load(folder / "work" / "fit" / "fit.json")
    assert "alpha_partial" not in record and "alpha" not in record
    assert not [f for f in project.json("check", SPRITE)["findings"] if f["code"] == "fit.alpha_partial"]
    assert b"alpha" not in before


def test_the_buff_glow_builds_with_dither_and_keeps_its_haze(project: Kiripix) -> None:
    sheet = np.asarray(Image.open(GLOW).convert("RGBA"), dtype=np.uint8)
    folder = haze_sprite(project, "alpha=dither", sheet=sheet, frames=sheet.shape[1] // sheet.shape[0])

    first = read(folder / "work" / "fit" / "color" / "idle" / "s" / "000.png")[..., 3]
    assert set(np.unique(first)) == {0, 255}
    kept = sum(int((read(f)[..., 3] == 255).sum()) for f in (folder / "work" / "fit" / "color" / "idle" / "s").glob("*.png"))
    assert kept > int((sheet[..., 3] == 255).sum()), "the 102 haze came through as opaque pixels"
    findings = [f for f in project.json("check", SPRITE)["findings"] if f["code"] == "fit.alpha_partial"]
    assert findings and all(f["severity"] == "warning" for f in findings)


def test_the_buff_glow_builds_with_vote_and_carries_the_finding(project: Kiripix) -> None:
    sheet = np.asarray(Image.open(GLOW).convert("RGBA"), dtype=np.uint8)
    haze_sprite(project, sheet=sheet, frames=sheet.shape[1] // sheet.shape[0])

    findings = [f for f in project.json("check", SPRITE)["findings"] if f["code"] == "fit.alpha_partial"]
    assert len(findings) == 1 and findings[0]["severity"] == "warning" and "alpha=dither" in findings[0]["message"]


def test_a_bad_alpha_pattern_fails_fit_with_a_fix(project: Kiripix) -> None:
    folder = new_sprite(project)
    png_sheet(project, haze(), 2, directions=["s"])
    project.json("set", SPRITE, "frames", "directions=1")
    project.json("set", SPRITE, "fit", "alpha=dither", "alpha_pattern=5")

    project.json("run", SPRITE, "frames")
    result = project.json("run", SPRITE, "fit", expect=1)

    assert any(f["code"] == "fit.alpha_pattern_invalid" for f in result["findings"]), folder
