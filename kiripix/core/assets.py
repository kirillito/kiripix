"""Assets: IDs, folders, `asset.toml`, and creating one with `new`."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from kiripix.checks import Finding, Position
from kiripix.core import atomic
from kiripix.core.errors import KiripixError, fail
from kiripix.core.kinds import get_kind
from kiripix.core.project import Project
from kiripix.core.settings import AssetSettings, Scalar, load_asset_settings, save_settings
from kiripix.recipes.base import KindSpec

ASSET_FILE = "asset.toml"
HISTORY_FILE = "history.jsonl"
_NAME = re.compile(r"^[a-z0-9_]+$")
_ID = re.compile(r"^([a-z][a-z0-9_]*)\.([a-z0-9_]+)$")


@dataclass(frozen=True)
class Asset:
    id: str
    kind: str
    name: str
    dir: Path
    settings: AssetSettings


def asset_dir(project: Project, kind: str, name: str) -> Path:
    return project.root / "assets" / kind / name


def is_asset_id(text: str | None) -> bool:
    return bool(text and _ID.match(text))


def parse_asset_id(text: str) -> tuple[str, str]:
    """Split `<kind>.<name>`; names are lower-case letters, digits and underscores."""
    match = _ID.match(text)
    if not match:
        raise fail(
            "asset.invalid_id",
            f"'{text}' is not an Asset ID: expected <kind>.<name>, lower-case letters, digits and underscores",
            fix="kiripix status",
        )
    return match.group(1), match.group(2)


def _load(project: Project, kind: str, name: str) -> Asset:
    directory = asset_dir(project, kind, name)
    settings = load_asset_settings(directory / ASSET_FILE, project.relative(directory / ASSET_FILE))
    if settings.kind != kind:
        file = project.relative(directory / ASSET_FILE)
        raise fail(
            "asset.kind_mismatch",
            f"{file} says kind '{settings.kind}' but lives under assets/{kind}/",
            owner_action=f"Set kind = \"{kind}\" in {file}, or move the folder.",
            position=Position(asset=f"{kind}.{name}", file=file, field="kind"),
        )
    return Asset(f"{kind}.{name}", kind, name, directory, settings)


def load_asset(project: Project, asset_id: str) -> Asset:
    kind, name = parse_asset_id(asset_id)
    if not (asset_dir(project, kind, name) / ASSET_FILE).is_file():
        raise fail("asset.not_found", f"no Asset '{asset_id}' in this Project", fix="kiripix status")
    return _load(project, kind, name)


def list_assets(project: Project) -> tuple[list[Asset], list[Finding]]:
    """Every Asset, sorted by ID. A broken Asset becomes a finding instead of hiding the others."""
    assets: list[Asset] = []
    findings: list[Finding] = []
    for file in sorted((project.root / "assets").glob(f"*/*/{ASSET_FILE}")):
        kind, name = file.parent.parent.name, file.parent.name
        try:
            assets.append(_load(project, kind, name))
        except KiripixError as error:
            findings.extend(error.findings)
    return assets, findings


def validate_params(kind: KindSpec, params: Mapping[str, Scalar], asset_id: str) -> list[Finding]:
    findings: list[Finding] = []
    declared = {p.name: p for p in kind.params}
    for name in params:
        if name not in declared:
            findings.append(
                Finding(
                    code="asset.param_unknown",
                    message=f"Kind '{kind.name}' has no parameter '{name}'",
                    position=Position(asset=asset_id, field=name),
                    fix=f"kiripix new {kind.name} {asset_id.split('.', 1)[1]}",
                )
            )
    for spec in kind.params:
        if spec.name not in params:
            if spec.required:
                example = (spec.choices or ["<value>"])[0]
                findings.append(
                    Finding(
                        code="asset.param_required",
                        message=f"a {kind.name} needs --{spec.name} ({spec.description})",
                        position=Position(asset=asset_id, field=spec.name),
                        fix=f"kiripix new {kind.name} {asset_id.split('.', 1)[1]} --{spec.name} {example}",
                    )
                )
            continue
        problem = spec.problem(params[spec.name])
        if problem:
            findings.append(
                Finding(
                    code="asset.param_invalid",
                    message=f"--{spec.name}: {problem}",
                    position=Position(asset=asset_id, field=spec.name),
                    fix=f"kiripix describe {kind.name}",
                )
            )
    return findings


def create_asset(project: Project, kind_name: str, name: str, params: Mapping[str, Scalar]) -> tuple[Asset, list[str]]:
    """Create `assets/<kind>/<name>/` with `asset.toml`, an empty `history.jsonl` and `decisions/`."""
    kind = get_kind(kind_name)
    if name.startswith(f"{kind_name}."):
        name = name[len(kind_name) + 1 :]
    asset_id = f"{kind_name}.{name}"
    if not _NAME.match(name):
        raise fail(
            "asset.invalid_id",
            f"'{name}' is not a valid Asset name: use lower-case letters, digits and underscores",
            fix=f"kiripix new {kind_name} {re.sub(r'[^a-z0-9_]+', '_', name.lower()).strip('_') or 'name'}",
        )
    directory = asset_dir(project, kind_name, name)
    if directory.exists():
        raise fail(
            "asset.duplicate_id",
            f"the Asset '{asset_id}' already exists",
            fix=f"kiripix status --kind {kind_name}",
            position=Position(asset=asset_id),
        )
    findings = validate_params(kind, params, asset_id)
    if findings:
        raise KiripixError(findings)
    settings = AssetSettings(kind=kind_name, params=dict(params))
    save_settings(directory / ASSET_FILE, settings)
    atomic.write_text(directory / HISTORY_FILE, "")
    atomic.write_text(directory / "decisions" / ".gitkeep", "")
    created = [ASSET_FILE, HISTORY_FILE, "decisions/"]
    return Asset(asset_id, kind_name, name, directory, settings), [
        project.relative(directory / c) + ("/" if c.endswith("/") else "") for c in created
    ]
