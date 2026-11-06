"""The Exporter (spec §9, ADR 0003): writes engine files from an Asset's final outputs, under the Manifest's rules.

A room's or prop's `export` Stage leaves engine-free outputs in `out/export/`: a room's mapped Plate and `room.json` with
its shapes and Markers, a prop's sprite and `prop.json` with its origin and collision shapes. Only this package knows Godot. It sits above core and below the Commands; recipes know nothing of it.

The game's work is never overwritten (ADR 0003). A file is written only if the Manifest lists it and it still has the
listed hash. `force` backs up and overwrites an owned file the game changed; `adopt` backs up and takes over a file the
Manifest doesn't list. Every backup goes to `.kiripix/backups/<timestamp>/`, and an export plans every Asset and refuses
before it writes anything.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from kiripix.checks import Finding, Position
from kiripix.core import atomic, cancel
from kiripix.core.assets import Asset, list_assets
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.core.graph import AssetGraph, StageState
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.project import Project
from kiripix.core.project_checks import check_asset
from kiripix.export.checks import EXPORTERS, exits_naming, frozen_findings, pairing_findings
from kiripix.export.godot import prop_ids, prop_scene, room_ids, room_scene
from kiripix.export.manifest import ExportedIds, Manifest, kiripix_version, read_manifest, write_manifest
from kiripix.export.merge import apply_repairs, driver_finding, install_driver, merge_files, plan_repairs
from kiripix.export.prune import PrunePlan, PruneResult, apply_prune, plan_prune, preview
from kiripix.export.prop import SPRITE_FILE, read_prop
from kiripix.export.room import EXPORT_STAGE, PLATE_FILE, built_dir, read_room
from kiripix.export.target import GodotTarget, resolve_target


@dataclass(frozen=True)
class ExportOptions:
    force: bool = False  # back up and overwrite a file of the Manifest's that the game changed
    adopt: bool = False  # back up and take over a file the Manifest doesn't list
    dry_run: bool = False  # write nothing


@dataclass
class ExportResult:
    asset: str
    manifest: str
    counter: int
    written: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    would_write: list[str] = field(default_factory=list)  # a dry run's `written`
    backed_up: list[str] = field(default_factory=list)  # (would be, in a dry run)
    changed: list[str] = field(default_factory=list)  # refused: the game changed it; `--force` takes it
    unmanaged: list[str] = field(default_factory=list)  # refused: not the Manifest's; `--adopt` takes it
    findings: list[Finding] = field(default_factory=list)


@dataclass
class _Plan:
    asset: Asset
    files: dict[str, bytes]
    hashes: dict[str, str]
    record: Manifest
    manifest_res: str
    manifest_path: Path
    settled: bool
    on_disk: dict[str, str | None]
    backups: list[str]
    refusals: list[Finding]
    result: ExportResult


def _room_files(graph: AssetGraph, target: GodotTarget) -> tuple[dict[str, bytes], ExportedIds]:
    """The files of a room's export, by `res://` path, and the IDs they carry."""
    room = read_room(graph)
    name = graph.asset.id.split(".", 1)[1]
    folder = f"{target.root}/{graph.kind.name}/{name}"
    plate = f"{folder}/{PLATE_FILE}"
    files = {
        f"{folder}/{name}.tscn": room_scene(room, name, plate).encode("utf-8"),
        plate: (built_dir(graph) / PLATE_FILE).read_bytes(),
    }
    for layer in room["layers"]:
        files[f"{folder}/{layer['file']}"] = (built_dir(graph) / str(layer["file"])).read_bytes()
    return files, room_ids(room)


def _prop_files(graph: AssetGraph, target: GodotTarget) -> tuple[dict[str, bytes], ExportedIds]:
    """The files of a prop's export, by `res://` path, and the IDs they carry."""
    prop = read_prop(graph)
    name = graph.asset.id.split(".", 1)[1]
    folder = f"{target.root}/{graph.kind.name}/{name}"
    sprite = f"{folder}/{SPRITE_FILE}"
    files = {
        f"{folder}/{name}.tscn": prop_scene(prop, name, sprite).encode("utf-8"),
        sprite: (built_dir(graph) / SPRITE_FILE).read_bytes(),
    }
    return files, prop_ids(prop)


_FILES_BY_KIND: dict[str, Callable[[AssetGraph, GodotTarget], tuple[dict[str, bytes], ExportedIds]]] = {
    "room": _room_files, "prop": _prop_files}


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


