"""The review queue (spec §5, ticket 0325): everything on a set of Assets that waits on the Owner. Read-only.

A stop is one the Owner owns: a Stage in `needs-review`, a Stage in `needs-input` whose next step is the Owner's, or a
finding of a built Stage that has an `owner_action`. A finding with a `fix` is not a stop: an agent runs it, so it is counted
per Asset (Q3 of ticket 0324). Nothing is stored: the queue is derived from the Stages' hashes, their Checks, the Project
checks and the notes each time, as `status` is (ADR 0005). `queue` and `district` (ticket 0328) both read it here.
"""

from collections.abc import Hashable
from dataclasses import dataclass, field, replace
from typing import Literal

from pydantic import BaseModel, Field

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset, list_assets
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph, StageState
from kiripix.core.hashing import HashCache
from kiripix.core.memory import Memory
from kiripix.core.notes import live_notes
from kiripix.core.project import Project
from kiripix.core.project_checks import run_project_checks
from kiripix.recipes.base import StageSpec

StopType = Literal["review", "input", "finding"]


def what_next(graph: AssetGraph, spec: StageSpec, state: StageState) -> tuple[str | None, str | None]:
    """What a Stage that isn't done needs next: a `command` to run, or the Owner's `owner_action` (`next` and `queue` share
    this). Not for a `done` or `failed` Stage."""
    asset = graph.asset.id
    waiting = graph.needs_input(spec) if state.status == "needs-input" and (
        spec.run is not None or spec.needs_input is not None) else None
    if waiting is not None:
        return waiting.command, waiting.owner_action
    if state.status == "needs-input":
        return None, f"{state.reason[0].upper()}{state.reason[1:]}." if state.reason else "Provide input."
    if state.status == "needs-review":
        return None, f"Review and accept: kiripix accept {asset} {state.stage}"
    return f"kiripix run {asset}", None


class QueueNote(BaseModel):
    id: str
    text: str


class QueueStop(BaseModel):
    asset: str
    kind: str
    stage: str | None = Field(description="The Stage; null for a Project check's finding that names no Stage.")
    type: StopType
    input_hash: str | None = Field(description="The Stage's current input hash; null with no Stage.")
    reason: str | None = Field(None, description="For review and input: why the Stage waits. For a finding: its message.")
    owner_action: str | None = Field(None, description="What only the Owner can do.")
    command: str | None = Field(None, description="The command that settles the stop, when there is one: `accept` for a review.")
    code: str | None = Field(None, description="For a finding: its code.")
    severity: str | None = Field(None, description="For a finding: error or warning.")
    position: Position | None = Field(None, description="For a finding: where it is.")
    notes: list[QueueNote] = Field(default_factory=list, description="The Stage's live hand-over notes, oldest first.")


class Fix(BaseModel):
    stage: str | None
    code: str
    command: str


class AssetFixable(BaseModel):
    asset: str
    count: int
    fixes: list[Fix]


class Queue(BaseModel):
    stops: list[QueueStop]
    agent_fixable: list[AssetFixable]
    clear: list[str] = Field(description="The Assets with no stop and nothing agent-fixable.")
    errors: list[Finding] = Field(default_factory=list, description="Assets that couldn't be read; they hold no stops.")

    def by_asset(self, asset: str) -> tuple[dict[str, int], int]:
        """The Asset's stops by type, and its agent-fixable count: what a district's row shows."""
        counts = {"review": 0, "input": 0, "finding": 0}
        for stop in self.stops:
            if stop.asset == asset:
                counts[stop.type] += 1
        fixable = next((f.count for f in self.agent_fixable if f.asset == asset), 0)
        return counts, fixable

    def counts(self) -> dict[str, int]:
        found = {"review": 0, "input": 0, "finding": 0}
        for stop in self.stops:
            found[stop.type] += 1
        return {**found, "total": len(self.stops), "agent_fixable": sum(f.count for f in self.agent_fixable)}


def _order(finding: Finding, stages: list[str]) -> tuple[int, int]:
    stage = finding.position.stage if finding.position else None
    return (stages.index(stage) if stage in stages else len(stages), 0 if finding.severity == "error" else 1)


def _located(finding: Finding, asset: str, stage: str | None) -> Finding:
    position = finding.position or Position()
    return finding.model_copy(update={"position": position.model_copy(update={
        "asset": position.asset or asset, "stage": position.stage or stage})})


@dataclass(frozen=True)
class AssetState:
    """One Asset's Stage states: what `status` and `queue` both start from. `errors` hold why they couldn't be worked out
    (a base that isn't one), with no states then. `graph` is there for the caller that works the Asset out once and goes
    on with it; what `Memory` keeps leaves it out."""

    states: list[StageState] = field(default_factory=list)
    waits_on: dict[str, str] = field(default_factory=dict)
    errors: list[Finding] = field(default_factory=list)
    graph: AssetGraph | None = None


def asset_state(project: Project, asset: Asset, cache: HashCache) -> AssetState:
    """Work out the Stage states of `asset`, and the first open Stage that each not-done Stage reads."""
    try:
        graph = AssetGraph(project, asset, cache)
        states = graph.states()
        first_open = next((s.stage for s in states if s.status != "done"), None)
        waits_on = {} if first_open is None else {
            s.stage: first_open for s in states if first_open in graph.upstream_chain(graph.spec(s.stage))}
    except KiripixError as error:
        return AssetState(errors=list(error.findings))
    return AssetState(states, waits_on, graph=graph)


