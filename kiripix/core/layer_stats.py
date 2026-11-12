"""The `layer-stats` Probe's work (spec §10.1, ticket 0084): each Layer's numbers and its y-sort line, from the `layers`
output as built (one awaiting review too) and the sorting Stage's current Decisions. Nothing is recorded, no status
changes and no lock is taken. What is specific to a Recipe comes from the Stage's `LayerStatsHooks`."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from kiripix.ops.lazy import lazy_module
if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

from kiripix.checks import Position
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba
from kiripix.core.project import Project
from kiripix.ops import connected_regions, enclosed_holes
from kiripix.recipes.base import SortPosition

SPECK = 50  # a piece under this many pixels is listed, with its pixels, so a speck can be trimmed from the answer alone
LARGEST = 5  # how many of the biggest pieces' sizes are listed


def layer_stats(project: Project, asset: Asset) -> dict[str, Any]:
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    spec, hooks = graph.stage_with(lambda s: s.layer_stats, "lifts Layers")
    folder = graph.output_dir(spec)
    layers, removed = hooks.read(folder, asset.id)
    status = graph.state(spec.name).status
    decisions = graph.replay(hooks.sort_stage).current
    sorts = {position.layer: position for position in hooks.sort(decisions, [layer for layer, _ in layers], removed)}
    answers = []
    for layer, path in layers:
        if not path.is_file():
            raise fail("probe.not_ready", f"{layer} has no file in the built {spec.name} output",
                       fix=f"kiripix run {asset.id} {spec.name} --force",
                       position=Position(asset=asset.id, stage=spec.name))
        alpha = load_rgba(path, project.relative(path))[..., 3]
        answers.append({"id": layer, **_numbers(alpha), "sort": _sort(sorts[layer]),
                        "ysort": _ysort(layer, alpha, hooks.ysort)})
    return {"stage": spec.name, "status": status, "awaiting_review": status == "needs-review", "layers": answers}


def _box(rows: np.ndarray, columns: np.ndarray) -> dict[str, int]:
    left, top = int(columns.min()), int(rows.min())
    return {"x": left, "y": top, "width": int(columns.max()) - left + 1, "height": int(rows.max()) - top + 1}


def piece_numbers(present: np.ndarray) -> dict[str, Any]:
    """The 8-connected pieces of a boolean image: their count, the sizes of the biggest, and each speck with its pixels."""
    pieces = connected_regions(present, eight=True)
    sizes = sorted((len(piece) for piece in pieces), reverse=True)
    specks = [{"pixels": len(piece), "at": [[int(x), int(y)] for y, x in piece.tolist()]}
              for piece in pieces if len(piece) < SPECK]
    return {"count": len(pieces), "largest": sizes[:LARGEST], "small": specks}


def _numbers(alpha: np.ndarray) -> dict[str, Any]:
    present = alpha > 0
    rows, columns = np.nonzero(present)
    return {
        "pixels": int(present.sum()),
        "box": _box(rows, columns) if rows.size else None,
        "pieces": piece_numbers(present),
        "holes": int(enclosed_holes(present).sum()),
        "partial": int(((alpha > 0) & (alpha < 255)).sum()),
    }


def _sort(position: SortPosition) -> dict[str, Any]:
    if position.above:
        return {"state": "above"}
    if position.y is None:
        return {"state": "none"}
    return {"state": "line", "marker": position.marker, "y": position.y, "slope": position.slope}


def _ysort(layer: str, alpha: np.ndarray,
          line: Callable[[str, int, int, int], dict[str, Any]]) -> dict[str, Any] | None:
    rows, columns = np.nonzero(alpha > 0)
    if not rows.size:
        return None
    return line(layer, int(columns.min()), int(columns.max()), int(rows.max()))
