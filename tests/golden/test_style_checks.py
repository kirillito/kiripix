"""Unit tests for the style Checks (ticket 0333)."""

from kiripix.checks import check_outline_density, check_pixel_scale, check_style_measures
from kiripix.ops import OutlineMeasure, ScaleMeasure

FIX = "kiripix set mc03 --stage finish --param outline=true"


def outline(density: float) -> OutlineMeasure:
    return OutlineMeasure(outline_px=int(density * 100), edge_px=100, density=density)


def scale(gcd: int, runs: int = 80) -> ScaleMeasure:
    return ScaleMeasure(runs=runs, gcd=gcd, median=float(gcd), run1_share=0.0)


REFS = {"character/b": outline(1.48), "character/a": outline(2.02), "sprite/r": outline(1.0)}


def test_outline_in_range_gives_nothing() -> None:
    assert check_outline_density("character/x", outline(1.5), REFS, FIX) == []
    assert check_outline_density("character/x", outline(0.5), REFS, FIX) == []


def test_outline_missing_warns_with_range_and_furthest_reference() -> None:
    [finding] = check_outline_density("character/x", outline(0.0), REFS, FIX)
    assert (finding.code, finding.severity, finding.fix, finding.owner_action) == ("style.outline_density", "warning", FIX, None)
    assert "0.00" in finding.message and "1.00 to 2.02" in finding.message and "character/a at 2.02" in finding.message
    assert finding.data["furthest"] == "character/a" and finding.data["density"] == 0.0


def test_outline_without_references_still_warns() -> None:
    [finding] = check_outline_density("character/x", outline(0.1), {}, FIX)
    assert "no references" in finding.message and finding.data["furthest"] is None


def test_outline_of_an_image_with_no_edge_is_not_judged() -> None:
    assert check_outline_density("character/x", OutlineMeasure(0, 0, 0.0), REFS, FIX) == []


def test_scale_in_range_gives_nothing() -> None:
    assert check_pixel_scale("room/x", scale(1), {"room/a": scale(1)}, FIX) == []
    assert check_pixel_scale("room/x", scale(2, runs=49), {}, FIX) == []


def test_scale_2x_warns() -> None:
    refs = {"room/b": scale(1), "room/a": scale(1)}
    [finding] = check_pixel_scale("room/x", scale(2), refs, FIX, stage="palette")
    assert (finding.code, finding.severity, finding.fix) == ("style.pixel_scale", "warning", FIX)
    assert finding.position is not None and finding.position.stage == "palette"
    assert "2x" in finding.message and "1.00 to 1.00" in finding.message and "room/a at 1" in finding.message


def test_measures_is_info_with_all_the_numbers() -> None:
    [finding] = check_style_measures("character/x", outline(1.5), scale(1), FIX)
    assert (finding.code, finding.severity) == ("style.measures", "info")
    assert finding.data["outline_density"]["density"] == 1.5 and finding.data["pixel_scale"]["gcd"] == 1
    [finding] = check_style_measures("room/x", None, scale(1), FIX)
    assert "outline_density" not in finding.data
