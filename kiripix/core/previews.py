"""Preview PNGs (spec §10.5): a Stage's image at integer zoom, with the Masks tinted over it on request.

Written to `.kiripix/previews/`, a cache that deleting loses nothing from. Nothing here takes a lock or records anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typing import TYPE_CHECKING
from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")
if TYPE_CHECKING:
    import numpy.typing as npt
else:
    npt = lazy_module("numpy.typing")

from kiripix.checks import Finding, Position
import json

from kiripix.core.assets import Asset, load_asset
from kiripix.core.cast import Figure, NothingToDraw, cast_sheet
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba, save_png
from kiripix.core.project import Project
from kiripix.recipes.base import StageSpec
from kiripix.ops.normals import lit
from kiripix.ops.preview import TINTS, brighten, draw_grid, tint_mask, tint_masks
from kiripix.ops.resample import upscale

NPC_FILE = "npc.json"  # what an NPC's `choose` writes, which its figure preview draws (ticket 0356)
MASKS_STAGE = "masks"  # the Stage whose output holds one 1-bit PNG per Mask, named after it
NORMALS_STAGE = "normals"  # the Stage whose `normal.png` the `lit` overlay lights the image with (ticket 0341)
NORMAL_FILE = "normal.png"


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
    layers: tuple[tuple[str, str], ...] = ()  # each tinted Layer's ID and its colour, as #rrggbb
    awaiting_review: bool | None = None  # for the layers overlay: whether the `layers` build awaits the owner


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


def _normals(graph: AssetGraph, shape: tuple[int, ...]) -> tuple[npt.NDArray[np.uint8], list[Finding]]:
    """The room's normal map for the `lit` overlay, and a warning when the Stage isn't `done`: it is used as built."""
    asset = graph.asset.id
    spec = graph.kind.stage(NORMALS_STAGE)
    if spec is None:
        raise fail("preview.no_normals", f"{asset} is a {graph.kind.name}, which has no normal map to light it with",
                   fix=f"kiripix describe {graph.kind.name}", position=Position(asset=asset))
    path = graph.output_dir(spec) / NORMAL_FILE
    if graph.built_hash(spec) is None or not path.is_file():
        raise fail("preview.no_normals", f"{asset} has no normal map: turn the normals Stage on with mode=depth, then run it",
                   fix=f"kiripix set {asset} {NORMALS_STAGE} mode=depth", position=Position(asset=asset, stage=NORMALS_STAGE))
    rgba = load_rgba(path, graph.project.relative(path))
    if rgba.shape[:2] != shape[:2]:
        raise fail("preview.overlay_size_mismatch",
                   f"{NORMAL_FILE} is {rgba.shape[1]}x{rgba.shape[0]} but the image is {shape[1]}x{shape[0]}",
                   fix=f"kiripix run {asset} {NORMALS_STAGE} --force", position=Position(asset=asset, stage=NORMALS_STAGE))
    status = graph.state(NORMALS_STAGE).status
    if status == "done":
        return rgba, []
    return rgba, [Finding(code="preview.overlay_out_of_date", severity="warning",
                          message=f"{asset} {NORMALS_STAGE} is {status}, so the lit overlay shows its last build",
                          position=Position(asset=asset, stage=NORMALS_STAGE), fix=f"kiripix run {asset} {NORMALS_STAGE}")]


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


def _layers(graph: AssetGraph, shape: tuple[int, ...],
            only: str | None) -> tuple[list[tuple[str, tuple[int, int, int], npt.NDArray[np.bool_]]], bool, list[Finding]]:
    """The Layers to tint as (ID, colour, alpha), from the `layers` output as built (one awaiting review too).

    A Layer's colour comes from its place among all the Layers, so `only` keeps the colour it has in the whole view.
    """
    asset = graph.asset.id
    spec, hooks = graph.stage_with(lambda s: s.layer_stats, "lifts Layers", code="preview.no_layers",
                                   position=Position(asset=asset))
    found, _ = hooks.read(graph.output_dir(spec), asset)
    if not found:
        raise fail("preview.no_layers", f"{asset} has no built Layers to overlay",
                   fix=f"kiripix run {asset} {spec.name}", position=Position(asset=asset, stage=spec.name))
    if only is not None and only not in [layer for layer, _ in found]:
        names = ", ".join(layer for layer, _ in found)
        raise fail("input.invalid", f"'{only}' is not a Layer of {asset}; the Layers are {names}",
                   fix=f"kiripix preview {asset} --overlay layers --layer {found[0][0]}",
                   position=Position(asset=asset, stage=spec.name))
    chosen = []
    for index, (layer, path) in enumerate(found):
        if only is not None and layer != only:
            continue
        rgba = load_rgba(path, graph.project.relative(path))
        if rgba.shape[:2] != shape[:2]:
            raise fail("preview.overlay_size_mismatch",
                       f"{path.name} is {rgba.shape[1]}x{rgba.shape[0]} but the image is {shape[1]}x{shape[0]}",
                       fix=f"kiripix run {asset} {spec.name} --force", position=Position(asset=asset, stage=spec.name))
        chosen.append((layer, TINTS[index % len(TINTS)], rgba[..., 3] > 0))
    awaiting = graph.state(spec.name).status == "needs-review"
    findings = []
    if awaiting:
        findings.append(Finding(
            code="preview.layers_awaiting_review", severity="warning",
            message=f"{asset} {spec.name} is awaiting review, so the layers overlay shows the build as it stands",
            position=Position(asset=asset, stage=spec.name),
            owner_action=f"Review {asset} {spec.name}, then accept it: kiripix accept {asset} {spec.name}"))
    return chosen, awaiting, findings


def npc_figure(project: Project, asset: Asset, path: Path, stage: str = "choose") -> Figure:
    """The figure an NPC's built `npc.json` names: its base with the Wearables over it in stack order, their orders and the
    colours swapped, titled with the NPC's ID. Used by the figure preview and by `cast-sheet --match` (ticket 0359)."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        base = load_asset(project, document["base"])
        worn = [load_asset(project, entry["id"]) for entry in document["wearables"]]
        orders = {str(entry["id"]): int(entry["order"]) for entry in document["wearables"]}
        colours = {str(part): [(int(c[0]), int(c[1]), int(c[2])) for c in choice["rgb"]]
                   for part, choice in document["colours"].items()}
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        raise fail("preview.not_built", f"{asset.id}'s {path.name} can't be read; build it again",
                   fix=f"kiripix run {asset.id} {stage} --force", position=Position(asset=asset.id, stage=stage)) from None
    return Figure((base, *worn), colours, orders, title=asset.id)


