"""The character's `finish` Stage (spec §6.3, ADR 0004, ticket 0111).

Two things, both after `palette`:

- the outline: a 1 px silhouette of each colour frame's alpha, painted in the palette colour `outline_colour` (an index into the
  Project palette) once the colours are mapped, so it is a palette colour and never dithered or mapped. `outline=false` skips it.
  `placement` is `outside` (the line is the transparent pixels around the silhouette, so the silhouette keeps its pixels and a
  Prop's outline matches; where the character touches the frame's edge the line has nowhere to go) or `edge` (the line is the
  silhouette's own edge pixels). `render`'s cell leaves the character at least `ceil(0.1 * height)` px under its feet and more
  elsewhere, so `outside` has room.
- the eyes (ticket 0203), with `eyes=stamp` or `pupils`, before the outline: the pixels of the eye materials that `render`
  followed (its `eyes` parameter) are filled with the skin round them, and each eye is painted as a small fixed pattern from
  where the posed Model puts it (`plan_eyes`): chosen once for a clip and a direction, on whole pixels, moving only when the
  head has. A frame in its clip's `blink` list gets closed eyes, one in `wink_left` or `wink_right` that eye closed. The colours are Project palette colours (`eye_colour`,
  `eye_white`). The normal pass is not changed.
- the inner lines (ticket 0215), with `inner_lines=outline` or `dark`, after the eyes and before the outline: the farther pixel
  of each border between two materials (`inner_lines` in the ops), in the outline's colour or, with `dark`, a darker palette
  colour of its own material chosen once over all the frames (`line_colours`). `line_skip` drops borders. Only inside the
  render's mask, never over an eye pixel, never on the eye materials. The normal pass is not changed. A sprite (ticket 0320)
  has its lines between its parts, the colour regions `palette` joined (its material pass); a region in no part is one of its
  own. It has no depth, so the line is the lower pixel of a border (the right one, side by side), and no mask, so its alpha
  is the inside. `line_skip` names its parts.
- the normal pass, from `render`: quantised to `normal_levels` values per axis, encoded for Godot, and cut by the final colour
  frame's alpha, so an outline pixel gets a normal that faces the camera and the two images line up pixel for pixel. It is
  never palette-mapped.

Output in `work/finish/`, in `render`'s layout: `color/<clip>/<dir>/<NNN>.png` and `normal/<clip>/<dir>/<NNN>.png` for every
frame, `render.json` (copied, so the frame list and pivots go on to `sheet`) and `finish.json` (what was drawn).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import (
    EyeCover,
    Finding,
    PartCounts,
    Position,
    check_conformance,
    check_eyes_covered,
    check_part_vanishes,
)
from kiripix.checks.sheet import SheetFrame, check_normal_size
from kiripix.ops import (
    EyeAnchor,
    EyeStamp,
    Placement,
    add_outline,
    conformance,
    encode_normals,
    fill_from_neighbours,
    height_from_alpha,
    inner_lines,
    line_colours,
    normals_from_height,
    paint_eyes,
    plan_eyes,
    quantise_normals,
    stamped_mask,
)
from kiripix.recipes.base import CheckFunction, ParamSpec, StageFailure, StageFunction, StageRun
from kiripix.recipes.character_palette import RENDER_FILE, _colour_files, material_indexes
from kiripix.recipes.common import palette_rgb, read_rgba, write_rgba

FINISH_SCHEMA_VERSION = 3
FINISH_FILE = "finish.json"
FLAT = (128, 128, 255, 255)  # a normal facing the camera, as `encode_normals` writes it


def normals_params(default: str = "pass") -> tuple[ParamSpec, ParamSpec]:
    """The `normals` and `relief` parameters, for a Recipe that declares them (the sprite's `finish`, ticket 0176, which has no
    normal pass and defaults to `height`). The character doesn't: a new parameter would change its hashes, and it reads `pass`
    when `normals` isn't declared, which is also what they default to here."""
    return (
        ParamSpec(name="normals", type="choice", choices=["pass", "height", "flat"], default=default,
                  description="pass: the normal pass of the frame Stage; height: normals from a rounded height of the "
                              "silhouette; flat: every opaque pixel faces the camera."),
        ParamSpec(name="relief", type="float", minimum=0.0, maximum=1.0, default=0.0,
                  description="With normals=height, the share of the colour frame's lightness in the height, 0 to 1."),
    )


