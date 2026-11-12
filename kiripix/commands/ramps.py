"""The Project ramp table (ticket 0167, spec §6.3): `ramps-add` (owner-only) appends parts of a character's built `palette.json` to
`[[character.ramps]]` in `kiripix.toml`, so every character gets the same part names, ramp lengths and rows."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.ramp_table import RAMPS_EXAMPLE, RampRow
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import atomic
from kiripix.core import ramps as core_ramps  # noqa: F401 - registers the Project check `palette.parts_differ`
from kiripix.core.assets import load_asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import PROJECT_FILE, find_project
from kiripix.core.settings import (
    PROJECT_SCHEMA_VERSION,
    ProjectSettings,
    RampSpec,
    ramp_table_findings,
    read_project_palette,
    save_settings,
)

_NAME = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")


class RampsAddInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character: str = Field(description="The character Asset whose built `palette` the parts are taken from, such as "
                                       "character.hero.")
    parts: str = Field(min_length=1, description="The parts to add, comma-separated, each named as in the character's "
                                                 f"palette.json. Example: `{RAMPS_EXAMPLE}`.")
    colours: bool = Field(False, description="Give each added part the colours of the character's ramp (`rgb`), so every "
                                             "character shares them; without it only the name, length and row are shared.")
    dry_run: bool = Field(False, description="Write nothing; show the table that would be written.")


class RampsAddData(BaseModel):
    character: str
    dry_run: bool
    wrote: bool = Field(description="Whether kiripix.toml changed.")
    added: list[str] = Field(description="The parts appended to the table.")
    unchanged: list[str] = Field(description="The parts already in the table, with the same length and colours.")
    table: list[RampRow] = Field(description="The table after the Command (the one it would write, with dry_run).")

    def text(self) -> str:
        verb = "would add" if self.dry_run else "added"
        if not self.added:
            return f"The ramp table already holds {', '.join(self.unchanged)}: nothing to write"
        return f"{verb} {', '.join(self.added)} to the ramp table ({len(self.table)} rows in all)"


def _row(ramp: RampSpec) -> RampRow:
    return RampRow(name=ramp.name, length=ramp.length, rgb=[list(c) for c in ramp.rgb] if ramp.rgb is not None else None)


def _block(ramp: RampSpec) -> str:
    lines = ["[[character.ramps]]", f"name = {tomli_w.dumps({'v': ramp.name})[4:].strip()}", f"length = {ramp.length}"]
    if ramp.rgb is not None:
        lines.append("rgb = [" + ", ".join(f"[{r}, {g}, {b}]" for r, g, b in ramp.rgb) + "]")
    return "\n".join(lines) + "\n"


def _write(path: Path, text: str, updated: ProjectSettings, added: list[RampSpec]) -> None:
    """Append the new rows to the file as text, so the Owner's comments stay; when the file isn't at the current schema version
    or the text doesn't read back as the new settings, write the whole file."""
    try:
        document = tomllib.loads(text)
        if document.get("schema_version") == PROJECT_SCHEMA_VERSION:
            new_text = text + ("" if text.endswith("\n") else "\n") + "\n" + "\n".join(_block(r) for r in added)
            if ProjectSettings.model_validate(tomllib.loads(new_text)) == updated:
                atomic.write_text(path, new_text)
                return
    except (tomllib.TOMLDecodeError, ValidationError):
        pass
    save_settings(path, updated)


@command(
    "ramps-add",
    summary="Append parts of a character's built palette to the Project's ramp table (owner-only).",
    input=RampsAddInput,
    output=RampsAddData,
    kind="owner-only",
    mcp="owner-only",
    locks=LockNeeds(project=True),
    cli=CliMeta(positional=("character",)),
)
def ramps_add(arguments: RampsAddInput, context: Context) -> Outcome[RampsAddData]:
    """Example: `kiripix ramps-add character.hero --parts skin,hair --colours`; then `kiripix ramps-add character.hero
    --parts top` adds a part whose colours each character fits for itself."""
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.character)
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    palette = core_ramps.built_palette(graph)
    if palette is None:
        raise fail("ramps.palette_not_built", f"{asset.id} has no built `palette` Stage to take parts from",
                   fix=f"kiripix run {asset.id} palette")
    built = {str(p.get("name")): p for p in palette.get("parts", []) if isinstance(p, dict)}
    names = [n.strip() for n in arguments.parts.split(",") if n.strip()]
    if not names:
        raise fail("ramps.parts_missing", "no part named in --parts", owner_action="Name parts, such as --parts skin,hair.")
    table = list(project.settings.character.ramps)
    in_table = {r.name: r for r in table}
    added: list[RampSpec] = []
    unchanged: list[str] = []
    for name in dict.fromkeys(names):
        if name not in built:
            have = ", ".join(built) or "none (the character has no `parts`)"
            raise fail("ramps.part_unknown", f"{asset.id}'s palette has no part '{name}'; its parts are: {have}",
                       owner_action=f"Name one of the character's parts, or set them: kiripix set {asset.id} palette parts=...")
        if not _NAME.match(name):
            raise fail("ramps.part_name_invalid", f"'{name}' can't be a row of the table: a part name there is lower-case "
                       "snake_case", owner_action=f"Rename the part in {asset.id}'s `parts` (kiripix set {asset.id} palette "
                       "parts=...), then add it.")
        rgb = [tuple(int(c) for c in colour) for colour in built[name].get("rgb", [])]
        existing = in_table.get(name)
        if existing is not None:
            differs = []
            if existing.length != len(rgb):
                differs.append(f"length is {existing.length} in the table and {len(rgb)} in {asset.id}")
            if arguments.colours and (existing.rgb or None) != (rgb or None):
                differs.append(f"rgb are {'not set' if existing.rgb is None else 'other colours'} in the table")
            if differs:
                raise fail("ramps.part_differs", f"'{name}' is already in the ramp table, and differs: {'; '.join(differs)}",
                           owner_action=f"Edit [[character.ramps]] '{name}' in {PROJECT_FILE}, or change the character's part "
                                        f"to match.")
            unchanged.append(name)
            continue
        spec_kwargs = {"name": name, "length": len(rgb)}
        try:
            spec = RampSpec.model_validate({**spec_kwargs, **({"rgb": rgb} if arguments.colours else {})})
        except ValidationError as error:
            raise fail("ramps.part_invalid", f"'{name}' can't be a row of the table: {error.errors()[0]['msg']}",
                       owner_action=f"Give the part in {asset.id} a ramp of at least 2 steps (parts={name}:3).") from None
        table.append(spec)
        in_table[name] = spec
        added.append(spec)
    updated = project.settings.model_copy(update={
        "character": project.settings.character.model_copy(update={"ramps": table})})
    problems = ramp_table_findings(table, read_project_palette(project.root, project.settings.project.palette))
    if problems:
        raise KiripixError(problems)
    wrote = bool(added) and not arguments.dry_run
    if wrote:
        path = project.root / PROJECT_FILE
        _write(path, path.read_text(encoding="utf-8"), updated, added)
    return Outcome(RampsAddData(character=asset.id, dry_run=arguments.dry_run, wrote=wrote,
                                added=[r.name for r in added], unchanged=unchanged, table=[_row(r) for r in table]))
