"""The Commands for an Asset's Variants: import and pick."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import loopkit, sheets, sources
from kiripix.core.errors import fail
from kiripix.core.assets import is_asset_id, load_asset
from kiripix.core.graph import AssetGraph, StageState
from kiripix.core.hashing import HashCache
from kiripix.core.project import find_project


class _AssetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")


def _asset_lock(arguments: _AssetInput) -> str | None:
    return arguments.asset if is_asset_id(arguments.asset) else None


# import


class ImportInput(_AssetInput):
    file: Path = Field(description="A room's or Prop's PNG or JPEG (a JPEG is stored as a PNG); a character's .glb, "
                                   ".fbx or .blend; a sprite's PNG or ZIP of PNGs.")
    role: Literal["variant", "clip-source", "rigged", "sheet"] | None = Field(
        None, description="What the file is. variant: a Source to pick (the default, except for a sprite). "
                          "clip-source: an animation file (a Mixamo .fbx) that a `clip` Decision's `source` names by "
                          "its file stem. rigged: the rigged file that comes back from Mixamo. The last two are for a "
                          "character. sheet: a sprite's PNG sheet or ZIP of PNGs, stored whole in src/sheets/ (the "
                          "default for a sprite; a ZIP with an unsafe or non-PNG entry is refused whole).")
    look: str | None = Field(None, description="A room's Look: store the image as an edit Variant of that Look "
                                               "(src/looks/<look>/), made on the room's picked Source, instead of as a "
                                               "Source. The room's source Stage stays done.")
    loop: str | None = Field(None, description="A room's frame Loop: import painted frames (the FILE, and any more PNGs "
                                               "after it) as its frames 1 to N-1, in name order, each exactly the size "
                                               "of the Loop's region box (`kiripix loop kit` writes a kit). Frame 0 is "
                                               "always the room's: a frame_000.png among them is skipped. Records the "
                                               "fit and the palette they were painted on.")
    frames: list[Path] = Field([], description="With --loop: more frames to import with FILE.")


class ImportData(BaseModel):
    asset: str
    look: str | None = Field(description="With --look: the Look the edit belongs to.")
    role: str
    variant: str | None = Field(description="With role variant: the Variant's name.")
    sheet: str | None = Field(description="With role sheet: the sheet's name, the start of its hash.")
    clip_source: str | None = Field(description="With role clip-source: its name, the file stem.")
    rigged: str | None = Field(description="With role rigged: the rigged file's name.")
    file: str
    created: bool
    loop: str | None = Field(None, description="With --loop: the Loop whose frames were imported.")
    loop_frames: list[str] = Field([], description="With --loop: the stored frames' names, for frames 1 to N-1, in order.")
    skipped: list[str] = Field([], description="With --loop: the files left out because they are frame 0.")
    variants: list[str] = Field(description="The Asset's Variants; with --look, that Look's edits.")
    clip_sources: list[str]
    sheets: list[str]

    def text(self) -> str:
        added = "added" if self.created else "already had"
        if self.loop is not None:
            skipped = f" (left out {', '.join(self.skipped)}: frame 0 is the room's)" if self.skipped else ""
            return (f"{self.asset}: imported {len(self.loop_frames)} frames of Loop {self.loop} ({self.file} ...){skipped}")
        if self.look is not None:
            return (f"{self.asset}: {added} the edit {self.variant} of Look {self.look} ({self.file}); pick it with "
                    f"kiripix pick {self.asset} {self.variant} --look {self.look}")
        if self.role == "sheet":
            return f"{self.asset}: {added} the sheet {self.sheet} ({self.file})"
        if self.role == "variant":
            return (f"{self.asset}: {added} the Variant {self.variant} ({self.file}); pick it with "
                    f"kiripix pick {self.asset} {self.variant}")
        what = f"the clip source {self.clip_source}" if self.role == "clip-source" else "the rigged file"
        return f"{self.asset}: {added} {what} ({self.file})"


@command(
    "import",
    summary="Add a file made elsewhere to an Asset: an image as a Variant (a PNG, named by its hash), for a "
            "character a Model, an animation file or the rigged file, or for a sprite a PNG sheet or a ZIP of PNGs "
            "(--role).",
    input=ImportInput,
    output=ImportData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("asset", "file", "frames")),
    locks=LockNeeds(asset=_asset_lock),
    files=("file",),
)
def import_variant(arguments: ImportInput, context: Context) -> Outcome[ImportData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    if arguments.loop is not None:
        shown = [arguments.file, *arguments.frames]
        if arguments.look is not None or (arguments.role or "variant") != "variant":
            raise fail("import.loop_takes_images", "--loop takes images only: not with --look or another --role",
                       fix=f"kiripix import {asset.id} {arguments.file} --loop {arguments.loop}")
        done = loopkit.import_frames(project, asset, [context.cwd / p for p in shown], [str(p) for p in shown],
                                     arguments.loop)
        return Outcome(ImportData(
            asset=asset.id, look=None, role="variant", variant=None, sheet=None, clip_source=None, rigged=None,
            file=project.relative(done.paths[0]), created=done.created, variants=[], clip_sources=[], sheets=[],
            loop=arguments.loop, loop_frames=done.names, skipped=done.skipped), done.findings)
    if arguments.frames:
        raise fail("import.frames_need_loop", "more than one file is imported only as the frames of a Loop",
                   fix=f"kiripix import {asset.id} {arguments.file} --loop <loop>")
    if arguments.look is not None:
        role = arguments.role or "variant"
        name, path, created = sources.import_look(project, asset, context.cwd / arguments.file, str(arguments.file),
                                                  role, arguments.look)
        return Outcome(ImportData(
            asset=asset.id, look=arguments.look, role=role, variant=name, sheet=None, clip_source=None, rigged=None,
            file=project.relative(path), created=created,
            variants=list(sources.look_variants(asset, arguments.look)), clip_sources=[], sheets=[]))
    role = arguments.role or ("sheet" if sources.takes_sheets(asset) else "variant")
    name, path, created = sources.import_file(asset, context.cwd / arguments.file, str(arguments.file), role)
    return Outcome(ImportData(
        asset=asset.id, look=None, role=role,
        variant=name if role == "variant" else None,
        sheet=name if role == "sheet" else None,
        clip_source=name if role == "clip-source" else None,
        rigged=name if role == "rigged" else None,
        file=project.relative(path), created=created,
        variants=list(sources.variants(asset)), clip_sources=list(sources.clip_sources(asset)),
        sheets=list(sheets.sheets(asset))))


# pick


class PickInput(_AssetInput):
    variant: str = Field(description="The Variant to use as the Source; `kiripix next` lists them. With --look, one "
                                     "of that Look's edits.")
    look: str | None = Field(None, description="A room's Look: pick that Look's edit Variant (made on the room's "
                                               "current Source) instead of the room's Source.")


class PickData(BaseModel):
    asset: str
    look: str | None = Field(description="With --look: the Look whose edit was picked.")
    stage: str
    variant: str
    id: str
    stages: list[StageState]

    def text(self) -> str:
        if self.look is not None:
            return f"{self.asset}: picked {self.variant} as the edit of Look {self.look} ({self.stage} Decision {self.id})"
        return f"{self.asset}: picked {self.variant} as the Source ({self.stage} Decision {self.id})"


@command(
    "pick",
    summary="Pick one of an Asset's Variants as its Source (records the Pick Decision).",
    input=PickInput,
    output=PickData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "variant")),
    locks=LockNeeds(asset=_asset_lock),
)
def pick(arguments: PickInput, context: Context) -> Outcome[PickData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    if arguments.look is not None:
        spec, entry = sources.pick_look(project, asset, arguments.look, arguments.variant)
    else:
        spec, entry = sources.pick(project, asset, arguments.variant)
    states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
    return Outcome(PickData(asset=asset.id, look=arguments.look, stage=spec.name, variant=arguments.variant,
                            id=entry.id, stages=states))
