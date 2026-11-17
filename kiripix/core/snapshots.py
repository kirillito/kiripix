"""Snapshots (spec §10, ticket 0248): what an Asset's `sheet` Stage built, kept under a label so settings can be compared
across a cast.

A snapshot copies `sheet.json` and the colour atlas into `.kiripix/snapshots/<label>/<id>/`, with `snapshot.json`: the
parameters of every Stage the sheet was built from, and which of those Stages were not current. It records nothing in the
Project, and deleting `.kiripix/snapshots/` loses nothing that can't be built again.
"""

from __future__ import annotations

import json
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from kiripix.checks import Finding, Position
from kiripix.core import atomic
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba
from kiripix.core.project import Project
from kiripix.recipes.base import Scalar
from kiripix.recipes.character_sheet import SHEET_FILE, SHEET_SCHEMA_VERSION

SHEET_STAGE = "sheet"
SNAPSHOT_FILE = "snapshot.json"
SNAPSHOT_SCHEMA_VERSION = 1
_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")


class SnapshotNote(BaseModel):
    """`snapshot.json`: how a snapshot of one Asset was built."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    asset: str
    label: str
    params: dict[str, dict[str, Scalar]]  # by Stage, for every Stage the sheet was built from, in build order
    stale: list[str]  # the Stages among them that were not current when it was taken


@dataclass(frozen=True)
class Snapshot:
    note: SnapshotNote
    document: dict[str, Any]
    atlas: Any  # numpy array


@dataclass(frozen=True)
class SnapshotLabel:
    label: str
    assets: list[str]


def snapshots_dir(project: Project) -> Path:
    return project.state_dir / "snapshots"


def check_label(label: str) -> str:
    if not _LABEL.match(label):
        raise fail("snapshot.invalid_label", f"'{label}' is not a label: lower-case letters, digits and underscores, "
                   "starting with a letter", fix="kiripix snapshot --list")
    return label


def _label_dir(project: Project, label: str) -> Path:
    return snapshots_dir(project) / check_label(label)


def _built_from(graph: AssetGraph, stage: str) -> list[str]:
    """`stage` and every Stage upstream of it, in the Kind's order."""
    wanted: set[str] = set()
    pending = [stage]
    while pending:
        name = pending.pop()
        if name not in wanted:
            wanted.add(name)
            pending += graph.spec(name).inputs.upstream
    return [s.name for s in graph.kind.stages if s.name in wanted]


