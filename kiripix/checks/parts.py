"""The vanishing-part Check (spec §6.3, ticket 0159): does a small part, such as an eye, drop out of some frames?"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from dataclasses import dataclass

from kiripix.checks.finding import Finding, Position

OWNER_ACTION = ("Make the part bigger in the Model, or raise the character's height, so it covers a pixel in every frame; "
                "then run render again.")


@dataclass(frozen=True)
class PartCounts:
    """How many pixels of each material a finished frame holds. Every material is a key, with 0 when it's absent."""

    clip: str
    direction: str
    index: int
    pixels: Mapping[str, int]


def check_part_vanishes(frames: list[PartCounts], watch: Collection[str] | None = None, minimum: int = 1) -> list[Finding]:
    """`sheet.part_vanishes`: in one clip and direction, a material that has at least `minimum` pixels in most frames (more than
    half) but fewer in others. A material missing from every frame, or from half or more of them, is a part that turns away,
    not one that vanishes. `watch` limits the materials (None or empty is all). One finding per clip, direction and material,
    in that order, naming the frames."""
    groups: dict[tuple[str, str], list[PartCounts]] = {}
    for f in sorted(frames, key=lambda f: (f.clip, f.direction, f.index)):
        groups.setdefault((f.clip, f.direction), []).append(f)
    findings: list[Finding] = []
    for (clip, direction), group in groups.items():
        for material in sorted({m for f in group for m in f.pixels}):
            if watch and material not in watch:
                continue
            missing = [f.index for f in group if f.pixels.get(material, 0) < minimum]
            present = len(group) - len(missing)
            if not missing or present * 2 <= len(group):
                continue
            listed = ", ".join(str(i) for i in missing)
            findings.append(Finding(
                code="sheet.part_vanishes", severity="warning", owner_action=OWNER_ACTION,
                position=Position(field=f"{clip}/{direction}"),
                message=f"clip {clip}, direction {direction}: the material {material} is in {present} of {len(group)} frames "
                        f"but missing from frame{'s' if len(missing) > 1 else ''} {listed}"))
    return findings
