"""`gen --motion skeleton` (ticket 0389): a sprite's clip from a character's `render`, through PixelLab's skeleton.

Core reads the character's built `render.json` (the Stage's output, current, else `gen.render_stale`), checks the points it
needs (`kiripix.providers.keypoints.POINTS`, else `gen.render_points_missing`) and the directions it covers
(`gen.render_direction_missing`), and turns the clip's frames into PixelLab's 18 joints per direction (the pure mapping is in
`kiripix.providers.keypoints`). `gen_sprite` plans `estimate_skeleton` and `animate_skeleton` from it; the retarget onto the
sprite's own skeleton happens at send time, from the estimate's answer (`gen_sprite._feed`).

`--preview` writes, per direction, `<clip>_<direction>.json` and `<clip>_<direction>_overlay.png` (the render's frames with the
joints drawn, the character's right side red) under `.kiripix/calls/preview/<sprite>/`, so the mapping is checked by eye before
anything is spent. Nothing is planned or sent.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    from PIL import Image, ImageDraw
else:  # PIL loads on first use, so `kiripix --help` and `schema` stay light (tests/cli/test_start_imports.py)
    Image = lazy_module("PIL.Image")
    ImageDraw = lazy_module("PIL.ImageDraw")

from kiripix.core import atomic
from kiripix.core.assets import Asset, load_asset
from kiripix.core.errors import fail
from kiripix.core.gen import CALLS_DIR
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.providers import keypoints

RENDER_STAGE = "render"
RENDER_FILE = "render.json"
PREVIEW_DIR = "preview"
SCALE = 6  # the overlay's enlargement
FRAMES_RANGE = (keypoints.MIN_FRAMES, keypoints.MAX_FRAMES)


@dataclass
class DirectionPlan:
    """One direction of the render's clip: the first pose and the chosen frames' joints, in fractions of the render's frame."""

    direction: str
    first: list[keypoints.Joint]
    frames: list[list[keypoints.Joint]]
    meta: dict[str, Any]
    images: list[Path | None] = field(default_factory=list)  # the first frame's colour image, then the chosen frames'


@dataclass
class RenderPlan:
    character: str
    clip: str
    size: tuple[int, int]
    directions: dict[str, DirectionPlan]


def _colour(folder: Path, frame: dict[str, Any]) -> Path | None:
    name = (frame.get("files") or {}).get("color")
    return folder / str(name) if name and (folder / str(name)).is_file() else None


def first_frame(project: Project, character: str, clip: str, direction: str = "s") -> Path:
    """The first frame of the character's current `render` for `clip` in `direction` (0390: a style image for `gen --image`)."""
    asset = load_asset(project, character)
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    state = graph.state(RENDER_STAGE)
    if state.status != "done":
        raise fail("gen.render_stale", f"{character}'s render is {state.status}: gen reads only a current render",
                   fix=f"kiripix run {character} {RENDER_STAGE}")
    folder = graph.output_dir(graph.spec(RENDER_STAGE))
    try:
        clips = {str(c["name"]): c for c in json.loads((folder / RENDER_FILE).read_text(encoding="utf-8"))["clips"]}
    except (OSError, ValueError, KeyError, TypeError):
        raise fail("gen.render_stale", f"{character}'s render.json can't be read",
                   fix=f"kiripix run {character} {RENDER_STAGE} --force") from None
    if clip not in clips:
        raise fail("gen.render_clip_unknown", f"{character}'s render has no clip '{clip}'; its clips are {', '.join(clips)}",
                   fix=f"kiripix show {character}")
    frames = (clips[clip].get("directions") or {}).get(direction) or []
    found = _colour(folder, min(frames, key=lambda f: int(f["index"]))) if frames else None
    if found is None:
        raise fail("gen.render_direction_missing", f"{character}'s render of '{clip}' has no frame in direction {direction}",
                   fix=f"kiripix run {character} {RENDER_STAGE} --force")
    return found


