"""Checks, run by `check` (spec §10.5): the Checks of every built Stage of an Asset, and the Project checks.

A Project check looks across Assets (exit pairing, in ticket 0022). It is a function of the Project and every Asset in
it, registered here with `register_project_check`; `check --all` runs them all. Nothing in this module writes.
"""

from collections.abc import Callable

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset, list_assets
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph
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


def check_asset(project: Project, asset: Asset, cache: HashCache) -> tuple[list[str], list[Finding]]:
    """Run every Check of every Stage of `asset` that has an output. Returns the Stages checked and the findings."""
    graph = AssetGraph(project, asset, cache)
    checked: list[str] = []
    findings: list[Finding] = []
    for spec in graph.kind.stages:
        if spec.check is None or graph.built_hash(spec) is None:
            continue
        checked.append(spec.name)
        findings.extend(_located(f, asset.id, spec.name) for f in graph.check(spec))
    return checked, findings


def check_all(project: Project, cache: HashCache) -> tuple[list[str], list[str], list[Finding], bool]:
    """Check every Asset, then run the Project checks. Returns the Assets and `asset stage` pairs checked, the
    findings, and whether anything beyond a Check's own finding went wrong (an Asset that couldn't be loaded)."""
    assets, findings = list_assets(project)
    broken = bool(findings)
    names: list[str] = []
    stages: list[str] = []
    for asset in assets:
        names.append(asset.id)
        try:
            done, found = check_asset(project, asset, cache)
        except KiripixError as error:
            findings.extend(error.findings)
            broken = True
            continue
        stages.extend(f"{asset.id} {stage}" for stage in done)
        findings.extend(found)
    for project_check in _PROJECT_CHECKS:
        findings.extend(project_check(project, assets))
    return names, stages, findings, broken