def _document(run: StageRun) -> dict[str, Any]:
    try:
        document: dict[str, Any] = json.loads((run.upstream["palette"] / RENDER_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure("palette has no render.json; run it again") from None
    return document


def _normal_name(colour_name: str) -> str:
    return "normal/" + colour_name.partition("/")[2]


def _outline_colour(run: StageRun, palette: np.ndarray, force: bool = False) -> tuple[int, tuple[int, int, int]] | None:
    """The outline's index and colour, or None for `outline=false` (unless `force`: the colour for `inner_lines=outline`);
    StageFailure when the index isn't in the palette."""
    if not run.params["outline"] and not force:
        return None
    index = int(run.params["outline_colour"])
    if not 0 <= index < len(palette):
        raise StageFailure(f"the outline colour {index} is not in the palette, which has {len(palette)} colours "
                           f"(indexes 0 to {len(palette) - 1}); kiripix set {run.asset_id} finish outline_colour=0",
                           code="finish.outline_colour_unknown",
                           fix=f"kiripix set {run.asset_id} finish outline_colour=0")
    r, g, b = (int(v) for v in palette[index])
    _refuse_a_ramp_colour(run, palette, index, (r, g, b))
    return index, (r, g, b)


def _refuse_a_ramp_colour(run: StageRun, palette: np.ndarray, index: int, rgb: tuple[int, int, int]) -> None:
    """An outline in a part's ramp would be recoloured with the part by the game's swap: `finish.outline_in_ramp`, with the first
    palette colour that no ramp and no fixed colour of the character has as the fix (ticket 0150)."""
    try:
        document = json.loads((run.upstream["palette"] / "palette.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    parts = document.get("parts", [])
    if parts:  # the Project's ramp table reserves its colours for every character with a part of it (ticket 0168)
        parts = parts + [r for r in document.get("table", []) if r.get("rgb") is not None
                         and all(p["name"] != r["name"] for p in parts)]
    owner = next((p["name"] for p in parts if list(rgb) in p["rgb"]), None)
    if owner is None:
        return
    used = {tuple(rgb_) for p in parts for rgb_ in p["rgb"]} | {tuple(c["rgb"]) for c in document.get("colors", [])}
    free = next((i for i, colour in enumerate(palette) if tuple(int(v) for v in colour) not in used), None)
    if free is None:
        raise StageFailure(f"the outline colour {index} is in the ramp of part {owner!r}, and the character's ramps and colours "
                           f"use the whole palette, so no colour is free for the outline",
                           code="finish.outline_in_ramp",
                           owner_action="Give the character fewer colours or a shorter ramp (palette colors, parts), or add a "
                                        "colour to the Project palette for the outline.")
    raise StageFailure(f"the outline colour {index} is in the ramp of part {owner!r}, so swapping that part would recolour the "
                       f"outline; palette colour {free} is free", code="finish.outline_in_ramp",
                       fix=f"kiripix set {run.asset_id} finish outline_colour={free}")


def _normals_mode(run: StageRun) -> str:
    mode = str(run.params.get("normals", "pass"))
    if mode not in ("pass", "height", "flat"):
        raise StageFailure(f"normals must be pass, height or flat, not {mode!r}", fix=f"kiripix set {run.asset_id} finish normals=pass")
    return mode


def _lightness(colour: np.ndarray) -> np.ndarray:
    """Each pixel's luma, 0 to 1."""
    rgb = colour[..., :3].astype(np.float64)
    return np.asarray((rgb @ np.array([0.2126, 0.7152, 0.0722])) / 255.0)


def _flat_frame(colour: np.ndarray) -> np.ndarray:
    """`normals=flat`: every opaque pixel of the final colour frame faces the camera. Already quantised and encoded."""
    out = np.zeros(colour.shape, dtype=np.uint8)
    out[colour[..., 3] > 0] = np.array(FLAT, dtype=np.uint8)
    return out


def _height_pass(mapped: np.ndarray, relief: float) -> np.ndarray:
    """`normals=height`: a raw normal pass from the mapped colour frame's silhouette (before the outline), for
    `_normal_frame` to quantise, encode and cut."""
    alpha = np.where(mapped[..., 3] > 0, 255, 0).astype(np.uint8)
    height = height_from_alpha(alpha)
    if relief > 0:
        height = (1.0 - relief) * height + relief * _lightness(mapped) * (alpha > 0)
    return cast("np.ndarray", normals_from_height(height, alpha))


def _normal_frame(normal: np.ndarray, colour: np.ndarray, levels: int) -> np.ndarray:
    """The quantised, encoded normal pass cut by the colour frame's alpha: an opaque colour pixel with no normal under it (the
    outline) faces the camera."""
    encoded = encode_normals(quantise_normals(normal, levels))
    opaque = colour[..., 3] > 0
    out = np.zeros_like(encoded)
    out[opaque] = np.where((encoded[..., 3] > 0)[opaque][:, None], encoded[opaque], np.array(FLAT, dtype=np.uint8))
    return out


# An eye counts as seen in a frame unless the pixel at its centre is nearer the camera than the eye is by more than this
# share of the character's height: an arm in front of the face, or the head itself in front of its far eye. The brow, the
# nose and a fringe are nearer by less, and hiding the eye for them would bring back the flicker the stamp is there to end.
SEEN_MARGIN = 0.067


def _covered_by(labels: np.ndarray, found: dict[str, Any], eye_labels: list[int]) -> int | None:
    """The material pass at an eye's place (ticket 0225): None when an eye material is there, or when the place is off the
    frame or empty; else the index of the other material that most pixels of the eye's box hold (the box is the eye's extent,
    at least its centre pixel)."""
    x, y = float(found["x"]), float(found["y"])
    half_w, half_h = float(found.get("width", 0.0)) / 2, float(found.get("height", 0.0)) / 2
    left, right = int(np.floor(x - half_w + 0.5)), int(np.floor(x + half_w - 0.5))
    top, bottom = int(np.floor(y - half_h + 0.5)), int(np.floor(y + half_h - 0.5))
    left, right = min(left, int(np.floor(x))), max(right, int(np.floor(x)))
    top, bottom = min(top, int(np.floor(y))), max(bottom, int(np.floor(y)))
    if right < 0 or bottom < 0:  # wholly off the frame's left or top: a negative slice end would wrap around
        return None
    left, top = max(left, 0), max(top, 0)
    box = labels[top:bottom + 1, left:right + 1]
    if box.size == 0 or np.isin(box, eye_labels).any():
        return None
    values, counts = np.unique(box[box > 0], return_counts=True)
    return int(values[int(np.argmax(counts))]) if len(values) else None


def _eyes_mode(run: StageRun) -> str:
    return str(run.params.get("eyes", "render"))


def _palette_colour(run: StageRun, palette: np.ndarray, name: str, index: int) -> tuple[int, tuple[int, int, int]]:
    if not 0 <= index < len(palette):
        raise StageFailure(f"the {name} {index} is not in the palette, which has {len(palette)} colours (indexes 0 to "
                           f"{len(palette) - 1}); kiripix set {run.asset_id} finish {name}=-1",
                           code="finish.eye_colour_unknown", fix=f"kiripix set {run.asset_id} finish {name}=-1")
    r, g, b = (int(v) for v in palette[index])
    return index, (r, g, b)


class _Eyes:
    """What `eyes=stamp` needs for a run: the eye materials' indexes in the material pass, the colours, and each frame's
    patterns, planned per clip and direction."""

    def __init__(self, run: StageRun, source: str, document: dict[str, Any], palette: np.ndarray) -> None:
        self.run, self.source = run, source
        names = [str(n) for n in document.get("eyes", [])]
        self.labels = [int(m["index"]) for m in document.get("materials", []) if str(m["name"]) in names]
        if not self.labels or source not in run.upstream:
            raise StageFailure(
                "finish can't stamp the eyes: render didn't follow them. Name the Model's eye materials in render's eyes "
                f"parameter (kiripix set {run.asset_id} render eyes=<materials>), or leave the eyes as rendered",
                code="finish.eyes_not_followed", fix=f"kiripix set {run.asset_id} finish eyes=render")
        self.whites = _eyes_mode(run) == "stamp"
        gap = int(run.params.get("eye_gap", 0))
        near, far = (float(v) for v in document["depth_range"])
        margin = SEEN_MARGIN * float(document["height"]) / float(document["px_per_unit"])
        self.stamps: dict[tuple[str, str, int], list[EyeStamp | None]] = {}
        self.closed: dict[tuple[str, int], set[int]] = {}  # (clip, frame) -> the eyes closed in it, as `render` orders them
        seen_colours: dict[tuple[int, int, int], int] = {}
        for entry in document["clips"]:
            for key, which in (("blink", (0, 1)), ("wink_right", (0,)), ("wink_left", (1,))):  # the right eye is first
                for index in entry.get(key, []):
                    self.closed.setdefault((str(entry["name"]), int(index)), set()).update(which)
            for direction, listed in entry["directions"].items():
                run.check_cancel()
                anchors: list[list[EyeAnchor]] = []
                for frame in listed:
                    labels = _read_labels(run.upstream[source] / str(frame["files"]["material"]))
                    eye = np.isin(labels, self.labels)
                    if eye.any():
                        mapped = read_rgba(run.upstream["palette"] / str(frame["files"]["color"]))
                        colours, counts = np.unique(mapped[eye & (mapped[..., 3] > 0)][:, :3], axis=0, return_counts=True)
                        for rgb, count in zip(colours, counts, strict=True):
                            found_rgb = (int(rgb[0]), int(rgb[1]), int(rgb[2]))
                            seen_colours[found_rgb] = seen_colours.get(found_rgb, 0) + int(count)
                    depth = near + _read_depth(run.upstream[source] / str(frame["files"]["depth"])) / 65535.0 * (far - near)
                    anchors.append([self._anchor(found, depth, margin, labels) for found in frame.get("eyes", [])])
                for frame, stamps in zip(listed, plan_eyes(anchors, self.whites, gap), strict=True):
                    self.stamps[(str(entry["name"]), direction, int(frame["index"]))] = stamps
        wanted = int(run.params.get("eye_colour", -1))
        if wanted >= 0:
            self.pupil = _palette_colour(run, palette, "eye_colour", wanted)
        else:
            lightness = _lightness(palette[None, :, :])[0]
            common = max(seen_colours, key=lambda c: (seen_colours[c], c)) if seen_colours else None
            index = next((i for i, c in enumerate(palette) if common == tuple(int(v) for v in c)), int(np.argmin(lightness)))
            self.pupil = _palette_colour(run, palette, "eye_colour", index)
        white = int(run.params.get("eye_white", -1))
        if white < 0:
            white = int(np.argmax(_lightness(palette[None, :, :])[0]))
        self.white = _palette_colour(run, palette, "eye_white", white)

    def _anchor(self, found: dict[str, Any], depth: np.ndarray, margin: float, labels: np.ndarray) -> EyeAnchor:
        x, y = float(found["x"]), float(found["y"])
        column, row = int(np.floor(x)), int(np.floor(y))
        inside = 0 <= row < depth.shape[0] and 0 <= column < depth.shape[1]
        seen = inside and float(depth[row, column]) >= float(found["depth"]) - margin
        if seen and _covered_by(labels, found, self.labels) is not None:  # another material is on the eye (ticket 0225)
            seen = False
        normal = found["normal"]
        return EyeAnchor(x, y, float(found["width"]), float(found["height"]), float(normal[0]), float(normal[2]), seen)

    def paint(self, colour: np.ndarray, clip: str, direction: str, index: int,
              material: str) -> tuple[np.ndarray, np.ndarray]:
        """The frame with its eyes filled and stamped, and the pixels the eyes changed or drew (whatever their colour
        was), which no line may paint over."""
        eye = np.isin(_read_labels(self.run.upstream[self.source] / material), self.labels)
        if eye.shape != colour.shape[:2]:
            eye = np.zeros(colour.shape[:2], dtype=np.bool_)
        filled = fill_from_neighbours(colour, eye)
        stamps, closed = self.stamps.get((clip, direction, index), []), self.closed.get((clip, index), set())
        painted = paint_eyes(filled, stamps, self.pupil[1], self.white[1] if self.whites else None, closed)
        return cast("np.ndarray", painted), eye | stamped_mask(filled, stamps, closed)

    def drawn(self) -> dict[str, Any]:
        return {"mode": _eyes_mode(self.run), "pupil": {"colour": self.pupil[0], "rgb": list(self.pupil[1])},
                "white": {"colour": self.white[0], "rgb": list(self.white[1])} if self.whites else None}


def _lines_mode(run: StageRun) -> str:
    return str(run.params.get("inner_lines", "off"))


class _InnerLines:
    """What `inner_lines=outline` or `dark` needs for a run (ticket 0215): the skipped borders, the eye materials that get no
    line, and, for `dark`, each material's line colour, chosen once over all the palette frames before the first is painted."""

    def __init__(self, run: StageRun, source: str, document: dict[str, Any], palette: np.ndarray,
                 files: list[tuple[str, str, int, str]]) -> None:
        self.run, self.source, self.mode = run, source, _lines_mode(run)
        if source not in run.upstream:
            raise StageFailure(f"finish can't draw inner lines: it has no material pass from {source}; run {source} again")
        self.described = _palette_document(run)
        if self.mode == "dark" and self.described.get("parts") and not self.described.get("part_lines"):
            raise StageFailure("inner_lines=dark with palette parts needs a line step in each part's ramp, so that swapping the "
                               "part recolours its lines too; palette part_lines=true adds it (inner_lines=outline needs "
                               "none)", code="finish.inner_lines_with_parts",
                               fix=f"kiripix set {run.asset_id} palette part_lines=true")
        if not document.get("materials"):
            raise StageFailure("finish can't draw inner lines: there are no parts to draw between (a sprite's are palette "
                               f"`parts`, ticket 0320); name them (kiripix set {run.asset_id} palette parts=...) or draw none",
                               code="finish.inner_lines_without_parts", fix=f"kiripix set {run.asset_id} finish inner_lines=off")
        self.indexes = material_indexes(document)  # the Model's materials, and a held thing's after them (ticket 0305)
        self.merge: np.ndarray | None = None
        if document.get("kind") == "sprite":
            self._join_sprite_parts()
        by_name = {n: i[0] for n, i in self.indexes.items()}
        self.skip_text: list[str] = []
        self.skip: list[int | tuple[int, int]] = []
        for token in (t.strip() for t in str(run.params.get("line_skip", "")).split(",")):
            if not token:
                continue
            names = [n.strip() for n in token.split("+")]
            unknown = [n for n in names if n not in by_name]
            if unknown or len(names) > 2 or not all(names):
                what = f"no material {unknown[0]!r}" if unknown else f"{token!r} is not a material or a pair a+b"
                raise StageFailure(f"line_skip: {what} in {token!r}; the materials are {', '.join(sorted(by_name)) or 'none'}",
                                   code="finish.line_skip_unknown", fix=f"kiripix set {run.asset_id} finish line_skip=")
            self.skip_text.append("+".join(names))
            if len(names) == 1:  # every index of the name, a held thing's as well as the Model's (ticket 0313)
                self.skip += self.indexes[names[0]]
            else:
                self.skip += [(a, b) for a in self.indexes[names[0]] for b in self.indexes[names[1]]]
        eye_names = {str(n) for n in document.get("eyes", [])}
        self.skip += [i for n, found in self.indexes.items() if n in eye_names for i in found]
        self.frames: dict[tuple[str, str, int], dict[str, str]] = {
            (str(e["name"]), d, int(f["index"])): {k: str(v) for k, v in f["files"].items()}
            for e in document["clips"] for d, listed in e["directions"].items() for f in listed}
        self.names = {i: n for n, found in self.indexes.items() for i in found}
        # `line_depth` px of the render's scale, in the depth pass's 16 bit unit: px / px_per_unit is world units, and the pass
        # spans `depth_range` over 65535 (ticket 0247).
        self.line_depth = float(run.params.get("line_depth", 0.0))
        self.depth_step: float | None = None
        if self.line_depth > 0 and "depth_range" in document:  # a sprite has no depth pass
            near, far = (float(v) for v in document["depth_range"])
            self.depth_step = self.line_depth / float(document["px_per_unit"]) / max(far - near, 1e-9) * 65535.0
        self.outline: tuple[int, tuple[int, int, int]] | None = None
        self.colours: dict[int, tuple[int, tuple[int, int, int]]] = {}
        if self.mode == "outline":
            self.outline = _outline_colour(run, palette, force=True)
        else:
            self._choose(files, palette)

    def _join_sprite_parts(self) -> None:
        """A sprite's material pass is its colour regions; its lines are between its parts (ticket 0320). Each part's regions
        become its first region's index (`merge`, applied to every label read), and the part's name stands for them, so
        `line_skip` and finish.json name parts. A region in no part keeps its own index and name."""
        merge = np.arange(256, dtype=np.uint8)
        joined: dict[str, list[int]] = {}
        taken: set[str] = set()
        for part in self.described.get("parts", []):
            found = [i for m in part["materials"] for i in self.indexes.get(str(m), [])]
            if not found:
                continue
            merge[found] = found[0]
            joined[str(part["name"])] = [found[0]]
            taken.update(str(m) for m in part["materials"])
        joined.update({n: i for n, i in self.indexes.items() if n not in taken and n not in joined})
        self.indexes, self.merge = joined, merge

    def _labels(self, path: Path) -> np.ndarray:
        labels = _read_labels(path)
        return labels if self.merge is None else self.merge[labels]

    def _choose(self, files: list[tuple[str, str, int, str]], palette: np.ndarray) -> None:
        # With `part_lines` (ticket 0216) a part's line is the first colour of its ramp, the step the frames never use; the
        # materials of no part get a darker colour that is in no ramp, so no swap touches it.
        ramp_colours: set[tuple[int, ...]] = set()
        claimed: list[int] = []
        parts = self.described.get("parts", [])
        if parts:
            ramp_colours = {tuple(int(v) for v in rgb) for p in parts for rgb in p["rgb"]}
            ramp_colours |= {tuple(int(v) for v in rgb) for r in self.described.get("table", [])
                             if r.get("rgb") is not None for rgb in r["rgb"]}
            for part in parts:
                for material in [part["name"]] if self.merge is not None else part["materials"]:
                    for found in self.indexes.get(material, []):
                        claimed.append(found)
                        r, g, b = (int(v) for v in part["rgb"][0])
                        self.colours[found] = (int(part["indexes"][0]), (r, g, b))
        mapped: list[np.ndarray] = []
        labels: list[np.ndarray] = []
        for clip, direction, index, name in files:
            self.run.check_cancel()
            frame = read_rgba(self.run.upstream["palette"] / name)
            label = self._labels(self._path(clip, direction, index, "material"))
            if claimed:
                frame[np.isin(label, np.array(claimed, dtype=np.int64)), 3] = 0
            mapped.append(frame)
            labels.append(label)
        if claimed and not any(bool((f[..., 3] == 255).any()) for f in mapped):
            return
        keep = [i for i, colour in enumerate(palette) if tuple(int(v) for v in colour) not in ramp_colours]
        try:
            chosen = line_colours(mapped, labels, palette[keep], float(self.run.params.get("line_darkness", 0.55)))
        except ValueError as error:
            raise StageFailure(f"can't choose the colours of the inner lines: {error}") from None
        for m, c in chosen.items():
            index = keep[c]
            self.colours[m] = (index, (int(palette[index][0]), int(palette[index][1]), int(palette[index][2])))

    def _path(self, clip: str, direction: str, index: int, kind: str) -> Path:
        return self.run.upstream[self.source] / self.frames[(clip, direction, index)][kind]

    def paint(self, colour: np.ndarray, clip: str, direction: str, index: int, eyed: np.ndarray | None) -> np.ndarray:
        """The frame with the lines painted, inside the render's mask and never over a pixel the eyes painted."""
        files = self.frames[(clip, direction, index)]
        try:
            labels = self._labels(self._path(clip, direction, index, "material"))
            # a sprite has no depth or mask pass (ticket 0320): every pixel ties, and its alpha is the inside
            depth = _read_depth(self._path(clip, direction, index, "depth")) if "depth" in files else np.zeros(labels.shape)
            inside = (_read_labels(self._path(clip, direction, index, "mask")) > 0 if "mask" in files
                      else colour[..., 3] > 0)
        except (OSError, KeyError):
            raise StageFailure(f"{self.source} has no material, depth or mask pass for {clip}/{direction} frame {index}; "
                               f"run {self.source} again") from None
        if labels.shape != colour.shape[:2] or depth.shape != labels.shape or inside.shape != labels.shape:
            return colour  # not the colour frame's size: `normal.size_mismatch` says so
        line = inner_lines(labels, depth, self.skip, self.depth_step) & inside
        if eyed is not None:
            line &= ~eyed
        out = colour.copy()
        if self.outline is not None:
            out[line] = (*self.outline[1], 255)
            return out
        for material, (_, rgb) in self.colours.items():
            out[line & (labels == material)] = (*rgb, 255)
        return out

    def drawn(self) -> dict[str, Any]:
        out: dict[str, Any] = {"mode": self.mode, "skip": self.skip_text, "line_depth": self.line_depth}
        if self.outline is not None:
            out["colour"] = {"colour": self.outline[0], "rgb": list(self.outline[1])}
        else:
            out["darkness"] = float(self.run.params.get("line_darkness", 0.55))
            out["colours"] = {self.names.get(m, str(m)): {"material": m, "colour": c, "rgb": list(rgb)}
                              for m, (c, rgb) in sorted(self.colours.items())}
        return out


def _palette_document(run: StageRun) -> dict[str, Any]:
    try:
        document: dict[str, Any] = json.loads((run.upstream["palette"] / "palette.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return document


def _materials_by_frame(document: dict[str, Any]) -> dict[tuple[str, str, int], str]:
    return {(str(e["name"]), d, int(f["index"])): str(f["files"].get("material", ""))
            for e in document["clips"] for d, listed in e["directions"].items() for f in listed}


def _is_effect(run: StageRun) -> bool:
    """The sprite's `fit` was told `effect` (ticket 0362): its cell keeps 1 px around the frames for the outline."""
    return "fit" in run.upstream_params and bool(run.upstream_params["fit"].get("effect", False))


def _trim_render(source: Path, target: Path) -> None:
    """`render.json` for frames cut by 1 px on every side: the cell is 2 px smaller, and every pivot and foot 1 px nearer the corner."""
    document: dict[str, Any] = json.loads(source.read_text(encoding="utf-8"))
    document["frame"] = {"width": document["frame"]["width"] - 2, "height": document["frame"]["height"] - 2}
    document["pivot"] = [document["pivot"][0] - 1, document["pivot"][1] - 1]
    for entry in document["clips"]:
        for listed in entry["directions"].values():
            for frame in listed:
                frame["pivot"] = [frame["pivot"][0] - 1, frame["pivot"][1] - 1]
                if "feet" in frame:
                    frame["feet"] = [frame["feet"][0] - 1, frame["feet"][1] - 1]
    target.write_text(json.dumps(document, indent=1) + "\n", encoding="utf-8")


def _run_finish(run: StageRun, source: str) -> None:
    document = _document(run)
    mode, relief = _normals_mode(run), float(run.params.get("relief", 0.0))
    palette = palette_rgb(run)
    outline = _outline_colour(run, palette)
    levels, placement = int(run.params["normal_levels"]), str(run.params["placement"])
    eyes = _Eyes(run, source, document, palette) if _eyes_mode(run) != "render" else None
    files = _colour_files(document)
    spare = outline is None and _is_effect(run) and bool(document["frame"]["width"] > 2 and document["frame"]["height"] > 2)
    lines = _InnerLines(run, source, document, palette, files) if _lines_mode(run) != "off" else None
    materials = _materials_by_frame(document) if eyes is not None else {}
    for number, (clip, direction, index, name) in enumerate(files):
        run.check_cancel()
        run.progress(number, len(files), f"finishing {clip}/{direction}/{index:03d}")
        colour = read_rgba(run.upstream["palette"] / name)
        if eyes is not None:
            colour, eyed = eyes.paint(colour, clip, direction, index, materials[(clip, direction, index)])
        else:
            eyed = None
        if lines is not None:
            colour = lines.paint(colour, clip, direction, index, eyed)
        mapped = colour
        if outline is not None:
            colour = add_outline(colour, outline[1], cast(Placement, placement))
        try:
            if mode == "flat":
                finished = _flat_frame(colour)
            else:
                normal = _height_pass(mapped, relief) if mode == "height" else read_rgba(run.upstream[source] / _normal_name(name))
                if normal.shape != colour.shape:
                    finished = normal  # not the colour frame's size: `normal.size_mismatch` says so, there is no cut to make
                else:
                    finished = _normal_frame(normal, colour, levels)
        except ValueError as error:
            raise StageFailure(f"{clip}/{direction} frame {index}: can't quantise the normal pass: {error}") from None
        except OSError:
            raise StageFailure(f"{source} has no normal pass for {clip}/{direction} frame {index}; "
                               f"run {source} again") from None
        if spare:  # an effect with no outline: the cell `fit` left 1 px around it goes
            colour, finished = colour[1:-1, 1:-1], finished[1:-1, 1:-1]
        for target, image in ((run.output_dir / name, colour), (run.output_dir / _normal_name(name), finished)):
            target.parent.mkdir(parents=True, exist_ok=True)
            write_rgba(target, image)
    if spare:
        _trim_render(run.upstream["palette"] / RENDER_FILE, run.output_dir / RENDER_FILE)
    else:
        shutil.copyfile(run.upstream["palette"] / RENDER_FILE, run.output_dir / RENDER_FILE)
    drawn = {"schema_version": FINISH_SCHEMA_VERSION, "normal_levels": levels,
             **({} if mode == "pass" else {"normals": mode}),
             "outline": None if outline is None else {"colour": outline[0], "rgb": list(outline[1]), "placement": placement},
             **({} if eyes is None else {"eyes": eyes.drawn()}),
             **({} if lines is None else {"inner_lines": lines.drawn()})}
    (run.output_dir / FINISH_FILE).write_text(json.dumps(drawn, indent=2) + "\n", encoding="utf-8")


def _read_labels(path: Path) -> np.ndarray:
    """A material frame: mode L, each pixel's material index."""
    from PIL import Image

    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.uint8).copy()


def _read_depth(path: Path) -> np.ndarray:
    """A depth frame: 16 bit gray, as `render` wrote it."""
    from PIL import Image

    with Image.open(path) as image:
        return np.asarray(image, dtype=np.float64).copy()


def _vanishing_parts(run: StageRun, source: str, document: dict[str, Any], frames: list[SheetFrame],
                     read: dict[Path, np.ndarray] | None = None) -> list[Finding]:
    """`sheet.part_vanishes` (ticket 0159): each material's pixels per finished frame, counted where the final colour frame is
    opaque, from the material pass `render` wrote. Nothing when the pass isn't there to read."""
    names = {int(m["index"]): str(m["name"]) for m in document.get("materials", [])}
    render = run.upstream.get(source)
    if not names or render is None:
        return []
    if _eyes_mode(run) != "render":  # the stamped eyes are not the render's: its eye materials have nothing to vanish from
        names = {index: name for index, name in names.items() if name not in document.get("eyes", [])}
    watch = [w.strip() for w in str(run.params.get("watch_parts", "")).split(",") if w.strip()]
    by_name = {(f.clip, f.direction, f.index): f for f in frames}
    counted: list[PartCounts] = []
    for entry in document["clips"]:
        for direction, listed in entry["directions"].items():
            for frame in listed:
                found = by_name.get((entry["name"], direction, int(frame["index"])))
                path = render / str(frame["files"].get("material", ""))
                if found is None or not path.is_file():
                    continue
                labels = _read_labels(path)
                if read is not None and direction in FRONT_VIEWS:
                    read[path] = labels  # `_covered_eyes` reads the front views' material frames too
                if labels.shape != found.image.shape[:2]:
                    continue
                inside = labels[found.image[..., 3] > 0]
                counted.append(PartCounts(entry["name"], direction, int(frame["index"]),
                                          {name: int((inside == index).sum()) for index, name in sorted(names.items())}))
    findings = check_part_vanishes(counted, watch, int(run.params.get("part_min_pixels", 1)))
    for finding in findings:
        finding.position = Position(asset=run.asset_id, stage="finish", field=finding.position.field if finding.position else None)
    return findings


FRONT_VIEWS = ("s", "sw", "se")
FACING_CAMERA = 0.0  # an eye whose normal's z (toward the camera) is above this faces it; the stamp's own limit (`ops.eyes`)


def _covered_eyes(run: StageRun, source: str, document: dict[str, Any],
                  read: dict[Path, np.ndarray] | None = None) -> list[Finding]:
    """`sheet.eyes_covered` (ticket 0225): per frame of the front views, whether the eyes that face the camera are all behind
    another material in the render's material pass. Nothing when render followed no eyes."""
    render = run.upstream.get(source)
    names = [str(n) for n in document.get("eyes", [])]
    by_index = {int(m["index"]): str(m["name"]) for m in document.get("materials", [])}
    eye_labels = [i for i, n in by_index.items() if n in names]
    if render is None or not eye_labels:
        return []
    frames: list[EyeCover] = []
    for entry in document["clips"]:
        for direction in FRONT_VIEWS:
            for frame in entry["directions"].get(direction, []):
                path = render / str(frame["files"].get("material", ""))
                facing = [e for e in frame.get("eyes", []) if float(e["normal"][2]) > FACING_CAMERA]
                if not facing or not path.is_file():
                    continue
                labels = read.get(path) if read is not None else None
                if labels is None:
                    labels = _read_labels(path)
                covers = [_covered_by(labels, e, eye_labels) for e in facing]
                hidden = all(c is not None for c in covers)
                found = [by_index.get(c, "") for c in covers if c is not None]
                by = max(sorted(set(found)), key=found.count) if hidden and found else None
                frames.append(EyeCover(str(entry["name"]), direction, int(frame["index"]), hidden, by))
    findings = check_eyes_covered(frames)
    for finding in findings:
        finding.position = Position(asset=run.asset_id, stage="finish", field=finding.position.field if finding.position else None)
    return findings


def _check_finish(run: StageRun, source: str) -> list[Finding]:
    """`normal.size_mismatch` on every frame, and `palette.off_palette` on the colour frames against the Project palette."""
    out = run.output_dir
    try:
        document = json.loads((out / RENDER_FILE).read_text(encoding="utf-8"))
        palette = palette_rgb(run)
    except (OSError, ValueError, StageFailure):
        return []  # nothing built to check
    fix = f"kiripix run {run.asset_id} finish --force"
    frames: list[SheetFrame] = []
    findings: list[Finding] = []
    for clip, direction, index, name in _colour_files(document):
        colour_path, normal_path = out / name, out / _normal_name(name)
        if not colour_path.is_file() or not normal_path.is_file():
            missing = name if not colour_path.is_file() else _normal_name(name)
            findings.append(Finding(code="normal.size_mismatch", message=f"{missing} ({clip}, {direction}, frame {index}) is "
                                    f"missing", position=Position(asset=run.asset_id, stage="finish", file=missing), fix=fix))
            continue
        colour = read_rgba(colour_path)
        frames.append(SheetFrame(clip, direction, index, colour, (0, 0), read_rgba(normal_path)))
        findings += check_conformance(conformance(colour, palette), name, fix=fix)
    findings += check_normal_size(frames, fix)
    labels_read: dict[Path, np.ndarray] = {}
    findings += _vanishing_parts(run, source, document, frames, labels_read)
    findings += _covered_eyes(run, source, document, labels_read)
    for finding in findings:
        if finding.position is None:
            finding.position = Position()
        finding.position.asset, finding.position.stage = run.asset_id, "finish"
    return findings


def finish_stage(frames: str = "render") -> tuple[StageFunction, CheckFunction]:
    """The Stage's `run` and `check` for a Recipe whose frame list, normal frames and material frames are in the Stage named
    `frames` (the character's `render`, a sprite's `fit`; ticket 0176). The Stage must list it and `palette` upstream."""
    return (lambda run: _run_finish(run, frames)), (lambda run: _check_finish(run, frames))


run_character_finish, check_character_finish = finish_stage("render")
