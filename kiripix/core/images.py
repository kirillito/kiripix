"""Reading and writing images and palette files: the I/O around the pure Ops."""

import io
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageOps, UnidentifiedImageError

from kiripix.checks import Position, check_palette
from kiripix.core import atomic
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.ops import Palette, PaletteSyntaxError, parse_gpl, parse_hex
from kiripix.ops.colour import U8

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"


def load_rgba(path: Path | io.BytesIO, shown: str) -> U8:
    """An image as an (H, W, 4) uint8 array. `shown` is the path as the caller gave it, for messages."""
    try:
        with Image.open(path) as image:
            image.load()
            rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
    except FileNotFoundError:
        raise fail("image.not_found", f"no image at {shown}", owner_action=f"Check the path {shown}.") from None
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise fail(
            "image.unreadable",
            f"{shown} is not a readable image: {error}",
            owner_action=f"Save {shown} as a PNG.",
            position=Position(file=shown),
        ) from None
    return rgba.copy()


def read_png(path: Path, shown: str) -> tuple[bytes, U8]:
    """A PNG file's bytes and its pixels; any other format is refused with `image.not_png`."""
    try:
        data = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise fail("image.not_found", f"no image at {shown}", owner_action=f"Check the path {shown}.") from None
    if not data.startswith(PNG_SIGNATURE):
        raise fail("image.not_png", f"{shown} is not a PNG", owner_action=f"Save {shown} as a PNG.",
                   position=Position(file=shown))
    return data, load_rgba(io.BytesIO(data), shown)


def read_as_png(path: Path, shown: str) -> tuple[bytes, U8]:
    """A PNG or JPEG file as PNG bytes and its pixels; any other format is refused with `image.not_png_or_jpeg`.

    A PNG's bytes are kept as they are. A JPEG is turned upright by its EXIF orientation, made opaque RGBA and
    encoded as a PNG, so what Kiripix stores is always a PNG.
    """
    try:
        data = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise fail("image.not_found", f"no image at {shown}", owner_action=f"Check the path {shown}.") from None
    if data.startswith(PNG_SIGNATURE):
        return data, load_rgba(io.BytesIO(data), shown)
    if not data.startswith(JPEG_SIGNATURE):
        raise fail("image.not_png_or_jpeg", f"{shown} is not a PNG or a JPEG",
                   owner_action=f"Save {shown} as a PNG.", position=Position(file=shown))
    try:
        with Image.open(io.BytesIO(data)) as image:
            upright = ImageOps.exif_transpose(image)
            rgba = np.asarray(upright.convert("RGBA"), dtype=np.uint8).copy()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise fail("image.unreadable", f"{shown} is not a readable image: {error}",
                   owner_action=f"Save {shown} as a PNG.", position=Position(file=shown)) from None
    return png_bytes(rgba), rgba


def png_bytes(rgba: U8) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buffer, format="PNG")
    return buffer.getvalue()


def save_png(path: Path, rgba: U8) -> None:
    atomic.write_bytes(path, png_bytes(rgba))


def save_mask_png(path: Path, mask: npt.NDArray[np.bool_]) -> None:
    """A Mask as a 1-bit PNG."""
    buffer = io.BytesIO()
    Image.fromarray(mask).save(buffer, format="PNG")
    atomic.write_bytes(path, buffer.getvalue())


def load_palette(path: Path, shown: str) -> Palette:
    """Load a `.gpl` (stored) or `.hex` (imported) palette and run the palette Checks on it.

    A palette that fails its Checks ends the Command with exit code 2.
    """
    suffix = path.suffix.lower()
    if suffix not in (".gpl", ".hex"):
        raise fail(
            "palette.unknown_format",
            f"{shown}: unknown palette format '{suffix}'; Kiripix reads .gpl and .hex",
            owner_action=f"Export {shown} as a GIMP .gpl palette.",
        )
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise fail("palette.not_found", f"no palette at {shown}", owner_action=f"Create {shown}, or fix the path.") from None
    try:
        palette = parse_gpl(text) if suffix == ".gpl" else parse_hex(text, path.stem)
    except PaletteSyntaxError as error:
        raise fail(
            "palette.syntax",
            f"{shown}: {error}",
            owner_action=f"Fix line {error.line} of {shown}.",
            position=Position(file=shown, line=error.line),
        ) from None
    findings = check_palette(palette, shown)
    if findings:
        raise KiripixError(findings, ExitCode.CHECK_FAILED)
    return palette
