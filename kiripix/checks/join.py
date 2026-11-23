"""Checks on a join (ticket 0135): the numbers the join Ops return, as findings. All are warnings: the Owner may like the join."""

from kiripix.checks.finding import Finding, Position

MAX_RESIDUAL = 0.5  # px; trial 0063 registered its pieces to 0.3. The default of `[extend] max_residual` (ticket 0377)
# The most `[extend] max_residual` and `--max-residual` may raise it to (ticket 0377): a strip GPT Image re-rendered registers
# to 0.66 px, a strip from another scene to 1.34 px or more, and a strip with part of it moved 2 px to 1.2 px.
RESIDUAL_CEILING = 1.0
MAX_GAIN_RANGE = (0.8, 1.25)  # a piece darker or brighter than this against the base is a different exposure, not a tint
MAX_SEAM_DIFFERENCE = 12.0  # mean absolute RGB difference (0..255) along the cut


def check_join_residual(residual: float, patches: int, file: str, limit: float = MAX_RESIDUAL) -> list[Finding]:
    """The registration left more than `limit` px (half a pixel by default, `[extend] max_residual`) between the edge
    patches and the fit."""
    if residual <= limit:
        return []
    return [
        Finding(
            code="join.residual_high",
            severity="warning",
            message=f"{file} registers to {residual:.2f} px over {patches} patches; more than {limit:g} px "
            "shows as a step in the join",
            position=Position(file=file),
            owner_action=f"Widen the overlap of {file}, or generate the piece again with a wider strip of the base.",
        )
    ]


def check_join_gain(low: float, high: float, file: str) -> list[Finding]:
    """The tone gain went beyond a tint: the piece and the base differ in more than light."""
    if MAX_GAIN_RANGE[0] <= low and high <= MAX_GAIN_RANGE[1]:
        return []
    return [
        Finding(
            code="join.gain_wide",
            severity="warning",
            message=f"{file} needs a gain of {low:.2f} to {high:.2f} to match the base; beyond "
            f"{MAX_GAIN_RANGE[0]} to {MAX_GAIN_RANGE[1]}",
            position=Position(file=file),
            owner_action=f"Look at {file} against the base: a gain this large usually means the model changed the scene.",
        )
    ]


def check_seam_difference(mean_difference: float, length: float, file: str) -> list[Finding]:
    """The seam had to cut through pixels that differ: no band of low difference in the overlap."""
    if mean_difference <= MAX_SEAM_DIFFERENCE:
        return []
    return [
        Finding(
            code="join.seam_costly",
            severity="warning",
            message=f"the seam of {file} ({length:.0f} px) cuts through pixels that differ by "
            f"{mean_difference:.1f} on average; more than {MAX_SEAM_DIFFERENCE:.0f} shows",
            position=Position(file=file),
            owner_action=f"Register and tone {file} again, or widen its overlap, so a quiet path exists.",
        )
    ]
