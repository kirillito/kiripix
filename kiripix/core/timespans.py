"""The Owner's active time (ticket 0182): `assets/<kind>/<id>/time.jsonl`, append-only, one span per line, LF,
`merge=union`, committed like the Decision journal.

A span is `{schema_version, id, stage, seconds, source}`. The ULID `id` is the span's end. `stage` is a Stage of the
Asset's Kind, or `extend`. `source` is `ui` (the Owner's session token) or `cli` (an interactive terminal). Only the
Owner's own Commands write one (`track`, and the CLI's own count in `note_cli`), nothing leaves the machine.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError

from kiripix.core import atomic, journal
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.kinds import get_kind
from kiripix.core.project import Project

TIME_FILE = "time.jsonl"
SCHEMA_VERSION = 1
EXTEND = "extend"  # the tool that runs before `source`; not a Stage of the Kind
IDLE_SECONDS = 180  # active: the Stage's screen focused and an input event in the last three minutes
MIN_SPAN = 1
MAX_SPAN = 3600
CLI_STATE = "cli-time"  # in `.kiripix/`: `<asset>.json`, when the Owner's previous Command on that Asset ended (one file
# per Asset, so the Asset's lock guards it)

Source = Literal["ui", "cli"]


class TimeSpan(BaseModel):
    """One line of `time.jsonl`."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    id: str
    stage: str
    seconds: int
    source: Source


def time_path(asset: Asset) -> Path:
    return asset.dir / TIME_FILE


def stage_names(asset: Asset) -> list[str]:
    return [*(spec.name for spec in get_kind(asset.kind).stages), EXTEND]


def read_spans(asset: Asset) -> list[TimeSpan]:
    """The spans of an Asset in ULID order. A missing file is no time."""
    path = time_path(asset)
    if not path.is_file():
        return []
    spans = []
    for number, line in enumerate(path.read_bytes().decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        where = f"{asset.id}/{TIME_FILE} line {number}"
        try:
            span = TimeSpan.model_validate(json.loads(line))
        except (ValueError, ValidationError) as error:
            raise fail("time.invalid", f"{where} is not valid: {error}",
                       owner_action=f"Fix line {number} of {TIME_FILE} in {asset.id}, or remove it if a bad merge "
                                    "left it behind.") from None
        if span.schema_version != SCHEMA_VERSION:
            raise fail("time.invalid", f"{where} has schema_version {span.schema_version}; this Kiripix reads "
                                       f"{SCHEMA_VERSION}", owner_action="Update Kiripix.")
        spans.append(span)
    return sorted(spans, key=lambda span: span.id)


def append_span(asset: Asset, stage: str, seconds: int, source: Source) -> TimeSpan:
    """Append one span ending now. The caller holds the Asset's lock."""
    span = TimeSpan(schema_version=SCHEMA_VERSION, id=journal.new_ulid(), stage=stage, seconds=seconds,
                    source=source)
    atomic.append_jsonl(time_path(asset), span.model_dump())
    return span


def check_span(asset: Asset, stage: str, seconds: int) -> None:
    names = stage_names(asset)
    if stage not in names:
        raise fail("time.stage_unknown", f"{asset.id} has no Stage '{stage}'; the Stages are {', '.join(names)}",
                   fix=f"kiripix describe {asset.kind}")
    if not MIN_SPAN <= seconds <= MAX_SPAN:
        raise fail("time.seconds_invalid",
                   f"a span is {MIN_SPAN} to {MAX_SPAN} seconds, not {seconds}; the UI sends one at least every minute",
                   owner_action="Send the span in pieces of at most an hour.")


def has_merge_attribute(project: Project) -> bool:
    """Whether the Project's `.gitattributes` makes `time.jsonl` merge as a union. Without it, two branches that both
    log time conflict on merge."""
    path = project.root / ".gitattributes"
    if not path.is_file():
        return True  # no .gitattributes: not a git Project the Owner set up with `init`; nothing to say
    return any(line.split()[:1] == [TIME_FILE] and "merge=union" in line
               for line in path.read_text(encoding="utf-8").splitlines())


def note_cli(project: Project, asset: Asset, stage: str, started: float, ended: float) -> TimeSpan | None:
    """The CLI's own count: the time from the end of the Owner's previous Command on this Asset to the start of this one,
    when that is under the idle threshold. Keeps this Command's end in `.kiripix/` for the next one."""
    path = project.state_dir / CLI_STATE / f"{asset.id}.json"
    try:
        before = json.loads(path.read_text(encoding="utf-8")).get("ended")
    except (OSError, ValueError, AttributeError):
        before = None
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic.write_json(path, {"ended": ended})
    if not isinstance(before, (int, float)) or stage not in stage_names(asset):
        return None
    seconds = round(started - before)
    if not MIN_SPAN <= seconds < IDLE_SECONDS:
        return None
    return append_span(asset, stage, seconds, "cli")


# stats


@dataclass
class StageTime:
    ui: int = 0
    cli: int = 0
    decisions: int = 0
    undos: int = 0
    redos: int = 0

    def add(self, other: "StageTime") -> None:
        self.ui += other.ui
        self.cli += other.cli
        self.decisions += other.decisions
        self.undos += other.undos
        self.redos += other.redos


@dataclass
class AssetTime:
    asset: str
    stages: dict[str, StageTime] = field(default_factory=dict)

    def total(self) -> StageTime:
        total = StageTime()
        for stage in self.stages.values():
            total.add(stage)
        return total


def parse_since(text: str) -> float:
    """The start of a date (`2026-11-12`, local time) or a date and time, as seconds since the epoch."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError:
        raise fail("stats.since_invalid", f"--since '{text}' is not a date such as 2026-11-12",
                   fix="kiripix stats --all --since 2026-11-12") from None
    return moment.timestamp()  # a naive moment is local time


def asset_time(asset: Asset, since: float | None) -> AssetTime:
    """Active seconds from `time.jsonl`, and Decisions, undos and redos from the journals, with the entries made since
    `since`. An `accept`'s re-recorded entries (`replaces`) are not new Decisions."""
    result = AssetTime(asset.id)

    def stage(name: str) -> StageTime:
        return result.stages.setdefault(name, StageTime())

    for span in read_spans(asset):
        if since is not None and journal.ulid_time(span.id) < since:
            continue
        current = stage(span.stage)
        if span.source == "ui":
            current.ui += span.seconds
        else:
            current.cli += span.seconds
    for path in sorted((asset.dir / "decisions").glob("*.jsonl")):
        entries = journal.read_entries(path, f"{asset.id}/decisions/{path.name}")
        for entry in entries:
            if since is not None and journal.ulid_time(entry.id) < since:
                continue
            if entry.decision is not None and entry.replaces is None:
                stage(path.stem).decisions += 1
            elif entry.undo is not None:
                stage(path.stem).undos += 1
            elif entry.redo is not None:
                stage(path.stem).redos += 1
    result.stages = dict(sorted(result.stages.items()))
    return result

