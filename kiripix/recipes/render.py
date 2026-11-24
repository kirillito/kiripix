"""The character's `render` Stage (spec §6.3, ticket 0104): every clip of `clips.json` in every direction, at the target pixel
size, as four passes (colour, normal, depth, object mask), by headless Blender, into `render.json` and the frame files.

A camera preset is `[character.camera.<name>]` in kiripix.toml (its elevation and 4 or 8 directions), picked by the `camera`
parameter. The Model is turned about its up axis in fixed steps (in Blender the camera orbits the pivot, so the light stays with
it): `s` faces the camera, then `sw w nw n ne e se` as the screen reads them. All directions are rendered, none mirrored (Q6).
Renders aren't pinned (ADR 0010): the Blender version and every render setting are inputs, so a change makes the Stage stale.
The device is not an input: a run with `--cpu` renders on the CPU and holds no GPU lock.

Reuse (ticket 0119): each clip of `render.json` carries a `key`, a hash of everything that changes its frames: its own entry
in `clips.json` (with its source's hash), the rig's and the Model's input hashes (so the Model's file, `facing` and the Blender
version), the camera preset's numbers, the toon settings, the height, the Blender version, the device and the render script. On a
rebuild the frames of a clip whose key matches the one in the Stage's `previous` output are copied from it, and Blender gets only
the other clips. The output is the same bytes as a full rebuild's. `--force` and a `previous` without keys render everything.

Frame size (ticket 0155): one square cell for the whole character. It starts at `ceil(1.5 * height)` px rounded up to even,
with the pivot, the ground point the camera orbits, at its centre column and `ceil(0.1 * height)` px above its bottom. Before
rendering, Blender measures where every frame of every clip lands (`"measure": true`, no shading), and the cell grows, never
shrinks, until every pose fits with a pixel to spare on each side for `finish`'s outline, both as rendered and as `sheet` places
it by its pivot. So no pose is cut, and characters of one height share a cell unless one reaches further. The measures are kept
per clip in `render.json` with a key of what poses the clip, so a rebuild measures only clips that changed.
`cell_margin` (ticket 0291) grows every measured extent by that many px on each side before the cell is fitted, so a Wearable
that reaches past the body (`wearable.outside_cell`) can fit; the recorded `bounds` stay the poses' own.

Pivots (ticket 0154): a `stationary` clip's pivot is the cell's pivot in every frame, where the feet are: the point under the
root sways with the hips, and a pivot that follows it would make `sheet` shift the whole sprite by a pixel as it crosses a half
pixel. A `root_motion` clip's camera follows the root, so its pivot is the cell's too; any other clip reports the pivot as
the root puts it.
The Model's standing height (its z extent, seen from the camera) is `height` px: pixels per Blender unit is
`height / (Model height * cos(elevation))`.

Toon shading (ticket 0105): the colour pass is the Model's colour lit by one key light fixed in camera space (the preset's
`light_angle` and `light_tilt`), cut into `bands` steps and darkened by `shadow`. `band_edge` moves the cuts (half-Lambert is shifted by `0.5 - band_edge`) and
`band_smooth` blurs the normals inside the silhouette before they are lit (ticket 0213). It is done in the script on the normal, not with
a Blender shader, because Shader to RGB is EEVEE-only and render uses Cycles so that `--cpu` works. The other passes don't change.

Painted-room look (ticket 0382), each parameter off at its default, and then `toon`, `render.json` and every frame are the bytes
they were: `shadow_hue` and `light_hue` (a `#rrggbb` colour, with `hue_strength`) move the darkest steps toward a cool colour and
the lightest toward a warm one at their own lightness, so the hue lives in the ramp `palette` fits or the table holds; `highlight`
(half-Lambert, with `highlight_gain`) adds one step above the brightest, a highlight; `bands` goes to 8; `contact` (with
`contact_distance`, a share of the Model's height, and `contact_threshold`) puts a pixel one step down where Blender's
ambient-occlusion pass finds it closed. `render.json`'s `bands` is the steps a part's ramp needs: `bands`, one more with a highlight.
The new keys are in `toon` only when they are on.

Transitions (ticket 0218): a `transition` clip of `clips.json` has no action of its own. Blender poses the rig at each end's
frame and renders the blend of the two, per bone, at each of the clip's `frames` (the blend positions). The key hashes the
whole entry, which carries both ends' source hashes and frames, so a transition is rendered again when a clip it reads changes
its end frame or its source, and no other clip is.

Material pass (ticket 0148): `material/<clip>/<dir>/<NNN>.png` holds each pixel's material, numbered from 1 by name, 0 for the
background. `render.json` lists them (`materials`: `[{"index", "name"}]`) and records the toon `bands` beside `toon`, so
`palette` can size a part's ramp. More than 255 materials fail the Stage.

Eyes (ticket 0203): with the `eyes` parameter, the names of the Model's eye materials, Blender also reports where each eye is
in every frame, from the posed mesh and not from the pixels: `render.json` then has `eyes` (the names) and each frame an
`eyes` list (`x`, `y`, `width`, `height` in px, `depth` as the depth pass counts it, and the camera-space `normal`), for
`finish` to stamp the eyes from. A clip's
`blink`, `wink_left` and `wink_right` frames are copied to its entry. None of these keys is written when it isn't set.

Points (ticket 0237): with the `points` parameter, `<name>@<target>` entries, comma-separated (`hand_r@mixamorig:RightHand`), a
`name` (`[a-z][a-z0-9_]*`) is a point for the game and a `target` a bone of the Model's armature (its head) or an Empty of the
Model (its own place; a socket parented to a bone follows the bone), by name. Blender reports each point in every frame as the
eyes are, from the posed Model: `render.json` then has `points` (the entries, as `{"name", "target"}`) and each frame a `points`
map, `{name: {"x", "y", "depth", "hidden"}}` in render px (sub-pixel, y down), the depth the eyes have, and `hidden` when the
depth pass has the body in front of it. A target that isn't there is `render.point_unknown`, which lists the armature's bones
and the Model's Empties. Without the parameter nothing is written, and the keys of the clips don't change.

Held things (ticket 0302): a clip of `clips.json` with `attach` shows each held thing, the current Variant of `src/things/<id>/`, at its
socket bone with its `offset` and `turn` (in the bone's frame, Model units), in that clip's frames only, in every direction. The
thing is part of the character's render: its pixels are in the colour, normal, depth and mask passes and the clip's measured extent.
Its materials are numbered in the material pass after the Model's, as `core.things` numbers them (the things in the order they were
first imported, each one's own materials by name), and `render.json` lists them in `things`: `[{"thing", "file", "materials":
[{"index", "name"}]}]`, the things up to the last one a clip holds (a later one is in no clip and moves no number); `materials` stays the Model's own. Each clip entry has its
`attach`. A socket an attached thing sits on is also a point (named for the bone, `rightforearm` for `mixamorig:RightForeArm`; `socket_<name>` when a given point of that name aims at another
bone), unless `points` already has one at that bone, so the game's fallback and the real thing agree.

A cell per clip (ticket 0303): the top-level `frame` and `pivot` are the body's cell, fitted to the clips that hold nothing (to
every clip when all hold something). A clip whose extent fits it keeps it; a clip that doesn't (its held thing, a long attack)
gets its own, the body's grown until it fits. Each clip entry has its `frame` (`{"width", "height"}`) and `pivot` (`[x, y]`),
which are the body's for most clips; a stationary clip's frames have that pivot. Blender runs once for each cell size, since the
frame size and the pivot are the scene's. A clip's key holds its own cell, so one clip's growing renders no other.
"""

