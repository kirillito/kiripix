"""The palette Checks: on a palette, and on an image against a palette."""

from kiripix.checks.finding import Finding, Position
from kiripix.ops import ConformanceReport, Palette


def check_palette(palette: Palette, file: str) -> list[Finding]:
    """A palette must have colours, all opaque, none repeated."""
    if not palette.entries:
        return [
            Finding(
                code="palette.empty",
                message=f"{file} has no colours",
                position=Position(file=file),
                owner_action=f"Add the project's colours to {file}.",
            )
        ]
    findings: list[Finding] = []
    seen: dict[tuple[int, int, int], int] = {}
    for entry in palette.entries:
        if entry.alpha != 255:
            findings.append(
                Finding(
                    code="palette.alpha",
                    message=f"{file}:{entry.line}: {entry.hex} has alpha {entry.alpha}; palette colours are opaque",
                    position=Position(file=file, line=entry.line),
                    owner_action=f"Make {entry.hex} opaque or remove it from {file}.",
                )
            )
        key = (entry.r, entry.g, entry.b)
        if key in seen:
            findings.append(
                Finding(
                    code="palette.duplicate_colour",
                    message=f"{file}:{entry.line}: {entry.hex} repeats the colour on line {seen[key]}",
                    position=Position(file=file, line=entry.line),
                    owner_action=f"Remove one of the two {entry.hex} lines from {file}.",
                )
            )
        else:
            seen[key] = entry.line
    return findings


def check_alpha(report: ConformanceReport, file: str) -> list[Finding]:
    """Pixel art has no partial alpha: every pixel is fully opaque or fully transparent."""
    if not report.partial_alpha:
        return []
    x, y = report.first_partial_alpha[0]
    return [
        Finding(
            code="image.partial_alpha",
            message=f"{file} has {report.partial_alpha} partially transparent pixels, the first at ({x}, {y})",
            position=Position(file=file, x=x, y=y),
            owner_action=f"Make every pixel of {file} fully opaque or fully transparent.",
        )
    ]


def check_conformance(report: ConformanceReport, file: str, fix: str) -> list[Finding]:
    """Every opaque pixel is a palette colour. `fix` is the command that maps the image onto the palette."""
    if not report.off_palette:
        return []
    x, y = report.first_off_palette[0]
    return [
        Finding(
            code="palette.off_palette",
            message=f"{file} has {report.off_palette} pixels off the palette, the first at ({x}, {y})",
            position=Position(file=file, x=x, y=y),
            fix=fix,
        )
    ]
