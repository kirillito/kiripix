"""The Checks on an NPC's `choose` output (ticket 0357, ADR 0015, spec §6.3), from what `npc.json` says against what the Project
holds now: the Wearables' bodies, the ramp table's choices and the stack of the base and the Wearables.

`npc.wearable_body` and `npc.colour_choice` are the same facts that `choose` refuses at run time (`npc.wearable_body`,
`npc.choice_unknown`), asked of a built `npc.json` whose inputs have changed since: a Wearable moved to another body, a choice
renamed, removed or given another ramp in `kiripix.toml`. `wearable_body` keeps its code with its meaning; the colour code is its own,
because the run-time refusal is about a parameter and this about a built output. Nothing here is written, and nothing is read from disk.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kiripix.checks.finding import Finding, Position
from kiripix.ops import stack_by_depth, stack_by_order
from kiripix.ops.lazy import lazy_module

if TYPE_CHECKING:
    import numpy as np
else:
    np = lazy_module("numpy")

BURIED_SHARE = 0.1  # a frame counts when the order buries at least this share of a Wearable's pixels that the depth puts in front
WORST_FRAMES = 3  # frames named, with their numbers, in each `npc.stack` finding

Ramp = list[list[int]]


def _position(npc: str, field: str) -> Position:
    return Position(asset=npc, stage="choose", field=field)


def check_wearable_body(npc: str, base: str, worn: Sequence[tuple[str, str | None]], fix_without: Mapping[str, str]) -> list[Finding]:
    """`npc.wearable_body` (error): each Wearable the built choice lists whose `body` isn't the NPC's base. `worn` is each
    Wearable's ID and its body now; `fix_without` is, by Wearable ID, the command that sets the choice without it."""
    return [Finding(
        code="npc.wearable_body", severity="error",
        message=f"{asset_id} is worn on {body}, not on this NPC's base {base}; take it out of the choice",
        position=_position(npc, f"wearables/{asset_id}"), fix=fix_without[asset_id],
        data={"wearable": asset_id, "body": body, "base": base})
        for asset_id, body in worn if body is not None and body != base]


def check_colour_choice(npc: str, built: Mapping[str, tuple[str, Ramp]], table: Mapping[str, Mapping[str, Ramp]],
                        fix_without: Mapping[str, str], fix_rebuild: str) -> list[Finding]:
    """`npc.colour_choice` (error): a Part whose built colour isn't one of the ramp table's `choices` for it now. `built` is
    each Part's choice name and ramp in `npc.json`; `table` is the choices of each Part's row now. The Part may be gone from the
    table, its choice gone from the row, or the choice given another ramp since the build."""
    findings: list[Finding] = []
    for part, (choice, ramp) in built.items():
        choices = table.get(part)
        names = ", ".join(choices) if choices else "none"
        if choices is None:
            reason, message = "part_gone", f"'{part}' is no longer a Part of the ramp table"
        elif choice not in choices:
            reason, message = "choice_gone", f"'{part}' is built with '{choice}', which is not one of its choices now ({names})"
        elif [list(c) for c in choices[choice]] != [list(c) for c in ramp]:
            reason, message = "choice_changed", f"'{choice}' of '{part}' has another ramp in the ramp table now than the one built"
        else:
            continue
        findings.append(Finding(
            code="npc.colour_choice", severity="error", message=message,
            position=_position(npc, f"colours/{part}"),
            fix=fix_rebuild if reason == "choice_changed" else fix_without[part],
            data={"part": part, "choice": choice, "choices": list(choices or {}), "reason": reason}))
    return findings


def check_part_unset(npc: str, built: Sequence[str], table: Mapping[str, Mapping[str, Ramp]],
                     fix_with: Mapping[str, str]) -> list[Finding]:
    """`npc.part_unset` (info): a Part of the ramp table that has choices, and that the NPC leaves as it was built."""
    return [Finding(
        code="npc.part_unset", severity="info",
        message=f"'{part}' has choices ({', '.join(choices)}) and this NPC keeps the colours it was built with",
        position=_position(npc, f"colours/{part}"), fix=fix_with[part], data={"part": part, "choices": list(choices)})
        for part, choices in table.items() if choices and part not in built]


@dataclass(frozen=True)
class LayerFrame:
    """One Wearable in one frame of the stack: its opaque pixels, and those the depth pass puts in front but the order buries."""

    wearable: str
    clip: str
    direction: str
    index: int
    opaque: int
    buried: int


def buried_by_order(colours: Sequence[np.ndarray], depths: Sequence[np.ndarray]) -> list[tuple[int, int]]:
    """For each RGBA frame of one cell, the lowest first (the base, then the Wearables), its opaque pixels and the pixels where
    it is the nearest by depth but another frame covers it by order. The two stackings are `stack_by_order` and
    `stack_by_depth`, each run on the frames painted with their own number, so the winner at a pixel is read off."""
    tags = []
    for number, frame in enumerate(colours, start=1):
        tag = np.zeros_like(frame)
        tag[..., 0] = number
        tag[..., 3] = np.where(frame[..., 3] > 0, 255, 0)
        tags.append(tag)
    by_order, by_depth = stack_by_order(tags)[..., 0], stack_by_depth(tags, depths)[..., 0]
    return [(int((frame[..., 3] > 0).sum()), int(((by_depth == number) & (by_order != number)).sum()))
            for number, frame in enumerate(colours, start=1)]


def check_npc_stack(npc: str, frames: Sequence[LayerFrame], fix: Callable[[str], str]) -> list[Finding]:
    """`npc.stack` (warning): a Wearable whose pixels the order buries, though the depth puts them in front, in most of its
    frames (a frame counts at `BURIED_SHARE` of its pixels). The game that stacks by order alone draws it hidden. `fix` gives
    the command for a Wearable: the caller knows the choice it is part of."""
    findings: list[Finding] = []
    for wearable in dict.fromkeys(f.wearable for f in frames):
        mine = [f for f in frames if f.wearable == wearable and f.opaque]
        hit = sorted((f for f in mine if f.buried >= BURIED_SHARE * f.opaque), key=lambda f: (-f.buried, f.clip, f.direction, f.index))
        if not mine or len(hit) * 2 <= len(mine):
            continue
        named = "; ".join(f"{f.clip} {f.direction} {f.index}: {f.buried} of {f.opaque} px" for f in hit[:WORST_FRAMES])
        findings.append(Finding(
            code="npc.stack", severity="warning",
            message=f"{wearable} is stacked under another layer by order in {len(hit)} of {len(mine)} frames, where the depth puts "
                    f"it in front ({named}); a game that stacks by order alone draws it hidden. Give it a higher order",
            position=_position(npc, f"wearables/{wearable}"), fix=fix(wearable),
            data={"wearable": wearable, "frames": len(mine), "buried_frames": len(hit),
                  "buried": sum(f.buried for f in hit),
                  "worst": [{"clip": f.clip, "direction": f.direction, "frame": f.index, "buried": f.buried, "opaque": f.opaque}
                            for f in hit[:WORST_FRAMES]]}))
    return findings
