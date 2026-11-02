"""`kiripix op quantize` and `kiripix op conformance` through the CLI."""

import shutil
from pathlib import Path

from PIL import Image

from conftest import Kiripix

GOLDEN = Path(__file__).parent.parent / "golden" / "inputs"


def copy_input(runner: Kiripix, name: str) -> str:
    shutil.copy(GOLDEN / name, runner.cwd / name)
    return name


def test_quantize_writes_a_png_on_the_project_palette(project: Kiripix) -> None:
    image = copy_input(project, "gradient.png")

    data = project.json("op", "quantize", image, "out.png", "--dither", "bayer4")["data"]

    assert data["palette"] == "style/palette.gpl"
    assert (data["width"], data["height"]) == (64, 32)
    assert data["input_conformance"]["off_palette"] > 0
    assert 1 < data["colours_used"] <= 16
    check = project.json("op", "conformance", "out.png")["data"]
    assert check["off_palette"] == 0


def test_quantize_outside_a_project_needs_a_palette(kpx: Kiripix) -> None:
    image = copy_input(kpx, "gradient.png")

    finding = kpx.json("op", "quantize", image, "out.png", expect=1)["findings"][0]

    assert finding["code"] == "palette.not_set"
    assert finding["fix"] == "kiripix op quantize gradient.png out.png --palette style/palette.gpl"
    copy_input(kpx, "palette.gpl")
    assert kpx.json("op", "quantize", image, "out.png", "--palette", "palette.gpl")["ok"]


def test_quantize_reads_a_hex_palette(kpx: Kiripix) -> None:
    image = copy_input(kpx, "gradient.png")
    (kpx.cwd / "p.hex").write_text("000000\nFFFFFF\n", encoding="utf-8")

    data = kpx.json("op", "quantize", image, "out.png", "--palette", "p.hex")["data"]

    assert data["colours_used"] == 2


def test_quantize_refuses_partial_alpha(project: Kiripix) -> None:
    image = copy_input(project, "partial_alpha.png")

    finding = project.json("op", "quantize", image, "out.png", expect=2)["findings"][0]

    assert finding["code"] == "image.partial_alpha"
    assert (finding["position"]["x"], finding["position"]["y"]) == (7, 5)
    assert not (project.cwd / "out.png").exists()


def test_quantize_refuses_a_palette_with_duplicates(project: Kiripix) -> None:
    image = copy_input(project, "gradient.png")
    palette = copy_input(project, "duplicates.gpl")

    finding = project.json("op", "quantize", image, "out.png", "--palette", palette, expect=2)["findings"][0]

    assert finding["code"] == "palette.duplicate_colour"
    assert finding["position"]["line"] == 6 and finding["owner_action"]


def test_quantize_rejects_a_bad_strength(project: Kiripix) -> None:
    image = copy_input(project, "gradient.png")

    result = project.json("op", "quantize", image, "out.png", "--strength", "2", expect=1)

    assert result["findings"][0]["code"] == "input.invalid"


def test_conformance_reports_off_palette_pixels_with_a_fix(project: Kiripix) -> None:
    image = copy_input(project, "gradient.png")

    result = project.json("op", "conformance", image, expect=2)

    assert 0 < result["data"]["off_palette"] <= 64 * 32
    assert len(result["data"]["first_off_palette"]) == 10
    finding = result["findings"][0]
    assert finding["code"] == "palette.off_palette"
    assert finding["fix"] == "kiripix op quantize gradient.png gradient.quantized.png"


def test_an_unreadable_image(project: Kiripix) -> None:
    (project.cwd / "notes.png").write_text("not an image", encoding="utf-8")

    assert project.json("op", "conformance", "notes.png", expect=1)["findings"][0]["code"] == "image.unreadable"
    assert project.json("op", "conformance", "missing.png", expect=1)["findings"][0]["code"] == "image.not_found"


def test_a_palette_syntax_error_names_the_line(project: Kiripix) -> None:
    Image.new("RGBA", (2, 2), (0, 0, 0, 255)).save(project.cwd / "in.png")
    (project.cwd / "bad.gpl").write_text("GIMP Palette\nName: bad\n#\n0 0 zero\n", encoding="utf-8")

    finding = project.json("op", "conformance", "in.png", "--palette", "bad.gpl", expect=1)["findings"][0]

    assert finding["code"] == "palette.syntax"
    assert finding["position"]["line"] == 4