def _figure_preview(project: Project, asset: Asset, graph: AssetGraph, spec: StageSpec, cache: HashCache, factor: int,
                    overlay: str | None) -> Preview:
    """The preview of a Stage whose output names a figure (`StageSpec.preview_figure`, an NPC's `choose`): the base with its
    Wearables stacked and its colours swapped, one frame per direction of the base's idle, drawn by `cast-sheet`'s code."""
    name = spec.name
    if graph.built_hash(spec) is None:
        raise fail("preview.not_built", f"{asset.id} {name} has no output yet", fix=f"kiripix run {asset.id} {name}",
                   position=Position(asset=asset.id, stage=name))
    if overlay is not None:
        raise fail("input.invalid", f"the {name} preview of {asset.id} is a figure and has no overlays",
                   fix=f"kiripix preview {asset.id} --stage {name}", position=Position(asset=asset.id, stage=name))
    path = graph.output_dir(spec) / NPC_FILE
    figure = npc_figure(project, asset, path, name)
    base, worn, colours, orders = figure.assets[0], figure.assets[1:], figure.colours, figure.orders
    base_graph = AssetGraph(project, base, cache)
    try:
        sheet = json.loads((base_graph.output_dir(base_graph.spec("sheet")) / "sheet.json").read_text(encoding="utf-8"))
        clip = next((c for c in sheet["clips"] if c["name"] == "idle"), sheet["clips"][0])
        clips, directions = [str(clip["name"])], [str(d) for d in clip["directions"]]
    except (OSError, ValueError, KeyError, IndexError):
        raise fail("preview.not_built", f"{base.id} has no built sheet to draw {asset.id} from",
                   fix=f"kiripix run {base.id} sheet", position=Position(asset=base.id, stage="sheet")) from None
    try:
        made = cast_sheet(project, [Figure((base, *worn), colours, orders)], clips, directions, 1, factor)
    except NothingToDraw as nothing:
        raise fail("preview.not_built", f"nothing of {asset.id} could be drawn: " + "; ".join(f.message for f in nothing.findings),
                   fix=f"kiripix status {asset.id}", position=Position(asset=asset.id, stage=name)) from None
    return Preview(name, made.path, made.width, made.height, [], None, None, None, made.findings)


