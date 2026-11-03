"""Preview PNGs (spec §10.5): a Stage's image at integer zoom, with the Masks tinted over it on request.

Written to `.kiripix/previews/`, a cache that deleting loses nothing from. Nothing here takes a lock or records anything.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from kiripix.checks import Position
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba, save_png
from kiripix.core.project import Project
from kiripix.ops.preview import tint_masks
from kiripix.ops.resample import upscale

MASKS_STAGE = "masks"  # the Stage whose output holds one 1-bit PNG per Mask, named after it


@dataclass(frozen=True)
class Preview:
    stage: str
    path: Path
    width: int
    height: int
    masks: list[str]


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
        found[path.stem] = rgba[..., 0] > 127
    return found


def write_preview(project: Project, asset: Asset, cache: HashCache, stage: str | None, overlay: str | None,
                  factor: int) -> Preview:
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
    masks = _masks(graph, image.shape) if overlay == "masks" else {}
    if masks:
        image = tint_masks(image, masks)
    image = upscale(image, factor)
    suffix = ".masks" if overlay == "masks" else ""
    path = project.state_dir / "previews" / f"{asset.id}.{spec.name}{suffix}.x{factor}.png"
    save_png(path, image)
    return Preview(spec.name, path, image.shape[1], image.shape[0], sorted(masks))
