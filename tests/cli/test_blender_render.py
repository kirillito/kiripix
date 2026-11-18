"""The `render` script's newer paths on the real Blender 5.2 (ticket 0281, spec §6.3, ADR 0010).

The fake Blender of `kiripix_test_recipes.py` covers the Stages; these tests run `render_frames.py` itself, through the CLI, on
the committed render Model (`tests/fixtures/characters/render_model.glb`, built by `tests/fixtures/make_render_model.py`):
about 270 faces, rigged with Mixamo bone names, the materials `cloth`, `eye_iris`, `eye_white` and `skin`, a flat eye patch of
each eye material on each side of the face, a hand bone on each arm, and the actions `idle` (frame 1 is the rest pose) and
`walk` (frame 1 and 13 are opposite poses, the middle of them the rest pose). They check counts, places and masks, never exact
colours. Skipped without Blender 5.2.x (`KIRIPIX_BLENDER` or PATH).

Most tests read one shared render (the `rendered` fixture), because the render is the slow part.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from conftest import Kiripix
from PIL import Image

FIXTURES = Path(__file__).parent.parent / "fixtures"
MODEL = "render_model.glb"
HERO = "character.hero"
DIRECTIONS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
IDLE = {"name": "idle", "source": "idle", "start": 1, "end": 1, "fps": 6, "loop": True, "stationary": True}

pytestmark = pytest.mark.blender

Rendered = tuple[Path, dict[str, Any]]


def run(project: Kiripix, *args: str, timeout: int = 900) -> dict[str, Any]:
    return project.json(*args, test_recipes=False, timeout=timeout)


def clip(project: Kiripix, data: dict[str, Any], asset: str = HERO) -> None:
    run(project, "decide", asset, "clips", "--decision", json.dumps({"decision": "clip", "data": data}))


def folder_of(project: Kiripix, asset: str = HERO) -> Path:
    return project.cwd / "assets" / "character" / asset.split(".", 1)[1]


def set_blender(project: Kiripix) -> None:
    path = project.cwd / "kiripix.toml"
    quoted = json.dumps(os.environ["KIRIPIX_BLENDER"])
    if f"\nblender = {quoted}" in path.read_text("utf-8"):  # set once: a second character in the Project
        return
    path.write_text(path.read_text("utf-8").replace("# blender = ", f"blender = {quoted}  # blender = ", 1), encoding="utf-8")


def hero(project: Kiripix, name: str = "hero", base: str | None = None, rigged: Path | None = None, model: str = MODEL) -> Path:
    """A character on the real Blender, its Model picked and its `model` and `rig` Stages run."""
    asset = f"character.{name}"
    run(project, "new", "character", name, *(["--base", base] if base else []))
    set_blender(project)
    source = project.cwd / f"{name}-model.glb"
    shutil.copy(FIXTURES / "characters" / model, source)
    run(project, "pick", asset, run(project, "import", asset, source.name)["data"]["variant"])
    run(project, "run", asset, "model")
    if rigged is not None:
        run(project, "import", asset, str(rigged), "--role", "rigged")
    run(project, "run", asset, "rig")
    return folder_of(project, asset)


def render(project: Kiripix, *settings: str, asset: str = HERO, height: int = 64) -> dict[str, Any]:
    run(project, "run", asset, "clips")
    run(project, "set", asset, "render", f"height={height}", *settings)
    result = run(project, "run", asset, "render", "--cpu", timeout=1800)
    assert result["findings"] == []
    return result


def render_json(folder: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads((folder / "work" / "render" / "render.json").read_text("utf-8"))
    return document


def frames_of(document: dict[str, Any], clip_name: str, direction: str = "s") -> list[dict[str, Any]]:
    entry = next(c for c in document["clips"] if c["name"] == clip_name)
    found: list[dict[str, Any]] = entry["directions"][direction]
    return found


def pass_of(folder: Path, frame: dict[str, Any], kind: str) -> np.ndarray:
    return np.array(Image.open(folder / "work" / "render" / frame["files"][kind]))


def mask_of(folder: Path, frame: dict[str, Any]) -> np.ndarray:
    return pass_of(folder, frame, "mask") == 255


def test_the_model_is_rigged_with_four_materials_and_a_few_hundred_faces() -> None:
    probe = subprocess.run(
        [os.environ["KIRIPIX_BLENDER"], "--background", "--factory-startup", "--python", str(FIXTURES / "blender_probe.py"),
         "--", str(FIXTURES / "characters" / MODEL)], capture_output=True, text=True, timeout=120)
    [line] = [x for x in probe.stdout.splitlines() if x.startswith("PROBE ")]
    info = json.loads(line[len("PROBE "):])
    assert 200 <= info["triangles"] <= 1000
    assert {"root", "mixamorig:Hips", "mixamorig:RightHand"} <= set(info["bones"])
    assert info["materials"] == ["cloth", "eye_iris", "eye_white", "skin"] and info["actions"] == ["idle", "walk"]


@pytest.fixture(scope="module")
def rendered(tmp_path_factory: pytest.TempPathFactory) -> Rendered:
    """One real render of every clip the tests below read, with the eyes and a point on the hand: the character's folder and
    its `render.json`."""
    project = Kiripix(tmp_path_factory.mktemp("render"))
    project.json("init")
    folder = hero(project)
    still = {"loop": False, "stationary": True, "fps": 6}
    clip(project, IDLE)
    clip(project, {"name": "hold", "source": "idle", "start": 5, "end": 5, "fps": 8, "loop": True, "stationary": True,
                   "still": 3})
    clip(project, {"name": "slow", "source": "idle", "start": 1, "end": 13, "fps": 6, "loop": True, "stationary": True})
    clip(project, {"name": "quick", "source": "idle", "start": 1, "end": 13, "fps": 6, "loop": True, "stationary": True,
                   "speed": 2})
    clip(project, {"name": "walk", "source": "walk", "start": 1, "end": 13, "fps": 4, "loop": False})
    clip(project, {**still, "name": "fore", "source": "walk", "start": 1, "end": 1})
    clip(project, {**still, "name": "back", "source": "walk", "start": 13, "end": 13})
    run(project, "decide", HERO, "clips", "--decision", json.dumps({"decision": "transition", "data": {
        "name": "fore_to_back", "from": {"clip": "fore"}, "to": {"clip": "back"}, "length": 3}}))
    render(project, "eyes=eye_white, eye_iris", "points=hand@mixamorig:RightHand")
    return folder, render_json(folder)


def test_render_records_both_eyes_in_every_frame_and_the_eye_facing_away_is_not_seen_in_the_back_views(
        rendered: Rendered) -> None:
    folder, document = rendered
    assert document["eyes"] == ["eye_white", "eye_iris"]
    names = {m["name"]: m["index"] for m in document["materials"]}
    for entry in document["clips"]:
        for direction, frames in entry["directions"].items():
            for frame in frames:
                assert len(frame["eyes"]) == 2, (entry["name"], direction)
                assert all(e["width"] > 0 and e["height"] > 0 for e in frame["eyes"])
    assert len(frames_of(document, "slow")) > 1
    for frame in frames_of(document, "slow") + frames_of(document, "idle"):
        right, left = frame["eyes"]  # the Model's right one first: -X, on the screen's left from the front
        assert right["x"] < left["x"] and abs(right["y"] - left["y"]) < 0.5
        # facing the camera: it looks down 30 degrees, so the normal's Z is 0.87
        assert right["normal"][2] > 0.8 and left["normal"][2] > 0.8
    for frame in frames_of(document, "slow", "n"):
        right, left = frame["eyes"]
        assert right["x"] > left["x"]  # the right eye is on the screen's right from behind
        assert right["normal"][2] < -0.8 and left["normal"][2] < -0.8  # facing away: the face is the Model's back here
    iris, white = names["eye_iris"], names["eye_white"]
    front = pass_of(folder, frames_of(document, "idle", "s")[0], "material")
    back = pass_of(folder, frames_of(document, "idle", "n")[0], "material")
    assert (front == iris).any() and (front == white).any()  # the eyes are seen from the front
    assert not (back == iris).any() and not (back == white).any()  # and covered by the head from behind


def test_the_material_pass_numbers_the_materials_by_name_from_1_and_the_background_is_0(rendered: Rendered) -> None:
    folder, document = rendered
    assert document["materials"] == [{"index": 1, "name": "cloth"}, {"index": 2, "name": "eye_iris"},
                                     {"index": 3, "name": "eye_white"}, {"index": 4, "name": "skin"}]
    seen: set[int] = set()
    for frames in next(c for c in document["clips"] if c["name"] == "idle")["directions"].values():
        indexes, mask = pass_of(folder, frames[0], "material"), mask_of(folder, frames[0])
        assert (indexes[~mask] == 0).all() and (indexes[mask] >= 1).all()
        seen |= {int(v) for v in np.unique(indexes)}
    assert seen == {0, 1, 2, 3, 4}


def test_a_3_frame_transition_renders_and_its_middle_is_the_rest_pose_between_two_opposite_poses(
        rendered: Rendered) -> None:
    folder, document = rendered
    assert all(len(frames_of(document, "fore_to_back", d)) == 3 for d in DIRECTIONS)
    first, middle, last = (mask_of(folder, f) for f in frames_of(document, "fore_to_back", "e"))
    fore, back, rest = (mask_of(folder, frames_of(document, name, "e")[0]) for name in ("fore", "back", "idle"))

    def apart(a: np.ndarray, b: np.ndarray) -> int:
        return int((a != b).sum())

    assert apart(fore, back) > 40  # the two poses differ, so the checks below mean something
    assert apart(middle, rest) <= 4  # halfway between opposite swings is the rest pose, to a pixel of the mask
    assert apart(first, fore) < apart(first, back) and apart(last, back) < apart(last, fore)  # each end is near its clip
    assert apart(first, middle) > 0 and apart(middle, last) > 0  # and the frames are three different poses


def test_still_holds_one_pose_for_the_frames_it_asks_and_speed_gives_fewer_frames(rendered: Rendered) -> None:
    folder, document = rendered
    for direction in ("s", "e"):
        hold = frames_of(document, "hold", direction)
        assert len(hold) == 3
        assert len({pass_of(folder, f, "color").tobytes() for f in hold}) == 1  # one pose, held
    slow, quick = len(frames_of(document, "slow")), len(frames_of(document, "quick"))
    assert (slow, quick) == (3, 2)  # 13 source frames at 24 a second shown at 6 a second, a loop's last not repeated; twice as fast
    entry = {c["name"]: c for c in document["clips"]}
    assert entry["hold"]["fps"] == 8 and entry["quick"]["fps"] == 6


def test_a_point_on_the_hand_bone_is_inside_the_masks_in_every_frame_and_follows_the_arm(rendered: Rendered) -> None:
    folder, document = rendered
    assert document["points"] == [{"name": "hand", "target": "mixamorig:RightHand"}]
    skin = next(m["index"] for m in document["materials"] if m["name"] == "skin")
    moved: set[tuple[float, float]] = set()
    checked = 0
    for direction in DIRECTIONS:
        for frame in frames_of(document, "walk", direction):
            point = frame["points"]["hand"]
            mask = mask_of(folder, frame)
            column, row = int(np.floor(point["x"])), int(np.floor(point["y"]))
            assert mask[row, column], (direction, frame["files"]["mask"], point)  # inside the character's mask
            if not point["hidden"]:  # nothing nearer covers it: the pixel is the hand itself
                assert pass_of(folder, frame, "material")[row, column] == skin, (direction, point)
            if direction == "s":
                moved.add((point["x"], point["y"]))
            checked += 1
    assert checked == 8 * len(frames_of(document, "walk")) and len(moved) >= 3  # the arm swings, so the point moves
    front = frames_of(document, "walk", "s")[0]["points"]["hand"]
    back = frames_of(document, "walk", "n")[0]["points"]["hand"]
    assert not front["hidden"] and front["depth"] > 0 and back["x"] > front["x"]  # the Model's right is screen-left at the front


def test_a_character_on_a_smaller_copy_of_the_bases_rig_renders_that_much_smaller(project: Kiripix, tmp_path: Path) -> None:
    smaller = tmp_path / "smaller"
    subprocess.run([os.environ["KIRIPIX_BLENDER"], "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                    str(FIXTURES / "make_render_model.py"), "--", str(smaller), "small", "0.8"],
                   check=True, capture_output=True, timeout=300)
    # the rigged file is made from the Model, as Mixamo's is: the same geometry, here at the Model's size and at 0.8 of it
    body = hero(project, "zed", rigged=FIXTURES / "characters" / MODEL)
    clip(project, IDLE, "character.zed")
    guard = hero(project, "guard", base="character.zed", rigged=smaller / "small.glb")

    render(project, asset="character.zed", height=52)
    run(project, "run", "character.guard", "clips")
    result = run(project, "run", "character.guard", "render", "--cpu", timeout=1800)

    assert result["findings"] == []
    assert json.loads((guard / "work" / "rig" / "rig.json").read_text("utf-8"))["height"] == pytest.approx(
        0.8 * json.loads((body / "work" / "rig" / "rig.json").read_text("utf-8"))["height"], rel=0.01)
    base_document, guard_document = render_json(body), render_json(guard)
    assert base_document["height"] == 52 and guard_document["height"] == 42  # 0.8 of 52, rounded half up

    def extent(folder: Path, document: dict[str, Any]) -> int:
        rows = np.nonzero(mask_of(folder, frames_of(document, "idle")[0]).any(axis=1))[0]
        return int(rows.max() + 1 - rows.min())

    assert abs(extent(guard, guard_document) - 0.8 * extent(body, base_document)) <= 2


# a Wearable with the body as holdout (ticket 0291) ----------------------------------------------------------------------------
# `render_vest.glb` is a vest and a skirt on the body's skeleton, `render_with_vest.glb` the body and the vest in one file: the
# full render to compare a stack with. Both stay inside the body's bounds, so the body, the vest and both are normalised alike.

VEST = "wearable.vest"
FULL = "character.full"
WALK = {"name": "walk", "source": "walk", "start": 1, "end": 13, "fps": 4, "loop": False}
BODY_MATERIALS = {"cloth": 1, "eye_iris": 2, "eye_white": 3, "skin": 4}


class Stack:
    """The body, the vest worn on it and the character that has both in its Model, each rendered once."""

    def __init__(self, project: Kiripix) -> None:
        self.project = project
        self.body = hero(project)
        self.full = hero(project, "full", model="render_with_vest.glb")
        for asset in (HERO, FULL):
            clip(project, IDLE, asset)
            clip(project, WALK, asset)
        render(project)
        render(project, asset=FULL)
        run(project, "new", "wearable", "vest", "--body", HERO)
        shutil.copy(FIXTURES / "characters" / "render_vest.glb", project.cwd / "vest.glb")
        run(project, "pick", VEST, run(project, "import", VEST, "vest.glb")["data"]["variant"])
        run(project, "run", VEST, "model")
        run(project, "run", VEST, "rig")
        started = time.monotonic()
        self.result = run(project, "run", VEST, "render", "--cpu", timeout=1800)
        self.seconds = time.monotonic() - started
        self.vest = project.cwd / "assets" / "wearable" / "vest"
        self.documents = {"body": render_json(self.body), "full": render_json(self.full), "vest": json.loads(
            (self.vest / "work" / "render" / "render.json").read_text("utf-8"))}

    def frames(self) -> list[tuple[str, str, int]]:
        found = []
        for entry in self.documents["body"]["clips"]:
            for direction, frames in entry["directions"].items():
                found.extend((entry["name"], direction, f["index"]) for f in frames)
        return found

    def passes(self, which: str, name: str, direction: str, index: int) -> dict[str, np.ndarray]:
        folder = {"body": self.body, "full": self.full, "vest": self.vest}[which] / "work" / "render"
        frame = frames_of(self.documents[which], name, direction)[index]
        return {kind: np.array(Image.open(folder / frame["files"][kind])) for kind in ("color", "depth", "mask", "material")}


@pytest.fixture(scope="module")
def stacked(tmp_path_factory: pytest.TempPathFactory) -> Stack:
    project = Kiripix(tmp_path_factory.mktemp("stack"))
    project.json("init")
    return Stack(project)


def test_a_wearable_renders_with_the_bodys_cell_clips_and_depth_scale_and_its_own_materials_numbered_after_the_bodys(
        stacked: Stack) -> None:
    body, vest = stacked.documents["body"], stacked.documents["vest"]

    assert stacked.result["findings"] == [] and vest["outside_cell"] == []
    assert [c["name"] for c in vest["clips"]] == [c["name"] for c in body["clips"]] == ["idle", "walk"]
    for ours, theirs in zip(vest["clips"], body["clips"], strict=True):
        assert {d: len(f) for d, f in ours["directions"].items()} == {d: len(f) for d, f in theirs["directions"].items()}
    assert vest["frame"] == body["frame"] and vest["pivot"] == body["pivot"] and vest["directions"] == body["directions"]
    assert vest["depth_range"] == pytest.approx(body["depth_range"], abs=1e-3) and vest["px_per_unit"] == body["px_per_unit"]
    assert [m["name"] for m in body["materials"]] == list(BODY_MATERIALS)
    assert vest["materials"] == [{"index": 5, "name": "trim"}, {"index": 6, "name": "vest"}]
    assert vest["seconds"]["frames"] == len(stacked.frames()) and vest["seconds"]["render"] > 0


def test_a_wearables_alpha_is_empty_where_the_body_is_in_front_of_it_and_nowhere_else_but_in_the_full_render(
        stacked: Stack) -> None:
    for name, direction, index in stacked.frames():
        vest = stacked.passes("vest", name, direction, index)
        full = stacked.passes("full", name, direction, index)
        drawn = vest["mask"] == 255
        body_in_front = np.isin(full["material"], list(BODY_MATERIALS.values()))
        assert not (drawn & body_in_front).any(), (name, direction, index)  # never drawn where the body is nearest
        assert not (drawn & (full["mask"] != 255)).any(), (name, direction, index)  # and only where something is
        assert (vest["material"][drawn] >= 5).all() and (vest["material"][~drawn] == 0).all()
        # what shows of the vest is what the full render shows of it, to a few px (a depth tie at 16 bits)
        assert abs(int(drawn.sum()) - int((full["material"] >= 5).sum())) <= 4, (name, direction, index)
    front, back = (int((stacked.passes("vest", "idle", d, 0)["mask"] == 255).sum()) for d in ("s", "n"))
    assert front > 200 and back < front / 2  # behind the torso, the body hides most of the vest


def test_the_body_and_the_wearable_stacked_by_depth_match_a_full_render_of_both_within_a_few_px(stacked: Stack) -> None:
    worst, total, pixels = 0, 0, 0
    for name, direction, index in stacked.frames():
        body = stacked.passes("body", name, direction, index)
        vest = stacked.passes("vest", name, direction, index)
        full = stacked.passes("full", name, direction, index)
        body_on, vest_on = body["mask"] == 255, vest["mask"] == 255
        vest_wins = vest_on & (~body_on | (vest["depth"] < body["depth"]))
        shown = body_on | vest_on
        colour = np.where(vest_wins[..., None], vest["color"], body["color"])
        full_on = full["mask"] == 255
        differing = int((shown != full_on).sum() + (shown & full_on & (colour != full["color"]).any(axis=-1)).sum())
        worst, total, pixels = max(worst, differing), total + differing, pixels + int(full_on.sum())
    assert worst <= 6 and total <= 0.001 * pixels, (worst, total, pixels)