import hashlib
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any

from kiripix.recipes.base import Scalar, StageFailure, StageRun, computed_setting, param_or_generated
from kiripix.recipes.blender_launcher import launch
from kiripix.recipes.clips import (
    DIRECTIONS, EYELIDS, clip_files, held_things_of, socket_message, thing_journal, unknown_sockets,
)

# 2: each clip carries its measured `bounds` (0155), a stationary clip one pivot (0154)
# 3: a material pass, `materials` and `bands` (0148)
# 4: the toon object gains `band_edge` and `band_smooth` (0213)
RENDER_SCHEMA_VERSION = 4
# A Stage input (ADR 0010), as the Blender version is: a render in an older format is stale, so `render` and every Stage
# after it are built again. Read at call time, so that a test can change the version.
FORMAT_SETTING = "render.format"
computed_setting(FORMAT_SETTING, lambda: RENDER_SCHEMA_VERSION)
PASSES = ("color", "normal", "depth", "mask", "material")
MAX_MATERIALS = 255  # an 8 bit pass: 0 is the background
EIGHT = DIRECTIONS
FOUR = ("s", "w", "n", "e")
# Degrees the Model turns about its up axis (counter-clockwise from above), for the direction it then faces on screen. The
# camera is at -Y looking +Y, the Model at rest faces -Y (toward it), screen right is +X.
YAW = {"s": 0, "sw": -45, "w": -90, "nw": -135, "n": 180, "ne": 135, "e": 90, "se": 45}
CELL_RATIO = 1.5
BOTTOM_RATIO = 0.1  # of the height, the pivot's distance above the cell's bottom
ROOTS = ("root",)


POINT_NAME = re.compile(r"[a-z][a-z0-9_]*")