def write_preview(project: Project, asset: Asset, cache: HashCache, stage: str | None, overlay: str | None,
                  factor: int, region: str | None = None, grid: int | None = None, layer: str | None = None,
                  bright: float = 1.0) -> Preview:
    """Write the preview of `stage` (default: the last `done` Stage with an image) and say where it is."""
    graph = AssetGraph(project, asset, cache)
    figure = next((s for s in graph.kind.stages if s.preview_figure), None)
    if figure is not None and (stage == figure.name or (stage is None and not any(s.image for s in graph.kind.stages))):
        return _figure_preview(project, asset, graph, figure, cache, factor, overlay)
    if stage is None:
        candidates = [s for s in graph.kind.stages if s.image is not None and graph.state(s.name).status == "done"
                      and (graph.output_dir(s) / s.image).is_file()]  # a Stage that is off has no image
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
    if not image_path.is_file():
        raise fail("preview.no_image", f"the {spec.name} Stage of {asset.id} wrote no {spec.image}: it is off", fix=f"kiripix describe {asset.kind}",
                   position=Position(asset=asset.id, stage=spec.name))
    image = load_rgba(image_path, project.relative(image_path))
    if layer is not None and overlay != "layers":
        raise fail("input.invalid", "--layer needs --overlay layers", fix=f"kiripix preview {asset.id} --overlay layers "
                   f"--layer {layer}", position=Position(asset=asset.id))
    if bright <= 0:
        raise fail("input.invalid", f"--brighten must be above 0, not {bright:g}",
                   fix=f"kiripix preview {asset.id} --brighten 1", position=Position(asset=asset.id))
    box = parse_region(region, asset.id, image.shape[1], image.shape[0]) if region is not None else None
    findings: list[Finding] = []
    if overlay == "lit":
        normals, findings = _normals(graph, image.shape)
        image = lit(image, normals)
    image = brighten(image, bright)
    masks = _masks(graph, image.shape) if overlay == "masks" else {}
    if masks:
        image = tint_masks(image, masks)
    if overlay in DERIVED:
        ground, findings = _derived(graph, overlay, image.shape)
        image = tint_mask(image, ground, DERIVED[overlay].tint)
    tinted: list[tuple[str, str]] = []
    awaiting = None
    if overlay == "layers":
        chosen, awaiting, findings = _layers(graph, image.shape, layer)
        for name, colour, alpha in chosen:
            image = tint_mask(image, alpha, colour)
            tinted.append((name, "#%02x%02x%02x" % colour))
    origin = (0, 0)
    if box is not None:
        x, y, w, h = box
        image = image[y:y + h, x:x + w]
        origin = (x, y)
    image = upscale(image, factor)
    if grid is not None:
        image = draw_grid(image, grid, factor, origin)
    suffix = f".{overlay}" if overlay is not None else ""
    suffix += f".l{layer}" if layer is not None else ""
    suffix += f".b{bright:g}".replace(".", "_") if bright != 1 else ""
    suffix += f".r{'_'.join(map(str, box))}" if box is not None else ""
    suffix += f".g{grid}" if grid is not None else ""
    path = project.state_dir / "previews" / f"{asset.id}.{spec.name}{suffix}.x{factor}.png"
    save_png(path, image)
    return Preview(spec.name, path, image.shape[1], image.shape[0], sorted(masks), box, grid, overlay, tuple(findings),
                   tuple(tinted), awaiting)