def read(project: Project, character: str, clip: str, directions: list[str], frames: int | None, again: str) -> RenderPlan:
    """The joints of the character's render for `clip` in `directions`, `frames` of them picked evenly (all when None). Refusals:
    `gen.render_not_character`, `gen.render_stale`, `gen.render_points_missing`, `gen.render_clip_unknown`,
    `gen.render_direction_missing`, `gen.frames_range`."""
    asset = load_asset(project, character)
    if asset.kind != "character":
        raise fail("gen.render_not_character", f"--render names {character}, a {asset.kind}: it takes a character, the Asset "
                   "whose `render` Stage draws the motion", fix="kiripix status")
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    state = graph.state(RENDER_STAGE)
    if state.status != "done":
        raise fail("gen.render_stale", f"{character}'s render is {state.status}" + (f" ({state.reason})" if state.reason else "")
                   + ": gen reads only a current render", fix=f"kiripix run {character} {RENDER_STAGE}")
    folder = graph.output_dir(graph.spec(RENDER_STAGE))
    try:
        document = json.loads((folder / RENDER_FILE).read_text(encoding="utf-8"))
        size = (int(document["frame"]["width"]), int(document["frame"]["height"]))
        clips = {str(c["name"]): c for c in document["clips"]}
    except (OSError, ValueError, KeyError, TypeError):
        raise fail("gen.render_stale", f"{character}'s render.json can't be read",
                   fix=f"kiripix run {character} {RENDER_STAGE} --force") from None
    named = [str(p.get("name")) for p in document.get("points") or [] if isinstance(p, dict)]
    absent = keypoints.missing_points(named)
    if absent:
        raise fail("gen.render_points_missing", f"{character}'s render doesn't record the points {', '.join(absent)}, which the "
                   "skeleton's joints are made from", fix=f"kiripix set {character} {RENDER_STAGE} points={keypoints.POINTS}")
    if clip not in clips:
        raise fail("gen.render_clip_unknown", f"{character}'s render has no clip '{clip}'; its clips are {', '.join(clips)}",
                   fix=f"{again.split(' --render-clip')[0]} --render-clip {next(iter(clips), 'idle')}")
    entry = clips[clip]
    frame_size = (int(entry["frame"]["width"]), int(entry["frame"]["height"])) if isinstance(entry.get("frame"), dict) else size
    covered = entry.get("directions") or {}
    lacking = [d for d in directions if not covered.get(d)]
    if lacking:
        raise fail("gen.render_direction_missing", f"{character}'s render of '{clip}' has no frames in "
                   f"{', '.join(lacking)} (it has {', '.join(covered) or 'none'}): the sprite asks for them",
                   fix=f"{again.split(' --directions')[0]} --directions {','.join(d for d in directions if d in covered)}"
                   if any(d in covered for d in directions) else f"kiripix show {character}")
    plan = RenderPlan(character=character, clip=clip, size=frame_size, directions={})
    for direction in directions:
        motion = covered[direction]
        chosen = [motion[i] for i in keypoints.pick(len(motion), frames)]
        if not FRAMES_RANGE[0] <= len(chosen) <= FRAMES_RANGE[1]:
            raise fail("gen.frames_range", f"{character}'s '{clip}' gives {len(chosen)} frames in {direction}: PixelLab's "
                       f"skeleton motion takes {FRAMES_RANGE[0]} to {FRAMES_RANGE[1]}",
                       fix=f"{again.split(' --frames')[0]} --frames {min(max(len(motion), FRAMES_RANGE[0]), FRAMES_RANGE[1])}")
        first = motion[0]
        try:
            first_joints = keypoints.skeleton(first, frame_size)
            joints = [keypoints.skeleton(f, frame_size) for f in chosen]
        except ValueError as error:
            raise fail("gen.render_points_missing", f"{character}'s render of '{clip}' in {direction}: {error}",
                       fix=f"kiripix set {character} {RENDER_STAGE} points={keypoints.POINTS}") from None
        meta = {"character": character, "camera": document.get("camera"), "frame": list(frame_size), "clip": clip,
                "direction": direction, "frames": [int(f["index"]) for f in chosen], "of": len(motion),
                "first": {"clip": clip, "index": int(first["index"]), "color": (first.get("files") or {}).get("color")},
                "fps": entry.get("fps"), "loop": entry.get("loop")}
        plan.directions[direction] = DirectionPlan(
            direction=direction, first=first_joints, frames=joints, meta=meta,
            images=[_colour(folder, f) for f in (first, *chosen)])
    return plan


def overlay(images: list[Path | None], skeletons: list[list[keypoints.Joint]], size: tuple[int, int]) -> bytes:
    """Each skeleton over its image (none: a dark panel), side by side, enlarged: the character's right side red, its left blue."""
    width, height = size
    sheet = Image.new("RGBA", (width * SCALE * len(skeletons), height * SCALE), (40, 40, 48, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (path, joints) in enumerate(zip(images, skeletons, strict=True)):
        if path is not None:
            image = Image.open(path).convert("RGBA").resize((width * SCALE, height * SCALE), Image.Resampling.NEAREST)
            sheet.alpha_composite(image, (i * width * SCALE, 0))
        at = {j["label"]: (i * width * SCALE + j["x"] * width * SCALE, j["y"] * height * SCALE) for j in joints}
        for a, b in keypoints.LIMBS:
            tint = ((230, 60, 60, 255) if "RIGHT" in a + b else (60, 120, 240, 255) if "LEFT" in a + b
                    else (240, 240, 240, 255))
            draw.line([at[a], at[b]], fill=tint, width=2)
        for x, y in at.values():
            draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 220, 0, 255))
    out = io.BytesIO()
    sheet.save(out, "PNG")
    return out.getvalue()


def write_preview(project: Project, asset: Asset, plan: RenderPlan) -> list[tuple[str, str]]:
    """Write each direction's keypoints JSON and overlay PNG under `.kiripix/calls/preview/<sprite>/`; (json, png) per direction,
    relative to the Project."""
    folder = project.state_dir / CALLS_DIR / PREVIEW_DIR / asset.id
    written: list[tuple[str, str]] = []
    for direction, found in plan.directions.items():
        stem = f"{plan.clip}_{direction}"
        document = {"first_frame_keypoints": found.first, "keypoints": found.frames, "meta": found.meta}
        data = _dump(document)
        atomic.write_bytes(folder / f"{stem}.json", data)
        atomic.write_bytes(folder / f"{stem}_overlay.png", overlay(found.images, [found.first, *found.frames], plan.size))
        written.append((project.relative(folder / f"{stem}.json"), project.relative(folder / f"{stem}_overlay.png")))
    return written


def _dump(document: dict[str, Any]) -> bytes:
    return (json.dumps(document, indent=1) + "\n").encode("utf-8")


__all__ = ["FRAMES_RANGE", "DirectionPlan", "RenderPlan", "overlay", "read", "write_preview"]
