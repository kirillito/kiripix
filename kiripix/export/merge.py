"""Branch merges of the Manifest (spec §9, ADR 0003, ticket 0049).

When two game branches export the same Asset, git can't merge its Manifest by text. `kiripix manifest merge` is the git
merge driver that does: the counter is the higher plus one, the IDs are the union (an ID frozen on either branch stays
frozen), `exported` is either's, and `files` keeps ours, with theirs in `replacing` so the next export accepts either.
`manifest install` sets the driver up in the game's clone; `manifest repair` applies the same rule to a Manifest that was
committed with conflict markers in it (GitHub never runs a custom driver).
"""

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from kiripix.checks import Finding
from kiripix.core import atomic
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.export.manifest import (
    MANIFEST_DIR, MANIFEST_SCHEMA_VERSION, ExportedIds, Manifest, has_conflict_markers, write_manifest,
)
from kiripix.export.target import GodotTarget

DRIVER = "kiripix-manifest"
INSTALL_FIX = "kiripix manifest install"
_GIT_TIMEOUT = 20


def _union(first: list[str], second: list[str]) -> list[str]:
    return first + [item for item in second if item not in first]


def merge_manifests(ours: Manifest, theirs: Manifest) -> Manifest:
    """The merge of two branches' Manifests of one Asset (ticket 0049). Pure."""
    if ours.asset != theirs.asset:
        raise ValueError(f"the two sides are the Manifests of different Assets: {ours.asset} and {theirs.asset}")
    files = {**theirs.files, **ours.files}  # a file only theirs lists is still the Manifest's
    replacing: dict[str, str] = {**(theirs.replacing or {}), **(ours.replacing or {})}
    for res, hashed in theirs.files.items():
        if res in ours.files and ours.files[res] != hashed:
            replacing[res] = hashed
    ids = ExportedIds(markers=_union(ours.ids.markers, theirs.ids.markers),
                      layers=_union(ours.ids.layers, theirs.ids.layers),
                      masks=_union(ours.ids.masks, theirs.ids.masks))
    return Manifest(kiripix_version=ours.kiripix_version, asset=ours.asset, exported=ours.exported or theirs.exported,
                    counter=max(ours.counter, theirs.counter) + 1, ids=ids, files=files, replacing=replacing or None)


def _parse(data: bytes, side: str, shown: str) -> Manifest:
    """One side of a merge, or the refusal why it can't be read. A newer `schema_version` is named as such."""
    try:
        value = json.loads(data)
    except ValueError as error:
        raise _unreadable(shown, side, f"it isn't JSON: {error}") from None
    version = value.get("schema_version") if isinstance(value, dict) else None
    if isinstance(version, int) and version > MANIFEST_SCHEMA_VERSION:
        raise _unreadable(shown, side, f"its schema_version {version} is newer than this Kiripix reads "
                                       f"({MANIFEST_SCHEMA_VERSION}); upgrade Kiripix")
    try:
        return Manifest.model_validate(value)
    except ValidationError as error:
        raise _unreadable(shown, side, str(error)) from None


def _unreadable(shown: str, side: str, why: str) -> KiripixError:
    return fail("manifest.merge_unreadable", f"the {side} Manifest {shown} can't be merged: {why}",
                owner_action=f"Resolve {shown} by hand in git (or upgrade Kiripix if a newer one wrote it). "
                             "Nothing was changed.")


def merge_files(ours_path: Path, theirs_path: Path) -> Manifest:
    """Merge `theirs_path` into `ours_path`, written atomically. Unreadable input leaves `ours_path` alone and raises."""
    shown = ours_path.name
    try:
        ours_bytes, theirs_bytes = ours_path.read_bytes(), theirs_path.read_bytes()
    except OSError as error:
        raise fail("manifest.merge_unreadable", f"can't read the Manifests to merge: {error}",
                   owner_action=f"Resolve {shown} by hand in git. Nothing was changed.") from None
    ours = _parse(ours_bytes, "our", shown)
    theirs = _parse(theirs_bytes, "their", shown)
    try:
        merged = merge_manifests(ours, theirs)
    except ValueError as error:
        raise _unreadable(shown, "merged", str(error)) from None
    write_manifest(ours_path, merged)
    return merged


# conflict markers


def split_conflict(data: bytes) -> tuple[bytes, bytes]:
    """The two whole versions a conflicted file holds: ours (the first part of each conflict) and theirs (the second).
    A diff3 base part is dropped."""
    ours: list[bytes] = []
    theirs: list[bytes] = []
    state = "both"
    for line in data.splitlines(keepends=True):
        if state == "both" and line.startswith(b"<<<<<<< "):
            state = "ours"
        elif state == "ours" and line.startswith(b"||||||| "):
            state = "base"
        elif state in ("ours", "base") and line.startswith(b"=======") and line.rstrip(b"\r\n") == b"=======":
            state = "theirs"
        elif state == "theirs" and line.startswith(b">>>>>>> "):
            state = "both"
        else:
            if state in ("both", "ours"):
                ours.append(line)
            if state in ("both", "theirs"):
                theirs.append(line)
    return b"".join(ours), b"".join(theirs)


@dataclass
class Repair:
    path: Path
    res: str
    merged: Manifest


