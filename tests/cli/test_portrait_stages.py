"""The portrait's image Stages (ticket 0243, spec §6.7): cutout, register, fit, palette and finish on a fixture set made here:
a neutral image on a noisy green with a light rim, and emotions that are shifted and scaled copies of it (what an image model
does to an edit), or copies with other noise, each with its own changed face.

The game's rules (ticket 0321) leave `register` off and `finish`'s lock off by default; the tests of registration and the lock
(0243's) switch them on with `still_body`."""

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix, stage_statuses
from PIL import Image

PORTRAIT = "portrait.sanjay"
KEY = (30, 238, 24)
WIDTH, HEIGHT = 480, 640
SCALE = 2.6  # the figure's 520 rows onto the 200 canvas rows from `head_top` 40 to the anchor's row 239
FIGURE = (slice(120, 640), slice(100, 380))  # rows, columns: the figure stands on the bottom edge
CANVAS = (240, 192)  # rows, columns: the default canvas (0323)
FACE = (slice(130, 270), slice(170, 310))
FACE_POLYGON = [[150, 110], [330, 110], [330, 290], [150, 290]]  # the face's box with room for a 1 % shift
REGION = (slice(110, 291), slice(150, 331))  # the same, as a box


def blocks(rng: np.random.Generator, rows: int, columns: int, size: int = 8) -> np.ndarray:
    tile = rng.integers(40, 220, size=(-(-rows // size), -(-columns // size), 3)).astype(np.uint8)
    return np.repeat(np.repeat(tile, size, axis=0), size, axis=1)[:rows, :columns]


def neutral() -> np.ndarray:
    """A figure of random blocks on a green a few levels off everywhere (a lossy codec's), a light rim round it and a stray
    island of the figure's colour on the background."""
    rng = np.random.default_rng(3)
    image = np.clip(np.array(KEY) + rng.integers(-3, 4, size=(HEIGHT, WIDTH, 3)), 0, 255).astype(np.uint8)
    image[115:640, 95:385] = (248, 248, 248)  # the rim, 5 px wide
    image[FIGURE] = blocks(rng, 520, 280)
    image[40:56, 20:36] = blocks(rng, 16, 16)
    return image


def moved(image: np.ndarray, scale: float, dx: float, dy: float) -> np.ndarray:
    """What an image model does to an edit: the picture sampled at `scale * p + shift` (nearest)."""
    xs = np.clip(np.floor(scale * np.arange(WIDTH) + dx + 0.5).astype(int), 0, WIDTH - 1)
    ys = np.clip(np.floor(scale * np.arange(HEIGHT) + dy + 0.5).astype(int), 0, HEIGHT - 1)
    return image[ys][:, xs]


def with_face(image: np.ndarray, seed: int) -> np.ndarray:
    out = image.copy()
    out[FACE] = blocks(np.random.default_rng(seed), 140, 140)
    return out


def save(project: Kiripix, name: str, image: np.ndarray) -> str:
    Image.fromarray(image, "RGB").save(project.cwd / f"{name}.png")
    return f"{name}.png"


def declare(project: Kiripix, emotion: str, image: np.ndarray) -> None:
    entry = json.dumps({"decision": "emotion", "data": {"id": emotion}})
    project.json("decide", PORTRAIT, "source", "--decision", entry)
    variant = project.json("import", PORTRAIT, save(project, emotion, image), "--emotion", emotion)["data"]["variant"]
    project.json("pick", PORTRAIT, variant, "--emotion", emotion)


def make_set(project: Kiripix, emotions: dict[str, np.ndarray], face: bool = True) -> Path:
    project.json("new", "portrait", "sanjay")
    variant = project.json("import", PORTRAIT, save(project, "neutral", neutral()))["data"]["variant"]
    project.json("pick", PORTRAIT, variant)
    for name, image in emotions.items():
        declare(project, name, image)
    if face:
        draw_face(project)
    return project.cwd / "assets" / "portrait" / "sanjay"


def draw_face(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    build(project, "cutout")  # the face is drawn on the neutral cutout
    entry = json.dumps({"decision": "face", "data": {"points": FACE_POLYGON}})
    return project.json("decide", PORTRAIT, "register", "--decision", entry, expect=expect)


def still_body(project: Kiripix, mode: str = "outside_face") -> None:
    """0243's set: registration on and the body locked to the neutral's outside the face."""
    project.json("set", PORTRAIT, "register", f"mode={mode}")
    project.json("set", PORTRAIT, "finish", "lock_outside_face=true")


def work(folder: Path, stage: str, name: str = "") -> Path:
    return folder / "work" / stage / name


def record(folder: Path, stage: str, name: str) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(work(folder, stage, name).read_text("utf-8"))
    return value


def image_of(folder: Path, stage: str, emotion: str, neutral_name: str) -> np.ndarray:
    name = neutral_name if emotion == "neutral" else f"emotions/{emotion}.png"
    return np.asarray(Image.open(work(folder, stage, name)).convert("RGBA"))


def to_canvas(folder: Path, x: float, y: float) -> tuple[float, float]:
    """A point of the 640 x 480 picture on the canvas, through the Grid and the padding `fit` recorded."""
    grid = record(folder, "fit", "grid.json")
    scale = float(Fraction(str(grid["scale_x"])))
    left, top = grid["padding"][0], grid["padding"][1]
    return (x + left - grid["offset_x"]) / scale, (y + top - grid["offset_y"]) / scale


def target_box(folder: Path, rows: slice, columns: slice) -> tuple[slice, slice]:
    """A box of the 640 x 480 picture in the canvas's pixels, widened by one."""
    x0, y0 = to_canvas(folder, columns.start, rows.start)
    x1, y1 = to_canvas(folder, columns.stop, rows.stop)
    return slice(max(int(y0) - 1, 0), int(y1) + 2), slice(max(int(x0) - 1, 0), int(x1) + 2)


STAGES = ["brief", "source", "cutout", "register", "fit", "palette", "finish"]


def build(project: Kiripix, upto: str = "finish", expect: int = 0) -> dict[str, Any]:
    """Run each Stage up to `upto` in order (a done Stage is skipped); the last must exit with `expect`."""
    result: dict[str, Any] = {}
    for stage in STAGES[:STAGES.index(upto) + 1]:
        last = stage == upto
        result = project.json("run", PORTRAIT, stage, expect=expect if last else 0)
    return result


def run_finish(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    return build(project, "finish", expect)


@pytest.mark.parametrize("mode", ["outside_face", "figure"])
def test_shifted_and_scaled_emotions_end_on_the_canvas_with_the_body_still(project: Kiripix, mode: str) -> None:
    base = neutral()
    emotions = {"happy": with_face(moved(base, 1.01, 2.4, -1.8), 11), "sad": with_face(moved(base, 0.99, -2.2, 1.9), 12)}
    folder = make_set(project, emotions)
    still_body(project, mode)

    result = run_finish(project)

    assert not [f for f in result["findings"] if f["severity"] == "error"]
    shown = record(folder, "register", "register.json")
    for name in emotions:
        entry = shown["images"][name]
        assert entry["applied"] and not entry["problems"] and entry["residual_target"] < 0.5, entry
    grid = record(folder, "fit", "grid.json")
    assert (grid["width"], grid["height"]) == (192, 240) and grid["anchor"] == [96, 239]
    colours = {tuple(c) for c in record(folder, "palette", "palette.json")["colours"]}
    assert 1 < len(colours) <= 32
    box = target_box(folder, *REGION)
    outside = np.ones(CANVAS, dtype=bool)
    outside[box] = False
    base_image = image_of(folder, "finish", "neutral", "finish.png")
    assert outside.sum() > 10000 and (base_image[..., 3] == 255).sum() > 10000
    for name in ("neutral", *emotions):
        image = image_of(folder, "finish", name, "finish.png")
        assert image.shape == (*CANVAS, 4), "the canvas's size"
        assert set(np.unique(image[..., 3])) <= {0, 255}, "alpha is binary"
        opaque = image[image[..., 3] == 255][:, :3]
        assert {tuple(int(v) for v in c) for c in np.unique(opaque, axis=0)} <= colours, "every pixel on the set's colours"
        assert (image[outside] == base_image[outside]).all(), f"the body of {name} is the neutral's, pixel for pixel"
        if name != "neutral":
            assert (image[target_box(folder, *FACE)] != base_image[target_box(folder, *FACE)]).any(), "the face is its own"


def test_an_emotion_shifted_past_the_limits_is_misaligned(project: Kiripix) -> None:
    folder = make_set(project, {"happy": with_face(moved(neutral(), 1.0, 40, 0), 11)})
    still_body(project)

    result = build(project, "register", expect=2)

    found = [f for f in result["findings"] if f["code"] == "portrait.misaligned"]
    assert len(found) == 1 and found[0]["severity"] == "error" and found[0]["owner_action"]
    assert found[0]["data"]["emotion"] == "happy" and found[0]["data"]["problems"]
    assert not record(folder, "register", "register.json")["images"]["happy"]["applied"]


def noisy(image: np.ndarray, seed: int) -> np.ndarray:
    """The same picture, every pixel of the figure re-rendered with other noise, as an image model does."""
    rng = np.random.default_rng(seed)
    out = image.astype(int)
    out[FIGURE] += rng.integers(-5, 6, size=(520, 280, 3))
    return np.clip(out, 0, 255).astype(np.uint8)


def test_noise_outside_the_face_is_locked_to_the_neutral_s_pixels(project: Kiripix) -> None:
    base = neutral()
    folder = make_set(project, {"happy": with_face(noisy(base, 5), 11), "angry": with_face(noisy(base, 6), 12)})
    still_body(project)

    result = run_finish(project)

    finish = record(folder, "finish", "finish.json")
    assert finish["locked"] and finish["face"]
    shimmer = [f for f in result["findings"] if f["code"] == "portrait.shimmer"]
    assert {f["data"]["emotion"] for f in shimmer} == {"happy", "angry"}, "what the lock removed is still reported"
    assert all(f["data"]["locked"] and f["data"]["exact"] > 100 for f in shimmer)
    box = target_box(folder, *REGION)
    outside = np.ones(CANVAS, dtype=bool)
    outside[box] = False
    base_image = image_of(folder, "finish", "neutral", "finish.png")
    for name in ("happy", "angry"):
        assert (image_of(folder, "finish", name, "finish.png")[outside] == base_image[outside]).all()


def test_without_the_lock_shimmer_counts_the_noise(project: Kiripix) -> None:
    base = neutral()
    folder = make_set(project, {"happy": with_face(noisy(base, 5), 11)})  # the lock is off by default

    result = run_finish(project)

    [found] = [f for f in result["findings"] if f["code"] == "portrait.shimmer"]
    assert not found["data"]["locked"] and found["data"]["face"] and found["data"]["exact"] > 100
    assert found["data"]["boxes"] and found["severity"] == "info" and found["owner_action"]
    outside = np.ones(CANVAS, dtype=bool)
    outside[target_box(folder, *REGION)] = False
    happy = image_of(folder, "finish", "happy", "finish.png")
    base_image = image_of(folder, "finish", "neutral", "finish.png")
    here = int((happy != base_image).any(axis=2)[outside].sum())
    assert abs(here - found["data"]["exact"]) <= found["data"]["exact"] * 0.1, "the box round the region is a little wider"


def test_without_a_face_region_nothing_is_locked_and_every_pixel_counts(project: Kiripix) -> None:
    base = neutral()
    make_set(project, {"happy": noisy(base, 5)}, face=False)

    result = run_finish(project)

    [found] = [f for f in result["findings"] if f["code"] == "portrait.shimmer"]
    assert not found["data"]["face"] and not found["data"]["locked"] and found["data"]["exact"] > 100
    assert "no face region" in found["message"]


def test_shimmer_counts_a_known_change_outside_the_face(project: Kiripix) -> None:
    base = neutral()
    changed = with_face(base, 11)
    changed[450:474, 250:274] = (255, 0, 255)  # a 24 px block, 8 to 9 canvas px across, on the body
    folder = make_set(project, {"happy": changed})

    result = run_finish(project)
    left, top = (int(v) for v in to_canvas(folder, 250, 450))

    [found] = [f for f in result["findings"] if f["code"] == "portrait.shimmer"]
    assert 40 <= found["data"]["exact"] <= 160 and found["data"]["visible"] >= 40
    [box] = [b for b in found["data"]["boxes"] if b["pixels"] >= 40]
    assert box["y"] <= top + 9 and box["y"] + box["height"] >= top and box["x"] <= left + 9 and box["x"] + box["width"] >= left
    assert found["position"]["x"] >= 0


def test_cutout_keys_a_noisy_background_and_takes_the_rim_and_the_island_off(project: Kiripix) -> None:
    folder = make_set(project, {"happy": with_face(neutral(), 11)})

    build(project, "cutout")

    cut = image_of(folder, "cutout", "neutral", "cutout.png")
    assert (cut[:100, :90, 3] == 0).all(), "the noisy green, and the island at (20, 40), are gone"
    assert (cut[FIGURE][..., 3] == 255).mean() > 0.99, "the figure stays"
    assert (cut[116:640, 96, 3] == 0).all() and (cut[200, 94, 3] == 0), "the rim is gone"
    info = record(folder, "cutout", "cutout.json")["images"]["neutral"]
    assert abs(info["chroma"][1] - KEY[1]) <= 2 and info["rim"] > 1000 and info["islands"] > 100


def test_cutout_with_a_wrong_key_says_so(project: Kiripix) -> None:
    make_set(project, {})
    project.json("set", PORTRAIT, "cutout", "chroma=#FF00FF")

    result = build(project, "cutout", expect=2)

    assert "cutout.chroma_keyed_nothing" in [f["code"] for f in result["findings"]]


def test_the_palette_modes_and_the_outline(project: Kiripix) -> None:
    folder = make_set(project, {"happy": with_face(neutral(), 11)})
    project.json("set", PORTRAIT, "palette", "n=8")

    run_finish(project)

    colours = record(folder, "palette", "palette.json")
    assert len(colours["colours"]) == 8 and colours["mode"] == "set" and colours["outline"] in colours["colours"]
    finish = image_of(folder, "finish", "neutral", "finish.png")
    row = np.nonzero(finish[150, :, 3])[0]
    assert (finish[150, row[0], :3] == np.array(colours["outline"], dtype=np.uint8)).all(), "the figure's edge is the outline"
    assert (finish[239, 50:140, 3] == 255).all(), "no line along the cut at the bottom of the canvas: the figure is there"
    assert (finish[239, 70:120, :3] != np.array(colours["outline"], dtype=np.uint8)).any()
    project.json("set", PORTRAIT, "palette", "mode=off")
    run_finish(project)
    off = image_of(folder, "finish", "neutral", "finish.png")
    assert len(np.unique(off[off[..., 3] == 255][:, :3], axis=0)) > 8, "colours kept"
    project.json("set", PORTRAIT, "palette", "mode=project")
    run_finish(project)
    assert len(record(folder, "palette", "palette.json")["colours"]) >= 1


def test_a_new_emotion_is_added_without_cutting_the_others_again(project: Kiripix) -> None:
    base = neutral()
    make_set(project, {"happy": with_face(base, 11)})
    build(project, "register")

    declare(project, "sad", with_face(base, 12))
    messages = " ".join(str(r.get("message")) for stage in ("cutout", "register") for r in build(project, stage)["data"]["results"])
    assert "2 of 3 images unchanged" in messages and "1 of 2 emotions unchanged" in messages


def test_a_face_region_makes_register_and_what_follows_stale(project: Kiripix) -> None:
    make_set(project, {"happy": with_face(neutral(), 11)}, face=False)
    run_finish(project)
    assert stage_statuses(project)["portrait.sanjay/finish"] == "done"

    draw_face(project)

    statuses = stage_statuses(project)
    assert [statuses[f"portrait.sanjay/{s}"] for s in ("cutout", "register", "fit", "palette", "finish")] == [
        "done", "stale", "stale", "stale", "stale"]


def test_a_face_edit_makes_register_stale_and_not_needs_review(project: Kiripix) -> None:
    """The Owner's rule (2026-11-18, ticket 0298): a `face` change is stale only, for the UI reruns `register` each stroke."""
    make_set(project, {"happy": with_face(neutral(), 11)})
    build(project, "register")
    assert stage_statuses(project)["portrait.sanjay/register"] == "done"

    entry = json.dumps({"decision": "face", "data": {"points": FACE_POLYGON, "radius": 6}})
    project.json("decide", PORTRAIT, "register", "--decision", entry)

    shown = project.json("show", PORTRAIT)["data"]["stages"]
    register = next(s for s in shown if s["stage"] == "register")
    assert register["status"] == "stale" and register["status"] != "needs-review"


def test_show_lists_each_emotions_built_images_per_stage(project: Kiripix) -> None:
    make_set(project, {"happy": with_face(neutral(), 11)})
    before = project.json("show", PORTRAIT)["data"]["emotions"][0]["images"]
    # drawing the face built `source` and `cutout`; `register` is not built, so it lists only the input it will use
    assert [(i["stage"], i["image"] is None) for i in before] == [("source", False), ("cutout", False), ("register", True)]

    build(project, "register")
    images = {i["stage"]: i for i in project.json("show", PORTRAIT)["data"]["emotions"][0]["images"]}
    assert images["cutout"]["image"].endswith("work/cutout/emotions/happy.png")
    assert images["register"]["image"].endswith("work/register/emotions/happy.png")
    assert images["register"]["input_image"] == images["cutout"]["image"]
    assert images["fit"]["image"] is None  # not built yet: only its input is listed
    assert (project.cwd / images["register"]["image"]).is_file()


# ticket 0321: whole-body emotions


ARM = (slice(130, 250), slice(390, 430))  # rows, columns: a raised arm beside the head, outside the face region


def test_a_raised_arm_goes_through_finish_where_its_image_put_it(project: Kiripix) -> None:
    base = neutral()
    wave = with_face(base, 11)
    wave[ARM] = blocks(np.random.default_rng(21), 120, 40)
    folder = make_set(project, {"wave": wave})

    registered = build(project, "register")
    result = run_finish(project)

    codes = [f["code"] for f in result["findings"]]
    assert "portrait.misaligned" not in codes and "portrait.residual" not in codes
    shown = record(folder, "register", "register.json")
    assert shown["mode"] == "off" and shown["images"]["wave"]["scale"] == [1.0, 1.0] and not shown["images"]["wave"]["applied"]
    assert "registration is off" in " ".join(str(r.get("message")) for r in registered["data"]["results"])
    assert not record(folder, "finish", "finish.json")["locked"]
    rows, columns = target_box(folder, *ARM)
    inner = (slice(rows.start + 2, rows.stop - 3), slice(columns.start + 2, columns.stop - 3))  # inside the arm's outline
    arm = image_of(folder, "finish", "wave", "finish.png")[inner][..., 3] == 255
    assert arm.mean() > 0.9, "the arm is the emotion's own (a pale block at its edge goes with the light rim)"
    assert (image_of(folder, "finish", "neutral", "finish.png")[inner][..., 3] == 0).all(), "the neutral has no arm there"


def test_fit_puts_the_head_top_at_head_top_and_the_foot_on_the_anchor(project: Kiripix) -> None:
    base = neutral()
    folder = make_set(project, {"happy": with_face(base, 11), "sad": with_face(moved(base, 1.0, 0, 30), 12)}, face=False)

    build(project, "fit")

    grid = record(folder, "fit", "grid.json")
    assert grid["head_top"] == 40 and grid["scale_x"] == grid["scale_y"] == "13/5", "one scale, the set's"
    assert grid["figure"]["top_y"] == 40 and grid["figure"]["foot_y"] == 239
    fitted = image_of(folder, "fit", "neutral", "fit.png")
    assert fitted.shape == (*CANVAS, 4) and (fitted[:40, ..., 3] == 0).all() and fitted[40, :, 3].any()
    assert (fitted[:, :3, 3] == 0).all(), "transparent where the source has no pixels"
    sad = image_of(folder, "fit", "sad", "emotions/sad.png")
    assert int(np.nonzero(sad[..., 3].any(axis=1))[0].min()) < 40, "an emotion that sits higher is not moved to the neutral"

    project.json("set", PORTRAIT, "fit", "head_top=-1")
    build(project, "fit")
    assert record(folder, "fit", "grid.json")["scale_x"] == "5/2", "`Grid.cover`'s fill: 480/192"


def test_an_emotion_that_reaches_the_edge_is_out_of_canvas(project: Kiripix) -> None:
    base = neutral()
    lean = with_face(base, 11)
    lean[300:360, 20:100] = blocks(np.random.default_rng(22), 60, 80)  # an arm out to the left, joined to the body
    make_set(project, {"happy": with_face(base, 12), "lean": lean}, face=False)
    project.json("set", PORTRAIT, "brief", "width=160")  # a canvas narrower than the picture, so the arm reaches its edge

    result = run_finish(project)

    found = [f for f in result["findings"] if f["code"] == "portrait.out_of_canvas"]
    assert [f["data"]["emotion"] for f in found] == ["lean"]
    [one] = found
    assert one["severity"] == "warning" and one["owner_action"] and not one.get("fix")
    assert one["data"]["edges"]["left"] > 0 and one["data"]["edges"]["top"] == 0 and one["position"]["x"] == 0


# ticket 0322: the white rim's leftover specks


def test_pale_specks_on_the_edge_are_a_light_rim_until_finish_clears_them(project: Kiripix) -> None:
    base = neutral()
    specks = with_face(base, 11)
    for rows in (slice(380, 385), slice(450, 455)):  # grey, lighter than the cutout's rim test reaches (L 0.75, under 0.8)
        specks[rows, 95:100] = (175, 175, 175)  # where the rim was: specks of 2 x 2 canvas px at most
    folder = make_set(project, {"specks": specks}, face=False)
    project.json("set", PORTRAIT, "palette", "mode=off")  # the colours as they are, so the grey stays grey
    project.json("set", PORTRAIT, "finish", "clear_light_edge=false")

    kept = run_finish(project)

    found = [f for f in kept["findings"] if f["code"] == "portrait.light_rim"]
    [one] = [f for f in found if f["data"]["emotion"] == "specks"]
    assert one["severity"] == "warning" and one["fix"] == f"kiripix set {PORTRAIT} finish clear_light_edge=true"
    left = int(to_canvas(folder, 100, 0)[0])
    assert len([b for b in one["data"]["boxes"] if b["x"] <= left]) == 2, "both specks, on the figure's left edge"

    project.json("set", PORTRAIT, "finish", "clear_light_edge=true")
    cleared = run_finish(project)

    assert "portrait.light_rim" not in [f["code"] for f in cleared["findings"]]
    entry = record(folder, "finish", "finish.json")["light_edge"]
    assert entry["cleared"] and entry["images"]["specks"]["cleared"] >= one["data"]["pixels"]