def recall_state(project: Project, asset: Asset, cache: HashCache, memory: Memory | None) -> AssetState:
    """`asset_state`, from `memory` when there is one (`serve`): worked out once, until a recorded change drops it."""
    if memory is None:
        return asset_state(project, asset, cache)
    return memory.recall("state", asset, lambda: replace(asset_state(project, asset, cache), graph=None))


@dataclass(frozen=True)
class AssetQueue:
    stops: list[QueueStop] = field(default_factory=list)
    fixes: list[Fix] = field(default_factory=list)
    errors: list[Finding] = field(default_factory=list)


def _project_stamp(findings: list[Finding]) -> Hashable:
    return tuple(f.model_dump_json() for f in findings)


def build_queue(project: Project, assets: list[Asset], cache: HashCache, every: list[Asset] | None = None,
                memory: Memory | None = None) -> Queue:
    """The queue of `assets` (in ID order). `every` is all the Project's Assets, which the Project checks read; their findings
    count only where they name one of `assets`. With `memory` (`serve`) each Asset's part is worked out once until a recorded
    change drops it, and again when the Project checks' findings that name it differ."""
    ordered = sorted(assets, key=lambda a: a.id)
    ids = {a.id for a in ordered}
    if every is None:
        every, _ = list_assets(project)
    named: dict[str, list[Finding]] = {}
    for found in run_project_checks(project, every):
        if found.position is not None and found.position.asset in ids:
            named.setdefault(found.position.asset, []).append(found)
    stops: list[QueueStop] = []
    fixable: list[AssetFixable] = []
    errors: list[Finding] = []
    clear: list[str] = []
    for asset in ordered:
        mine_findings = named.get(asset.id, [])

        def work(asset: Asset = asset, mine_findings: list[Finding] = mine_findings) -> AssetQueue:
            state = recall_state(project, asset, cache, memory)
            if state.errors:
                return AssetQueue(errors=state.errors)
            try:
                found_stops, fixes = _asset_queue(project, asset, cache, mine_findings, state.states, state.graph)
            except KiripixError as error:
                return AssetQueue(errors=list(error.findings))
            return AssetQueue(found_stops, fixes)

        part = work() if memory is None else memory.recall("queue", asset, work, stamp=lambda _: _project_stamp(mine_findings))
        if part.errors:
            errors.extend(part.errors)
            continue
        stops.extend(part.stops)
        if part.fixes:
            fixable.append(AssetFixable(asset=asset.id, count=len(part.fixes), fixes=part.fixes))
        if not part.stops and not part.fixes:
            clear.append(asset.id)
    return Queue(stops=stops, agent_fixable=fixable, clear=clear, errors=errors)


def _asset_queue(project: Project, asset: Asset, cache: HashCache, project_findings: list[Finding],
                 states: list[StageState] | None = None, graph: AssetGraph | None = None) -> tuple[list[QueueStop], list[Fix]]:
    graph = graph or AssetGraph(project, asset, cache)
    stages = [s.name for s in graph.kind.stages]
    notes = live_notes(asset)

    def stop(stage: str | None, type: StopType, **fields: object) -> QueueStop:
        held = [QueueNote(id=n.id, text=n.text) for n in notes.get(stage or "", [])]
        return QueueStop(asset=asset.id, kind=asset.kind, stage=stage, type=type, notes=held,
                         input_hash=graph.input_hash(stage) if stage else None, **fields)

    stops: list[QueueStop] = []
    findings: list[Finding] = []
    states = states if states is not None else graph.states()
    open_stages = {s.stage for s in states if s.status != "done"}
    for state in states:
        spec = graph.spec(state.stage)
        if open_stages.intersection(graph.upstream_chain(spec)):
            continue  # it reads a Stage that isn't done, so what it says may change once that is (§5): not a stop yet
        if state.status == "needs-review":
            _, action = what_next(graph, spec, state)
            stops.append(stop(state.stage, "review", reason=state.reason, owner_action=action,
                              command=f"kiripix accept {asset.id} {state.stage}"))
        elif state.status == "needs-input":
            command, action = what_next(graph, spec, state)
            if command is None and action is not None:  # a Runner call is a command an agent runs, not the Owner's stop
                stops.append(stop(state.stage, "input", reason=state.reason, owner_action=action))
        elif state.status == "done":
            findings.extend(_located(f, asset.id, state.stage) for f in graph.check(spec))
    findings.extend(_located(f, asset.id, None) for f in project_findings)
    fixes: list[Fix] = []
    owned: list[Finding] = []
    for found in sorted(findings, key=lambda f: _order(f, stages)):
        if found.severity == "info":
            continue
        position = found.position
        stage = position.stage if position else None
        if found.owner_action is not None:
            owned.append(found)
        elif found.fix is not None:
            fixes.append(Fix(stage=stage, code=found.code, command=found.fix))
    for found in owned:
        position = found.position
        stage = position.stage if position and position.stage in stages else None
        stops.append(stop(stage, "finding", reason=found.message, owner_action=found.owner_action, code=found.code,
                          severity=found.severity, position=position))
    stops.sort(key=lambda s: (stages.index(s.stage) if s.stage in stages else len(stages)))  # stable: errors stay first
    return stops, fixes