def parse_points(text: str, asset_id: str) -> list[dict[str, str]]:
    """`points` as `[{"name", "target"}]`. A malformed entry, a bad name or a name given twice fails with a fix."""
    found: list[dict[str, str]] = []
    fix = f"kiripix set {asset_id} render points="
    for entry in (e.strip() for e in text.split(",")):
        if not entry:
            continue
        name, at, target = (part.strip() for part in entry.partition("@"))
        if not at or not target or not POINT_NAME.fullmatch(name):
            raise StageFailure(f"the point {entry!r} should be <name>@<bone or empty>, with a name of lower case letters, digits "
                               f"and underscores that starts with a letter, such as hand_r@mixamorig:RightHand",
                               code="render.point_invalid", fix=fix)
        if any(p["name"] == name for p in found):
            raise StageFailure(f"the point {name} is given twice", code="render.point_invalid", fix=fix)
        found.append({"name": name, "target": target})
    return found


def _check_points(run: StageRun, result: dict[str, Any]) -> None:
    """Fails with `render.point_unknown` when Blender reports points whose target is neither a bone nor an Empty."""
    if "points_unknown" in result:
        raise StageFailure(
            f"the Model has no bone or empty named {', '.join(result['points_unknown'])}; its bones are "
            f"{', '.join(result['bones']) or 'none'}" + (f", its empties {', '.join(result['empties'])}" if result["empties"] else ""),
            code="render.point_unknown", fix=f"kiripix set {run.asset_id} render points=")


HEX = re.compile(r"#[0-9a-fA-F]{6}")


def _toon_extra(run: StageRun, shadow_hue: str, light_hue: str) -> dict[str, Any]:
    """The `toon` keys of the painted-room look (ticket 0382), only those that are on, so a render with none of them is as it
    was. StageFailure `render.hue_invalid` for a hue that isn't `#rrggbb`."""
    extra: dict[str, Any] = {}
    for name, value in (("shadow_hue", shadow_hue), ("light_hue", light_hue)):
        if not value:
            continue
        if not HEX.fullmatch(value):
            raise StageFailure(f"{name} is {value!r}, not a colour written #rrggbb", code="render.hue_invalid",
                               fix=f"kiripix set {run.asset_id} render {name}=")
        extra[name] = value.lower()
    if extra:
        extra["hue_strength"] = float(run.params.get("hue_strength", 0.25))
    if float(run.params.get("highlight", 0)) > 0:
        extra["highlight"] = float(run.params["highlight"])
        extra["highlight_gain"] = float(run.params.get("highlight_gain", 0.35))
    if bool(run.params.get("contact", False)):
        extra["contact"] = {"distance": float(run.params.get("contact_distance", 0.05)),
                            "threshold": float(run.params.get("contact_threshold", 0.5))}
    return extra


def cell_size(height: int) -> int:
    side = math.ceil(CELL_RATIO * height)
    return side + side % 2


def _half_up(value: float) -> int:
    return math.floor(value + 0.5)  # as `sheet` rounds a pivot


def clip_bounds(measured: dict[str, list[dict[str, Any]]], follows_root: bool) -> list[float]:
    """A clip's extent [left, top, right, bottom] in px from the cell's pivot, over every direction and frame: as rendered,
    and, when its pivot follows the root, also as `sheet` places each frame by its rounded pivot."""
    left = top = math.inf
    right = bottom = -math.inf
    for frames in measured.values():
        for frame in frames:
            x0, y0, x1, y1 = frame["bounds"]
            shifts = [(0, 0)]
            if follows_root:
                shifts.append((_half_up(frame["under"][0]), _half_up(frame["under"][1])))
            for dx, dy in shifts:
                left, top, right, bottom = min(left, x0 - dx), min(top, y0 - dy), max(right, x1 - dx), max(bottom, y1 - dy)
    return [left, top, right, bottom]


def fit_cell(height: int, bounds: list[list[float]]) -> tuple[int, list[float]]:
    """The cell's side and pivot: the default cell, grown until every extent in `bounds` fits with 1 px left on each side for
    the outline. A pixel is drawn when its centre is covered, so `ceil` of an extent is the pixels it can reach."""
    side, below = cell_size(height), math.ceil(BOTTOM_RATIO * height)
    finite = [b for b in bounds if all(math.isfinite(v) for v in b)]
    if finite:
        left, top = min(b[0] for b in finite), min(b[1] for b in finite)
        right, bottom = max(b[2] for b in finite), max(b[3] for b in finite)
        below = max(below, math.ceil(bottom) + 1)
        half = math.ceil(max(-left, right, 0.0)) + 1
        side = max(side, 2 * half, below + math.ceil(max(-top, 0.0)) + 1)
        side += side % 2
    return side, [side / 2, float(side - below)]


def padded(bounds: list[float], margin: int) -> list[float]:
    """A clip's extent grown by `margin` px on every side (the `cell_margin` parameter)."""
    return [bounds[0] - margin, bounds[1] - margin, bounds[2] + margin, bounds[3] + margin] if margin else bounds


