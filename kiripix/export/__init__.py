"""The Exporter (spec §9, ADR 0003): writes engine files from an Asset's final outputs, under the Manifest's rules.

A room's `export` Stage leaves engine-free outputs in `out/export/`: the mapped Plate, and `room.json` with its shapes and
Markers. Only this package knows Godot. It sits above core and below the Commands; recipes know nothing of it.
"""

import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from kiripix.checks import Finding, Position
from kiripix.core import atomic, cancel
from kiripix.core.assets import Asset
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.project import Project
from kiripix.core.project_checks import check_asset
from kiripix.export.godot import exported_markers, room_scene
from kiripix.export.manifest import MANIFEST_DIR, ExportedIds, Manifest, kiripix_version, read_manifest, write_manifest

EXPORT_STAGE = "export"
_RES = "res://"
_ROOM_FILE = "room.json"
_ROOM_SCHEMA_VERSION = 1
_PLATE_FILE = "plate.png"


@dataclass(frozen=True)
class GodotTarget:
    """Where an export goes: the Godot project's folder, and the export root inside it as `res://...`."""

    folder: Path
    root: str

    def path(self, res: str) -> Path:
        return self.folder / res.removeprefix(_RES)

    def manifest(self, asset_id: str) -> str:
        return f"{self.root}/{MANIFEST_DIR}/{asset_id}.json"


@dataclass(frozen=True)
class ExportResult:
    written: list[str]
    unchanged: list[str]
    manifest: str
    counter: int


def _target(project: Project) -> GodotTarget:
    godot = project.settings.export.godot
    if godot.project is None:
        raise fail("export.no_target", "no Godot project to export into",
                   owner_action="Set project under [export.godot] in kiripix.toml to the Godot project's folder.",
                   exit_code=ExitCode.NEEDS_OWNER)
    root = godot.root.rstrip("/")
    parts = PurePosixPath(root.removeprefix(_RES)).parts
    if not root.startswith(_RES) or not parts or ".." in parts:
        raise fail("export.bad_root", f"the export root '{godot.root}' isn't a folder inside the Godot project",
                   owner_action="Set root under [export.godot] in kiripix.toml to a folder such as res://kiripix.")
    folder = project.root / godot.project
    if not (folder / "project.godot").is_file():
        raise fail("export.no_project", f"no Godot project at '{godot.project}': it has no project.godot",
                   owner_action="Clone the game there, or fix project under [export.godot] in kiripix.toml.",
                   exit_code=ExitCode.NEEDS_OWNER)
    return GodotTarget(folder, root)


def _room_files(graph: AssetGraph, target: GodotTarget) -> tuple[dict[str, bytes], ExportedIds]:
    """The files of a room's export, by `res://` path, and the IDs they carry."""
    built = graph.output_dir(graph.spec(EXPORT_STAGE))
    room = json.loads((built / _ROOM_FILE).read_text(encoding="utf-8"))
    if room.get("schema_version") != _ROOM_SCHEMA_VERSION:
        raise fail("export.room_invalid", f"{graph.asset.id}'s {_ROOM_FILE} has schema_version "
                   f"{room.get('schema_version')}; this Kiripix reads {_ROOM_SCHEMA_VERSION}",
                   fix=f"kiripix run {graph.asset.id} {EXPORT_STAGE} --force")
    name = graph.asset.id.split(".", 1)[1]
    folder = f"{target.root}/{graph.kind.name}/{name}"
    plate = f"{folder}/{_PLATE_FILE}"
    files = {
        f"{folder}/{name}.tscn": room_scene(room, name, plate).encode("utf-8"),
        plate: (built / _PLATE_FILE).read_bytes(),
    }
    ids = ExportedIds(markers=sorted(str(marker["id"]) for marker in exported_markers(room)), layers=["plate"],
                      masks=sorted(room["collision"]))
    return files, ids


_FILES_BY_KIND = {"room": _room_files}


def _hashes(files: dict[str, bytes]) -> dict[str, str]:
    return {res: hash_bytes(content) for res, content in files.items()}


