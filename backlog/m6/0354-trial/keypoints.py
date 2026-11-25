"""Trial 0354: PixelLab skeletons from a Kiripix render, for `pixellab.py skeleton`.

Kiripix's character `render` already projects named bones through the camera in every frame (its `points` parameter, ticket
0237): `work/render/render.json` holds, per clip, direction and frame, `points: {name: {x, y, depth, hidden}}` in px of the
frame, and `eyes` (the Model's right eye first). So no Blender script is needed: a scratch character made from mc03_male,
with POINTS below set as its `[stages.render] points`, gives the mc03 rig's joints at `top34_8` for every clip.

    uv run python backlog/m6/0354-trial/keypoints.py <character>/work/render/render.json --clip walk --out keypoints/

writes, per direction, `<clip>_<direction>.json` ({"first_frame_keypoints", "keypoints", "meta"}) and an overlay PNG
(`<clip>_<direction>_overlay.png`: the render's frames with the joints drawn, 6x, the character's right side in red) to check
the mapping by eye before spending anything.

PixelLab's 18 joints (read 2026-11-25 from `/v2/openapi.json`, `SkeletonLabel`): x and y as fractions 0-1 of the image,
`z_index` (higher draws on top) and an optional `depth` 0-255 (about 128 at the body's centre, higher is nearer). "RIGHT ARM"
is the wrist and "RIGHT LEG" the ankle (OpenPose's order); RIGHT is taken to be the character's own right, as OpenPose's is.
That is checked once with `pixellab.py estimate` on one south frame (README, step 3): its RIGHT SHOULDER must land on the
image's left.

The body's 14 joints are the mc03 rig's bones. Mixamo's rig has no nose, eye or ear bones, so those 5 are made from the
render's `eyes` and the head's two bones (Head, at the skull's base, and HeadTop_End): the nose a little below the eyes'
middle along the head's axis, each ear at the head's axis at eye height, out past its eye by EAR_SPREAD times the eyes'
spacing. A rough guess, good to a pixel or two at 52 px; the overlay shows it.
"""

from __future__ import annotations

import argparse
import json
import math
from typing import Any
from pathlib import Path

from PIL import Image, ImageDraw

# The scratch character's `[stages.render] points` (name@bone), mc03's Mixamo bones.
POINTS = ("neck@mixamorig:Neck,head@mixamorig:Head,head_top@mixamorig:HeadTop_End,"
          "shoulder_r@mixamorig:RightArm,elbow_r@mixamorig:RightForeArm,wrist_r@mixamorig:RightHand,"
          "shoulder_l@mixamorig:LeftArm,elbow_l@mixamorig:LeftForeArm,wrist_l@mixamorig:LeftHand,"
          "hip_r@mixamorig:RightUpLeg,knee_r@mixamorig:RightLeg,ankle_r@mixamorig:RightFoot,"
          "hip_l@mixamorig:LeftUpLeg,knee_l@mixamorig:LeftLeg,ankle_l@mixamorig:LeftFoot")

BODY = {"NECK": "neck", "RIGHT SHOULDER": "shoulder_r", "RIGHT ELBOW": "elbow_r", "RIGHT ARM": "wrist_r",
        "LEFT SHOULDER": "shoulder_l", "LEFT ELBOW": "elbow_l", "LEFT ARM": "wrist_l", "RIGHT HIP": "hip_r",
        "RIGHT KNEE": "knee_r", "RIGHT LEG": "ankle_r", "LEFT HIP": "hip_l", "LEFT KNEE": "knee_l", "LEFT LEG": "ankle_l"}
FACE = ("NOSE", "RIGHT EYE", "LEFT EYE", "RIGHT EAR", "LEFT EAR")
LABELS = ("NOSE", "NECK", "RIGHT SHOULDER", "RIGHT ELBOW", "RIGHT ARM", "LEFT SHOULDER", "LEFT ELBOW", "LEFT ARM",
          "RIGHT HIP", "RIGHT KNEE", "RIGHT LEG", "LEFT HIP", "LEFT KNEE", "LEFT LEG", "RIGHT EYE", "LEFT EYE",
          "RIGHT EAR", "LEFT EAR")
