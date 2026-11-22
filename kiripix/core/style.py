"""Style references and the style Checks' wiring (ticket 0334, trial 0332, spec §4 and §10.5).

`[style] references` in `kiripix.toml` names Assets whose look is the Project's. For every other Asset whose Kind has style
Checks, `check` measures the Stage 0332 named (`STYLE_STAGES`) and runs `kiripix.checks.style` against the references' measures.
The measures are `kiripix.ops.style`. Nothing here writes: no cache is kept (a room's Plate takes tens of milliseconds, see
the ticket's Result).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any


from kiripix.checks import Finding, Position
from kiripix.checks.style import (
    OUTLINE_DENSITY_FLOOR,
    OUTLINE_KINDS,
    PIXEL_SCALE_GCD,
    PIXEL_SCALE_MIN_RUNS,
    STYLE_STAGES,
    check_outline_density,
    check_pixel_scale,
    check_style_measures,
)
from kiripix.core.assets import Asset, load_asset
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_palette, load_rgba
from kiripix.core.project import Project
from kiripix.ops import OutlineMeasure, ScaleMeasure, outline_density, pixel_scale
from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

FINISH_FILE = "finish.json"
_PLATE = {"room": "plate.png", "prop": "sprite.png"}  # a room's mapped Plate, not the composite with its Layers
__all__ = ["StyleMeasures", "measure", "probe_style", "reference_findings", "style_findings"]


@dataclass(frozen=True)
class StyleMeasures:
    """One Asset's measures, on its Stage's output as built."""

    asset: str
    kind: str
    stage: str
    outline: OutlineMeasure | None
    """None for a Kind with no outline measure (room, prop) and for a Wearable, whose `finish` draws none."""
    scale: ScaleMeasure
    outline_drawn: bool
    """Whether `finish` drew the outline (`finish.json`); False for a room and a prop."""


def _box(image: np.ndarray) -> np.ndarray:
    """The image cut to its opaque box (the image itself when nothing is opaque)."""
    ys, xs = np.nonzero(image[..., 3] > 0)
    if not len(ys):
        return image
    return image[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def _first(names: list[str], wanted: str) -> str:
    return wanted if wanted in names else names[0]


def _figure_frame(graph: AssetGraph, folder_name: str) -> tuple[np.ndarray, Any] | None:
    """`finish`'s colour frame of clip `idle` (else the first), direction `s` (else the first), frame 0, cut to its box."""
    spec = graph.spec(folder_name)
    folder = graph.output_dir(spec)
    colour = folder / "color"
    clips = sorted(p.name for p in colour.iterdir() if p.is_dir()) if colour.is_dir() else []
    if not clips:
        return None
    clip = colour / _first(clips, "idle")
    directions = sorted(p.name for p in clip.iterdir() if p.is_dir())
    if not directions:
        return None
    frames = sorted((clip / _first(directions, "s")).glob("*.png"))
    if not frames:
        return None
    try:
        drawn = json.loads((folder / FINISH_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        drawn = {}
    return _box(load_rgba(frames[0], str(frames[0].relative_to(graph.project.root)))), drawn


def _outline_rgb(graph: AssetGraph, drawn: Any) -> tuple[int, int, int] | None:
    """The outline colour: `finish.json`'s, else (outline off) the palette colour of `finish`'s `outline_colour`; None when
    `finish` has no such parameter (a Wearable's), so there is nothing to measure."""
    outline = drawn.get("outline") if isinstance(drawn, dict) else None
    if isinstance(outline, dict) and isinstance(outline.get("rgb"), list) and len(outline["rgb"]) == 3:
        r, g, b = (int(c) for c in outline["rgb"])
        return r, g, b
    params = graph.params(graph.spec("finish"))
    index = params.get("outline_colour")
    if not isinstance(index, int) or isinstance(index, bool):
        return None
    path = graph.palette_path()
    entries = load_palette(path, path.name).entries
    if not 0 <= index < len(entries):
        return None
    return entries[index].r, entries[index].g, entries[index].b


def measure(project: Project, asset: Asset, cache: HashCache) -> StyleMeasures | None:
    """The Asset's measures, or None when its Kind has no style Checks or the measured Stage has no output."""
    stage = STYLE_STAGES.get(asset.kind)
    if stage is None:
        return None
    graph = AssetGraph(project, asset, cache)
    spec = graph.spec(stage)
    if graph.built_hash(spec) is None:
        return None
    if stage == "finish":  # a figure: character, sprite or Wearable; only the first two have an outline to measure
        found = _figure_frame(graph, stage)
        if found is None:
            return None
        image, drawn = found
        rgb = _outline_rgb(graph, drawn) if asset.kind in OUTLINE_KINDS else None
        outline = outline_density(image, rgb) if rgb is not None else None
        outline_drawn = isinstance(drawn, dict) and isinstance(drawn.get("outline"), dict)
    else:
        path = graph.output_dir(spec) / _PLATE.get(asset.kind, "")
        if not path.is_file():
            return None
        image = _box(load_rgba(path, str(path.relative_to(project.root))))
        outline, outline_drawn = None, False
    return StyleMeasures(asset.id, asset.kind, stage, outline, pixel_scale(image), outline_drawn)


def _fix_outline(measures: StyleMeasures) -> str:
    if measures.outline_drawn:
        return f"kiripix set {measures.asset} finish placement=outside"
    return f"kiripix set {measures.asset} finish outline=true"


def _fix_scale(measures: StyleMeasures) -> tuple[str | None, str | None]:
    """The `fix` and the `owner_action` for a picture drawn too big: a sprite's `fit` can scale it down; anything else
    needs a new Source or Model at the Project's pixel size, which only the Owner can give."""
    if measures.kind == "sprite":
        return f"kiripix set {measures.asset} fit mode=downscale", None
    return None, (f"Give {measures.asset} a Source (or, for a figure, a render) at the Project's pixel size: every colour "
                  "run is a multiple of the same length, so it was drawn or scaled up.")


def _located(finding: Finding, measures: StyleMeasures) -> Finding:
    position = finding.position or Position()
    return finding.model_copy(update={"position": position.model_copy(update={
        "asset": measures.asset, "stage": position.stage or measures.stage})})


def _compare(measures: StyleMeasures, references: Mapping[str, StyleMeasures]) -> list[Finding]:
    """The style Checks of one Asset against the references' measures (the Asset itself is not among them)."""
    findings: list[Finding] = []
    if measures.outline is not None:
        outlines = {n: m.outline for n, m in references.items() if m.outline is not None}
        findings += check_outline_density(measures.asset, measures.outline, outlines, _fix_outline(measures))
    fix, owner_action = _fix_scale(measures)
    findings += check_pixel_scale(measures.asset, measures.scale, {n: m.scale for n, m in references.items()},
                                  fix, measures.stage, owner_action=owner_action)
    findings += check_style_measures(measures.asset, measures.outline, measures.scale, f"kiripix probe style {measures.asset}")
    return [_located(f, measures) for f in findings]


class References:
    """The Project's references and their measures, each measured once per call."""

    def __init__(self, project: Project, cache: HashCache) -> None:
        self.project, self.cache = project, cache
        self._measured: dict[str, StyleMeasures | None] = {}
        self.findings: list[Finding] = []
        self.ids = list(dict.fromkeys(project.settings.style.references))
        self._reported: set[str] = set()

    def measures(self, asset_id: str) -> StyleMeasures | None:
        if asset_id not in self._measured:
            try:
                self._measured[asset_id] = measure(self.project, load_asset(self.project, asset_id), self.cache)
            except KiripixError:
                self._measured[asset_id] = None
        return self._measured[asset_id]

    def built(self, left_out: str) -> dict[str, StyleMeasures]:
        """The references with measures, other than `left_out`. A reference that can't be measured is reported once, as
        `style.reference_unbuilt` (info), and left out of the range."""
        found: dict[str, StyleMeasures] = {}
        for reference in self.ids:
            got = self.measures(reference)
            if got is None:
                self._unbuilt(reference)
            elif reference != left_out:
                found[reference] = got
        return found

    def _unbuilt(self, reference: str) -> None:
        if reference in self._reported:
            return
        self._reported.add(reference)
        try:
            asset = load_asset(self.project, reference)
        except KiripixError:
            return  # `style.reference_unknown`, which `reference_findings` reports
        stage = STYLE_STAGES.get(asset.kind)
        if stage is None:
            return
        self.findings.append(Finding(
            code="style.reference_unbuilt", severity="info",
            message=f"the style reference {reference} has no built `{stage}` Stage, so it is left out of the range",
            position=Position(asset=reference, stage=stage), fix=f"kiripix run {reference} {stage}"))


def reference_findings(project: Project) -> list[Finding]:
    """`style.reference_unknown` for each entry of `[style] references` that names no Asset or an Asset of a Kind with no style
    Checks. A settings finding: `check --all` reports it, and `style-remove` takes the entry out."""
    found: list[Finding] = []
    for reference in dict.fromkeys(project.settings.style.references):
        try:
            asset = load_asset(project, reference)
        except KiripixError:
            why = "names no Asset"
        else:
            if asset.kind in STYLE_STAGES:
                continue
            why = f"is a {asset.kind}, which has no style Checks (they are for {', '.join(sorted(STYLE_STAGES))})"
        found.append(Finding(
            code="style.reference_unknown", severity="error",
            message=f"[style] references in kiripix.toml has '{reference}', which {why}",
            position=Position(file="kiripix.toml", field="style.references"),
            owner_action=f"Take it out with `kiripix style-remove {reference}` (the Owner's), or name an Asset of one of those Kinds."))
    return found


def style_findings(project: Project, cache: HashCache, judged: list[Asset], references: References | None = None) -> list[Finding]:
    """The style findings of `judged` against `[style] references`. With no references, or none left once the Asset itself is
    out, nothing runs and nothing is reported."""
    held = references or References(project, cache)
    if not held.ids:
        return []
    findings: list[Finding] = []
    for asset in judged:
        if asset.kind not in STYLE_STAGES:
            continue
        others = held.built(asset.id)
        if not others:
            continue
        try:
            mine = measure(project, asset, cache) if asset.id not in held.ids else held.measures(asset.id)
        except KiripixError as error:
            findings.extend(error.findings)
            continue
        if mine is not None:
            findings.extend(_compare(mine, others))
    return findings + held.findings


def _numbers(measures: StyleMeasures | None) -> dict[str, Any] | None:
    if measures is None:
        return None
    return {"outline_density": None if measures.outline is None else asdict(measures.outline),
            "pixel_scale": asdict(measures.scale)}


def _spread(values: Mapping[str, float], mine: float | None) -> dict[str, Any] | None:
    if not values:
        return None
    furthest = None if mine is None else min(values, key=lambda n: (-abs(values[n] - mine), n))
    return {"low": min(values.values()), "high": max(values.values()), "furthest": furthest}


def probe_style(project: Project, asset: Asset, cache: HashCache) -> dict[str, Any]:
    """What `kiripix probe style <id>` answers (the UI reads it): the Asset's measures, each reference's, the range and the
    findings `check` gives. `stage` is null for a Kind with no style Checks."""
    stage = STYLE_STAGES.get(asset.kind)
    holder = References(project, cache)
    mine = measure(project, asset, cache) if stage is not None else None
    rows: list[dict[str, Any]] = []
    others: dict[str, StyleMeasures] = {}
    for reference in holder.ids:
        got = holder.measures(reference)
        if got is not None and reference != asset.id:
            others[reference] = got
        try:
            kind = load_asset(project, reference).kind
        except KiripixError:
            kind = None
        rows.append({"asset": reference, "kind": kind, "stage": STYLE_STAGES.get(kind or ""), "built": got is not None,
                     "left_out": reference == asset.id, "measures": _numbers(got)})
    own = mine.outline.density if mine is not None and mine.outline is not None else None
    outlines = {n: m.outline.density for n, m in others.items() if m.outline is not None and m.outline.edge_px}
    scales = {n: float(m.scale.gcd) for n, m in others.items() if m.scale.runs}
    findings = _compare(mine, others) if mine is not None and others else []
    return {
        "asset": asset.id, "kind": asset.kind, "stage": stage, "built": mine is not None,
        "measures": _numbers(mine),
        "references": rows,
        "range": {"outline_density": _spread(outlines, own),
                  "pixel_scale": _spread(scales, None if mine is None else float(mine.scale.gcd))},
        "limits": {"outline_density_floor": OUTLINE_DENSITY_FLOOR, "pixel_scale_gcd": PIXEL_SCALE_GCD,
                   "pixel_scale_min_runs": PIXEL_SCALE_MIN_RUNS},
        "findings": [f.model_dump(mode="json") for f in findings],
    }
