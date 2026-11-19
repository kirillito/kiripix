"""A character's held things (ticket 0301, 0238): the mesh a clip's `attach` holds (a phone, a class's weapon), stored per Asset.

A thing `<id>` (lower-case `[a-z0-9_]+`) is the folder `src/things/<id>/`. Each import of a file under the ID is a Variant,
`<hash>.glb` or `<hash>.blend`, so importing again under the same ID adds a Variant and keeps the earlier ones. The newest
import is the thing's current Variant, the one a render holds; there is no Pick, because the thing is part of the character's
render, not a choice between sources. A thing's origin and axes are its grip: the import keeps the file's own, and a clip's
`offset` and `turn` adjust them.

The materials of a thing are read from its file: a `.glb`'s by reading its JSON, a `.blend`'s by Blender when the import is made
(stored as `<hash>.materials.json` beside it, which is not a Variant). They are the names the render numbers them by (the
materials the meshes use, sorted), and the thing's are numbered after the Model's: the Model's 1 to N stay put, then each
thing's, in the order the things were first imported, each thing's own materials sorted by name. A thing added later comes last,
so no earlier number moves. The caller holds the Asset lock."""

import json
import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from kiripix.checks import Position
from kiripix.core import atomic, sources
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.project import Project
from kiripix.recipes import clips
from kiripix.recipes.base import StageFailure
from kiripix.recipes.blender_launcher import launch_for

THING_SUFFIXES = (".glb", ".blend")
MATERIALS_SUFFIX = ".materials.json"
CLIPS_STAGE = "clips"
_GLB_MAGIC = b"glTF"
_JSON_CHUNK = 0x4E4F534A


def check_id(asset: Asset, thing: str, shown: str | None = None) -> None:
    """Refuse an ID that isn't lower-case `[a-z0-9_]+`."""
    if re.fullmatch(clips.THING_ID, thing) is None:
        raise fail("thing.invalid_id", f"'{thing}' is not a thing ID: lower-case letters, digits and underscores",
                   owner_action="Choose an ID such as phone or rake_2.",
                   position=Position(asset=asset.id, file=shown))


def folder(asset: Asset, thing: str) -> Path:
    return asset.dir / clips.THINGS_DIR / thing


def variants(asset: Asset, thing: str) -> dict[str, Path]:
    """A thing's Variants by name (the start of the file's hash), sorted."""
    return {p.stem: p for p in sorted(folder(asset, thing).glob("*"))
            if p.is_file() and p.suffix in THING_SUFFIXES and not p.name.endswith(MATERIALS_SUFFIX)}


def _journal(asset: Asset) -> list[str]:
    """The stored files of things in the order they were imported, one entry per import, from `imported.jsonl`."""
    path = asset.dir / sources.IMPORTED_FILE
    found: list[str] = []
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = sources.ImportedName.model_validate_json(line)
        except ValidationError:
            continue  # `sources.imported_names` is the one that refuses a bad line
        if entry.file.startswith(clips.THINGS_DIR):
            found.append(entry.file)
    return found


def thing_ids(asset: Asset) -> list[str]:
    """The IDs of the things that have a Variant, in the order they were first imported (a thing with no record, such as a
    folder laid by hand, after those, by ID)."""
    present = {t for t in _known(asset) if variants(asset, t)}
    ordered: list[str] = []
    for file in _journal(asset):
        thing = file[len(clips.THINGS_DIR):].split("/", 1)[0]
        if thing in present and thing not in ordered:
            ordered.append(thing)
    return ordered + sorted(present - set(ordered))


def _known(asset: Asset) -> set[str]:
    root = asset.dir / clips.THINGS_DIR
    return {p.name for p in root.iterdir() if p.is_dir()} if root.is_dir() else set()


def current(asset: Asset, thing: str) -> Path | None:
    """The thing's current Variant: the newest imported (the last in `imported.jsonl`), else the newest file."""
    found = variants(asset, thing)
    if not found:
        return None
    for file in reversed(_journal(asset)):
        path = asset.dir / file
        if path.parent.name == thing and path in found.values():
            return path
    return max(found.values(), key=lambda p: (p.stat().st_mtime_ns, p.name))


def glb_materials(data: bytes) -> list[str] | None:
    """The names of the materials a `.glb`'s meshes use, sorted; None when it isn't a readable `.glb`. A material with no name
    is `Material`, as Blender names it."""
    if len(data) < 20 or data[:4] != _GLB_MAGIC:
        return None
    length, kind = struct.unpack("<II", data[12:20])
    if kind != _JSON_CHUNK:
        return None
    try:
        document = json.loads(data[20:20 + length].decode("utf-8"))
        materials = document.get("materials", [])
        used = {p["material"] for mesh in document.get("meshes", []) for p in mesh.get("primitives", []) if "material" in p}
        return sorted({str(materials[i].get("name") or "Material") for i in used})
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        return None


def materials_of(path: Path) -> list[str] | None:
    """A Variant's material names, sorted; None when they aren't known (a `.blend` made without Blender, an unreadable file)."""
    sidecar = path.with_name(path.stem + MATERIALS_SUFFIX)
    if sidecar.is_file():
        try:
            return [str(n) for n in json.loads(sidecar.read_text(encoding="utf-8"))["materials"]]
        except (ValueError, KeyError, TypeError):
            return None
    if path.suffix == ".glb":
        return glb_materials(path.read_bytes())
    return None