def take(project: Project, assets: list[Asset], label: str, replace: bool) -> tuple[list[SnapshotNote], list[Finding]]:
    """Snapshot each Asset's built sheet under `label`. An Asset with no built sheet is a warning and left out, and the
    others are kept. Refuses an existing label unless `replace` (which replaces only the given Assets' entries), an Asset
    whose Kind has no `sheet` Stage, and a call that kept nothing."""
    folder = _label_dir(project, label)
    if folder.exists() and not replace:
        raise fail("snapshot.label_exists", f"the label '{label}' already has snapshots: "
                   f"{', '.join(sorted(p.name for p in folder.iterdir() if p.is_dir()))}",
                   fix="kiripix snapshot <id,...> --label " + label + " --replace")
    cache = HashCache(project.state_dir)
    findings: list[Finding] = []
    notes: list[SnapshotNote] = []
    for asset in assets:
        graph = AssetGraph(project, asset, cache)
        position = Position(asset=asset.id, stage=SHEET_STAGE)
        if graph.kind.stage(SHEET_STAGE) is None:
            raise fail("snapshot.no_sheet", f"{asset.id} is a {asset.kind}, which has no {SHEET_STAGE} Stage to "
                       "snapshot", fix="kiripix snapshot character.a,character.b --label " + label, position=position)
        output = graph.output_dir(graph.spec(SHEET_STAGE))
        document: dict[str, Any] | None = None
        try:
            document = json.loads((output / SHEET_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            document = None
        if document is None or document.get("schema_version") != SHEET_SCHEMA_VERSION:
            why = "has no built sheet" if document is None else "has a sheet from an older Kiripix"
            findings.append(Finding(code="snapshot.not_built", severity="warning", position=position,
                                    message=f"{asset.id} {why}, so it is left out of the snapshot '{label}'",
                                    fix=f"kiripix run {asset.id} {SHEET_STAGE}"))
            continue
        color = output / document["files"]["color"]
        if not color.is_file():
            findings.append(Finding(code="snapshot.not_built", severity="warning", position=position,
                                    message=f"{asset.id}'s sheet has no atlas, so it is left out of the snapshot "
                                            f"'{label}'", fix=f"kiripix run {asset.id} {SHEET_STAGE}"))
            continue
        names = _built_from(graph, SHEET_STAGE)
        stale = [n for n in names if graph.state(n).status != "done"]
        note = SnapshotNote(schema_version=SNAPSHOT_SCHEMA_VERSION, asset=asset.id, label=label,
                            params={n: dict(graph.params(graph.spec(n))) for n in names}, stale=stale)
        if stale:
            findings.append(Finding(code="snapshot.stale", severity="warning", position=position,
                                    message=f"{asset.id}: {', '.join(stale)} not current; the snapshot holds the sheet "
                                            "as last built, with the parameters set now",
                                    fix=f"kiripix run {asset.id} {SHEET_STAGE}"))
        _store(folder / asset.id, output / SHEET_FILE, color, note)
        notes.append(note)
    if not notes:
        raise KiripixError([*findings, Finding(code="snapshot.empty", message="no Asset had a built sheet to snapshot; "
                                               "the findings before this say why", fix="kiripix status")])
    return notes, findings


def _store(target: Path, sheet: Path, color: Path, note: SnapshotNote) -> None:
    """Write the Asset's entry whole, into place: built beside it, then swapped in."""
    target.parent.mkdir(parents=True, exist_ok=True)
    building = target.parent / f".building-{uuid.uuid4().hex[:8]}"
    building.mkdir()
    try:
        shutil.copyfile(sheet, building / SHEET_FILE)
        shutil.copyfile(color, building / color.name)
        atomic.write_json(building / SNAPSHOT_FILE, note.model_dump())
        if target.exists():
            old = target.parent / f".old-{uuid.uuid4().hex[:8]}"
            target.rename(old)
            try:
                building.rename(target)
            except OSError:
                old.rename(target)  # the entry as it was, never none
                raise
            shutil.rmtree(old, ignore_errors=True)
        else:
            building.rename(target)
    finally:
        shutil.rmtree(building, ignore_errors=True)


def labels(project: Project) -> list[SnapshotLabel]:
    root = snapshots_dir(project)
    if not root.is_dir():
        return []
    return [SnapshotLabel(p.name, sorted(a.name for a in p.iterdir() if a.is_dir() and (a / SNAPSHOT_FILE).is_file()))
            for p in sorted(root.iterdir()) if p.is_dir() and _LABEL.match(p.name)]


def drop(project: Project, label: str) -> list[str]:
    """Delete a label with every snapshot under it; returns the Assets it held."""
    folder = _label_dir(project, label)
    if not folder.is_dir():
        raise fail("snapshot.unknown_label", f"there is no snapshot label '{label}'", fix="kiripix snapshot --list")
    held = sorted(a.name for a in folder.iterdir() if a.is_dir())
    gone = folder.with_name(f".dropped-{label}-{uuid.uuid4().hex[:8]}")
    folder.rename(gone)
    shutil.rmtree(gone, ignore_errors=True)
    return held


def require(project: Project, label: str) -> Path:
    """The label's folder, or a refusal naming the labels there are."""
    folder = _label_dir(project, label)
    if not folder.is_dir():
        known = ", ".join(entry.label for entry in labels(project)) or "none"
        raise fail("snapshot.unknown_label", f"there is no snapshot label '{label}'; the labels are {known}",
                   fix="kiripix snapshot --list")
    return folder


def read(project: Project, label: str, asset: str) -> Snapshot | None:
    """The Asset's snapshot under the label, or None when it has none."""
    folder = require(project, label) / asset
    shown = project.relative(folder / SNAPSHOT_FILE)
    if not (folder / SNAPSHOT_FILE).is_file():
        return None
    try:
        note = SnapshotNote.model_validate_json((folder / SNAPSHOT_FILE).read_text(encoding="utf-8"))
        document = json.loads((folder / SHEET_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError, ValidationError) as error:
        raise fail("snapshot.unreadable", f"{shown} can't be read: {error}",
                   fix=f"kiripix snapshot {asset} --label {label} --replace") from None
    if note.schema_version != SNAPSHOT_SCHEMA_VERSION or document.get("schema_version") != SHEET_SCHEMA_VERSION:
        raise fail("snapshot.unreadable", f"{shown} is from another Kiripix version",
                   fix=f"kiripix snapshot {asset} --label {label} --replace")
    return Snapshot(note, document, load_rgba(folder / document["files"]["color"], f"{asset}'s snapshot atlas"))
