"""A sprite Asset's sheets: PNGs and ZIPs of PNGs, stored whole in `src/sheets/` by their hash (ticket 0178).

A sheet is a Source file, immutable once imported. Nothing is unpacked into `src/`; the `frames` Stage reads the file.
A ZIP is checked here, before anything is written, and refused whole when it could do harm or isn't what it says.
The caller holds the Asset lock.
"""

import io
import stat
from pathlib import Path

from kiripix.checks import Position
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError, fail
from kiripix.recipes.base import KindSpec

SHEETS_DIR = "sheets"
MAX_ENTRIES = 4096
MAX_UNPACKED = 256 * 1024 * 1024  # bytes, over every entry
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ZIP_SIGNATURES = (b"PK\x03\x04", b"PK\x05\x06")
_CHUNK = 1024 * 1024


def takes_sheets(kind: KindSpec) -> bool:
    return kind.takes_sheets


def sheets(asset: Asset) -> dict[str, Path]:
    """The Asset's sheets by name (the start of their hash), sorted."""
    folder = asset.dir / "src" / SHEETS_DIR
    return {path.stem: path for path in sorted(folder.glob("*")) if path.is_file() and path.suffix in (".png", ".zip")}


def png_count(path: Path) -> int | None:
    """A ZIP sheet's PNG count; None for a PNG sheet."""
    if path.suffix != ".zip":
        return None
    import zipfile

    with zipfile.ZipFile(path) as archive:
        return sum(1 for info in archive.infolist() if not info.is_dir())


def _unsafe_path(name: str) -> str | None:
    """Why an entry's path may not be unpacked, or None."""
    if name.startswith(("/", "\\")) or (len(name) >= 2 and name[1] == ":"):
        return "its path is absolute or names a drive"
    if ".." in name.replace("\\", "/").split("/"):
        return "its path leaves the archive (..)"
    if "\x00" in name:
        return "its path has a null byte"
    return None


def check(data: bytes, shown: str, position: Position) -> str:
    """Validate a file as a sheet and return its suffix (`.png` or `.zip`). Raises `import.sheet_invalid`."""

    def refuse(why: str, entry: str | None = None) -> KiripixError:
        subject = f"{shown}'s entry {entry}" if entry is not None else shown
        return fail("import.sheet_invalid", f"{subject} can't be a sheet: {why}", position=position,
                    owner_action=f"Export {shown} again as a PNG, or as a ZIP of PNGs with plain relative paths, "
                                 f"at most {MAX_ENTRIES} entries and {MAX_UNPACKED // (1024 * 1024)} MB unpacked.")

    if data.startswith(PNG_SIGNATURE):
        return ".png"
    if not data.startswith(_ZIP_SIGNATURES):
        raise refuse("it is neither a PNG nor a ZIP by its bytes")
    import zipfile

    try:
        archive = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise refuse("it isn't a readable ZIP") from None
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            raise refuse(f"it holds {len(infos)} entries, more than {MAX_ENTRIES}")
        for info in infos:  # every path first, so nothing unsafe is read
            why = _unsafe_path(info.filename)
            if why is not None:
                raise refuse(why, info.filename)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise refuse("it is a link", info.filename)
            if info.flag_bits & 0x1:
                raise refuse("it is encrypted", info.filename)
        total = 0
        pngs = 0
        for info in infos:
            if info.is_dir():
                continue
            total += info.file_size
            if total > MAX_UNPACKED:
                raise refuse(f"the archive unpacks to more than {MAX_UNPACKED // (1024 * 1024)} MB", info.filename)
            try:
                with archive.open(info) as entry:  # reading to the end checks the CRC and the real size
                    head = entry.read(len(PNG_SIGNATURE))
                    if head != PNG_SIGNATURE:
                        raise refuse("it isn't a PNG by its bytes", info.filename)
                    read = len(head)
                    while chunk := entry.read(_CHUNK):
                        read += len(chunk)
                        if total - info.file_size + read > MAX_UNPACKED:
                            raise refuse(f"the archive unpacks to more than {MAX_UNPACKED // (1024 * 1024)} MB",
                                         info.filename)
            except (zipfile.BadZipFile, NotImplementedError, RuntimeError, EOFError, OSError, ValueError) as error:
                raise refuse(f"it can't be read ({error})", info.filename) from None
            pngs += 1
        if pngs == 0:
            raise refuse("it holds no PNG")
    return ".zip"
