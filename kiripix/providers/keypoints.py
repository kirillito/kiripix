"""PixelLab's 18 skeleton joints from a character's render, and the retarget onto a sprite (ticket 0389; the trial's
`backlog/m6/0354-trial/keypoints.py`). Pure: plain dicts and lists in, plain dicts and lists out, no I/O, nothing from Kiripix.

A frame is as `render.json` holds it: `points` (`{name: {x, y, depth, hidden}}` in px of the frame, the names of `POINTS`) and
`eyes` (the Model's right eye first). PixelLab's joints (read 2026-11-25 from its OpenAPI, `SkeletonLabel`) are `x` and `y` as
fractions 0-1 of the image, `label` and `z_index` (higher draws on top); an optional `depth` is left out unless asked for.
"RIGHT ARM" is the wrist and "RIGHT LEG" the ankle (OpenPose's order); RIGHT is the character's own right.

The body's 13 joints are the rig's bones. A Mixamo rig has no nose, eye or ear bones, so those are made from the render's
`eyes` and the head's two bones (`head` at the skull's base, `head_top`): the nose a little below the eyes' middle along the
head's axis, each ear on the head's axis at eye height, out past its eye by `EAR_SPREAD` times the eyes' spacing. A rough guess,
good to a pixel or two at 52 px; `gen --preview` draws it.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from typing import Any

# What a character's `[stages.render] points` must hold: name@bone, Mixamo's bones (`kiripix set <character> render points=...`).
POINTS = ("neck@mixamorig:Neck,head@mixamorig:Head,head_top@mixamorig:HeadTop_End,"
          "shoulder_r@mixamorig:RightArm,elbow_r@mixamorig:RightForeArm,wrist_r@mixamorig:RightHand,"
          "shoulder_l@mixamorig:LeftArm,elbow_l@mixamorig:LeftForeArm,wrist_l@mixamorig:LeftHand,"
          "hip_r@mixamorig:RightUpLeg,knee_r@mixamorig:RightLeg,ankle_r@mixamorig:RightFoot,"
          "hip_l@mixamorig:LeftUpLeg,knee_l@mixamorig:LeftLeg,ankle_l@mixamorig:LeftFoot")
POINT_NAMES = tuple(entry.split("@")[0] for entry in POINTS.split(","))

BODY = {"NECK": "neck", "RIGHT SHOULDER": "shoulder_r", "RIGHT ELBOW": "elbow_r", "RIGHT ARM": "wrist_r",
        "LEFT SHOULDER": "shoulder_l", "LEFT ELBOW": "elbow_l", "LEFT ARM": "wrist_l", "RIGHT HIP": "hip_r",
        "RIGHT KNEE": "knee_r", "RIGHT LEG": "ankle_r", "LEFT HIP": "hip_l", "LEFT KNEE": "knee_l", "LEFT LEG": "ankle_l"}
LABELS = ("NOSE", "NECK", "RIGHT SHOULDER", "RIGHT ELBOW", "RIGHT ARM", "LEFT SHOULDER", "LEFT ELBOW", "LEFT ARM",
          "RIGHT HIP", "RIGHT KNEE", "RIGHT LEG", "LEFT HIP", "LEFT KNEE", "LEFT LEG", "RIGHT EYE", "LEFT EYE",
          "RIGHT EAR", "LEFT EAR")
LIMBS = (("NECK", "RIGHT SHOULDER"), ("RIGHT SHOULDER", "RIGHT ELBOW"), ("RIGHT ELBOW", "RIGHT ARM"),
         ("NECK", "LEFT SHOULDER"), ("LEFT SHOULDER", "LEFT ELBOW"), ("LEFT ELBOW", "LEFT ARM"),
         ("NECK", "RIGHT HIP"), ("RIGHT HIP", "RIGHT KNEE"), ("RIGHT KNEE", "RIGHT LEG"),
         ("NECK", "LEFT HIP"), ("LEFT HIP", "LEFT KNEE"), ("LEFT KNEE", "LEFT LEG"), ("NECK", "NOSE"),
         ("NOSE", "RIGHT EYE"), ("RIGHT EYE", "RIGHT EAR"), ("NOSE", "LEFT EYE"), ("LEFT EYE", "LEFT EAR"))
EYE_HEIGHT = 0.45   # the eyes' height up the head, from `head` (the skull's base) to `head_top`
NOSE_DROP = 0.18    # the nose below the eyes' middle, in head heights
EAR_SPREAD = 0.9    # each ear out past its eye, in the eyes' spacing
MIN_FRAMES, MAX_FRAMES = 3, 15  # what `animate-with-skeleton-v3` takes with keypoints

Joint = dict[str, Any]


def missing_points(names: Iterable[str]) -> list[str]:
    """The points of `POINTS` that `names` (a render's recorded points) lack, in `POINTS` order."""
    have = set(names)
    return [name for name in POINT_NAMES if name not in have]


def face(points: dict[str, Any], eyes: Sequence[dict[str, Any]] | None) -> dict[str, tuple[float, float, float]]:
    """The nose, eyes and ears in px from the head's bones and the render's eyes: {label: (x, y, depth)}."""
    hx, hy, hd = points["head"]["x"], points["head"]["y"], points["head"]["depth"]
    tx, ty, td = points["head_top"]["x"], points["head_top"]["y"], points["head_top"]["depth"]
    ax, ay, ad = (hx + EYE_HEIGHT * (tx - hx), hy + EYE_HEIGHT * (ty - hy), hd + EYE_HEIGHT * (td - hd))
    if eyes and len(eyes) >= 2:
        right = (eyes[0]["x"], eyes[0]["y"], eyes[0]["depth"])
        left = (eyes[1]["x"], eyes[1]["y"], eyes[1]["depth"])
    else:  # no eyes recorded: both on the axis, the face read as seen edge-on
        right = left = (ax, ay, ad)
    mx, my, md = ((right[0] + left[0]) / 2, (right[1] + left[1]) / 2, (right[2] + left[2]) / 2)
    nose = (mx + NOSE_DROP * (hx - tx), my + NOSE_DROP * (hy - ty), md - 0.02)
    across = (right[0] - left[0], right[1] - left[1], right[2] - left[2])
    ear_r = (ax + (0.5 + EAR_SPREAD) * across[0], ay + (0.5 + EAR_SPREAD) * across[1], ad + 0.05)
    ear_l = (ax - (0.5 + EAR_SPREAD) * across[0], ay - (0.5 + EAR_SPREAD) * across[1], ad + 0.05)
    return {"NOSE": nose, "RIGHT EYE": right, "LEFT EYE": left, "RIGHT EAR": ear_r, "LEFT EAR": ear_l}


def centre_depth(frame: dict[str, Any]) -> float:
    """The body's centre depth in a frame (the hips' middle), for `depth`; 0 when the frame has no hips."""
    points = frame.get("points") or {}
    if "hip_r" in points and "hip_l" in points:
        return float((points["hip_r"]["depth"] + points["hip_l"]["depth"]) / 2)
    return 0.0


def skeleton(frame: dict[str, Any], size: tuple[int, int], depth_scale: float | None = None,
             centre: float = 0.0) -> list[Joint]:
    """One frame's 18 joints for PixelLab: fractions of the frame, `z_index` by depth (nearer is higher). Raises `ValueError`
    naming the points the frame lacks."""
    points = frame.get("points") or {}
    missing = missing_points(points)
    if missing:
        raise ValueError(f"frame {frame.get('index')}: no point {', '.join(missing)}")
    places: dict[str, tuple[float, float, float]] = {
        label: (points[name]["x"], points[name]["y"], points[name]["depth"]) for label, name in BODY.items()}
    places |= face(points, frame.get("eyes"))
    width, height = size
    order = sorted(LABELS, key=lambda label: -places[label][2])  # farthest first
    joints: list[Joint] = []
    for label in LABELS:
        x, y, d = places[label]
        joint: Joint = {"x": round(min(1.0, max(0.0, x / width)), 4), "y": round(min(1.0, max(0.0, y / height)), 4),
                        "label": label, "z_index": order.index(label)}
        if depth_scale is not None:
            joint["depth"] = round(min(255.0, max(0.0, 128 + (centre - d) * depth_scale)), 1)
        joints.append(joint)
    return joints


def pick(count: int, wanted: int | None) -> list[int]:
    """`wanted` frame indexes spread evenly over `count` (all of them when None or not fewer than there are)."""
    if not wanted or wanted >= count:
        return list(range(count))
    return [round(i * count / wanted) for i in range(wanted)]


def joints_of(raw: Sequence[Any]) -> list[Joint]:
    """A skeleton PixelLab estimated, as our joints (`x`, `y`, `label`, `z_index`). Raises `ValueError` unless it holds all 18."""
    found: list[Joint] = [{"x": float(j["x"]), "y": float(j["y"]), "label": str(j["label"]), "z_index": int(j.get("z_index", 0))}
             for j in raw if isinstance(j, dict) and "label" in j and "x" in j and "y" in j]
    if {j["label"] for j in found} != set(LABELS):
        raise ValueError(f"the estimate has the joints {sorted(str(j['label']) for j in found)}, not PixelLab's 18")
    return found


def _span(joints: dict[str, tuple[float, float]]) -> float:
    """The body's length in px: the neck to the middle of the ankles."""
    nx, ny = joints["NECK"]
    ax = (joints["RIGHT LEG"][0] + joints["LEFT LEG"][0]) / 2
    ay = (joints["RIGHT LEG"][1] + joints["LEFT LEG"][1]) / 2
    return max(1e-6, math.hypot(ax - nx, ay - ny))


def retarget(first: Sequence[Joint], frames: Sequence[Sequence[Joint]], size: tuple[int, int], actor: Sequence[Joint],
             target: tuple[int, int]) -> list[list[Joint]]:
    """The render's motion moved onto another sprite: each joint at the sprite's own place plus how far the render's joint moved
    from its first pose, scaled by the two bodies' lengths. The sprite keeps its proportions and its camera; only the motion is
    the render's. `first` and `frames` are in fractions of `size` (the render's frame), `actor` in fractions of `target`."""
    def px(joints: Sequence[Joint], w: int, h: int) -> dict[str, tuple[float, float]]:
        return {j["label"]: (j["x"] * w, j["y"] * h) for j in joints}

    source, own = px(first, *size), px(actor, *target)
    scale = _span(own) / _span(source)
    moved: list[list[Joint]] = []
    for frame in frames:
        here = px(frame, *size)
        moved.append([{"x": round(min(1.0, max(0.0, (own[j["label"]][0] + scale * (here[j["label"]][0] - source[j["label"]][0]))
                                               / target[0])), 4),
                       "y": round(min(1.0, max(0.0, (own[j["label"]][1] + scale * (here[j["label"]][1] - source[j["label"]][1]))
                                               / target[1])), 4),
                       "label": j["label"], "z_index": j["z_index"]} for j in frame])
    return moved


__all__ = ["BODY", "LABELS", "LIMBS", "MAX_FRAMES", "MIN_FRAMES", "POINTS", "POINT_NAMES", "centre_depth", "joints_of",
           "missing_points", "pick", "retarget", "skeleton"]
