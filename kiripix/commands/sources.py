"""The Commands for an Asset's Variants: import and pick."""

from pathlib import Path

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
    file: Path = Field(description="The PNG or JPEG to add as a Variant; a JPEG is stored as a PNG.")


class ImportData(BaseModel):
    asset: str
    variant: str
    file: str
    created: bool
    variants: list[str]

    def text(self) -> str:
        added = "added" if self.created else "already had"
        return f"{self.asset}: {added} the Variant {self.variant} ({self.file}); pick it with " \
               f"kiripix pick {self.asset} {self.variant}"


@command(
    "import",
    summary="Add an image made elsewhere to an Asset as a Variant (a PNG, named by its hash).",
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
    name, path, created = sources.import_variant(asset, context.cwd / arguments.file, str(arguments.file))
    return Outcome(ImportData(asset=asset.id, variant=name, file=project.relative(path), created=created,
                              variants=list(sources.variants(asset))))


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
