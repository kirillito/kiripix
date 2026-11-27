"""`export --prune` (spec §9, ADR 0003, ticket 0048): a deleted Asset's files leave the game, under the hash rule.

A Manifest whose Asset isn't in the Project is a deleted Asset's. Each file it lists is removed only if its current hash is
the listed one (or the one a stopped export was replacing); a changed file refuses, and `--force` backs it up first. The
Manifest goes last, so a stopped prune can run again. Files the Manifest doesn't list are never looked at. A removed
file's Godot `.import` sidecar goes with it (ticket 0250), and the folders left empty after.
"""

from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from kiripix.checks import Finding, Position
from kiripix.core import atomic, cancel
from kiripix.core.assets import ASSET_FILE, asset_dir, is_asset_id, parse_asset_id
from kiripix.core.errors import fail
from kiripix.core.hashing import hash_bytes
from kiripix.core.match import matches
from kiripix.core.project import Project
from kiripix.export.manifest import MANIFEST_DIR, Manifest, read_manifest
from kiripix.export.target import GodotTarget

SIDECAR = ".import"  # Godot's import settings, beside a file it imported


@dataclass
class PruneResult:
    asset: str
    manifest: str
    removed: list[str] = field(default_factory=list)
    would_remove: list[str] = field(default_factory=list)  # a dry run's `removed`
    backed_up: list[str] = field(default_factory=list)  # (would be, in a dry run)
    changed: list[str] = field(default_factory=list)  # refused: the game changed it; `--force` takes it


@dataclass
class PrunePlan:
    asset: str
    manifest_res: str
    files: list[str]  # the listed files, in `res://` order
    present: list[str]  # those still there to remove
    backups: list[str]
    refusals: list[Finding]
    result: PruneResult


def _exists(project: Project, asset_id: str) -> bool:
    kind, name = parse_asset_id(asset_id)
    return (asset_dir(project, kind, name) / ASSET_FILE).is_file()


def _hash(path: Path) -> str | None:
    try:
        return hash_bytes(path.read_bytes())
    except FileNotFoundError:
        return None


def deleted_assets(project: Project, target: GodotTarget) -> list[str]:
    """The IDs of the Manifests under the export root whose Asset is no longer in the Project, sorted."""
    folder = target.path(f"{target.root}/{MANIFEST_DIR}")
    if not folder.is_dir():
        return []
    ids = [path.stem for path in folder.glob("*.json") if is_asset_id(path.stem)]
    return sorted(asset_id for asset_id in ids if not _exists(project, asset_id))


def _inside(res: str, folder: str) -> bool:
    parts = PurePosixPath(res.removeprefix(f"{folder}/")).parts
    return res.startswith(f"{folder}/") and bool(parts) and ".." not in parts and "\\" not in res


def _in_former_sound_folder(res: str, manifest: Manifest) -> bool:
    """A sound's file in the folder it was exported to before `[sound] folder` changed: an OGG directly in its use's folder
    (`<folder>/<use>/<name>.ogg`) inside the Godot project, as export writes them."""
    assert manifest.sound is not None
    path = PurePosixPath(res.removeprefix("res://"))
    return (res.startswith("res://") and "\\" not in res and ".." not in path.parts and len(path.parts) >= 3
            and path.suffix == ".ogg" and path.parent.name == manifest.sound.use)


def _owned(manifest: Manifest, target: GodotTarget, shown: str) -> list[str]:
    """The listed files, each checked to lie inside the export root, or, for a sound's, inside the `[sound] folder` (ADR 0016):
    a Manifest is the game's file, and what it lists must never lead outside what Kiripix owns."""
    for res in manifest.files:
        if _inside(res, target.root):
            continue
        if manifest.sound is not None and (_in_former_sound_folder(res, manifest) or _inside(res, target.sound_files_folder())):
            continue
        outside = target.root if manifest.sound is None else f"{target.root} or {target.sound_folder}"
        raise fail("export.manifest_invalid", f"the Manifest {shown} lists {res}, which isn't inside {outside}",
                   owner_action=f"Restore {shown} from the game's git history; nothing was removed.")
    return sorted(manifest.files)