LIMBS = (("NECK", "RIGHT SHOULDER"), ("RIGHT SHOULDER", "RIGHT ELBOW"), ("RIGHT ELBOW", "RIGHT ARM"),
         ("NECK", "LEFT SHOULDER"), ("LEFT SHOULDER", "LEFT ELBOW"), ("LEFT ELBOW", "LEFT ARM"),
         ("NECK", "RIGHT HIP"), ("RIGHT HIP", "RIGHT KNEE"), ("RIGHT KNEE", "RIGHT LEG"),
         ("NECK", "LEFT HIP"), ("LEFT HIP", "LEFT KNEE"), ("LEFT KNEE", "LEFT LEG"), ("NECK", "NOSE"),
         ("NOSE", "RIGHT EYE"), ("RIGHT EYE", "RIGHT EAR"), ("NOSE", "LEFT EYE"), ("LEFT EYE", "LEFT EAR"))
EYE_HEIGHT = 0.45   # the eyes' height up the head, from Head (the skull's base) to HeadTop_End
NOSE_DROP = 0.18    # the nose below the eyes' middle, in head heights
EAR_SPREAD = 0.9    # each ear out past its eye, in the eyes' spacing
SCALE = 6


def face(points: dict, eyes: list | None) -> dict:
    """The nose, eyes and ears in px from the head's bones and the render's eyes: {label: (x, y, depth)}."""
    hx, hy, hd = points["head"]["x"], points["head"]["y"], points["head"]["depth"]
    tx, ty, td = points["head_top"]["x"], points["head_top"]["y"], points["head_top"]["depth"]
    ax, ay, ad = (hx + EYE_HEIGHT * (tx - hx), hy + EYE_HEIGHT * (ty - hy), hd + EYE_HEIGHT * (td - hd))
    if eyes and len(eyes) >= 2:
        right, left = (eyes[0]["x"], eyes[0]["y"], eyes[0]["depth"]), (eyes[1]["x"], eyes[1]["y"], eyes[1]["depth"])
    else:  # no eyes recorded: both on the axis, the face read as seen edge-on
        right = left = (ax, ay, ad)
    mx, my, md = ((right[0] + left[0]) / 2, (right[1] + left[1]) / 2, (right[2] + left[2]) / 2)
    nose = (mx + NOSE_DROP * (hx - tx), my + NOSE_DROP * (hy - ty), md - 0.02)
    across = (right[0] - left[0], right[1] - left[1], right[2] - left[2])
    ear_r = (ax + (0.5 + EAR_SPREAD) * across[0], ay + (0.5 + EAR_SPREAD) * across[1], ad + 0.05)
    ear_l = (ax - (0.5 + EAR_SPREAD) * across[0], ay - (0.5 + EAR_SPREAD) * across[1], ad + 0.05)
    return {"NOSE": nose, "RIGHT EYE": right, "LEFT EYE": left, "RIGHT EAR": ear_r, "LEFT EAR": ear_l}


def skeleton(frame: dict, size: tuple[int, int], depth_scale: float | None, centre: float) -> list[dict]:
    """One frame's 18 joints for PixelLab: fractions of the frame, z_index by depth (nearer is higher)."""
    points = frame.get("points") or {}
    missing = [n for n in ("head", "head_top", *BODY.values()) if n not in points]
    if missing:
        raise SystemExit(f"frame {frame.get('index')}: no point {', '.join(missing)}; set the character's render "
                         f"points to keypoints.POINTS and build render again")
    places = {label: (points[name]["x"], points[name]["y"], points[name]["depth"]) for label, name in BODY.items()}
    places |= face(points, frame.get("eyes"))
    width, height = size
    order = sorted(LABELS, key=lambda label: -places[label][2])  # farthest first
    joints = []
    for label in LABELS:
        x, y, d = places[label]
        joint = {"x": round(min(1.0, max(0.0, x / width)), 4), "y": round(min(1.0, max(0.0, y / height)), 4),
                 "label": label, "z_index": order.index(label)}
        if depth_scale is not None:
            joint["depth"] = round(min(255.0, max(0.0, 128 + (centre - d) * depth_scale)), 1)
        joints.append(joint)
    return joints