def _conflict(res: str, current: str | None, wanted: str, manifest: Manifest | None, asset: str) -> Finding | None:
    """Why a file already there can't be overwritten, or None. The Manifest must list it (ADR 0003), with its hash, or as
    what a stopped export was writing or replacing. Overwriting the game's edits is the Owner's call, so each finding is
    an `owner_action` naming the flag."""
    if current is None:
        return None
    recorded = manifest.files.get(res) if manifest is not None else None
    if recorded is None:
        return Finding(code="export.file_unmanaged", message=f"{res} is already there, and the Manifest doesn't list it",
                       position=Position(asset=asset, file=res),
                       owner_action=f"To take it over, run: kiripix export {asset} --adopt. The file is backed up to "
                                    f".kiripix/backups/ first. Otherwise move it out of the way.")
    replacing = manifest.replacing if manifest is not None and manifest.replacing else {}
    if current in (recorded, wanted, replacing.get(res)):
        return None
    return Finding(code="export.file_changed", message=f"{res} was changed since Kiripix exported it",
                   position=Position(asset=asset, file=res),
                   owner_action=f"To overwrite your changes, run: kiripix export {asset} --force. The file is backed up "
                                f"to .kiripix/backups/ first. Otherwise move what you need into a scene of the game that "
                                f"instances {res}.")


def _plan(project: Project, asset: Asset, cache: HashCache, target: GodotTarget, options: ExportOptions) -> _Plan:
    """What exporting the Asset would do, or the refusal why not. Writes nothing."""
    if asset.kind not in _FILES_BY_KIND:
        raise fail("export.not_available", f"a {asset.kind} can't be exported yet; only rooms and props can",
                   fix="kiripix describe project")
    frozen = frozen_findings(project, asset, cache)
    if frozen:
        raise KiripixError(frozen, ExitCode.CHECK_FAILED)
    graph = _refuse_unless_ready(project, asset, cache)
    files, ids = _FILES_BY_KIND[asset.kind](graph, target)
    hashes = _hashes(files)
    manifest_res = target.manifest(asset.id)
    manifest_path = target.path(manifest_res)
    manifest = read_manifest(manifest_path, manifest_res)
    on_disk = {res: _file_hash(target.path(res)) for res in files}
    refusals: list[Finding] = []
    backups: list[str] = []
    changed: list[str] = []
    unmanaged: list[str] = []
    for res in files:
        found = _conflict(res, on_disk[res], hashes[res], manifest, asset.id)
        if found is None:
            continue
        taken = options.adopt if found.code == "export.file_unmanaged" else options.force
        if not taken:
            refusals.append(found)
            (unmanaged if found.code == "export.file_unmanaged" else changed).append(res)
        elif on_disk[res] != hashes[res]:
            backups.append(res)
    same_files = manifest is not None and manifest.files == hashes
    counter = (manifest.counter if manifest is not None else 0) + (0 if same_files else 1)
    record = Manifest(kiripix_version=kiripix_version(), asset=asset.id, exported=True, counter=counter, ids=ids,
                      files=hashes)
    settled = manifest is not None and same_files and manifest.ids == ids and not manifest.replacing
    result = ExportResult(asset.id, manifest_res, counter, changed=changed, unmanaged=unmanaged)
    result.unchanged = [res for res in files if on_disk[res] == hashes[res]]
    if options.dry_run:
        pending = [res for res in files if on_disk[res] != hashes[res] and res not in changed + unmanaged]
        result.would_write, result.backed_up = pending + ([] if settled else [manifest_res]), backups
    return _Plan(asset, files, hashes, record, manifest_res, manifest_path, settled, on_disk, backups, refusals, result)


def _backup_folder(project: Project) -> Path:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    root = project.state_dir / "backups"
    folder = root / stamp
    number = 1
    while folder.exists():
        number += 1
        folder = root / f"{stamp}-{number}"
    return folder


def _apply(plan: _Plan, target: GodotTarget, backup: Path) -> None:
    """Back up what is taken over, then write. The Manifest goes first, listing the new hashes and what they replace, and
    again once the files are written; so a stop at any point leaves only files a second run accepts as its own."""
    for res in plan.backups:
        cancel.check()
        atomic.write_bytes(backup / (target.folder.resolve().name or "godot") / res.removeprefix("res://"),
                           target.path(res).read_bytes())
    written = [res for res in plan.files if plan.on_disk[res] != plan.hashes[res]]
    if not plan.settled and written:
        replaced = {res: before for res in written if (before := plan.on_disk[res]) is not None}
        write_manifest(plan.manifest_path, plan.record.model_copy(update={"replacing": replaced}))
    for res in written:
        cancel.check()
        atomic.write_bytes(target.path(res), plan.files[res])
    if not plan.settled:
        write_manifest(plan.manifest_path, plan.record)
    plan.result.written, plan.result.backed_up = written, plan.backups


@dataclass
class ExportRun:
    results: list[ExportResult]
    pruned: list[PruneResult]
    findings: list[Finding]


def prune_assets(project: Project, only: str | None, options: ExportOptions) -> ExportRun:
    """Prune every deleted Asset's files and Manifest, or just `only`'s (which must not exist). Exports nothing. The caller
    holds the project lock. Planned in full before anything is removed: one changed file refuses them all."""
    target = resolve_target(project)
    return _commit(project, target, [], plan_prune(project, target, only, options.force), options, [])


