"""show, a Probe: one Asset as a UI needs it, with what `status` leaves out. Nothing here writes to the Project."""

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.decisions import DecisionOut, current_decisions
from kiripix.commands.registry import CliMeta, command
from kiripix.core import sources
from kiripix.core.assets import load_asset
from kiripix.core.graph import AssetGraph, Status
from kiripix.core.hashing import HashCache
from kiripix.core.project import find_project
from kiripix.recipes.base import Scalar


class ShowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")


class VariantOut(BaseModel):
    name: str
    file: str = Field(description="The image, relative to the Project.")


class StageDetail(BaseModel):
    stage: str
    status: Status
    reason: str | None
    params: dict[str, Scalar] = Field(description="The Stage's current parameters: its defaults and what `set` set.")
    decisions: list[DecisionOut]
    image: str | None = Field(description="The Stage's built image, relative to the Project.")
    input_image: str | None = Field(description="The built image this Stage is made from, relative to the Project.")


class ShowData(BaseModel):
    asset: str
    kind: str
    params: dict[str, Scalar] = Field(description="The Asset's own parameters, such as a room's view.")
    resolution: tuple[int, int] = Field(description="The game's internal resolution, from kiripix.toml.")
    variants: list[VariantOut]
    picked: str | None
    stages: list[StageDetail]

    def text(self) -> str:
        lines = [f"{self.asset} ({self.kind})"]
        lines += [f"  variant {v.name}{' (picked)' if v.name == self.picked else ''}" for v in self.variants]
        for stage in self.stages:
            params = ", ".join(f"{k}={v}" for k, v in stage.params.items())
            lines.append(f"  {stage.stage:<10} {stage.status}" + (f"  {params}" if params else ""))
        return "\n".join(lines)


@command(
    "show",
    summary="Show one Asset: its Variants and Pick, and each Stage's status, parameters, Decisions and images.",
    input=ShowInput,
    output=ShowData,
    kind="probe",
    mcp="hidden",
    cli=CliMeta(positional=("asset",)),
)
def show(arguments: ShowInput, context: Context) -> Outcome[ShowData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    cache = HashCache(project.state_dir)
    graph = AssetGraph(project, asset, cache)
    stages = []
    for state in graph.states():
        spec = graph.spec(state.stage)
        image = graph.output_dir(spec) / spec.image if spec.image is not None else None
        source = graph.input_image(spec)
        stages.append(StageDetail(
            stage=state.stage,
            status=state.status,
            reason=state.reason,
            params=graph.params(spec),
            decisions=current_decisions(graph.replay(state.stage).current),
            image=project.relative(image) if image is not None and image.is_file() else None,
            input_image=project.relative(source[1]) if source is not None and source[1].is_file() else None,
        ))
    takes_variants = sources.takes_pick(graph)
    variants = sources.variants(asset) if takes_variants else {}
    data = ShowData(
        asset=asset.id,
        kind=asset.kind,
        params=dict(asset.settings.params),
        resolution=project.settings.project.resolution,
        variants=[VariantOut(name=name, file=project.relative(path)) for name, path in variants.items()],
        picked=sources.picked(graph) if takes_variants else None,
        stages=stages,
    )
    cache.save()
    return Outcome(data)