def pick(count: int, wanted: int | None) -> list[int]:
    """`wanted` frame indexes spread evenly over `count` (all of them when None or more than there are)."""
    if not wanted or wanted >= count:
        return list(range(count))
    return [round(i * count / wanted) for i in range(wanted)]


def estimated(pattern: str, direction: str) -> tuple[list[dict], tuple[int, int], Path]:
    """Another sprite's skeleton in one direction, from the newest `pixellab.py estimate` run the pattern matches: its 18
    joints, its image's size and the image."""
    import glob
    folders = sorted(glob.glob(pattern.replace("{d}", direction)))
    if not folders:
        raise SystemExit(f"no estimate run matches {pattern.replace('{d}', direction)}")
    folder = Path(folders[-1])
    body = json.loads((folder / "response.json").read_text(encoding="utf-8")).get("body") or {}
    joints = [{"x": j["x"], "y": j["y"], "label": j["label"], "z_index": int(j.get("z_index", 0))}
              for j in body.get("keypoints") or []]
    if {j["label"] for j in joints} != set(LABELS):
        raise SystemExit(f"{folder}: the estimate hasn't the 18 joints: {sorted(j['label'] for j in joints)}")
    picture = folder / "in_image.png"
    return joints, Image.open(picture).size, picture


def span(joints: dict) -> float:
    """The body's length in px: the neck to the middle of the ankles."""
    nx, ny = joints["NECK"]
    ax = (joints["RIGHT LEG"][0] + joints["LEFT LEG"][0]) / 2
    ay = (joints["RIGHT LEG"][1] + joints["LEFT LEG"][1]) / 2
    return max(1e-6, math.hypot(ax - nx, ay - ny))


def retarget(first: list[dict], frames: list[list[dict]], size: tuple[int, int], actor: list[dict],
             target: tuple[int, int]) -> list[list[dict]]:
    """The render's motion moved onto another sprite: each joint at the sprite's own place plus how far the render's
    joint moved from its first pose, scaled by the two bodies' lengths. The sprite keeps its proportions and its camera;
    only the motion is mc03's."""
    def px(joints: list[dict], w: int, h: int) -> dict:
        return {j["label"]: (j["x"] * w, j["y"] * h) for j in joints}
    source, own = px(first, *size), px(actor, *target)
    scale = span(own) / span(source)
    moved = []
    for frame in frames:
        here = px(frame, *size)
        moved.append([{"x": round(min(1.0, max(0.0, (own[j["label"]][0] + scale * (here[j["label"]][0] - source[j["label"]][0])) / target[0])), 4),
                       "y": round(min(1.0, max(0.0, (own[j["label"]][1] + scale * (here[j["label"]][1] - source[j["label"]][1])) / target[1])), 4),
                       "label": j["label"], "z_index": j["z_index"]} for j in frame])
    return moved


def frame_image(render_dir: Path, frame: dict) -> Path | None:
    colour = frame.get("files", {}).get("color")
    return render_dir / colour if colour and (render_dir / colour).exists() else None