def _refuse_unless_ready(project: Project, asset: Asset, cache: HashCache) -> AssetGraph:
    """The Asset's graph, once it is known to be fully built and to pass its Checks (spec, principle 7)."""
    graph = AssetGraph(project, asset, cache)
    for state in graph.states():
        if state.status != "done":
            why = f" ({state.reason})" if state.reason else ""
            raise fail("export.not_ready", f"{asset.id} {state.stage} is {state.status}{why}", fix=f"kiripix next {asset.id}",
                       position=Position(asset=asset.id, stage=state.stage),
                       exit_code=ExitCode.NEEDS_OWNER if state.status in ("needs-input", "needs-review") else ExitCode.ERROR)
    errors = [finding for finding in check_asset(project, asset, cache)[1] if finding.severity == "error"]
    if errors:
        raise KiripixError(errors, ExitCode.CHECK_FAILED)
    return graph


def _file_hash(path: Path) -> str | None:
    try:
        return hash_bytes(path.read_bytes())
    except FileNotFoundError:
        return None


def _conflict(res: str, current: str | None, wanted: str, manifest: Manifest | None) -> Finding | None:
    """Why a file already there can't be overwritten, or None. The Manifest must list it (ADR 0003), with its hash, or as
    what a stopped export was writing or replacing."""
    if current is None:
        return None
    keep = f"Move what you need from {res} into a scene of the game that instances it, then delete {res} and export again."
    recorded = manifest.files.get(res) if manifest is not None else None
    if recorded is None:
        return Finding(code="export.file_unmanaged", message=f"{res} is already there, and the Manifest doesn't list it",
                       position=Position(file=res), owner_action=keep)
    replacing = manifest.replacing if manifest is not None and manifest.replacing else {}
    if current in (recorded, wanted, replacing.get(res)):
        return None
    return Finding(code="export.file_changed", message=f"{res} was changed since Kiripix exported it",
                   position=Position(file=res), owner_action=keep)


def export_asset(project: Project, asset: Asset, cache: HashCache) -> ExportResult:
    """Write the Asset's files and its Manifest into the Godot project, or refuse before writing anything. The caller
    holds the project and Asset locks. The Manifest goes first, listing the new hashes and what they replace, and again
    once the files are written; so a stop at any point leaves only files a second run accepts as its own."""
    if asset.kind not in _FILES_BY_KIND:
        raise fail("export.not_available", f"a {asset.kind} can't be exported yet; only rooms can",
                   fix="kiripix describe project")
    target = _target(project)
    graph = _refuse_unless_ready(project, asset, cache)
    files, ids = _FILES_BY_KIND[asset.kind](graph, target)
    hashes = _hashes(files)
    manifest_res = target.manifest(asset.id)
    manifest_path = target.path(manifest_res)
    manifest = read_manifest(manifest_path, manifest_res)
    on_disk = {res: _file_hash(target.path(res)) for res in files}
    conflicts = [found for res in files if (found := _conflict(res, on_disk[res], hashes[res], manifest))]
    if conflicts:
        raise KiripixError(conflicts, ExitCode.NEEDS_OWNER)
    unchanged = [res for res in files if on_disk[res] == hashes[res]]
    written = [res for res in files if on_disk[res] != hashes[res]]
    settled = manifest is not None and manifest.files == hashes and manifest.ids == ids and not manifest.replacing
    same_files = manifest is not None and manifest.files == hashes
    counter = (manifest.counter if manifest is not None else 0) + (0 if same_files else 1)
    record = Manifest(kiripix_version=kiripix_version(), asset=asset.id, exported=True, counter=counter, ids=ids,
                      files=hashes)
    if not settled and written:
        replaced = {res: before for res in written if (before := on_disk[res]) is not None}
        write_manifest(manifest_path, record.model_copy(update={"replacing": replaced}))
    for res in written:
        cancel.check()
        atomic.write_bytes(target.path(res), files[res])
    if not settled:
        write_manifest(manifest_path, record)
    return ExportResult(written, unchanged, manifest_res, counter)


def export_pending(project: Project, asset: Asset, cache: HashCache) -> bool:
    """Whether a fully built Asset has something the game doesn't have yet. A target that can't be used counts as yes:
    `export` then says why."""
    if asset.kind not in _FILES_BY_KIND:
        return False
    try:
        target = _target(project)
        manifest_res = target.manifest(asset.id)
        manifest = read_manifest(target.path(manifest_res), manifest_res)
    except KiripixError:
        return True
    if manifest is None:
        return True
    files, _ = _FILES_BY_KIND[asset.kind](AssetGraph(project, asset, cache), target)
    return manifest.files != _hashes(files) or bool(manifest.replacing)


__all__ = ["EXPORT_STAGE", "ExportResult", "export_asset", "export_pending"]