def fits_cell(side: int, pivot: list[float], bounds: list[float]) -> bool:
    """Whether an extent [left, top, right, bottom] in px from the pivot fits a cell of `side` px with `pivot` in it, with the
    pixel to spare on each side that `fit_cell` keeps for the outline."""
    left, top, right, bottom = bounds
    half = math.ceil(max(-left, right, 0.0)) + 1
    return (half <= pivot[0] and half <= side - pivot[0] and math.ceil(bottom) + 1 <= side - pivot[1]
            and math.ceil(max(-top, 0.0)) + 1 <= pivot[1])


def needed_margin(height: int, bodies: list[list[float]], wearing: list[list[float]], most: int = 64) -> int | None:
    """The smallest `cell_margin` at which a cell fitted to the body's extents (`bodies`) holds every extent in `wearing`,
    or None when none up to `most` does."""
    for margin in range(0, most + 1):
        side, pivot = fit_cell(height, [padded(b, margin) for b in bodies])
        if all(fits_cell(side, pivot, w) for w in wearing):
            return margin
    return None


def clip_cells(height: int, clips: list[dict[str, Any]],
               bounds: dict[str, list[float]]) -> tuple[int, list[float], dict[str, tuple[int, list[float]]]]:
    """The body's cell and each clip's (ticket 0303), `(side, pivot, {clip: (side, pivot)})`. The body's cell is fitted to the
    clips that hold nothing (every clip when all hold something). A clip whose extent fits it keeps it; one that doesn't gets
    its own, the body's grown until that extent fits, so it is never smaller than the body's."""
    body = [bounds[c["name"]] for c in clips if not c.get("attach")] or [bounds[c["name"]] for c in clips]
    side, pivot = fit_cell(height, body)
    cells: dict[str, tuple[int, list[float]]] = {}
    for clip in clips:
        own = bounds[clip["name"]]
        cells[clip["name"]] = (side, pivot) if fits_cell(side, pivot, own) else fit_cell(height, [*body, own])
    return side, pivot, cells


def _launch_cells(run: StageRun, args: dict[str, Any], cells: dict[str, tuple[int, list[float]]]) -> dict[str, Any]:
    """Blender for `args["clips"]`, once for each cell size they need (the frame and pivot are the scene's). The result is one
    result: the first's `depth_range` and `materials`, every clip's frames."""
    groups: dict[tuple[int, tuple[float, ...]], list[dict[str, Any]]] = {}
    for clip in args["clips"]:
        side, pivot = cells[clip["name"]]
        groups.setdefault((side, tuple(pivot)), []).append(clip)
    merged: dict[str, Any] | None = None
    for (size, place), group in groups.items():
        found = launch(run, "render_frames", {**args, "clips": group, "frame": [size, size], "pivot": list(place)})
        _check_points(run, found)
        if merged is None:
            merged = found
        else:
            if found["depth_range"] != merged["depth_range"]:
                raise StageFailure("Blender gave two depth ranges for one character", fix=f"kiripix run {run.asset_id} render --force")
            merged["frames"] = {**merged["frames"], **found["frames"]}
    assert merged is not None
    return merged


def _json(path: Path) -> dict[str, Any]:
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _rig_file(run: StageRun, rig: dict[str, Any]) -> Path:
    if rig["source"] == "rigged":
        return run.asset_dir / "src" / "rigged" / rig["file"]
    return run.upstream["model"] / "model.blend"


def _clip_file(run: StageRun, clip: dict[str, Any]) -> str | None:
    """The clip-source file a clip's `source` names (`<stem>` or `<stem>/<action>`), or None: an action of the rig's file."""
    found = clip_files(run).get(str(clip["source"]).partition("/")[0])  # the character's own, or its base's (ADR 0012)
    return str(found) if found is not None else None


def blender_clip(run: StageRun, clip: dict[str, Any]) -> dict[str, Any]:
    """A clip as the script gets it. A `transition` (ticket 0218) has no action of its own: it carries its two ends, each an
    action, its file and a frame, and `frames` are the blend positions between them."""
    if "transition" not in clip:
        return {"name": clip["name"], "action": clip["action"], "file": _clip_file(run, clip), "frames": clip["frames"],
                "root_motion": bool(clip["root_motion"])}
    ends = {end: {"action": clip["transition"][end]["action"], "file": _clip_file(run, clip["transition"][end]),
                  "frame": clip["transition"][end]["action_frame"], "root_motion": bool(clip["transition"][end]["root_motion"])}
            for end in ("from", "to")}
    return {"name": clip["name"], "frames": clip["frames"], "root_motion": False, "transition": ends}