def overlay(images: list[Path | None], skeletons: list[list[dict]], size: tuple[int, int], out: Path) -> None:
    """Each skeleton over its image (none: a dark panel), side by side, enlarged: the character's right side red, its
    left blue."""
    width, height = size
    sheet = Image.new("RGBA", (width * SCALE * len(skeletons), height * SCALE), (40, 40, 48, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (path, joints) in enumerate(zip(images, skeletons)):
        if path is not None:
            image = Image.open(path).convert("RGBA").resize((width * SCALE, height * SCALE), Image.Resampling.NEAREST)
            sheet.alpha_composite(image, (i * width * SCALE, 0))
        at = {j["label"]: (i * width * SCALE + j["x"] * width * SCALE, j["y"] * height * SCALE) for j in joints}
        for a, b in LIMBS:
            tint = (230, 60, 60, 255) if "RIGHT" in a + b else (60, 120, 240, 255) if "LEFT" in a + b else (240, 240, 240, 255)
            draw.line([at[a], at[b]], fill=tint, width=2)
        for label, (x, y) in at.items():
            draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 220, 0, 255))
    sheet.save(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("render_json", type=Path, help="a character's work/render/render.json, rendered with POINTS")
    parser.add_argument("--clip", required=True, help="the motion's clip, such as walk")
    parser.add_argument("--first-clip", help="the clip of the pose the actor's frame is in (default: --clip)")
    parser.add_argument("--first-index", type=int, default=0, help="that pose's frame index (default 0)")
    parser.add_argument("--frames", type=int, default=8, help="frames of the clip to keep, spread evenly (3 to 15)")
    parser.add_argument("--directions", default="s,sw,w,nw,n,ne,e,se")
    parser.add_argument("--depth-scale", type=float, help="send `depth` too: 128 + (centre - depth) x this, in units of "
                        "Blender units; by default depth is left out and PixelLab takes it from the template")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--retarget", help="move another sprite instead of the render's frame: a glob of the "
                        "`pixellab.py estimate` run folders of that sprite, with {d} for the direction, such as "
                        "\"backlog/m6/0354-trial/runs/*-estimate_worker_{d}\"")
    parser.add_argument("--print-points", action="store_true", help="print the render `points` value to set, and stop")
    args = parser.parse_args()
    if args.print_points:
        print(POINTS)
        return
    render = json.loads(args.render_json.read_text(encoding="utf-8"))
    size = (int(render["frame"]["width"]), int(render["frame"]["height"]))
    clips = {clip["name"]: clip for clip in render["clips"]}
    if args.clip not in clips or (args.first_clip or args.clip) not in clips:
        raise SystemExit(f"clips in {args.render_json}: {', '.join(clips)}")
    args.out.mkdir(parents=True, exist_ok=True)
    for direction in args.directions.split(","):
        motion = clips[args.clip]["directions"][direction]
        first = clips[args.first_clip or args.clip]["directions"][direction][args.first_index]
        chosen = [motion[i] for i in pick(len(motion), args.frames)]
        centre = (first["points"]["hip_r"]["depth"] + first["points"]["hip_l"]["depth"]) / 2 if "points" in first else 0.0
        first_joints = skeleton(first, size, args.depth_scale, centre)
        joints = [skeleton(frame, size, args.depth_scale, centre) for frame in chosen]
        name = f"{args.clip}_{direction}"
        meta: dict[str, Any] = {
            "render": str(args.render_json), "camera": render.get("camera"), "frame": list(size), "clip": args.clip,
            "direction": direction, "frames": [f["index"] for f in chosen],
            "first": {"clip": args.first_clip or args.clip, "index": args.first_index,
                      "color": first.get("files", {}).get("color")},
            "fps": clips[args.clip].get("fps"), "loop": clips[args.clip].get("loop")}
        pictures = [frame_image(args.render_json.parent, f) for f in (first, *chosen)]
        frame_size = size
        if args.retarget:
            actor, frame_size, picture = estimated(args.retarget, direction)
            joints = retarget(first_joints, joints, size, actor, frame_size)
            first_joints, pictures = actor, [picture] * (len(joints) + 1)
            meta |= {"retarget": str(picture.parent), "frame": list(frame_size)}
        plan = {"first_frame_keypoints": first_joints, "keypoints": joints, "meta": meta}
        (args.out / f"{name}.json").write_text(json.dumps(plan, indent=1) + "\n", encoding="utf-8", newline="\n")
        overlay(pictures, [first_joints, *joints], frame_size, args.out / f"{name}_overlay.png")
        print(f"{args.out / name}.json: {len(joints)} frames of {len(motion)}, frame {frame_size[0]}x{frame_size[1]}")


if __name__ == "__main__":
    main()
