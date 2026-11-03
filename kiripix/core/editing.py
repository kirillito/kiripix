"""Changing an Asset's decisions: `set` writes Stage parameters, `decide`, `undo` and `redo` append to the journal.

The caller holds the Asset lock. Everything is validated before anything is written, so a refused call changes nothing.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, ValidationError

from kiripix.checks import Finding, Position
from kiripix.core import journal
from kiripix.core.assets import ASSET_FILE, Asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.core.settings import save_settings
from kiripix.recipes.base import ParamSpec, Scalar, StageSpec


def _graph(project: Project, asset: Asset) -> AssetGraph:
    return AssetGraph(project, asset, HashCache(project.state_dir))


# set


def _range(param: ParamSpec) -> str:
    if param.choices is not None:
        return f"one of {', '.join(param.choices)}"
    if param.minimum is not None and param.maximum is not None:
        return f"{param.minimum:g} to {param.maximum:g}"
    if param.minimum is not None:
        return f"at least {param.minimum:g}"
    if param.maximum is not None:
        return f"at most {param.maximum:g}"
    return param.type


def _parse(param: ParamSpec, text: str) -> Scalar | None:
    """The text as the parameter's type, or None if it isn't one."""
    try:
        if param.type == "int":
            return int(text)
        if param.type == "float":
            return float(text)
    except ValueError:
        return None
    if param.type == "bool":
        return {"true": True, "false": False}.get(text.lower())
    return text


def set_params(project: Project, asset: Asset, stage: str, assignments: Sequence[str]) -> dict[str, Scalar]:
    """Write `[stages.<stage>]` in `asset.toml` and return the Stage's parameters as set."""
    graph = _graph(project, asset)
    spec = graph.spec(stage)
    declared = {p.name: p for p in spec.params}
    file = project.relative(asset.dir / ASSET_FILE)
    values: dict[str, Scalar] = {}
    findings: list[Finding] = []
    for assignment in assignments:
        name, equals, text = assignment.partition("=")
        if not equals or not name:
            findings.append(
                Finding(
                    code="set.invalid_assignment",
                    message=f"'{assignment}' is not key=value",
                    position=Position(asset=asset.id, stage=stage),
                    fix=f"kiripix describe {asset.kind}",
                )
            )
            continue
        position = Position(asset=asset.id, stage=stage, file=file, field=f"stages.{stage}.{name}")
        param = declared.get(name)
        if param is None:
            known = ", ".join(declared) or "none"
            findings.append(
                Finding(
                    code="set.unknown_parameter",
                    message=f"the Stage '{stage}' has no parameter '{name}'; its parameters are {known}",
                    position=position,
                    fix=f"kiripix describe {asset.kind}",
                )
            )
            continue
        value = _parse(param, text)
        problem = f"expected {param.type}, got {text!r}" if value is None else param.problem(value)
        if value is None or problem:
            findings.append(
                Finding(
                    code="set.invalid_value",
                    message=f"{stage}.{name}: {problem} (valid: {_range(param)})",
                    position=position,
                    fix=f"kiripix describe {asset.kind}",
                )
            )
            continue
        values[name] = value
    if findings:
        raise KiripixError(findings)
    stages = {name: dict(table) for name, table in asset.settings.stages.items()}
    stages.setdefault(stage, {}).update(values)
    save_settings(asset.dir / ASSET_FILE, asset.settings.model_copy(update={"stages": stages}))
    return stages[stage]


# the journal


class DecisionDocument(BaseModel):
    """A Decision as given to `decide`: its name, its data, and the image hash a click or Override was made on."""

    model_config = ConfigDict(extra="forbid")

    decision: str
    data: dict[str, Any]
    image_hash: str | None = None


def parse_decision(text: str, source: str, asset: Asset, stage: str) -> DecisionDocument:
    position = Position(asset=asset.id, stage=stage)
    try:
        return DecisionDocument.model_validate(json.loads(text))
    except json.JSONDecodeError as error:
        raise fail("decide.invalid_json", f"{source} is not JSON: {error}", position=position,
                   fix=f"kiripix describe {asset.kind}") from None
    except ValidationError as error:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'the Decision'}: {e['msg']}" for e in error.errors())
        raise fail("decide.invalid", f"{source} is not {{\"decision\": name, \"data\": {{...}}}}: {problems}",
                   position=position, fix=f"kiripix describe {asset.kind}") from None


def _entry_findings(spec: StageSpec, asset: Asset, document: DecisionDocument) -> list[Finding]:
    declared = next((d for d in spec.decisions if d.name == document.decision), None)
    if declared is None:
        known = ", ".join(d.name for d in spec.decisions) or "none"
        return [
            Finding(
                code="decision.unknown",
                message=f"the Stage '{spec.name}' takes no Decision '{document.decision}'; it takes {known}",
                position=Position(asset=asset.id, stage=spec.name),
                fix=f"kiripix describe {asset.kind}",
            )
        ]
    findings = []
    for error in sorted(Draft202012Validator(declared.entry_schema).iter_errors(document.data),
                        key=lambda e: [str(p) for p in e.absolute_path]):
        where = ".".join(str(part) for part in error.absolute_path)
        findings.append(
            Finding(
                code="decision.invalid",
                message=f"{document.decision}{'.' + where if where else ''}: {error.message}",
                position=Position(asset=asset.id, stage=spec.name, field=f"{document.decision}.{where}".rstrip(".")),
                fix=f"kiripix describe {asset.kind}",
            )
        )
    return findings


def _read(project: Project, asset: Asset, stage: str) -> tuple[Path, journal.Replay]:
    path = journal.journal_path(asset.dir, stage)
    return path, journal.replay(journal.read_entries(path, project.relative(path)))


def _append(path: Path, before: journal.Replay, **fields: Any) -> journal.JournalEntry:
    entry = journal.JournalEntry(id=journal.new_ulid(before.last_id), parent=before.last_id, **fields)
    journal.append(path, entry)
    return entry


def record_decision(project: Project, asset: Asset, stage: str, document: DecisionDocument) -> tuple[
        journal.JournalEntry, journal.Replay]:
    spec = _graph(project, asset).spec(stage)
    findings = _entry_findings(spec, asset, document)
    if findings:
        raise KiripixError(findings)
    path, before = _read(project, asset, stage)
    entry = _append(path, before, decision=document.decision, data=document.data, image_hash=document.image_hash)
    return entry, _read(project, asset, stage)[1]


def undo(project: Project, asset: Asset, stage: str) -> tuple[journal.JournalEntry, journal.Replay]:
    _graph(project, asset).spec(stage)
    path, before = _read(project, asset, stage)
    target = before.next_undo()
    if target is None:
        raise fail("decision.nothing_to_undo", f"{asset.id} {stage} has no Decision to undo",
                   position=Position(asset=asset.id, stage=stage), fix=f"kiripix status --kind {asset.kind}")
    entry = _append(path, before, undo=target)
    return entry, _read(project, asset, stage)[1]


def redo(project: Project, asset: Asset, stage: str) -> tuple[journal.JournalEntry, journal.Replay]:
    _graph(project, asset).spec(stage)
    path, before = _read(project, asset, stage)
    target = before.next_redo()
    if target is None:
        raise fail("decision.nothing_to_redo", f"{asset.id} {stage} has no undone Decision to redo",
                   position=Position(asset=asset.id, stage=stage), fix=f"kiripix status --kind {asset.kind}")
    entry = _append(path, before, redo=target)
    return entry, _read(project, asset, stage)[1]
