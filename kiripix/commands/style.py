"""The Project's style references (ticket 0334, spec §4 and §10.3): `style-add` and `style-remove` edit `[style] references`
in `kiripix.toml`, owner-only. `check` measures every other Asset against the references (`kiripix.core.style`)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from kiripix.checks.style import STYLE_STAGES
from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core.assets import load_asset
from kiripix.core.errors import KiripixError, fail
from kiripix.core.project import PROJECT_FILE, find_project
from kiripix.core.settings import layout_lost, save_settings


class StyleReferenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.ch01_dungeon_r01. Its Kind is one with style Checks: "
                                   + ", ".join(STYLE_STAGES) + ".")


class StyleReferenceData(BaseModel):
    asset: str
    changed: bool = Field(description="False when the list already was as asked (the Asset was already a reference, or wasn't one).")
    references: list[str] = Field(description="Every reference after the Command, in file order.")

    def text(self) -> str:
        return f"{self.asset}: {'done' if self.changed else 'no change'}; references: {', '.join(self.references) or 'none'}"


@command(
    "style-add",
    summary="Make an Asset a style reference: `check` measures every other Asset's outline and pixel scale against the references (owner-only).",
    input=StyleReferenceInput,
    output=StyleReferenceData,
    kind="owner-only",
    mcp="owner-only",
    locks=LockNeeds(project=True),
    cli=CliMeta(positional=("asset",)),
)
def style_add(arguments: StyleReferenceInput, context: Context) -> Outcome[StyleReferenceData]:
    """Example: `kiripix style-add character.hero`. The Asset's Kind has style Checks (character, sprite, wearable, room, prop)."""
    project = find_project(context.cwd)
    try:
        asset = load_asset(project, arguments.asset)
    except KiripixError:
        raise fail("style.reference_unknown", f"'{arguments.asset}' names no Asset, so it can't be a style reference",
                   fix="kiripix status") from None
    if asset.kind not in STYLE_STAGES:
        raise fail("style.reference_unknown", f"{asset.id} is a {asset.kind}, which has no style Checks; a reference is a "
                   f"{', '.join(STYLE_STAGES)}", fix="kiripix status")
    listed = list(project.settings.style.references)
    if asset.id in listed:
        return Outcome(StyleReferenceData(asset=asset.id, changed=False, references=listed))
    listed.append(asset.id)
    updated = project.settings.model_copy(update={"style": project.settings.style.model_copy(update={"references": listed})})
    kept = save_settings(project.root / PROJECT_FILE, updated)
    return Outcome(StyleReferenceData(asset=asset.id, changed=True, references=listed),
                   findings=[] if kept else [layout_lost(PROJECT_FILE)])


@command(
    "style-remove",
    summary="Take an Asset out of the style references (owner-only). An entry that names no Asset can be taken out too.",
    input=StyleReferenceInput,
    output=StyleReferenceData,
    kind="owner-only",
    mcp="owner-only",
    locks=LockNeeds(project=True),
    cli=CliMeta(positional=("asset",)),
)
def style_remove(arguments: StyleReferenceInput, context: Context) -> Outcome[StyleReferenceData]:
    """Example: `kiripix style-remove character.hero`."""
    project = find_project(context.cwd)
    listed = list(project.settings.style.references)
    if arguments.asset not in listed:
        return Outcome(StyleReferenceData(asset=arguments.asset, changed=False, references=listed))
    listed = [r for r in listed if r != arguments.asset]
    updated = project.settings.model_copy(update={"style": project.settings.style.model_copy(update={"references": listed})})
    kept = save_settings(project.root / PROJECT_FILE, updated)
    return Outcome(StyleReferenceData(asset=arguments.asset, changed=True, references=listed),
                   findings=[] if kept else [layout_lost(PROJECT_FILE)])
