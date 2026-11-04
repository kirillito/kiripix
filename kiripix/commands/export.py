"""`kiripix export`: an Asset's final outputs into the Godot project, under the Manifest's rules (spec §9, ADR 0003)."""

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core.assets import is_asset_id, load_asset
from kiripix.core.hashing import HashCache
from kiripix.core.project import find_project
from kiripix.export import export_asset


class ExportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")


class ExportData(BaseModel):
    asset: str
    written: list[str] = Field(description="The files written, as res:// paths.")
    unchanged: list[str] = Field(description="The files that already held what export would write.")
    manifest: str = Field(description="The Manifest's res:// path.")
    counter: int = Field(description="Goes up each time what this Asset exports changes.")

    def text(self) -> str:
        return f"{self.asset}: wrote {len(self.written)} file(s), {len(self.unchanged)} unchanged, counter {self.counter}"


@command(
    "export",
    summary="Write a fully built Asset into the Godot project: its scene, its images and its Manifest.",
    input=ExportInput,
    output=ExportData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset",)),
    locks=LockNeeds(project=True, asset=lambda a: a.asset if is_asset_id(a.asset) else None),
)
def export(arguments: ExportInput, context: Context) -> Outcome[ExportData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    cache = HashCache(project.state_dir)
    result = export_asset(project, asset, cache)
    cache.save()
    return Outcome(ExportData(asset=asset.id, written=result.written, unchanged=result.unchanged,
                              manifest=result.manifest, counter=result.counter))