def plan_repairs(target: GodotTarget) -> list[Repair]:
    """Every Manifest under the export root that has conflict markers, merged by the same rule. Nothing is written, and
    one that can't be repaired refuses them all."""
    folder = target.path(f"{target.root}/{MANIFEST_DIR}")
    paths = sorted(folder.glob("*.json")) if folder.is_dir() else []
    plans: list[Repair] = []
    refused: list[Finding] = []
    for path in paths:
        res = f"{target.root}/{MANIFEST_DIR}/{path.name}"
        try:
            data = path.read_bytes()
            if not has_conflict_markers(data):
                continue
            ours, theirs = split_conflict(data)
            merged = merge_manifests(_parse(ours, "our", res), _parse(theirs, "their", res))
        except KiripixError as error:
            refused.extend(error.findings)
        except (OSError, ValueError) as error:
            refused.append(Finding(code="manifest.repair_failed", message=f"{res} can't be repaired: {error}",
                                   owner_action=f"Resolve {res} by hand in git."))
        else:
            plans.append(Repair(path, res, merged))
    if refused:
        raise KiripixError(refused, ExitCode.ERROR)
    return plans


def apply_repairs(plans: list[Repair]) -> None:
    for plan in plans:
        write_manifest(plan.path, plan.merged)


# git


def _git(folder: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """Run git in the game's folder; None when git can't be run."""
    try:
        return subprocess.run(["git", "-C", str(folder), *args], capture_output=True, text=True, encoding="utf-8",
                              timeout=_GIT_TIMEOUT, stdin=subprocess.DEVNULL, check=False)
    except (OSError, subprocess.SubprocessError):
        return None


def in_git_repo(folder: Path) -> bool:
    done = _git(folder, "rev-parse", "--is-inside-work-tree")
    return done is not None and done.returncode == 0 and done.stdout.strip() == "true"


def driver_installed(target: GodotTarget) -> bool | None:
    """Whether the game's clone has the driver configured and the Manifests attributed to it. None when the game isn't
    a git repo or git can't be run: then there is nothing to say."""
    if not in_git_repo(target.folder):
        return None
    configured = _git(target.folder, "config", "--get", f"merge.{DRIVER}.driver")
    if configured is None or configured.returncode != 0 or not configured.stdout.strip():
        return False
    probe = f"{target.root.removeprefix('res://')}/{MANIFEST_DIR}/probe.json"
    attr = _git(target.folder, "check-attr", "merge", "--", probe)
    return attr is not None and attr.returncode == 0 and attr.stdout.strip().endswith(f": merge: {DRIVER}")


def driver_finding(target: GodotTarget) -> Finding | None:
    """The warning export gives when the game is a git repo without the driver (spec §9)."""
    if driver_installed(target) is not False:
        return None
    return Finding(code="export.merge_driver_missing", severity="warning",
                   message="the game's clone has no Manifest merge driver, so two branches that export the same Asset "
                           "will conflict in its Manifest (`.gitattributes` alone does nothing; the clone needs the "
                           "driver configured)",
                   fix=INSTALL_FIX)


GITATTRIBUTES = ".gitattributes"


def driver_command() -> str:
    """What git runs for the driver: this interpreter, by its full path, so it needs no `kiripix` on git's PATH."""
    python = sys.executable.replace("\\", "/")
    return f'"{python}" -m kiripix manifest merge %O %A %B'


def install_driver(target: GodotTarget) -> list[str]:
    """Write `<root>/manifest/.gitattributes` and set the driver in the clone's config. Returns what was changed, as
    paths relative to the game's folder or `git config`."""
    if _git(target.folder, "--version") is None:
        raise fail("manifest.no_git", "git can't be run", owner_action="Install git, and put it on the PATH.")
    if not in_git_repo(target.folder):
        raise fail("manifest.not_git", f"the Godot project at {target.folder} isn't in a git repository",
                   owner_action="Install the driver in the game's own clone, once the game is a git repository.")
    changed: list[str] = []
    attributes = target.path(f"{target.root}/{MANIFEST_DIR}/{GITATTRIBUTES}")
    line = f"*.json merge={DRIVER}\n"
    current = attributes.read_text("utf-8") if attributes.is_file() else None
    if current is None or line.strip() not in current.splitlines():
        # the game may have lines of its own in it: add ours, never replace
        kept = "" if not current else current if current.endswith("\n") else current + "\n"
        atomic.write_text(attributes, kept + line)
        changed.append(f"{target.root}/{MANIFEST_DIR}/{GITATTRIBUTES}")
    command = driver_command()
    have = _git(target.folder, "config", "--get", f"merge.{DRIVER}.driver")
    if have is None or have.stdout.strip() != command:
        for key, value in ((f"merge.{DRIVER}.name", "The Kiripix Manifest merge"), (f"merge.{DRIVER}.driver", command)):
            done = _git(target.folder, "config", "--local", key, value)
            if done is None or done.returncode != 0:
                raise fail("manifest.git_config_failed", f"git config {key} failed: "
                                                         f"{done.stderr.strip() if done else 'git can not be run'}",
                           owner_action="Check the game's .git/config is writable.")
        changed.append("git config")
    return changed