def _thing_files(run: StageRun) -> list[dict[str, Any]]:
    """The Asset's held things in numbering order, each `{"id", "file", "name"}` with the current Variant's path: the order they
    were first imported (the journal, `imported.jsonl`), a folder laid by hand after those, by ID. The current Variant is the
    newest import naming a file of the thing's folder, else the last by name. A Stage can't import core, so it reads these."""
    base = run.base  # its things come first (ticket 0312); the base's journal is read where it is, not hashed
    held = held_things_of(run.files, thing_journal(run.asset_dir), base.files if base is not None else None,
                          thing_journal(base.asset_dir) if base is not None else ())
    return [{"id": t.id, "file": t.variants[t.current], "name": Path(t.current).name} for t in held]


def _socket_points(points: list[dict[str, str]], clips: list[dict[str, Any]]) -> list[dict[str, str]]:
    """`points` with a point at each socket an `attach` uses that has none (a given point on the socket's bone is its point): named
    for the bone (lower case, other characters `_`); when a given point already has that name on another bone, `socket_<name>`
    (and a number after it if that is taken too), so the socket always gets its point (ticket 0313)."""
    found = list(points)
    for clip in clips:
        for held in clip.get("attach", []):
            socket = str(held["socket"])
            if any(p["target"] == socket for p in found):
                continue
            name = re.sub(r"[^a-z0-9]+", "_", socket.lower().split(":")[-1]).strip("_") or "socket"
            if not POINT_NAME.fullmatch(name):
                name = "socket_" + name
            taken = {p["name"] for p in found}
            if name in taken:
                base = f"socket_{name}" if not name.startswith("socket_") else name
                name, n = base, 2
                while name in taken:
                    name, n = f"{base}_{n}", n + 1
            found.append({"name": name, "target": socket})
    return found


def _check_held(run: StageRun, clips: list[dict[str, Any]], rig: dict[str, Any], things: list[dict[str, Any]]) -> None:
    """Each thing a clip holds is on the Asset and each socket is a bone of the rig (`clips` checks it too; this is the guard
    before Blender starts)."""
    known = {t["id"] for t in things}
    bones = list(rig.get("parents", {}))
    for clip in clips:
        attach = list(clip.get("attach", []))
        if lost := sorted({str(a["thing"]) for a in attach} - known):
            raise StageFailure(f"the clip {clip['name']} holds {', '.join(lost)}, and the Asset has no such thing",
                               code="clips.unknown_thing",
                               owner_action=f"Import the thing: kiripix import {run.asset_id} <file> --role thing --thing {lost[0]}")
        if bones and (wrong := unknown_sockets(attach, bones)):
            raise StageFailure(f"the clip {clip['name']}: {socket_message(wrong, bones)}", code="clips.unknown_socket",
                               fix=f"kiripix undo {run.asset_id} clips")


def _stamp_hash(folder: Path) -> str:
    """The input hash in a Stage's stamp (`.stage.json`): what the Stage's output was built from."""
    try:
        return str(json.loads((folder / ".stage.json").read_text(encoding="utf-8")).get("input_hash", ""))
    except (OSError, ValueError):
        return ""


def _script_hash() -> str:
    script = Path(__file__).resolve().parents[1] / "blender" / "render_frames.py"
    return hashlib.sha256(script.read_bytes()).hexdigest()


