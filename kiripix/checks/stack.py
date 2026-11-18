"""The stack Check (ticket 0294): where stacking a body's Wearables by order differs from stacking them by depth."""

from __future__ import annotations

from dataclasses import dataclass

from kiripix.checks.finding import Finding, Position

WORST_FRAMES = 3  # frames named, with their boxes, in each finding


@dataclass(frozen=True)
class StackFrame:
    """One frame stacked both ways. `differing` is the number of pixels that differ, `box` the smallest box holding them
    (x, y, width, height in frame px; None when none differ), `visible` the pixels the stack by depth shows."""

    clip: str
    direction: str
    index: int
    differing: int
    box: tuple[int, int, int, int] | None
    visible: int


def check_stack_differs(frames: list[StackFrame], body: str, wearables: list[str], fix: str) -> list[Finding]:
    """`wearable.stack_differs` (info): one finding for each clip with a frame where the order and the depth disagree. It
    says, for each direction, the differing pixels over its frames, and the worst frames with their boxes. A game that
    stacks by order alone draws those pixels wrong."""
    findings: list[Finding] = []
    clips = list(dict.fromkeys(f.clip for f in frames))
    for clip in clips:
        mine = [f for f in frames if f.clip == clip]
        total = sum(f.differing for f in mine)
        if not total:
            continue
        seen = sum(f.visible for f in mine)
        directions = list(dict.fromkeys(f.direction for f in mine))
        per_direction = ", ".join(
            f"{d} {sum(f.differing for f in mine if f.direction == d)}" for d in directions
            if any(f.differing for f in mine if f.direction == d))
        worst = sorted((f for f in mine if f.differing), key=lambda f: (-f.differing, f.direction, f.index))[:WORST_FRAMES]
        named = "; ".join(f"{f.direction} {f.index}: {f.differing} px in x {f.box[0]} y {f.box[1]} w {f.box[2]} h {f.box[3]}"
                          for f in worst if f.box is not None)
        share = f" of {seen} shown ({100 * total / seen:.1f} %)" if seen else ""
        top = worst[0]
        findings.append(Finding(
            code="wearable.stack_differs", severity="info",
            message=f"{clip}: stacked by order (the body, then {', '.join(wearables)}) {total} px differ from stacked by "
                    f"depth{share}; by direction: {per_direction}; the worst frames: {named}. A game that stacks by order "
                    "alone draws these pixels wrong",
            position=Position(asset=body, stage="render", field=f"{clip}/{top.direction}/{top.index}",
                              x=top.box[0] if top.box else None, y=top.box[1] if top.box else None,
                              width=top.box[2] if top.box else None, height=top.box[3] if top.box else None),
            fix=fix,
            data={"clip": clip, "differing": total, "shown": seen,
                  "worst": [{"direction": f.direction, "frame": f.index, "differing": f.differing,
                             "box": {"x": f.box[0], "y": f.box[1], "width": f.box[2], "height": f.box[3]}}
                            for f in worst if f.box is not None]}))
    return findings