def _commit(project: Project, target: GodotTarget, plans: list[_Plan], prunes: list[PrunePlan], options: ExportOptions,
            warnings: list[Finding]) -> ExportRun:
    """Apply what was planned, or in a dry run only say what would be done. Exports first, then prunes."""
    findings = list(warnings)
    if prunes:
        every = list_assets(project)[0]
        findings.extend(exits_naming(project, every, {doomed.asset for doomed in prunes}))
    refusals = [finding for plan in plans for finding in plan.refusals]
    refusals += [finding for doomed in prunes for finding in doomed.refusals]
    if options.dry_run:
        # a refusal is only a warning in a dry run: it stops nothing, and says what the real export would need
        findings.extend(f.model_copy(update={"severity": "warning"}) for f in refusals)
        for doomed in prunes:
            preview(doomed)
    else:
        if refusals:
            raise KiripixError(refusals, ExitCode.NEEDS_OWNER)
        backup = _backup_folder(project)
        for plan in plans:
            _apply(plan, target, backup)
        for prune in prunes:
            apply_prune(prune, target, backup)
    return ExportRun([plan.result for plan in plans], [doomed.result for doomed in prunes], findings)


def export_assets(project: Project, assets: list[Asset] | None, cache: HashCache, options: ExportOptions,
                  prune: bool = False) -> ExportRun:
    """Export `assets`, or every Asset with an exporter when None (`--all`). The caller holds the project and Asset locks.

    Every Asset is planned before any file is written: one refusal (an Asset not built, a frozen ID, a file the game
    owns) stops them all with nothing changed. With `--all`, Exit pairing must hold or nothing is exported; for one
    Asset it is only a warning. With `prune` (only with `--all`) the deleted Assets' files are planned too, and removed
    after the exports are written. Returns the results and the findings of the call."""
    for asset in assets or []:
        if asset.kind not in _FILES_BY_KIND:
            raise fail("export.not_available", f"a {asset.kind} can't be exported yet; only rooms and props can",
                       fix="kiripix describe project")
    target = resolve_target(project)
    prunes = plan_prune(project, target, None, options.force) if prune else []
    every, broken = list_assets(project)
    if broken and assets is None:
        raise KiripixError(broken)
    warnings: list[Finding] = []
    if (missing := driver_finding(target)) is not None:
        warnings.append(missing)
    if assets is None:
        assets = [asset for asset in every if asset.kind in EXPORTERS]
        errors = pairing_findings(project, every)
        if errors:
            raise KiripixError(errors, ExitCode.CHECK_FAILED)
    else:
        warnings += pairing_findings(project, every, only=assets[0].id, severity="warning") if len(assets) == 1 else []
    plans: list[_Plan] = []
    refused: list[Finding] = []
    code = ExitCode.ERROR
    for asset in assets:
        cancel.check()
        try:
            plans.append(_plan(project, asset, cache, target, options))
        except KiripixError as error:
            refused.extend(error.findings)
            code = max(code, error.exit_code)
    if refused:
        raise KiripixError(refused, code)
    return _commit(project, target, plans, prunes, options, warnings)


def export_pending(project: Project, asset: Asset, cache: HashCache) -> bool:
    """Whether a fully built Asset has something the game doesn't have yet. A target that can't be used counts as yes:
    `export` then says why."""
    if asset.kind not in _FILES_BY_KIND:
        return False
    try:
        target = resolve_target(project)
        manifest_res = target.manifest(asset.id)
        manifest = read_manifest(target.path(manifest_res), manifest_res)
    except KiripixError:
        return True
    if manifest is None:
        return True
    files, _ = _FILES_BY_KIND[asset.kind](AssetGraph(project, asset, cache), target)
    return manifest.files != _hashes(files) or bool(manifest.replacing)


def export_command(project: Project, asset: Asset, cache: HashCache, states: list[StageState] | None = None) -> str | None:
    """The Command that brings the game up to date, once every Stage is done and it is behind; else None. A `done` export
    Stage only means its outputs are built: this is what tells that from being in the game. Derived, never stored. A caller
    that has just worked out the Asset's `states` passes them, since that is most of the cost of a refresh."""
    if asset.kind not in _FILES_BY_KIND:
        return None
    command = f"kiripix export {asset.id}"
    try:
        built = all(state.status == "done" for state in states or AssetGraph(project, asset, cache).states())
        return command if built and export_pending(project, asset, cache) else None
    except KiripixError:
        return command  # `export` says what's wrong


__all__ = ["EXPORT_STAGE", "EXPORTERS", "ExportOptions", "ExportResult", "ExportRun", "PruneResult", "export_assets",
           "export_command", "export_pending", "frozen_findings", "install_driver", "merge_files", "pairing_findings",
           "apply_repairs", "plan_repairs", "prune_assets", "resolve_target"]
