"""The character's `palette` Stage (spec §6.3, ADR 0004, tickets 0110 and 0150).

It means what a room's `palette` means (a strict OKLab mapping, optional ordered dithering, orphan cleanup), with one
choice on top: the character shares one subset of the Project palette across every frame of every clip and direction,
chosen by `palette_subset`, so a colour never flickers between frames. Only the colour pass is mapped. The normal, depth
and mask passes stay in `render`'s folder, untouched; `render.json` is copied here, so the frame list goes on to `finish`.

With `parts` (the swappable parts, each a material of `render.json` or several joined by `+`) each part owns a ramp: palette
colours of its own, dark to light, which no other part, fixed material or ramp shares, so the game can recolour one part
without touching another. `colors` then counts only the fixed subset, the materials in no part, and every pixel is mapped by
the material pass onto its own part's ramp. A part's name is its key everywhere, never its position.

Output in `work/palette/`: `color/<clip>/<dir>/<NNN>.png` (as in `render`), `palette.json` and `render.json`.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
    from PIL import Image
else:
    np = lazy_module("numpy")
    Image = lazy_module("PIL.Image")

from kiripix.checks import Finding, Position, check_ramp_shared
from kiripix.ops import (
    conformance,
    palette_subset,
    part_ramps,
    quantize,
    quantize_by_part,
    remove_orphans,
    remove_orphans_by_part,
)
from kiripix.recipes.base import StageFailure, StageRun
from kiripix.recipes.common import BAYER, palette_rgb, read_rgba, write_rgba

PALETTE_SCHEMA_VERSION = 2  # 2: `parts` (each part's name, materials, indexes and RGB, dark to light); empty with no `parts`
RENDER_FILE = "render.json"
PALETTE_FILE = "palette.json"


def _render(run: StageRun) -> dict[str, Any]:
    path = run.upstream["render"] / RENDER_FILE
    try:
        document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure("render has no render.json; run it again") from None
    return document


def _colour_files(document: dict[str, Any]) -> list[tuple[str, str, int, str]]:
    """Every colour frame, as (clip, direction, index, file relative to the pass folder's parent)."""
    found = []
    for entry in document["clips"]:
        for direction, frames in entry["directions"].items():
            for frame in frames:
                found.append((entry["name"], direction, int(frame["index"]), str(frame["files"]["color"])))
    return found


def _material_files(document: dict[str, Any]) -> list[str]:
    """Every material frame, in the order of `_colour_files`."""
    found = []
    for entry in document["clips"]:
        for frames in entry["directions"].values():
            for frame in frames:
                found.append(str(frame["files"].get("material", "")))
    return found


def _indexes(subset: np.ndarray, palette: np.ndarray, taken: list[int] | None = None) -> list[int]:
    """The Project palette's index of each subset colour (the first, when the palette repeats a colour). `taken` holds the
    indexes already given to other colours, and grows with these."""
    taken = [] if taken is None else taken
    found: list[int] = []
    for colour in subset:
        matches = np.nonzero((palette == colour).all(axis=1))[0]
        free = [int(i) for i in matches if int(i) not in taken]
        if not free:
            raise StageFailure(f"the palette subset holds {tuple(int(c) for c in colour)}, which the Project palette "
                               f"doesn't hold {'that many times' if len(matches) else 'at all'}",
                               code="palette.subset_unknown")
        taken.append(free[0])
        found.append(free[0])
    return found


@dataclass(frozen=True)
class PartSpec:
    """One swappable part as `parts` names it: its name (the key everywhere), its materials and its ramp length."""

    name: str
    materials: list[str]
    steps: int


def parse_parts(text: str, materials: list[str], bands: int, asset_id: str) -> list[PartSpec]:
    """`skin,hair,jacket+hood,jeans:4` as parts. Each part is one material or several joined by `+`; `:n` sets its ramp length
    (`bands` when unset). A part is named as written, without its length. StageFailure when a name is no material of the
    render, a material is in two parts, a part is named twice, or a length isn't a whole number from 1."""
    shown = ",".join(materials)
    fix = f"kiripix set {asset_id} palette parts={shown}"
    parts: list[PartSpec] = []
    owner: dict[str, str] = {}
    for token in (t.strip() for t in text.split(",")):
        if not token:
            continue
        name, colon, length = token.partition(":")
        name = name.strip()
        steps = bands
        if colon:
            if not length.strip().isdigit() or int(length) < 1:
                raise StageFailure(f"the ramp length of part {name!r} is {length.strip()!r}, not a whole number from 1",
                                   code="palette.parts_invalid", fix=fix)
            steps = int(length)
        names = [m.strip() for m in name.split("+")]
        unknown = [m for m in names if m not in materials]
        if unknown or not all(names):
            raise StageFailure(f"part {name!r} names {', '.join(repr(m) for m in unknown) or 'no material'}, which "
                               f"render's materials don't include; they are: {shown}", code="palette.part_unknown", fix=fix)
        if any(p.name == name for p in parts):
            raise StageFailure(f"part {name!r} is named twice", code="palette.parts_invalid", fix=fix)
        for material in names:
            if material in owner:
                raise StageFailure(f"material {material!r} is in two parts, {owner[material]!r} and {name!r}",
                                   code="palette.parts_invalid", fix=fix)
            owner[material] = name
        parts.append(PartSpec(name, names, steps))
    return parts


def read_labels(path: Path) -> np.ndarray:
    """A material frame: mode L, each pixel the index of its material (0 is the background)."""
    with Image.open(path) as image:
        return np.asarray(image.convert("L"), dtype=np.uint8).copy()


def _fixed_only(frame: np.ndarray, label: np.ndarray, claimed: list[int]) -> np.ndarray:
    """The frame with the pixels of the parts' materials made transparent, so only the fixed ones count."""
    out = frame.copy()
    out[np.isin(label, np.array(claimed, dtype=np.int64)), 3] = 0
    return out


def _hex(rgb: np.ndarray) -> str:
    return "#%02x%02x%02x" % tuple(int(c) for c in rgb)


def run_character_palette(run: StageRun) -> None:
    render = run.upstream["render"]
    document = _render(run)
    files = _colour_files(document)
    palette = palette_rgb(run)
    count = int(run.params["colors"])
    materials = {str(m["name"]): int(m["index"]) for m in document.get("materials", [])}
    specs = parse_parts(str(run.params.get("parts", "")), list(materials), int(document.get("bands", 3)), run.asset_id)
    parts = {s.name: [materials[m] for m in s.materials] for s in specs}
    claimed = sorted(i for indexes in parts.values() for i in indexes)
    frames: list[np.ndarray] = []
    labels: list[np.ndarray] = []
    label_files = _material_files(document) if specs else []
    for number, (_clip, _direction, _index, name) in enumerate(files):
        run.check_cancel()
        run.progress(number, len(files) * 2, "reading frames")
        frames.append(read_rgba(render / name))
        if specs:
            try:
                labels.append(read_labels(render / label_files[number]))
            except OSError:
                raise StageFailure(f"render has no material pass for {name}; run it again", code="palette.part_unknown",
                                   fix=f"kiripix run {run.asset_id} render --force") from None
    run.check_cancel()
    try:
        if specs:
            counted = [_fixed_only(f, lab, claimed) for f, lab in zip(frames, labels, strict=True)]
            has_fixed = any(bool((c[..., 3] == 255).any()) for c in counted)
            # `colors` is a ceiling: the ramps take their colours out of the same palette, so the fixed ones leave them room
            room = len(palette) - sum(s.steps for s in specs)
            if has_fixed and room < 1:
                raise StageFailure(f"the parts' ramps ask for {sum(s.steps for s in specs)} colours, and the palette has "
                                   f"{len(palette)}, so none is left for the materials in no part", code="palette.ramp_unavailable",
                                   owner_action="Add colours to the Project palette, shorten the ramps (parts such as skin:2), "
                                                "or name more materials as parts.")
            subset = (palette_subset(counted, palette, min(count, room)) if has_fixed
                      else np.zeros((0, 3), dtype=np.uint8))
        else:
            subset = palette_subset(frames, palette, count)
    except ValueError as error:
        raise StageFailure(f"can't choose the character's colours: {error}") from None
    ramps: dict[str, np.ndarray] = {}
    if specs:
        try:
            ramps = part_ramps(frames, labels, parts, palette, {s.name: s.steps for s in specs}, subset)
        except ValueError as error:
            raise StageFailure(f"can't choose the part ramps: {error}; fewer fixed colours leave more for the ramps",
                               code="palette.ramp_unavailable",
                               fix=f"kiripix set {run.asset_id} palette colors={max(1, count - 1)}") from None
    dither, strength, orphans = BAYER[str(run.params["dither"])], float(run.params["strength"]), int(run.params["orphan_size"])
    for number, ((clip, direction, index, name), frame) in enumerate(zip(files, frames, strict=True)):
        run.check_cancel()
        run.progress(len(files) + number, len(files) * 2, f"mapping {clip}/{direction}/{index:03d}")
        try:
            if specs:
                mapped = quantize_by_part(frame, labels[number], parts, ramps, subset, dither, strength)
                cleaned = remove_orphans_by_part(mapped, labels[number], parts, orphans)
            else:
                cleaned = remove_orphans(quantize(frame, subset, dither, strength), orphans)
        except ValueError as error:
            raise StageFailure(f"{clip}/{direction} frame {index} can't be mapped: {error}") from None
        target = run.output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        write_rgba(target, cleaned)
    shutil.copyfile(render / RENDER_FILE, run.output_dir / RENDER_FILE)
    taken: list[int] = []
    colours = [{"index": i, "rgb": [int(c) for c in rgb], "hex": _hex(rgb)}
               for i, rgb in zip(_indexes(subset, palette, taken), subset, strict=True)]
    described = [{"name": s.name, "materials": s.materials, "indexes": _indexes(ramps[s.name], palette, taken),
                  "rgb": [[int(c) for c in rgb] for rgb in ramps[s.name]], "hex": [_hex(rgb) for rgb in ramps[s.name]]}
                 for s in specs]
    (run.output_dir / PALETTE_FILE).write_text(
        json.dumps({"schema_version": PALETTE_SCHEMA_VERSION, "colors": colours, "parts": described}, indent=2) + "\n",
        encoding="utf-8")


def check_character_palette(run: StageRun) -> list[Finding]:
    """`palette.off_palette` on every colour frame, against the character's own colours (the fixed subset and every ramp), and
    `palette.ramp_shared` when a ramp's colour is in two ramps or in a pixel of another part; a finding names the frame."""
    out = run.output_dir
    try:
        document = json.loads((out / PALETTE_FILE).read_text(encoding="utf-8"))
        chosen = document["colors"]
        described = document.get("parts", [])
        render = json.loads((out / RENDER_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return []  # nothing built to check
    colours = [c["rgb"] for c in chosen] + [rgb for part in described for rgb in part["rgb"]]
    subset = np.array(colours, dtype=np.uint8).reshape(-1, 3)
    materials = {str(m["name"]): int(m["index"]) for m in render.get("materials", [])}
    parts = {p["name"]: [materials[m] for m in p["materials"] if m in materials] for p in described}
    ramps = {p["name"]: np.array(p["rgb"], dtype=np.uint8).reshape(-1, 3) for p in described}
    label_files = _material_files(render)
    fix = f"kiripix run {run.asset_id} palette --force"
    findings = []
    shared: set[str] = set()
    for number, (clip, direction, index, name) in enumerate(_colour_files(render)):
        path = out / name
        if not path.is_file():
            findings.append(Finding(code="palette.off_palette", message=f"{name} ({clip}, {direction}, frame {index}) is "
                                    f"missing", position=Position(asset=run.asset_id, stage="palette", file=name), fix=fix))
            continue
        image = read_rgba(path)
        report = conformance(image, subset)
        if report.off_palette:
            x, y = report.first_off_palette[0]
            findings.append(Finding(
                code="palette.off_palette",
                message=f"clip {clip}, direction {direction}, frame {index} has {report.off_palette} pixels off the "
                        f"character's palette, the first at ({x}, {y})",
                position=Position(asset=run.asset_id, stage="palette", file=name, x=x, y=y), fix=fix))
        if not ramps:
            continue
        try:
            label = read_labels(run.upstream["render"] / label_files[number])
        except OSError:
            continue  # `render` has nothing to compare with: its own Stage says so
        if label.shape != image.shape[:2]:
            continue
        for found in check_ramp_shared(image, label, parts, ramps, name, fix):
            if found.message in shared:  # two ramps with a colour in common are one finding, not one per frame
                continue
            shared.add(found.message)
            found.position = Position(asset=run.asset_id, stage="palette", file=name,
                                      x=found.position.x if found.position else None,
                                      y=found.position.y if found.position else None)
            findings.append(found)
    return findings