@dataclass
class ThingInfo:
    thing: str
    variants: dict[str, Path]
    path: Path  # the current Variant
    materials: list[str] | None  # None: not known until a render reads them
    first: int  # the number of its first material among the things' (from 1); its materials follow in order


def listed(asset: Asset) -> list[ThingInfo]:
    """The Asset's things in numbering order, each with its current Variant's materials. A material's number is the Model's
    count plus `first` plus its place among the thing's own."""
    found: list[ThingInfo] = []
    first = 1
    for thing in thing_ids(asset):
        path = current(asset, thing)
        assert path is not None
        names = materials_of(path)
        found.append(ThingInfo(thing=thing, variants=variants(asset, thing), path=path, materials=names, first=first))
        first += len(names or [])
    return found


def model_material_count(asset: Asset) -> int | None:
    """How many materials the Model has, from the `render` Stage's output; None while `render` isn't built."""
    try:
        document: dict[str, Any] = json.loads((asset.dir / "work" / "render" / "render.json").read_text(encoding="utf-8"))
        return len(document["materials"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def attached_by(project: Project, asset: Asset, thing: str) -> list[str]:
    """The clips whose current Decision attaches the thing, by name."""
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    # Read as the Stage reads them (`decisions_view`): a clip decided again replaces its earlier Decision of the same name.
    held = [str(d.data["name"]) for d in graph.decisions(graph.spec(CLIPS_STAGE))
            if d.name == clips.CLIP.name and any(a["thing"] == thing for a in d.data.get("attach", []))]
    return sorted(held)


def _need_character(asset: Asset, shown: str) -> None:
    if asset.kind != sources.CHARACTER:
        raise fail("import.role_needs_character", f"--role thing is for a character; {asset.id} is a {asset.kind}",
                   owner_action="Import the thing into the character that holds it.",
                   position=Position(asset=asset.id, file=shown))


def import_thing(project: Project, asset: Asset, file: Path, shown: str, thing: str, *,
                 progress: Any, check_cancel: Any) -> tuple[str, Path, bool, list[str] | None]:
    """Store a mesh file as a Variant of the thing, the newest, which makes it current. Returns the Variant's name and path,
    whether the file is new, and the Variant's materials (None when not known)."""
    position = Position(asset=asset.id, file=shown)
    _need_character(asset, shown)
    check_id(asset, thing, shown)
    try:
        data = file.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise fail("import.not_found", f"no file at {shown}", owner_action=f"Check the path {shown}.") from None
    suffix = file.suffix.lower()
    if suffix not in THING_SUFFIXES:
        raise fail("import.not_a_thing_model", f"{shown} is not a .glb or .blend file",
                   owner_action=f"Export {shown} from your 3D tool as a .glb, or save it as a .blend.", position=position)
    name = hash_bytes(data)[:sources.VARIANT_NAME_LENGTH]
    path = folder(asset, thing) / f"{name}{suffix}"
    created = not path.exists()
    if created:
        atomic.write_bytes(path, data)
    sidecar = path.with_name(path.stem + MATERIALS_SUFFIX)
    names = materials_of(path)
    if names is None and suffix == ".blend":
        names = _blender_materials(project, path, progress, check_cancel)
        if names is not None:
            atomic.write_json(sidecar, {"materials": names})
    atomic.append_jsonl_many(asset.dir / sources.IMPORTED_FILE, [
        {"schema_version": sources.IMPORTED_SCHEMA_VERSION, "file": path.relative_to(asset.dir).as_posix(),
         "imported_as": file.name}])  # every import, so the newest line says which Variant is current
    return name, path, created, names


def _blender_materials(project: Project, path: Path, progress: Any, check_cancel: Any) -> list[str] | None:
    """The materials of a `.blend` thing, from Blender; None when Blender can't be run (they are read at the first render)."""
    try:
        result = launch_for("list_materials", {"input": str(path)}, executable=project.settings.character.blender,
                            progress=progress, check_cancel=check_cancel)
    except StageFailure:
        return None
    return sorted(str(n) for n in result["materials"])


def remove_thing(project: Project, asset: Asset, thing: str) -> list[Path]:
    """Take the thing and all its Variants away. Refused while a clip attaches it. Returns the files removed."""
    position = Position(asset=asset.id, stage=CLIPS_STAGE)
    _need_character(asset, "")
    held = attached_by(project, asset, thing)
    known = thing_ids(asset)
    if thing not in known:
        raise fail("thing.unknown", f"{asset.id} has no thing {thing} (its things are {', '.join(known) or 'none'})",
                   owner_action=f"Name one of its things, or import it: kiripix import {asset.id} <file> --role thing "
                                f"--thing {thing}", position=Position(asset=asset.id))
    if held:
        raise fail("thing.attached", f"{asset.id}'s clip {', '.join(held)} attaches {thing}, so it can't be removed",
                   owner_action=f"Decide the clip again without `attach` (kiripix decide {asset.id} clips), or remove "
                                "the clip, then remove the thing.", position=position)
    removed = sorted(p for p in folder(asset, thing).glob("*") if p.is_file())
    for path in removed:
        path.unlink()
    try:
        folder(asset, thing).rmdir()
    except OSError:
        pass
    return removed
