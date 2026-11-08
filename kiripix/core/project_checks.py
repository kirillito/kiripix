"""Checks, run by `check` (spec §10.5): the Checks of every built Stage of an Asset, and the Project checks.

A Project check looks across Assets (exit pairing, in ticket 0022). It is a function of the Project and every Asset in
it, registered here with `register_project_check`; `check --all` runs them all. Nothing in this module writes.
"""

from collections.abc import Callable

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset, list_assets
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph, StageState
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project

ProjectCheck = Callable[[Project, list[Asset]], list[Finding]]

_PROJECT_CHECKS: list[ProjectCheck] = []


def register_project_check(check: ProjectCheck) -> ProjectCheck:
    """Add a Project check; usable as a decorator."""
    _PROJECT_CHECKS.append(check)
    return check


def _located(finding: Finding, asset: str, stage: str) -> Finding:
    """The finding with its Asset and Stage filled in where its Check left them out."""
    position = finding.position or Position()
    return finding.model_copy(update={"position": position.model_copy(update={
        "asset": position.asset or asset, "stage": position.stage or stage})})


def check_asset(project: Project, asset: Asset, cache: HashCache) -> tuple[list[str], list[Finding], list[StageState]]:
    """Run every Check of every Stage of `asset` that has an output, however old. Returns the Stages checked, the
    findings, and the state of each checked Stage whose status isn't `done` (its result may not hold)."""
    graph = AssetGraph(project, asset, cache)
    checked: list[str] = []
    findings: list[Finding] = []
    out_of_date: list[StageState] = []
    for spec in graph.kind.stages:
        if spec.check is None or graph.built_hash(spec) is None:
            continue
        checked.append(spec.name)
        state = graph.state(spec.name)
        if state.status != "done":
            out_of_date.append(state)
        findings.extend(_located(f, asset.id, spec.name) for f in graph.check(spec))
    return checked, findings, out_of_date


def check_all(project: Project, cache: HashCache) -> tuple[
        list[str], list[str], list[Finding], bool, list[tuple[str, StageState]]]:
    """Check every Asset, then run the Project checks. Returns the Assets and `asset stage` pairs checked, the
    findings, whether anything beyond a Check's own finding went wrong (an Asset that couldn't be loaded), and the out-of-date
    Stages with their Asset."""
    assets, findings = list_assets(project)
    broken = bool(findings)
    names: list[str] = []
    stages: list[str] = []
    late: list[tuple[str, StageState]] = []
    for asset in assets:
        names.append(asset.id)
        try:
            done, found, old = check_asset(project, asset, cache)
        except KiripixError as error:
            findings.extend(error.findings)
            broken = True
            continue
        stages.extend(f"{asset.id} {stage}" for stage in done)
        findings.extend(found)
        late.extend((asset.id, state) for state in old)
    for project_check in _PROJECT_CHECKS:
        findings.extend(project_check(project, assets))
    return names, stages, findings, broken, late
