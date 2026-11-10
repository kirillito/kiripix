"""show, a Probe: one Asset as a UI needs it, with what `status` leaves out. Nothing here writes to the Project."""

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.decisions import DecisionOut, current_decisions
from kiripix.commands.registry import CliMeta, command
from kiripix.core import sources
from kiripix.core.assets import Asset, load_asset
from kiripix.core.graph import STAMP_FILE, AssetGraph, Status
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project, find_project
from kiripix.export import export_command
from kiripix.recipes.base import Scalar, SortPosition


class ShowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")


class VariantOut(BaseModel):
    name: str
    file: str = Field(description="The file, relative to the Project.")
    imported_as: str | None = Field(
        description="The file name it was imported with, or null if it was imported before Kiripix recorded names.")
    size: int = Field(description="The stored file's size in bytes.")


class StageDetail(BaseModel):
    stage: str
    status: Status
    reason: str | None
    params: dict[str, Scalar] = Field(description="The Stage's current parameters: its defaults and what `set` set.")
    decisions: list[DecisionOut]
    image: str | None = Field(description="The Stage's built image, relative to the Project.")
    input_image: str | None = Field(description="The built image this Stage is made from, relative to the Project.")
    outputs: list[str] = Field(description="The files of the Stage's built output, relative to the Project.")
    markers: list[dict[str, Any]] = Field(description="The Markers its Decisions place, whether built yet or not.")
    sort: list[SortPosition] = Field(
        description="Each Layer's sort position (layer, above, marker, y, slope), as its Decisions give it, whether built "
                    "yet or not. A Layer with no y-sort line and not above isn't listed: `check` reports it.")


class BodyOut(BaseModel):
    size: tuple[int, int] = Field(description="The Body's footprint in px: width and height.")
    dash: int = Field(description="The widest pit it can dash over, in px.")


class ShowData(BaseModel):
    asset: str
    kind: str
    params: dict[str, Scalar] = Field(description="The Asset's own parameters, such as a room's view.")
    resolution: tuple[int, int] = Field(description="The game's internal resolution, from kiripix.toml.")
    body: BodyOut = Field(description="The stand-in player, from kiripix.toml.")
    variants: list[VariantOut]
    picked: str | None
    clip_sources: list[VariantOut] = Field(description="A character's animation files, named by file stem.")
    rigged: VariantOut | None = Field(description="A character's rigged file.")
    stages: list[StageDetail]
    export_command: str | None = Field(
        None, description="While every Stage is done and the game doesn't have what is built: the Command that exports it.")

    def text(self) -> str:
        lines = [f"{self.asset} ({self.kind})"]
        lines += [f"  variant {v.name}{' (picked)' if v.name == self.picked else ''}" for v in self.variants]
        lines += [f"  clip source {c.name}" for c in self.clip_sources]
        lines += [f"  rigged {self.rigged.file}"] if self.rigged is not None else []
        for stage in self.stages:
            params = ", ".join(f"{k}={v}" for k, v in stage.params.items())
            lines.append(f"  {stage.stage:<10} {stage.status}" + (f"  {params}" if params else ""))
        if self.export_command:
            lines.append(f"  built, but not in the game yet: {self.export_command}")
        return "\n".join(lines)


def _variant(project: Project, asset: Asset, names: dict[str, str], name: str, path: Path) -> VariantOut:
    return VariantOut(name=name, file=project.relative(path),
                      imported_as=names.get(path.relative_to(asset.dir).as_posix()), size=path.stat().st_size)


def _outputs(project: Project, folder: Path) -> list[str]:
    if not (folder / STAMP_FILE).is_file():
        return []
    return [project.relative(path) for path in sorted(folder.iterdir()) if path.is_file() and path.name != STAMP_FILE]


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
    states = graph.states()
    for state in states:
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
            outputs=_outputs(project, graph.output_dir(spec)),
            markers=spec.markers(graph.replay(state.stage).current) if spec.markers is not None else [],
            sort=spec.sort(graph.replay(state.stage).current) if spec.sort is not None else [],
        ))
    takes_variants = sources.takes_pick(graph)
    variants = sources.variants(asset) if takes_variants else {}
    names = sources.imported_names(asset)
    data = ShowData(
        asset=asset.id,
        kind=asset.kind,
        params=dict(asset.settings.params),
        resolution=project.settings.project.resolution,
        body=BodyOut(size=project.settings.body.size, dash=project.settings.body.dash),
        variants=[_variant(project, asset, names, name, path) for name, path in variants.items()],
        picked=sources.picked(graph) if takes_variants else None,
        clip_sources=[_variant(project, asset, names, name, path)
                      for name, path in sources.clip_sources(asset).items()],
        rigged=_variant(project, asset, names, rigged_path.stem, rigged_path)
        if (rigged_path := sources.rigged(asset)) is not None else None,
        stages=stages,
        export_command=export_command(project, asset, cache, states),
    )
    cache.save()
    return Outcome(data)
