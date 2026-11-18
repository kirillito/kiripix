"""The data files `kiripix.toml` and `asset.toml`: their classes, schema versions and migrations.

Migrations are pure functions from version N to N + 1. They run in memory on every read; the file is written back
only when a writing Command saves it. Unknown keys are an error, so typos surface.
"""

import copy
import re
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import tomli_w
import tomlkit
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from kiripix.checks import Finding, Position
from kiripix.core import atomic
from kiripix.core.errors import KiripixError

PROJECT_FILE_NAME = "kiripix.toml"
Scalar = str | int | float | bool
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectSection(_Strict):
    name: str
    resolution: tuple[int, int] = (640, 360)
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


class ExtendSection(_Strict):
    """`[extend]`: the canvas, in px, that `kiripix extend <id> canvas` writes for the image model (ticket 0136)."""

    canvas: tuple[int, int] = Field((1376, 768), description="Width and height of the canvas for the next piece.")

    @model_validator(mode="after")
    def _positive(self) -> Self:
        if min(self.canvas) < 16:
            raise ValueError("canvas must be at least 16 x 16 px")
        return self


class IconSettings(_Strict):
    """`[icon]`: the square an icon is fitted to, the same for every icon in the Project unless its own `size` says otherwise
    (ticket 0262)."""

    size: Literal[16, 24, 32] = Field(24, description="The icon's side in px: 16, 24 or 32.")


class Providers(_Strict):
    default: str = "import"
    budget_usd_month: float = Field(20, ge=0)


class CameraPreset(_Strict):
    """A camera for the `render` Stage, picked by name by an Asset's `camera` parameter."""

    elevation: float = Field(30, gt=0, le=90)  # degrees above the ground plane
    directions: Literal[4, 8] = 8
    # The key light, fixed to the camera so it sits in the same place on screen for every character: its angle round the view
    # axis from the top of the screen (90 right, -45 upper left), and how far it leans toward the camera.
    light_angle: float = Field(-45, ge=-180, le=180)
    light_tilt: float = Field(35, ge=0, le=90)


def _default_cameras() -> dict[str, CameraPreset]:
    return {"top34_8": CameraPreset(elevation=30, directions=8)}


Channel = Annotated[int, Field(ge=0, le=255)]