def plan_prune(project: Project, target: GodotTarget, only: str | None, force: bool,
               match: str | None = None) -> list[PrunePlan]:
    """What pruning every deleted Asset (or just `only`) would do, or the refusal why not. Writes nothing."""
    if only is not None:
        parse_asset_id(only)
        if _exists(project, only):
            raise fail("export.asset_exists", f"{only} is still in the Project, so there is nothing to prune",
                       owner_action=f"Delete the Asset first if the game shouldn't have it any more, then run: "
                                    f"kiripix export {only} --prune. To update it instead, run: kiripix export {only}.",
                       position=Position(asset=only))
        if only not in deleted_assets(project, target):
            raise fail("export.not_exported", f"{only} has no Manifest in the game, so there is nothing to prune",
                       owner_action="Nothing was exported for this Asset, or it was pruned already.",
                       position=Position(asset=only))
        ids = [only]
    else:
        ids = [i for i in deleted_assets(project, target) if match is None or matches(i, match)]
    plans: list[PrunePlan] = []
    for asset_id in ids:
        cancel.check()
        shown = target.manifest(asset_id)
        manifest = read_manifest(target.path(shown), shown)
        if manifest is None:
            continue
        files = _owned(manifest, target, shown)
        replacing = manifest.replacing or {}
        result = PruneResult(asset_id, shown)
        present: list[str] = []
        backups: list[str] = []
        refusals: list[Finding] = []
        for res in files:
            current = _hash(target.path(res))
            if current is None:
                continue
            present.append(res)
            if current in (manifest.files[res], replacing.get(res)):
                continue
            if force:
                backups.append(res)
            else:
                result.changed.append(res)
                refusals.append(Finding(
                    code="export.file_changed", message=f"{res} was changed since Kiripix exported it",
                    position=Position(asset=asset_id, file=res),
                    owner_action=f"To remove it anyway, run: kiripix export --prune --force. The file is backed up to "
                                 f".kiripix/backups/ first. Otherwise move what you need out of {res}, or into a scene of "
                                 f"the game."))
        plans.append(PrunePlan(asset_id, shown, files, present, backups, refusals, result))
    return plans


def preview(plan: PrunePlan) -> None:
    """Fill the plan's result as a dry run's: what would go, and what would be backed up."""
    refused = set(plan.result.changed)
    plan.result.would_remove = [res for res in plan.present if res not in refused] + [plan.manifest_res]
    plan.result.backed_up = plan.backups


def _drop_empty_folders(plan: PrunePlan, target: GodotTarget) -> None:
    """Remove the folders a prune left empty, up to but not including the export root or the sound folder."""
    stops = {target.path(target.root), target.path(target.sound_folder)}
    for res in [plan.manifest_res, *plan.files]:
        folder = target.path(res).parent
        while folder not in stops and any(stop in folder.parents for stop in stops):
            try:
                folder.rmdir()  # only an empty folder goes
            except OSError:
                break
            folder = folder.parent


def apply_prune(plan: PrunePlan, target: GodotTarget, backup: Path) -> None:
    """Back up what the game changed, remove the files, then the Manifest, then the folders left empty."""
    backed_up = backup / (target.folder.resolve().name or "godot")

    def back_up(res: str) -> None:
        atomic.write_bytes(backed_up / res.removeprefix("res://"), target.path(res).read_bytes())

    for res in plan.backups:
        cancel.check()
        back_up(res)
    for res in plan.present:
        cancel.check()
        target.path(res).unlink(missing_ok=True)
        # Godot's `.import` sidecar of a pruned file goes with it (and is backed up with it); Godot makes it again, so the
        # Manifest never owned it, and only a pruned file's sidecar is touched.
        sidecar = target.path(res + SIDECAR)
        if sidecar.is_file():
            if res in plan.backups:
                back_up(res + SIDECAR)
            sidecar.unlink(missing_ok=True)
    target.path(plan.manifest_res).unlink(missing_ok=True)
    _drop_empty_folders(plan, target)
    plan.result.removed = [*plan.present, plan.manifest_res]
    plan.result.backed_up = plan.backups
