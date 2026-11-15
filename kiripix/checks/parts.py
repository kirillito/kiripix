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


@dataclass(frozen=True)
class EyeCover:
    """One frame's eyes that face the camera: `hidden` when none of them shows, `by` the material in front of them."""

    clip: str
    direction: str
    index: int
    hidden: bool
    by: str | None = None


EYES_OWNER_ACTION = ("Raise or narrow what covers the face in the Model (a hat brim, a fringe, a hood), or turn the clip's "
                     "pose so the eyes show; then run render again.")


def check_eyes_covered(frames: list[EyeCover]) -> list[Finding]:
    """`sheet.eyes_covered` (ticket 0225): in one clip and front direction, both eyes hidden behind another material in more than
    half of the frames. One finding per clip and direction, naming the covering material that hides them most."""
    groups: dict[tuple[str, str], list[EyeCover]] = {}
    for f in sorted(frames, key=lambda f: (f.clip, f.direction, f.index)):
        groups.setdefault((f.clip, f.direction), []).append(f)
    findings: list[Finding] = []
    for (clip, direction), group in groups.items():
        hidden = [f for f in group if f.hidden]
        if len(hidden) * 2 <= len(group):
            continue
        names = [f.by for f in hidden if f.by]
        material = max(sorted(set(names)), key=names.count) if names else "another material"
        findings.append(Finding(
            code="sheet.eyes_covered", severity="warning", owner_action=EYES_OWNER_ACTION,
            position=Position(field=f"{clip}/{direction}"),
            message=f"clip {clip}, direction {direction}: both eyes are hidden behind the material {material} in "
                    f"{len(hidden)} of {len(group)} frames"))
    return findings


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
