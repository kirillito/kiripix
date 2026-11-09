"""The Commands for an Asset's Variants: import and pick."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import sources
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
                                   ".fbx or .blend.")
    role: Literal["variant", "clip-source", "rigged"] = Field(
        "variant", description="What the file is. variant: a Source to pick. clip-source: an animation file (a Mixamo "
                               ".fbx) that a `clip` Decision's `source` names by its file stem. rigged: the rigged "
                               "file that comes back from Mixamo. The last two are for a character.")


class ImportData(BaseModel):
    asset: str
    role: str
    variant: str | None = Field(description="With role variant: the Variant's name.")
    clip_source: str | None = Field(description="With role clip-source: its name, the file stem.")
    rigged: str | None = Field(description="With role rigged: the rigged file's name.")
    file: str
    created: bool
    variants: list[str]
    clip_sources: list[str]

    def text(self) -> str:
        added = "added" if self.created else "already had"
        if self.role == "variant":
            return (f"{self.asset}: {added} the Variant {self.variant} ({self.file}); pick it with "
                    f"kiripix pick {self.asset} {self.variant}")
        what = f"the clip source {self.clip_source}" if self.role == "clip-source" else "the rigged file"
        return f"{self.asset}: {added} {what} ({self.file})"


@command(
    "import",
    summary="Add a file made elsewhere to an Asset: an image as a Variant (a PNG, named by its hash), or for a "
            "character a Model, an animation file or the rigged file (--role).",
    input=ImportInput,
    output=ImportData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("asset", "file")),
    locks=LockNeeds(asset=_asset_lock),
    files=("file",),
)
def import_variant(arguments: ImportInput, context: Context) -> Outcome[ImportData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    name, path, created = sources.import_file(asset, context.cwd / arguments.file, str(arguments.file), arguments.role)
    return Outcome(ImportData(
        asset=asset.id, role=arguments.role,
        variant=name if arguments.role == "variant" else None,
        clip_source=name if arguments.role == "clip-source" else None,
        rigged=name if arguments.role == "rigged" else None,
        file=project.relative(path), created=created,
        variants=list(sources.variants(asset)), clip_sources=list(sources.clip_sources(asset))))


# pick


class PickInput(_AssetInput):
    variant: str = Field(description="The Variant to use as the Source; `kiripix next` lists them.")


class PickData(BaseModel):
    asset: str
    stage: str
    variant: str
    id: str
    stages: list[StageState]

    def text(self) -> str:
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
    spec, entry = sources.pick(project, asset, arguments.variant)
    states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
    return Outcome(PickData(asset=asset.id, stage=spec.name, variant=arguments.variant, id=entry.id, stages=states))
