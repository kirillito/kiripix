"""Variants and the Pick: `import` copies an outside image into `src/` as a Variant, `pick` chooses the Source.

A Variant is `src/<hash>.png`, named by the start of its content hash, so importing the same image twice is a no-op
and a Variant never changes once picked. A character's Variants are Models instead: `src/<hash>.glb`, `.fbx` or
`.blend`. A character also has clip sources (`src/clips/<name>.<hash>.<ext>`, named by the file stem, which a `clip`
Decision's `source` names) and one rigged file (`src/rigged/<hash>.<ext>`, the Mixamo round trip's result). The
caller holds the Asset lock.
"""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

from kiripix.checks import Position
from kiripix.core import atomic, editing, journal
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.images import read_as_png
from kiripix.core.project import Project
from kiripix.recipes.base import PICK, StageSpec

VARIANT_NAME_LENGTH = 16  # hex digits of the SHA-256: 64 bits, plenty for one Asset's Variants
MODEL_SUFFIXES = (".glb", ".fbx", ".blend")
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg")
_IMAGE_SIGNATURES = (b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff")
CHARACTER = "character"


def takes_models(asset: Asset) -> bool:
    return asset.kind == CHARACTER


def variants(asset: Asset) -> dict[str, Path]:
    """The Asset's Variants by name, sorted: images, or for a character its Models."""
    suffixes = MODEL_SUFFIXES if takes_models(asset) else (".png",)
    return {path.stem: path for path in sorted((asset.dir / "src").glob("*")) if path.is_file()
            and path.suffix in suffixes}


def clip_sources(asset: Asset) -> dict[str, Path]:
    """A character's animation files by name (the file stem they were imported with), sorted."""
    found = {}
    for path in sorted((asset.dir / "src" / "clips").glob("*")):
        if path.is_file() and path.suffix in MODEL_SUFFIXES:
            found[Path(path.stem).stem] = path
    return dict(sorted(found.items()))


def rigged(asset: Asset) -> Path | None:
    """The character's rigged file, if one was imported."""
    found = [p for p in sorted((asset.dir / "src" / "rigged").glob("*")) if p.is_file() and p.suffix in MODEL_SUFFIXES]
    return max(found, key=lambda p: p.stat().st_mtime_ns) if found else None  # the newest, if a replace was cut short


def _slug(asset: Asset) -> str:
    return asset.id.split(".", 1)[-1]


def _read_for_import(file: Path, shown: str) -> bytes:
    try:
        return file.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise fail("import.not_found", f"no file at {shown}", owner_action=f"Check the path {shown}.") from None


def _is_image(file: Path, data: bytes) -> bool:
    return file.suffix.lower() in IMAGE_SUFFIXES or data.startswith(_IMAGE_SIGNATURES)


def _model_suffix(asset: Asset, file: Path, shown: str) -> str:
    suffix = file.suffix.lower()
    if suffix not in MODEL_SUFFIXES:
        raise fail("import.not_a_model", f"{shown} is not a .glb, .fbx or .blend file",
                   owner_action=f"Export {shown} from your 3D tool as a .glb, .fbx or .blend.",
                   position=Position(asset=asset.id, file=shown))
    return suffix


IMPORTED_FILE = "imported.jsonl"  # in the Asset folder, not `src/`: a Stage hashes `src/*`, and a name isn't an input
IMPORTED_SCHEMA_VERSION = 1


class ImportedName(BaseModel):
    """One line of `imported.jsonl`: the file name a stored file was imported with. The newest line for a file wins."""
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    file: str  # the stored file, relative to the Asset folder, with forward slashes
    imported_as: str


def _relative(asset: Asset, path: Path) -> str:
    return path.relative_to(asset.dir).as_posix()


def imported_names(asset: Asset) -> dict[str, str]:
    """The original file name of each stored file (key: its path relative to the Asset folder), from `imported.jsonl`.
    A file imported before the record existed isn't listed."""
    path = asset.dir / IMPORTED_FILE
    if not path.is_file():
        return {}
    names: dict[str, str] = {}
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            entry = ImportedName.model_validate_json(line)
        except ValidationError as error:
            raise fail("import.record_invalid", f"{asset.id}/{IMPORTED_FILE} line {number} is not valid: {error.errors()[0]['msg']}",
                       owner_action=f"Fix or remove line {number} of {IMPORTED_FILE} in {asset.id}.") from None
        if entry.schema_version != IMPORTED_SCHEMA_VERSION:
            raise fail("import.record_invalid", f"{asset.id}/{IMPORTED_FILE} line {number} has schema_version "
                       f"{entry.schema_version}; this Kiripix reads {IMPORTED_SCHEMA_VERSION}",
                       owner_action="Update Kiripix.")
        names[entry.file] = entry.imported_as
    return names


def imported_as(asset: Asset, path: Path) -> str | None:
    return imported_names(asset).get(_relative(asset, path))


def import_file(asset: Asset, file: Path, shown: str, role: str) -> tuple[str, Path, bool]:
    """Add a file to the Asset in a role. Returns its name, its path, and whether anything new was stored.
    Records the name the file was imported with (the newer name, if the same content comes again)."""
    name, path, created = _import(asset, file, shown, role)
    if imported_as(asset, path) != file.name:
        atomic.append_jsonl_many(asset.dir / IMPORTED_FILE, [
            {"schema_version": IMPORTED_SCHEMA_VERSION, "file": _relative(asset, path), "imported_as": file.name}])
    return name, path, created


def _import(asset: Asset, file: Path, shown: str, role: str) -> tuple[str, Path, bool]:
    """A character takes Models (`.glb`, `.fbx`, `.blend`) and a room or Prop images; the wrong one is refused with
    the Kind that takes it."""
    data = _read_for_import(file, shown)
    position = Position(asset=asset.id, file=shown)
    if not takes_models(asset):
        if role != "variant":
            raise fail("import.role_needs_character", f"--role {role} is for a character; {asset.id} is a {asset.kind}",
                       fix=f"kiripix new character {_slug(asset)}", position=position)
        if file.suffix.lower() in MODEL_SUFFIXES and not _is_image(file, data):
            raise fail("import.model_needs_character",
                       f"{shown} is a 3D Model, and a {asset.kind} takes an image (a PNG or JPEG)",
                       fix=f"kiripix new character {_slug(asset)}", position=position)
        return import_variant(asset, file, shown)
    if _is_image(file, data):
        raise fail("import.image_needs_room_or_prop",
                   f"{shown} is an image, and a character takes a Model (.glb, .fbx or .blend)",
                   fix=f"kiripix new prop {_slug(asset)}", position=position)
    suffix = _model_suffix(asset, file, shown)
    digest = hash_bytes(data)[:VARIANT_NAME_LENGTH]
    if role == "variant":
        return _store(asset.dir / "src", digest, suffix, data)
    if role == "rigged":
        name, path, created = _store(asset.dir / "src" / "rigged", digest, suffix, data)
        if created:
            for old in (asset.dir / "src" / "rigged").glob("*"):
                if old != path and old.suffix in MODEL_SUFFIXES:
                    old.unlink()
        return name, path, created
    name = file.stem
    folder = asset.dir / "src" / "clips"
    path = folder / f"{name}.{digest}{suffix}"
    if path.exists():
        return name, path, False
    atomic.write_bytes(path, data)
    for old in folder.glob("*"):  # the same name with other content replaces the earlier file
        if old != path and old.suffix in MODEL_SUFFIXES and Path(old.stem).stem == name:
            old.unlink()
    return name, path, True


def _store(folder: Path, digest: str, suffix: str, data: bytes) -> tuple[str, Path, bool]:
    path = folder / f"{digest}{suffix}"
    if path.exists():
        return digest, path, False
    atomic.write_bytes(path, data)
    return digest, path, True


def import_variant(asset: Asset, file: Path, shown: str) -> tuple[str, Path, bool]:
    """Copy a PNG (or a JPEG, stored as a PNG) into `src/` as a Variant. Returns its name, its path, and whether it
    is new."""
    data, _ = read_as_png(file, shown)
    name = hash_bytes(data)[:VARIANT_NAME_LENGTH]
    path = asset.dir / "src" / f"{name}.png"
    if path.exists():
        return name, path, False
    atomic.write_bytes(path, data)
    return name, path, True


def _pick_stage(graph: AssetGraph) -> StageSpec:
    spec = next((s for s in graph.kind.stages if any(d.name == PICK.name for d in s.decisions)), None)
    if spec is None:
        raise fail("pick.no_stage", f"a {graph.kind.name} has no Stage that takes a Pick",
                   fix=f"kiripix describe {graph.kind.name}")
    return spec


def takes_pick(graph: AssetGraph) -> bool:
    return any(d.name == PICK.name for s in graph.kind.stages for d in s.decisions)


def picked(graph: AssetGraph) -> str | None:
    """The Variant the Asset's current Pick names; None without a Pick."""
    picks = [d for d in graph.replay(_pick_stage(graph).name).current if d.name == PICK.name]
    return str(picks[-1].data["variant"]) if picks else None


def pick(project: Project, asset: Asset, variant: str) -> tuple[StageSpec, journal.JournalEntry]:
    """Record the Pick Decision on the Stage that takes it, the same entry `decide` would write."""
    spec = _pick_stage(AssetGraph(project, asset, HashCache(project.state_dir)))
    known = variants(asset)
    if variant not in known:
        position = Position(asset=asset.id, stage=spec.name)
        if not known:
            raise fail("pick.unknown_variant", f"{asset.id} has no Variants yet", position=position,
                       fix=f"kiripix import {asset.id} <file>")
        raise fail("pick.unknown_variant", f"{asset.id} has no Variant '{variant}'; its Variants are "
                   f"{', '.join(known)}", position=position,
                   owner_action=f"Pick one of them: kiripix pick {asset.id} <variant>")
    document = editing.DecisionDocument(decision=PICK.name, data={"variant": variant})
    entry, _ = editing.record_decision(project, asset, spec.name, document)
    return spec, entry
