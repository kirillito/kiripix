"""The style Checks (ticket 0333, trial 0332): an Asset's measures against its references'. Each out-of-range finding is a
warning that names the Asset's number, the references' range and the reference furthest from it.

The thresholds are the Owner's, set in trial 0332 (2026-11-20). The measures themselves are `kiripix.ops.style`; which
Stage's image is measured, and which Assets are references, is the caller's (ticket 0334).
"""

from collections.abc import Mapping

from kiripix.checks.finding import Finding, Position
from kiripix.ops import OutlineMeasure, ScaleMeasure

OUTLINE_DENSITY_FLOOR = 0.5
"""An outlined figure's density is 1.0 or more (the trial's: 1.00 to 2.02); warn below this."""
PIXEL_SCALE_GCD = 2
PIXEL_SCALE_MIN_RUNS = 50
"""Warn at a run gcd of at least `PIXEL_SCALE_GCD` over at least `PIXEL_SCALE_MIN_RUNS` runs (fewer is too little to tell)."""

STYLE_STAGES: dict[str, str] = {"character": "finish", "sprite": "finish", "wearable": "finish", "room": "palette", "prop": "export"}
"""The Kinds with style Checks and the Stage each is measured on (the Owner's verdict in trial 0332): `finish`'s colour frames
for a figure, `palette`'s Plate for a room, a Prop's export."""
OUTLINE_KINDS = frozenset({"character", "sprite"})
"""The Kinds whose outline is measured. Not a Wearable: its `finish` draws none, the game outlines the stack once."""


def _range(asset: float, refs: Mapping[str, float]) -> tuple[str, float | None, float | None, str | None]:
    """The references' range as text, its ends, and the reference furthest from `asset` (ties to the lowest name)."""
    if not refs:
        return "no references", None, None, None
    low, high = min(refs.values()), max(refs.values())
    furthest = min(refs, key=lambda name: (-abs(refs[name] - asset), name))
    return f"{low:.2f} to {high:.2f}", low, high, furthest


def check_outline_density(asset: str, measure: OutlineMeasure, references: Mapping[str, OutlineMeasure], fix: str) -> list[Finding]:
    """A figure (character or sprite) whose silhouette edge is mostly not the outline colour. `fix` is the
    command that turns the outline on (`finish`'s). An Asset with no edge is not judged."""
    if not measure.edge_px or measure.density >= OUTLINE_DENSITY_FLOOR:
        return []
    shown, low, high, furthest = _range(measure.density, {n: m.density for n, m in references.items() if m.edge_px})
    near = f", furthest {furthest} at {references[furthest].density:.2f}" if furthest else ""
    return [Finding(
        code="style.outline_density", severity="warning",
        message=f"{asset} has the outline on {measure.density:.2f} of its edge pixels ({measure.outline_px} of "
                f"{measure.edge_px}); below {OUTLINE_DENSITY_FLOOR}: it looks drawn without an outline. The references: "
                f"{shown}{near}",
        position=Position(asset=asset, stage="finish"), fix=fix,
        data={"density": measure.density, "outline_px": measure.outline_px, "edge_px": measure.edge_px,
              "floor": OUTLINE_DENSITY_FLOOR, "references_low": low, "references_high": high, "furthest": furthest})]


def check_pixel_scale(asset: str, measure: ScaleMeasure, references: Mapping[str, ScaleMeasure], fix: str | None,
                      stage: str | None = None, owner_action: str | None = None) -> list[Finding]:
    """An image painted at 2x or more: its colour runs all share a factor. Exactly one of `fix` (the command that sets the
    scale right: a sprite's `fit`) or `owner_action` (a new Source, which only the Owner can give)."""
    if (fix is None) == (owner_action is None):
        raise ValueError("check_pixel_scale needs exactly one of fix or owner_action")
    if measure.gcd < PIXEL_SCALE_GCD or measure.runs < PIXEL_SCALE_MIN_RUNS:
        return []
    shown, low, high, furthest = _range(float(measure.gcd), {n: float(m.gcd) for n, m in references.items() if m.runs})
    near = f", furthest {furthest} at {references[furthest].gcd}" if furthest else ""
    return [Finding(
        code="style.pixel_scale", severity="warning",
        message=f"{asset} is drawn at {measure.gcd}x: every colour run is a multiple of {measure.gcd} pixels long "
                f"({measure.runs} runs, median {measure.median:g}), so its pixels are bigger than the Project's. "
                f"The references' gcd: {shown}{near}",
        position=Position(asset=asset, stage=stage), fix=fix, owner_action=owner_action,
        data={"gcd": measure.gcd, "runs": measure.runs, "median": measure.median, "references_low": low,
              "references_high": high, "furthest": furthest})]


def check_style_measures(asset: str, outline: OutlineMeasure | None, scale: ScaleMeasure, fix: str) -> list[Finding]:
    """The numbers, as an info finding, so `check --json` shows them even when nothing is wrong. `outline` is None for
    a Kind with no outline measure. `fix` is the command that shows them again."""
    data: dict[str, object] = {"pixel_scale": {"gcd": scale.gcd, "runs": scale.runs, "median": scale.median,
                                               "run1_share": scale.run1_share}}
    said = f"pixel scale gcd {scale.gcd} over {scale.runs} runs"
    if outline is not None:
        data["outline_density"] = {"density": outline.density, "outline_px": outline.outline_px, "edge_px": outline.edge_px}
        said = f"outline density {outline.density:.2f}, " + said
    return [Finding(code="style.measures", severity="info", message=f"{asset}: {said}",
                    position=Position(asset=asset), fix=fix, data=data)]
