"""Preview PNGs (spec §10.5): a Stage's image at integer zoom, with the Masks tinted over it on request.

Written to `.kiripix/previews/`, a cache that deleting loses nothing from. Nothing here takes a lock or records anything.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba, save_png
from kiripix.core.project import Project
from kiripix.ops.preview import draw_grid, tint_mask, tint_masks
from kiripix.ops.resample import upscale

MASKS_STAGE = "masks"  # the Stage whose output holds one 1-bit PNG per Mask, named after it


@dataclass(frozen=True)
class Preview:
    stage: str
    path: Path
    width: int
    height: int
    masks: list[str]
    region: tuple[int, int, int, int] | None = None  # x, y, width, height in target pixels
    grid: int | None = None
    overlay: str | None = None
    findings: tuple[Finding, ...] = ()


@dataclass(frozen=True)
class Derived:
    """An overlay made from a Stage's output, rather than the Masks."""

    stage: str
    file: str
    tint: tuple[int, int, int]


DERIVED = {"walkable": Derived("place", "walkable.png", (0, 220, 60)),
           "reachable": Derived("reach", "reachable.png", (0, 200, 255))}


def parse_region(text: str, asset: str, width: int, height: int) -> tuple[int, int, int, int]:
    """`x,y,width,height` in target pixels, which must lie inside the `width` x `height` image."""
    fix = f"kiripix preview {asset} --region 0,0,{width},{height}"
    try:
        parts = [int(part) for part in text.split(",")]
    except ValueError:
        parts = []
    if len(parts) != 4 or parts[0] < 0 or parts[1] < 0 or parts[2] < 1 or parts[3] < 1:
        raise fail("preview.region_invalid", f"a region is x,y,width,height in whole target pixels, with a size of at "
                   f"least 1, not '{text}'", fix=fix, position=Position(asset=asset))
    x, y, w, h = parts
    if x + w > width or y + h > height:
        raise fail("preview.region_outside", f"the region {text} is not inside the image, which is {width}x{height}",
                   fix=fix, position=Position(asset=asset))
    return x, y, w, h


def _derived(graph: AssetGraph, overlay: str,
             shape: tuple[int, ...]) -> tuple[npt.NDArray[np.bool_], list[Finding]]:
    """The overlay's ground, and a warning when the Stage it comes from isn't `done`: it is drawn as built."""
    asset = graph.asset.id
    derived = DERIVED[overlay]
    stage = derived.stage
    spec = graph.kind.stage(stage)
    if spec is None or graph.built_hash(spec) is None:
        raise fail("preview.not_built", f"{asset} {stage} has no output yet, and the {overlay} overlay reads it",
                   fix=f"kiripix run {asset} {stage}", position=Position(asset=asset, stage=stage))
    path = graph.output_dir(spec) / derived.file
    rgba = load_rgba(path, graph.project.relative(path))
    if rgba.shape[:2] != shape[:2]:
        raise fail("preview.overlay_size_mismatch",
                   f"{derived.file} is {rgba.shape[1]}x{rgba.shape[0]} but the image is {shape[1]}x{shape[0]}",
                   fix=f"kiripix run {asset} {stage} --force", position=Position(asset=asset, stage=stage))
    mask: npt.NDArray[np.bool_] = rgba[..., 0] > 127
    status = graph.state(stage).status
    if status == "done":
        return mask, []
    return mask, [Finding(code="preview.overlay_out_of_date", severity="warning",
                          message=f"{asset} {stage} is {status}, so the {overlay} overlay shows its last build",
                          position=Position(asset=asset, stage=stage), fix=f"kiripix run {asset} {stage}")]


def _masks(graph: AssetGraph, shape: tuple[int, ...]) -> dict[str, npt.NDArray[np.bool_]]:
    asset = graph.asset.id
    spec = graph.kind.stage(MASKS_STAGE)
    if spec is None or graph.built_hash(spec) is None:
        raise fail("preview.no_masks", f"{asset} has no built Masks to overlay",
                   fix=f"kiripix run {asset}", position=Position(asset=asset, stage=MASKS_STAGE))
    found = {}
    for path in sorted(graph.output_dir(spec).glob("*.png")):
        rgba = load_rgba(path, graph.project.relative(path))
        if rgba.shape[:2] != shape[:2]:
            raise fail("preview.masks_size_mismatch",
                       f"the Mask {path.stem} is {rgba.shape[1]}x{rgba.shape[0]} but the image is "
                       f"{shape[1]}x{shape[0]}",
                       fix=f"kiripix run {asset} {MASKS_STAGE} --force",
                       position=Position(asset=asset, stage=MASKS_STAGE, file=graph.project.relative(path)))
        mask = rgba[..., 0] > 127
        if mask.any():
            found[path.stem] = mask
    return found


def write_preview(project: Project, asset: Asset, cache: HashCache, stage: str | None, overlay: str | None,
                  factor: int, region: str | None = None, grid: int | None = None) -> Preview:
    """Write the preview of `stage` (default: the last `done` Stage with an image) and say where it is."""
    graph = AssetGraph(project, asset, cache)
    if stage is None:
        candidates = [s for s in graph.kind.stages if s.image is not None and graph.state(s.name).status == "done"]
        if not candidates:
            raise fail("preview.nothing_built", f"{asset.id} has no done Stage with an image to preview",
                       fix=f"kiripix next {asset.id}", position=Position(asset=asset.id))
        spec = candidates[-1]
    else:
        spec = graph.spec(stage)
        if spec.image is None:
            names = ", ".join(s.name for s in graph.kind.stages if s.image is not None)
            raise fail("preview.no_image", f"the Stage '{stage}' has no image; the Stages with one are {names}",
                       fix=f"kiripix describe {asset.kind}", position=Position(asset=asset.id, stage=stage))
        if graph.built_hash(spec) is None:
            raise fail("preview.not_built", f"{asset.id} {stage} has no output yet",
                       fix=f"kiripix run {asset.id} {stage}", position=Position(asset=asset.id, stage=stage))
    assert spec.image is not None
    image_path = graph.output_dir(spec) / spec.image
    image = load_rgba(image_path, project.relative(image_path))
    box = parse_region(region, asset.id, image.shape[1], image.shape[0]) if region is not None else None
    masks = _masks(graph, image.shape) if overlay == "masks" else {}
    if masks:
        image = tint_masks(image, masks)
    findings: list[Finding] = []
    if overlay in DERIVED:
        ground, findings = _derived(graph, overlay, image.shape)
        image = tint_mask(image, ground, DERIVED[overlay].tint)
    origin = (0, 0)
    if box is not None:
        x, y, w, h = box
        image = image[y:y + h, x:x + w]
        origin = (x, y)
    image = upscale(image, factor)
    if grid is not None:
        image = draw_grid(image, grid, factor, origin)
    suffix = f".{overlay}" if overlay is not None else ""
    suffix += f".r{'_'.join(map(str, box))}" if box is not None else ""
    suffix += f".g{grid}" if grid is not None else ""
    path = project.state_dir / "previews" / f"{asset.id}.{spec.name}{suffix}.x{factor}.png"
    save_png(path, image)
    return Preview(spec.name, path, image.shape[1], image.shape[0], sorted(masks), box, grid, overlay, tuple(findings))
