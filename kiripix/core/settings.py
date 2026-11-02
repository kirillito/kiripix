"""The data files `kiripix.toml` and `asset.toml`: their classes, schema versions and migrations.

Migrations are pure functions from version N to N + 1. They run in memory on every read; the file is written back
only when a writing Command saves it. Unknown keys are an error, so typos surface.
"""

import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal, Self

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from kiripix.checks import Finding, Position
from kiripix.core import atomic
from kiripix.core.errors import KiripixError

Scalar = str | int | float | bool
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectSection(_Strict):
    name: str
    resolution: tuple[int, int] = (480, 270)
    tile: int = Field(16, gt=0)
    palette: str = "style/palette.gpl"


class Body(_Strict):
    """The stand-in player footprint for walkable, reachability and walk tests."""

    size: tuple[int, int] = (12, 8)
    dash: int = Field(0, ge=0)


class MaskDefinition(_Strict):
    """A Mask: painted (with a display and import colour) or derived (computed, never painted)."""

    colour: str | None = None
    meaning: str | None = None
    derived: bool = False

    @model_validator(mode="after")
    def _painted_or_derived(self) -> Self:
        if self.derived == (self.colour is not None):
            raise ValueError("set either colour (a painted Mask) or derived = true")
        if self.colour is not None and not _HEX.match(self.colour):
            raise ValueError(f"colour must be #RRGGBB, got {self.colour!r}")
        return self


class MaskSet(BaseModel):
    """The Masks of one view, by name, plus the extra colours accepted on import."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)
    __pydantic_extra__: dict[str, MaskDefinition] = Field(init=False)

    import_colours: dict[str, list[str]] = Field(default_factory=dict, alias="import")

    @model_validator(mode="after")
    def _import_names_masks(self) -> Self:
        names = set(self.__pydantic_extra__ or {})
        for colour, masks in self.import_colours.items():
            if not _HEX.match(colour):
                raise ValueError(f"import colour must be #RRGGBB, got {colour!r}")
            for mask in masks:
                if mask not in names:
                    raise ValueError(f"import colour {colour} names unknown Mask {mask!r}")
        return self


class GodotExport(_Strict):
    project: str | None = None
    root: str = "res://kiripix"
    version: str = "4.7"


class ExportSection(_Strict):
    godot: GodotExport = GodotExport()


class Providers(_Strict):
    default: str = "import"
    budget_usd_month: float = Field(20, ge=0)


def _default_masks() -> dict[Literal["top", "side"], MaskSet]:
    top = MaskSet.model_validate(
        {
            "solid": {"colour": "#FF0000", "meaning": "blocks movement"},
            "walkable": {"derived": True},
            "foreground": {"derived": True},
            "import": {"#FFFF00": ["solid"]},
        }
    )
    side = MaskSet.model_validate(
        {
            "solid": {"colour": "#FF0000"},
            "oneway": {"colour": "#00FFFF", "meaning": "platform passable from below"},
            "ladder": {"colour": "#00FF00"},
            "foreground": {"derived": True},
        }
    )
    return {"top": top, "side": side}


PROJECT_SCHEMA_VERSION = 1
ASSET_SCHEMA_VERSION = 1


class ProjectSettings(_Strict):
    """`kiripix.toml`."""

    schema_version: Literal[1] = 1
    project: ProjectSection
    body: Body = Body()
    masks: dict[Literal["top", "side"], MaskSet] = Field(default_factory=_default_masks)
    export: ExportSection = ExportSection()
    providers: Providers = Providers()


class AssetSettings(_Strict):
    """`asset.toml`: the Kind and parameters only. Never status (ADR 0005)."""

    schema_version: Literal[1] = 1
    kind: str
    params: dict[str, Scalar] = {}
    stages: dict[str, dict[str, Scalar]] = {}


Migration = Callable[[dict[str, Any]], dict[str, Any]]


def _add_schema_version(document: dict[str, Any]) -> dict[str, Any]:
    """Version 0 is a file written before schema versions, such as the spec §4 example: the same keys, unversioned."""
    return {"schema_version": 1, **document}


PROJECT_MIGRATIONS: dict[int, Migration] = {0: _add_schema_version}
ASSET_MIGRATIONS: dict[int, Migration] = {0: _add_schema_version}


def _field_path(location: tuple[int | str, ...]) -> str:
    return ".".join(str(part) for part in location if part not in ("function-after",))


def _validation_findings(error: ValidationError, file: str) -> list[Finding]:
    findings = []
    for item in error.errors():
        path = _field_path(item["loc"])
        if item["type"] == "extra_forbidden":
            findings.append(
                Finding(
                    code="config.unknown_key",
                    message=f"{file}: unknown key '{path}'",
                    position=Position(file=file, field=path),
                    owner_action=f"Remove '{path}' from {file}, or correct its spelling.",
                )
            )
        else:
            message = item["msg"].removeprefix("Value error, ")
            where = f"'{path}'" if path else "the file"
            findings.append(
                Finding(
                    code="config.invalid",
                    message=f"{file}: {where}: {message}",
                    position=Position(file=file, field=path or None),
                    owner_action=f"Fix {where} in {file}: {message}.",
                )
            )
    return findings


def _read_document(path: Path, file: str) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_bytes().decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
        raise KiripixError(
            [
                Finding(
                    code="config.syntax",
                    message=f"{file}: {error}",
                    position=Position(file=file),
                    owner_action=f"Fix the TOML syntax in {file}: {error}.",
                )
            ]
        ) from None


def _migrate(document: dict[str, Any], file: str, current: int, migrations: dict[int, Migration]) -> dict[str, Any]:
    version = document.get("schema_version", 0)
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        raise KiripixError(
            [
                Finding(
                    code="config.invalid",
                    message=f"{file}: 'schema_version' must be a whole number, got {version!r}",
                    position=Position(file=file, field="schema_version"),
                    owner_action=f"Fix 'schema_version' in {file}.",
                )
            ]
        )
    if version > current:
        raise KiripixError(
            [
                Finding(
                    code="config.newer_version",
                    message=f"{file} has schema_version {version}; this Kiripix reads up to {current}",
                    position=Position(file=file, field="schema_version"),
                    owner_action="Upgrade Kiripix to the version that wrote this project.",
                )
            ]
        )
    while version < current:
        document = migrations[version](document)
        version += 1
    return document


def load_project_settings(path: Path, file: str = "kiripix.toml") -> ProjectSettings:
    document = _migrate(_read_document(path, file), file, PROJECT_SCHEMA_VERSION, PROJECT_MIGRATIONS)
    try:
        return ProjectSettings.model_validate(document)
    except ValidationError as error:
        raise KiripixError(_validation_findings(error, file)) from None


def load_asset_settings(path: Path, file: str) -> AssetSettings:
    document = _migrate(_read_document(path, file), file, ASSET_SCHEMA_VERSION, ASSET_MIGRATIONS)
    try:
        return AssetSettings.model_validate(document)
    except ValidationError as error:
        raise KiripixError(_validation_findings(error, file)) from None


def settings_document(settings: BaseModel) -> dict[str, Any]:
    """The settings as plain TOML-ready data, by alias, without unset optional values."""
    document: dict[str, Any] = settings.model_dump(mode="json", by_alias=True, exclude_none=True)
    return document


def save_settings(path: Path, settings: ProjectSettings | AssetSettings) -> None:
    """Write a data file at the current schema version, atomically."""
    atomic.write_text(path, tomli_w.dumps(settings_document(settings)))