class RampSpec(_Strict):
    """One row of the Project's ramp table, `[[character.ramps]]` (ticket 0167): a part's name and ramp length, the same on every
    character, and, when `rgb` is given, its colours, dark to light, each a colour of the Project palette."""

    name: str = Field(pattern=r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", description="A part name: lower-case snake_case.")
    length: int = Field(ge=2, description="The steps of the part's ramp.")
    rgb: list[tuple[Channel, Channel, Channel]] | None = Field(
        None, description="The ramp's colours dark to light, `length` of them; unset when each character fits its own.")


class ClipSpec(_Strict):
    """One row of the Project's clip table, `[[character.clips]]` (ticket 0239): a clip's name, the frame count it renders to, its
    frame rate and whether it loops, the same on every body; `foot` also asks for foot frames (ticket 0172)."""

    name: str = Field(pattern=r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", description="The clip's name: lower-case snake_case.")
    frames: int = Field(ge=1, description="The rendered frame count of the clip in one direction.")
    fps: int = Field(ge=1, description="The clip's frame rate in the game.")
    loop: bool = Field(description="Whether the clip loops.")
    foot: bool = Field(False, description="The clip must have foot frames (`events.foot` in character.json).")


def _in_project(path: str) -> str:
    """A path inside the Project, relative to its root, with forward slashes."""
    parts = Path(path.replace("\\", "/")).parts
    if not path.strip() or Path(path).is_absolute() or Path(path).drive or path.startswith(("/", "\\")) or ".." in parts:
        raise ValueError(f"must be a path inside the Project, relative to its root, got {path!r}")
    return "/".join(parts)


class Generator(_Strict):
    """`[character.generators.<name>]` (ticket 0224): a script of the Project's own that builds a Model from a parameter
    file, run in the Project's Blender. Kiripix runs it and reads what it wrote; the script, the parts and the parameter
    files are the Project's."""

    script: str = Field(description="The Blender Python script, a path in the Project.")
    library: list[str] = Field(
        default_factory=list,
        description="The files and folders the script reads besides the parameter file (parts, base bodies, its own "
                    "modules), as paths in the Project. A change to any makes the `model` Stage of every character it "
                    "builds stale. One path may be given as text.")

    @model_validator(mode="before")
    @classmethod
    def _one_path_as_text(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("library"), str):
            return {**data, "library": [data["library"]]}
        return data

    @model_validator(mode="after")
    def _paths_in_project(self) -> Self:
        self.script = _in_project(self.script)
        self.library = [_in_project(path) for path in self.library]
        return self


class CharacterSettings(_Strict):
    """`[character]`: how characters are rendered, the same for every character in the Project."""

    height: int = Field(52, gt=0)  # the target height in px; a character's own `height` parameter overrides it
    blender: str | None = None  # the Blender executable; `PATH` when unset
    camera: dict[str, CameraPreset] = Field(default_factory=_default_cameras)
    generators: dict[str, Generator] = Field(
        default_factory=dict,
        description="The Project's Model generators by name; a character with a parameter file is built by one.")
    ramps: list[RampSpec] = Field(
        default_factory=list,
        description="The Project's ramp table: its order is the row order of every character's ramps. Empty: each character "
                    "chooses its own parts.")
    clips: list[ClipSpec] = Field(
        default_factory=list,
        description="The Project's clip table: a clip named here must have these frames, fps and loop on every character and "
                    "sprite that has it (`clips.timing_differs`). Empty: no clip is held to a timing.")


def _default_masks() -> dict[Literal["top", "side"], MaskSet]:
    top = MaskSet.model_validate(
        {
            "solid": {"colour": "#FF0000", "meaning": "blocks movement"},
            "pit": {"colour": "#0000FF", "meaning": "no walking on it, but the Body can dash over it"},
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


PROJECT_SCHEMA_VERSION = 8
ASSET_SCHEMA_VERSION = 1


class ProjectSettings(_Strict):
    """`kiripix.toml`."""

    schema_version: Literal[8] = 8
    project: ProjectSection
    body: Body = Body()
    masks: dict[Literal["top", "side"], MaskSet] = Field(default_factory=_default_masks)
    export: ExportSection = ExportSection()
    providers: Providers = Providers()
    character: CharacterSettings = Field(default_factory=CharacterSettings)
    extend: ExtendSection = Field(default_factory=ExtendSection)
    icon: IconSettings = Field(default_factory=IconSettings)


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


def _add_character_section(document: dict[str, Any]) -> dict[str, Any]:
    """Version 1 had no `[character]`; its defaults (height 52, the `top34_8` camera) apply."""
    return {**document, "schema_version": 2}


def _add_camera_light(document: dict[str, Any]) -> dict[str, Any]:
    """Version 2's camera presets had no key light; version 3 adds `light_angle` and `light_tilt` (ticket 0105), whose
    defaults (-45 and 35) apply."""
    return {**document, "schema_version": 3}


def _add_ramp_table(document: dict[str, Any]) -> dict[str, Any]:
    """Version 3 had no ramp table; version 4 adds `character.ramps` (ticket 0167), empty."""
    character = {**document.get("character", {})}
    character.setdefault("ramps", [])
    return {**document, "character": character, "schema_version": 4}


def _add_extend_section(document: dict[str, Any]) -> dict[str, Any]:
    """Version 4 had no `[extend]`; version 5 adds it (ticket 0136), its canvas defaulting to 1376 x 768."""
    return {**document, "schema_version": 5}


def _add_generators(document: dict[str, Any]) -> dict[str, Any]:
    """Version 5 had no Model generators; version 6 adds `character.generators` (ticket 0224), empty."""
    character = {**document.get("character", {})}
    character.setdefault("generators", {})
    return {**document, "character": character, "schema_version": 6}


def _add_clip_table(document: dict[str, Any]) -> dict[str, Any]:
    """Version 6 had no clip table; version 7 adds `character.clips` (ticket 0239), empty."""
    character = {**document.get("character", {})}
    character.setdefault("clips", [])
    return {**document, "character": character, "schema_version": 7}


def _add_icon_section(document: dict[str, Any]) -> dict[str, Any]:
    """Version 7 had no `[icon]`; version 8 adds it (ticket 0262), its size defaulting to 24."""
    return {**document, "schema_version": 8}


PROJECT_MIGRATIONS: dict[int, Migration] = {
    0: _add_schema_version, 1: _add_character_section, 2: _add_camera_light, 3: _add_ramp_table,
    4: _add_extend_section, 5: _add_generators, 6: _add_clip_table, 7: _add_icon_section}
ASSET_MIGRATIONS: dict[int, Migration] = {0: _add_schema_version}


def _add_crop_number(document: dict[str, Any]) -> dict[str, Any]:
    """A crop record (`extend/crop.json`, `extend/crops/<name>.json`): version 1 was the single `extend/crop.json` slot;
    version 2 adds `number`, the order the crops were written (ticket 0287). The old slot is 0, older than every crop of
    `crops/`."""
    return {**document, "schema_version": 2, "number": 0}


CROP_SCHEMA_VERSION = 2
CROP_MIGRATIONS: dict[int, Migration] = {1: _add_crop_number}


def migrate_crop_record(document: dict[str, Any], file: str) -> dict[str, Any]:
    """Pure: a crop record of any older schema_version as one of CROP_SCHEMA_VERSION; a newer one is refused."""
    return _migrate(document, file, CROP_SCHEMA_VERSION, CROP_MIGRATIONS)


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


def ramp_table_findings(ramps: list[RampSpec], palette: list[tuple[int, int, int]] | None,
                        file: str = "kiripix.toml") -> list[Finding]:
    """What is wrong with the ramp table: a name twice (`ramps.name_twice`), an `rgb` of the wrong length
    (`ramps.rgb_length`), a colour not in the palette (`ramps.colour_not_in_palette`) and a colour in two parts' `rgb`
    (`ramps.colour_shared`). `palette` is None when it can't be read: that Check is left out."""
    found: list[Finding] = []

    def add(code: str, row: int, field: str, message: str, owner_action: str) -> None:
        where = f"character.ramps.{row}.{field}"
        found.append(Finding(code=code, message=f"{file}: [[character.ramps]] row {row}: {message}",
                             position=Position(file=file, field=where), owner_action=owner_action))

    names: dict[str, int] = {}
    owner: dict[tuple[int, int, int], str] = {}
    for row, ramp in enumerate(ramps):
        if ramp.name in names:
            add("ramps.name_twice", row, "name", f"the part '{ramp.name}' is also row {names[ramp.name]}",
                f"Keep one [[character.ramps]] row named '{ramp.name}' in {file}.")
        names.setdefault(ramp.name, row)
        if ramp.rgb is None:
            continue
        if len(ramp.rgb) != ramp.length:
            add("ramps.rgb_length", row, "rgb",
                f"'{ramp.name}' has length {ramp.length} but {len(ramp.rgb)} colours in rgb",
                f"Give '{ramp.name}' {ramp.length} colours in rgb, or set its length to {len(ramp.rgb)}, in {file}.")
        for colour in ramp.rgb:
            if palette is not None and colour not in palette:
                add("ramps.colour_not_in_palette", row, "rgb",
                    f"'{ramp.name}' has the colour {list(colour)}, which the Project palette doesn't hold",
                    f"Use only colours of the Project palette in rgb in {file}, or add the colour to the palette first.")
            elif colour in owner and owner[colour] != ramp.name:
                add("ramps.colour_shared", row, "rgb",
                    f"'{ramp.name}' has the colour {list(colour)}, which '{owner[colour]}' has too",
                    f"Give each part colours of its own in {file}; no colour may be in two parts' rgb.")
            owner.setdefault(colour, ramp.name)
    return found


def clip_table_findings(clips: list[ClipSpec], file: str = "kiripix.toml") -> list[Finding]:
    """What is wrong with the clip table: a name twice (`clips.name_twice`)."""
    found: list[Finding] = []
    names: dict[str, int] = {}
    for row, clip in enumerate(clips):
        if clip.name in names:
            found.append(Finding(
                code="clips.name_twice", message=f"{file}: [[character.clips]] row {row}: the clip '{clip.name}' is also row "
                f"{names[clip.name]}", position=Position(file=file, field=f"character.clips.{row}.name"),
                owner_action=f"Keep one [[character.clips]] row named '{clip.name}' in {file}."))
        names.setdefault(clip.name, row)
    return found


def read_project_palette(root: Path, relative: str) -> list[tuple[int, int, int]] | None:
    """The Project palette's colours, or None when it can't be read (its own Check says so)."""
    from kiripix.ops import parse_gpl, parse_hex

    path = root / relative
    try:
        text = path.read_text(encoding="utf-8")
        palette = parse_gpl(text) if path.suffix.lower() == ".gpl" else parse_hex(text, path.stem)
    except (OSError, ValueError):
        return None
    return [(e.r, e.g, e.b) for e in palette.entries]


def load_project_settings(path: Path, file: str = "kiripix.toml") -> ProjectSettings:
    document = _migrate(_read_document(path, file), file, PROJECT_SCHEMA_VERSION, PROJECT_MIGRATIONS)
    try:
        settings = ProjectSettings.model_validate(document)
    except ValidationError as error:
        raise KiripixError(_validation_findings(error, file)) from None
    if settings.character.ramps:
        findings = ramp_table_findings(settings.character.ramps, read_project_palette(path.parent, settings.project.palette), file)
        if findings:
            raise KiripixError(findings)
    if settings.character.clips and (findings := clip_table_findings(settings.character.clips, file)):
        raise KiripixError(findings)
    return settings


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


def _same(old: Any, new: Any) -> bool:
    """Equal in value; a bool is not a number."""
    if isinstance(old, dict) or isinstance(new, dict):
        return (isinstance(old, dict) and isinstance(new, dict) and old.keys() == new.keys()
                and all(_same(old[k], new[k]) for k in old))
    if isinstance(old, list) or isinstance(new, list):
        return (isinstance(old, list) and isinstance(new, list) and len(old) == len(new)
                and all(_same(a, b) for a, b in zip(old, new, strict=True)))
    numbers = (int, float)
    if isinstance(old, numbers) and isinstance(new, numbers) and not isinstance(old, bool) and not isinstance(new, bool):
        return bool(old == new)  # the Owner's `20` stays `20` where the settings class holds 20.0
    return type(old) is type(new) and bool(old == new)


def _add(target: Any, key: str, value: Any) -> None:
    """Add a new key. A new `[[array.of.tables]]` gets a blank line after its last row, so the next table doesn't touch it."""
    target[key] = value
    added = target[key]
    if isinstance(added, tomlkit.items.AoT) and len(added):
        added[len(added) - 1].add(tomlkit.nl())


def _merge(target: Any, new: dict[str, Any]) -> None:
    """Edit the format-preserving `target` table in place until it holds `new`: keys that are gone are removed, new keys are
    added, a changed value is replaced, and everything else (comments, order, spacing, inline tables) is left as it is.
    A migration or a new `[[array.of.tables]]` needs nothing more: the document it returns is merged here."""
    for key in [k for k in target if k not in new]:
        del target[key]
    for key, value in new.items():
        if key not in target:
            _add(target, key, value)
            continue
        current = target[key]
        if isinstance(value, dict) and isinstance(current, dict):
            _merge(current, value)
        elif isinstance(current, tomlkit.items.AoT) and isinstance(value, list) and all(isinstance(v, dict) for v in value):
            for index, row in enumerate(value):
                if index < len(current):
                    _merge(current[index], row)
                else:
                    current.append(row)
            while len(current) > len(value):
                del current[len(current) - 1]
        elif (isinstance(current, list) and not current and isinstance(value, list) and value
              and all(isinstance(v, dict) for v in value)):
            del target[key]  # `rows = []` becomes the first `[[rows]]`
            _add(target, key, value)
        elif not _same(current.unwrap() if hasattr(current, "unwrap") else current, value):
            target[key] = value


def _apply_changes(target: Any, base: dict[str, Any], new: dict[str, Any]) -> None:
    """Edit `target` (what the file holds) by only what changed from `base` (what the file's settings dump to) to `new`: a value
    the Owner left alone, or a default the file never wrote, is not touched, and no default is added to the file."""
    for key in [k for k in base if k not in new]:
        if key in target:
            del target[key]
    for key, value in new.items():
        before = base.get(key)
        if key in base and _same(before, value):
            continue
        if key not in target:
            _add(target, key, value)
            continue
        current = target[key]
        if isinstance(before, dict) and isinstance(value, dict) and isinstance(current, dict):
            _apply_changes(current, before, value)
        elif (isinstance(before, list) and isinstance(value, list) and isinstance(current, tomlkit.items.AoT)
              and all(isinstance(v, dict) for v in before + value)):
            for index, row in enumerate(value):
                if index < len(current):
                    _apply_changes(current[index], before[index] if index < len(before) else {}, row)
                else:
                    current.append(row)
            while len(current) > len(value):
                del current[len(current) - 1]
        elif isinstance(current, list) and not current and value and all(isinstance(v, dict) for v in value):
            del target[key]  # `rows = []` becomes the first `[[rows]]`
            _add(target, key, value)
        else:
            target[key] = value


def _edited_in_place(path: Path, settings: ProjectSettings | AssetSettings, plain: str) -> str | None:
    """The file at `path` edited in place (tomlkit) to hold `settings`, or None when there is no file or the edit doesn't
    read back as the settings."""
    document = settings_document(settings)
    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8"))
        if isinstance(settings, ProjectSettings):
            migrated = _migrate(copy.deepcopy(raw), PROJECT_FILE_NAME, PROJECT_SCHEMA_VERSION, PROJECT_MIGRATIONS)
        else:
            migrated = _migrate(copy.deepcopy(raw), path.name, ASSET_SCHEMA_VERSION, ASSET_MIGRATIONS)
        base = settings_document(type(settings).model_validate(migrated))
        edited = tomlkit.parse(path.read_bytes().decode("utf-8"))
        _merge(edited, migrated)  # the migration, as edits
        _apply_changes(edited, base, document)  # then the change
        text = tomlkit.dumps(edited)
        if tomllib.loads(text) == tomllib.loads(plain) or type(settings).model_validate(tomllib.loads(text)) == settings:
            return text
    except (OSError, UnicodeDecodeError, ValueError, KiripixError, tomlkit.exceptions.TOMLKitError):
        pass
    return None


def render_settings(path: Path, settings: ProjectSettings | AssetSettings) -> str:
    """The text of the data file holding `settings`. When `path` exists it is edited in place (tomlkit): its comments, key
    order and layout stay, a migration changes only what it must, and only what differs from what the file already says is
    written. If the edit doesn't read back as the settings, the file is dumped whole."""
    plain = tomli_w.dumps(settings_document(settings))
    return _edited_in_place(path, settings, plain) or plain


def save_settings(path: Path, settings: ProjectSettings | AssetSettings) -> bool:
    """Write a data file at the current schema version, atomically, keeping the comments and layout of the file it replaces
    (the old file may be at an older schema version: a migration changes only what it must). Returns False when an existing
    file couldn't be edited in place and was written whole, losing its comments: the caller reports `settings.layout_lost`."""
    plain = tomli_w.dumps(settings_document(settings))
    existed = path.is_file()
    edited = _edited_in_place(path, settings, plain) if existed else None
    atomic.write_text(path, edited or plain)
    return edited is not None or not existed


def layout_lost(file: str) -> Finding:
    """The warning when `save_settings` had to write `file` whole."""
    return Finding(code="settings.layout_lost", severity="warning",
                   message=f"{file} couldn't be edited in place, so it was written whole: its comments and layout are gone",
                   position=Position(file=file),
                   owner_action=f"Restore the comments in {file} from its last commit (git diff {file}); the settings are right.")