def _previous_clips(run: StageRun, names: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    """The clips of the previous output that can be copied as they are, by name: they have a key, all the directions asked for
    and every frame file. Nothing when the Stage is forced, there is no previous output or its `render.json` can't be read."""
    if run.forced or run.previous is None:
        return {}
    try:
        document = _json(run.previous / "render.json")
        found: dict[str, dict[str, Any]] = {}
        for entry in document["clips"]:
            frames = entry["directions"]
            if "key" not in entry or list(frames) != list(names):
                continue
            files = [run.previous / f for direction in names for item in frames[direction] for f in item["files"].values()]
            if all(path.is_file() for path in files):
                found[entry["name"]] = {**entry, "depth_range": document["depth_range"]}
        return found
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _previous_bounds(run: StageRun) -> dict[str, tuple[str, list[float]]]:
    """The measured bounds of the previous output's clips, by name, with the key they were measured under."""
    if run.forced or run.previous is None:
        return {}
    try:
        document = _json(run.previous / "render.json")
        return {str(e["name"]): (str(e["measure_key"]), [float(v) for v in e["bounds"]])
                for e in document["clips"] if "measure_key" in e and len(e["bounds"]) == 4}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return {}


def _materials(run: StageRun, result: dict[str, Any], previous: Path | None) -> list[dict[str, Any]]:
    """The Model's materials by index, from this run's Blender, or from the previous output when every clip was kept."""
    if "materials" in result:
        found = [{"index": int(m["index"]), "name": str(m["name"])} for m in result["materials"]]
    else:
        found = []
        if previous is not None:
            try:
                found = [{"index": int(m["index"]), "name": str(m["name"])} for m in _json(previous / "render.json")["materials"]]
            except (OSError, ValueError, KeyError, TypeError):
                found = []
    if len(found) > MAX_MATERIALS:
        raise StageFailure(
            f"the Model has {len(found)} materials; the material pass holds at most {MAX_MATERIALS}",
            code="render.too_many_materials",
            owner_action=f"Join materials in the Model until it has {MAX_MATERIALS} or fewer, then run render again.")
    return found


def _held_materials(result: dict[str, Any], previous: Path | None, things: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """`render.json`'s `things`: each thing of the Asset with its file and the numbers of its materials, from this run's Blender,
    or from the previous output when every clip was kept."""
    found = result.get("things")
    if found is None and previous is not None:
        try:
            found = [{"thing": t["thing"], "materials": t["materials"]} for t in _json(previous / "render.json")["things"]]
        except (OSError, ValueError, KeyError, TypeError):
            found = None
    by_id = {str(t["thing"]): t["materials"] for t in found or []}
    return [{"thing": t["id"], "file": t["name"],
             "materials": [{"index": int(m["index"]), "name": str(m["name"])} for m in by_id.get(t["id"], [])]} for t in things]


def _copy_clip(run: StageRun, previous: Path, name: str) -> None:
    for kind in PASSES:
        shutil.copytree(previous / kind / name, run.output_dir / kind / name)
    run.check_cancel()


def _generated(model: dict[str, Any]) -> dict[str, Any]:
    """What a generated Model's generator said of it (ticket 0224): `model.json`'s `generated`; nothing for an imported one."""
    made = model.get("generated")
    return made if isinstance(made, dict) else {}


def render_generated_params(run: StageRun) -> dict[str, Scalar]:
    """`StageSpec.generated_params` of `render`: a generated Model's eye materials."""
    try:
        made = _generated(_json(run.upstream["model"] / "model.json"))
    except (OSError, ValueError):
        return {}  # not built yet
    return {"eyes": str(made["eyes"])} if "eyes" in made else {}


def _rig_height(rig: dict[str, Any], asset_id: str) -> float:
    value = rig.get("height")
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise StageFailure(f"the rig.json of {asset_id} was built before Kiripix recorded its rig's height, which sizes a "
                           "character made from a base", fix=f"kiripix run {asset_id} rig --force")
    return float(value)


def target_height(run: StageRun, model: dict[str, Any], rig: dict[str, Any]) -> int:
    """The character's height in px: its own `height`; else the Project's `[character] height`. A character made from a
    base (ADR 0012) without a `height` of its own is its base's height (the base's `height`, or the Project's) times its
    rig's height over the base rig's (`rig.json`'s `height`): each the height of the file that carries the armature, as
    Blender imported it, in the rest pose, so a build, an age or a stoop baked into the rest pose counts. The base's is its
    rigged file's when it has one, because that is the body a Model on its skeleton is built from, and Mixamo's file is not
    the size of the Model's. A generated Model's generator gives the ratio itself (ticket 0224), base or not. Rounded half
    up to whole px."""
    own = run.params.get("height")
    if own:
        return int(own)
    project = int(run.settings.get("character.height") or 52)
    made = _generated(model)
    if run.base is None and "height" not in made:
        return project
    standard = project if run.base is None else int(run.base.params.get("height") or project)
    if "height" in made:
        ratio = float(made["height"])
    else:
        assert run.base is not None
        try:
            theirs = _json(run.base.built["rig"] / "rig.json")
        except (OSError, ValueError):
            raise StageFailure(f"the base {run.base.asset_id} has no rig.json",
                               fix=f"kiripix run {run.base.asset_id} rig --force") from None
        ratio = _rig_height(rig, run.asset_id) / _rig_height(theirs, run.base.asset_id)
    return max(1, _half_up(standard * ratio))


def run_render(run: StageRun) -> None:
    camera_name = str(run.params.get("camera", "top34_8"))
    presets = run.settings.get("character.camera") or {}
    if camera_name not in presets:
        raise StageFailure(
            f"there is no camera preset {camera_name} (the presets are {', '.join(sorted(presets)) or 'none'})",
            code="render.camera_unknown",
            owner_action=f"Add [character.camera.{camera_name}] (elevation, directions) to kiripix.toml, or set the "
                         f"Asset's camera parameter to one of the presets.")
    preset = presets[camera_name]
    toon_extra = _toon_extra(run, str(run.params.get("shadow_hue", "")), str(run.params.get("light_hue", "")))
    elevation, count = float(preset["elevation"]), int(preset["directions"])

    clips_document = _json(run.upstream["clips"] / "clips.json")
    rig = _json(run.upstream["rig"] / "rig.json")
    model = _json(run.upstream["model"] / "model.json")
    height = target_height(run, model, rig)
    model_height = float(model["height"])
    side, pivot = fit_cell(height, [])  # the default cell: where the measure pass puts the camera
    names = EIGHT if count == 8 else FOUR
    clips = clips_document["clips"]
    args: dict[str, Any] = {
        "rig_file": str(_rig_file(run, rig)),
        "root": [*ROOTS, str(rig["mapping"].get("hips", "hips"))],
        "model_height": model_height,
        "clips": [blender_clip(run, c) for c in clips],
        "directions": [{"name": d, "yaw": YAW[d]} for d in names],
        "elevation": elevation,
        "frame": [side, side],
        "px_per_unit": round(height / (model_height * math.cos(math.radians(elevation))), 6),
        "pivot": pivot,
        "toon": {"bands": int(run.params.get("bands", 3)), "shadow": float(run.params.get("shadow", 0.5)),
                 "band_edge": float(run.params.get("band_edge", 0.5)), "band_smooth": float(run.params.get("band_smooth", 0)),
                 "light": {"angle": float(preset.get("light_angle", -45)), "tilt": float(preset.get("light_tilt", 35))},
                 **toon_extra},
        "device": "cpu" if run.cpu else "gpu",
        "output": str(run.output_dir),
    }
    made = _generated(model)
    followed = param_or_generated(run, "eyes", render_generated_params(run))  # the character's own, the generator's, the base's
    eyes = [name.strip() for name in str(followed or "").split(",") if name.strip()]
    if eyes:
        args["eyes"] = eyes
    things = _thing_files(run)
    _check_held(run, clips, rig, things)
    # A thing numbered after the last one a clip holds is in no clip and moves no number, so it isn't passed on (ticket 0313).
    order = {t["id"]: n for n, t in enumerate(things)}
    things = things[:max((order[str(a["thing"])] for c in clips for a in c.get("attach", [])), default=-1) + 1]
    for entry, source in zip(args["clips"], clips):
        if source.get("attach"):
            entry["attach"] = [dict(a) for a in source["attach"]]
    held = any(c.get("attach") for c in clips)
    if held:  # the things up to the last one held, so the material numbers are the same whichever clips hold them
        args["things"] = [{"id": t["id"], "file": str(t["file"])} for t in things]
    points = _socket_points(parse_points(str(run.params.get("points") or ""), run.asset_id), clips)
    if points:
        args["points"] = points
    posing: dict[str, Any] = {name: args[name] for name in ("root", "model_height", "elevation", "px_per_unit")}
    posing.update(directions=list(names), rig=_stamp_hash(run.upstream["rig"]), model=_stamp_hash(run.upstream["model"]),
                  blender=str(run.settings.get("blender.version", "")), script=_script_hash(), schema=RENDER_SCHEMA_VERSION)
    files = {t["id"]: t["name"] for t in things}
    measure_keys = {c["name"]: hashlib.sha256(json.dumps(
        {"clip": c, **posing, **({"held": {a["thing"]: files[a["thing"]] for a in c["attach"]}} if c.get("attach") else {})},
        sort_keys=True).encode("utf-8")).hexdigest() for c in clips}
    bounds = {name: found for name, (measured_under, found) in _previous_bounds(run).items()
              if measure_keys.get(name) == measured_under}
    unmeasured = [c for c in args["clips"] if c["name"] not in bounds]
    if unmeasured:
        run.progress(0, 1, f"measuring {len(unmeasured)} of {len(clips)} clips")
        found_bounds = launch(run, "render_frames", {**args, "clips": unmeasured, "measure": True})
        _check_points(run, found_bounds)
        measured = found_bounds["frames"]
        for clip in clips:
            if clip["name"] in measured:
                follows_root = not clip["stationary"] and not clip["root_motion"]
                bounds[clip["name"]] = clip_bounds(measured[clip["name"]], follows_root)
    margin = int(run.params.get("cell_margin", 0))
    side, pivot, cells = clip_cells(height, clips, {n: padded(b, margin) for n, b in bounds.items()})
    args.update(frame=[side, side], pivot=pivot)
    shared: dict[str, Any] = {"toon": args["toon"]}
    shared.update(posing)
    if eyes:
        shared["eyes"] = eyes
    if points:
        shared["points"] = points

    def key(clip: dict[str, Any], device: str) -> str:
        own: dict[str, Any] = {"frame": [cells[clip["name"]][0]] * 2, "pivot": cells[clip["name"]][1]}  # its own cell (ticket 0303)
        if clip.get("attach"):  # the things it holds and those numbered before them: a later one moves no number (ticket 0313)
            last = max(order[str(a["thing"])] for a in clip["attach"])
            own["things"] = [[t["id"], t["name"]] for t in things[:last + 1]]
        return hashlib.sha256(json.dumps({"clip": clip, **shared, **own, "device": device}, sort_keys=True)
                              .encode("utf-8")).hexdigest()

    keys = {c["name"]: key(c, args["device"]) for c in clips}
    kept = _previous_clips(run, names)
    kept = {name: entry for name, entry in kept.items() if name in keys and entry["key"] == keys[name]}
    every = list(args["clips"])
    reused = len(kept) * len(names)
    previous = run.previous
    args["clips"] = [c for c in every if c["name"] not in kept]

    if args["clips"]:
        run.progress(0, 1, "starting Blender" if not kept else
                     f"reused {reused} clip and direction pairs; starting Blender for {len(args['clips'])} of {len(every)} clips")
        result = _launch_cells(run, args, cells)
        if kept and result["depth_range"] != next(iter(kept.values()))["depth_range"]:
            # the depth scale moved, so the kept frames don't match the new ones. The key should prevent it; render all.
            kept, reused, args["clips"] = {}, 0, every
            result = _launch_cells(run, args, cells)
        if args["device"] == "gpu" and str(result.get("device", "")).startswith("cpu"):
            # No GPU was found, so Blender rendered on the CPU: the new frames are keyed as CPU frames, as they are.
            keys.update({c["name"]: key(c, "cpu") for c in clips if c["name"] not in kept})
            run.notes.append("no GPU was found, so the frames were rendered on the CPU; run with --cpu to reuse them next time")
    else:
        result = {"depth_range": next(iter(kept.values()), {"depth_range": [0.0, 1.0]})["depth_range"], "frames": {}}
        run.progress(0, 1, f"reused {reused} clip and direction pairs")
    materials = _materials(run, result, previous if kept else None)
    held_materials = _held_materials(result, previous if kept else None, things) if held else []
    for name in kept:
        assert previous is not None
        _copy_clip(run, previous, name)
    if reused:
        run.notes.append(f"reused {reused} of {len(clips) * len(names)} clip and direction pairs")

    entries = []
    for clip in clips:
        measures = {"measure_key": measure_keys[clip["name"]], "bounds": bounds[clip["name"]],
                    **({"attach": clip["attach"]} if clip.get("attach") else {})}
        side_of, pivot_of = cells[clip["name"]]
        measures = {**measures, "frame": {"width": side_of, "height": side_of}, "pivot": list(pivot_of)}  # its own cell (0303)
        if clip["name"] in kept:
            entry = {**{k: v for k, v in kept[clip["name"]].items() if k != "depth_range"}, **measures}
            if clip["stationary"]:  # an older render may have kept the swaying root's pivots (ticket 0154)
                entry["directions"] = {d: [{**f, "pivot": list(pivot_of)} for f in frames]
                                       for d, frames in entry["directions"].items()}
            entries.append(entry)
            continue
        directions: dict[str, list[dict[str, Any]]] = {}
        for direction in names:
            frames = []
            for index, found in enumerate(result["frames"][clip["name"]][direction]):
                files = {p: f"{p}/{clip['name']}/{direction}/{index:03d}.png" for p in PASSES}
                missing = [f for f in files.values() if not (run.output_dir / f).is_file()]
                if missing:
                    raise StageFailure(f"Blender finished without writing {missing[0]}")
                if eyes and not found.get("eyes"):
                    raise StageFailure(
                        f"the Model has no material named {' or '.join(eyes)} (it has "
                        f"{', '.join(m['name'] for m in materials) or 'none'}), so its eyes can't be followed",
                        code="render.eyes_unknown", fix=f"kiripix set {run.asset_id} render eyes=")
                frames.append({"index": index, "source_frame": clip["frames"][index], "files": files,
                               "pivot": list(pivot_of) if clip["stationary"] else found["pivot"],
                               **({"eyes": found["eyes"]} if eyes else {}),
                               **({"points": found["points"]} if points else {})})
            directions[direction] = frames
        entries.append({"name": clip["name"], "key": keys[clip["name"]], "fps": clip["fps"], "loop": clip["loop"],
                        "stationary": clip["stationary"], "root_motion": clip["root_motion"], "directions": directions,
                        **{key: clip[key] for key in EYELIDS if clip.get(key)}, **measures})
    document = {
        "schema_version": RENDER_SCHEMA_VERSION,
        "camera": camera_name,
        "elevation": elevation,
        "height": height,
        "frame": {"width": side, "height": side},
        "pivot": pivot,
        "px_per_unit": args["px_per_unit"],
        "toon": args["toon"],
        "bands": args["toon"]["bands"] + (1 if args["toon"].get("highlight") else 0),
        "materials": materials,
        **({"things": held_materials} if held else {}),
        **({"eyes": eyes} if eyes else {}),
        **({"points": points} if points else {}),
        **({"generated": made} if made else {}),  # for `palette`, which reads its `parts` (ticket 0224)
        "depth_range": result["depth_range"],
        "passes": list(PASSES),
        "directions": list(names),
        "clips": entries,
    }
    (run.output_dir / "render.json").write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")

