"""The Project's named terrain Masks (ticket 0344, spec §4, §6.1): `masks-add` adds a painted Mask to `[masks.<view>]` in
`kiripix.toml`, and `MaskRow` is how `describe room` lists every Mask of the Project. Only `solid` and `pit` block anything
in Kiripix; a Mask added here has no meaning to `reach` or the walk test, and is the game's to read."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.mask_table import MaskRow, mask_rows
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core.errors import fail
from kiripix.core.project import PROJECT_FILE, Project, find_project
from kiripix.core.settings import MaskDefinition, ProjectSettings, layout_lost, save_settings

_NAME = re.compile(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_RESERVED = ("walkable", "foreground", "import")  # derived Masks, and the key of the import colours


class MasksAddInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="The new Mask's name, lower-case snake_case, such as `cover`. Not `walkable`, "
                                  "`foreground` or the name of a Mask the view has.")
    colour: str = Field(description="Its display and import colour, #RRGGBB, not used by another Mask of the view.")
    meaning: str = Field(min_length=1, description="What it means to the game, in a few words. Kiripix attaches no "
                                                   "meaning to it: only `solid` and `pit` block anything.")
    view: Literal["top", "side"] = Field("top", description="The room view the Mask is for.")


class MasksAddData(BaseModel):
    view: Literal["top", "side"]
    mask: MaskRow = Field(description="The Mask that was added.")
    masks: list[MaskRow] = Field(description="Every Mask of the view after the Command, in file order.")

    def text(self) -> str:
        return f"added the {self.view}-view Mask '{self.mask.name}' ({self.mask.colour}): {self.mask.meaning}"


def _colour_findings(project: Project, view: Literal["top", "side"], colour: str) -> None:
    masks = project.settings.masks[view]
    for name, definition in masks.painted().items():
        if definition.colour is not None and definition.colour.upper() == colour:
            raise fail("masks.colour_taken", f"the colour {colour} is already the {view}-view Mask '{name}'",
                       owner_action=f"Choose another colour for the new Mask; the {view} view uses "
                                    f"{', '.join(sorted(d.colour for d in masks.painted().values() if d.colour))}.")
    for imported, names in masks.import_colours.items():
        if imported.upper() == colour:
            raise fail("masks.colour_taken", f"the colour {colour} is an import colour of the {view} view, for "
                       f"{', '.join(names)}", owner_action=f"Choose another colour for the new Mask, or remove "
                       f"[masks.{view}.import] {imported} in {PROJECT_FILE}.")


@command(
    "masks-add",
    summary="Add a named painted Mask to the Project, for the game to read (kiripix gives it no meaning).",
    input=MasksAddInput,
    output=MasksAddData,
    kind="writing",
    mcp="exposed",
    locks=LockNeeds(project=True),
    cli=CliMeta(positional=("name",)),
)
def masks_add(arguments: MasksAddInput, context: Context) -> Outcome[MasksAddData]:
    """Example: `kiripix masks-add cover --colour "#00AA00" --meaning "half cover"`; then paint it with `decide <room> masks`
    (brush, polygon, flood) as any painted Mask. It never blocks movement: `reach` and the walk test ignore it."""
    project = find_project(context.cwd)
    view = arguments.view
    name = arguments.name
    if not _NAME.match(name):
        raise fail("masks.name_invalid", f"'{name}' can't be a Mask name: it is lower-case snake_case, such as `cover`",
                   fix=f"kiripix masks-add <snake_case_name> --colour {arguments.colour} --meaning ...")
    existing = project.settings.masks[view]
    have = existing.definitions()
    if name in _RESERVED or name in have:
        why = "derived or reserved" if name in _RESERVED else f"already a Mask of the {view} view"
        raise fail("masks.name_taken", f"'{name}' can't be added: it is {why} ({', '.join(have)})",
                   owner_action="Choose another name; to change an existing Mask, edit " + PROJECT_FILE + ".")
    if not _HEX.match(arguments.colour):
        raise fail("masks.colour_invalid", f"the colour '{arguments.colour}' isn't #RRGGBB",
                   fix=f'kiripix masks-add {name} --colour "#RRGGBB" --meaning ...')
    colour = arguments.colour.upper()
    _colour_findings(project, view, colour)
    definition = MaskDefinition(colour=colour, meaning=arguments.meaning)
    changed = existing.model_copy(deep=True)
    assert changed.__pydantic_extra__ is not None
    changed.__pydantic_extra__[name] = definition
    updated = project.settings.model_copy(update={"masks": {**project.settings.masks, view: changed}})
    kept = save_settings(project.root / PROJECT_FILE, updated)
    rows = [row for row in mask_rows(updated) if row.view == view]
    row = next(r for r in rows if r.name == name)
    return Outcome(MasksAddData(view=view, mask=row, masks=rows), findings=[] if kept else [layout_lost(PROJECT_FILE)])
