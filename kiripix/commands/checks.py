"""check, a Probe (no lock, nothing recorded), and preview, which writes only a preview image under .kiripix/."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiripix.commands.contract import Context, ExitCode, Outcome
from kiripix.commands.registry import CliMeta, command
from kiripix.core.assets import load_asset
from kiripix.core.hashing import HashCache
from kiripix.core.previews import write_preview
from kiripix.core.project import find_project
from kiripix.core.project_checks import check_all, check_asset
from kiripix.export import frozen_findings


class CheckInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str | None = Field(None, description="The Asset ID. Omit with --all.")
    all: bool = Field(False, description="Check every Asset, then the Project checks.")

    @model_validator(mode="after")
    def _asset_or_all(self) -> Self:
        if self.all == (self.asset is not None):
            raise ValueError("give an Asset ID or --all, not both")
        return self


class OutOfDate(BaseModel):
    asset: str
    stage: str
    status: str = Field(description="The Stage's derived status, which isn't `done`.")
    reason: str | None = None


class CheckData(BaseModel):
    """What was checked; the findings are in the result's `findings`."""

    assets: list[str]
    stages: list[str] = Field(description="The `<asset> <stage>` pairs whose Checks ran: those with an output.")
    project_checks: bool
    out_of_date: list[OutOfDate] = Field(
        default_factory=list,
        description="The checked Stages whose status isn't `done`: their Checks ran on an output that may not match "
                    "the current inputs, so a clean result doesn't cover them. Empty when everything checked is current.")

    def text(self) -> str:
        scope = "the Project" if self.project_checks else ", ".join(self.assets)
        line = f"checked {len(self.stages)} built Stage(s) of {scope}"
        if self.out_of_date:
            names = ", ".join(f"{o.asset} {o.stage}" if self.project_checks else o.stage for o in self.out_of_date)
            line = f"checked {len(self.stages)} built Stage(s), {len(self.out_of_date)} out of date: {names}"
        return line


@command(
    "check",
    summary="Run the Checks of every built Stage of an Asset, or of every Asset and the Project (--all).",
    input=CheckInput,
    output=CheckData,
    kind="probe",
    mcp="exposed",
    cli=CliMeta(positional=("asset",)),
)
def check(arguments: CheckInput, context: Context) -> Outcome[CheckData]:
    project = find_project(context.cwd)
    cache = HashCache(project.state_dir)
    broken = False
    if arguments.all:
        assets, stages, findings, broken, late = check_all(project, cache)
    else:
        assert arguments.asset is not None
        asset = load_asset(project, arguments.asset)
        done, findings, old = check_asset(project, asset, cache)
        late = [(asset.id, state) for state in old]
        findings += frozen_findings(project, asset, cache)  # the Exporter's: it reads the game's Manifest
        assets, stages = [asset.id], [f"{asset.id} {s}" for s in done]
    cache.save()
    if broken:
        code = ExitCode.ERROR
    elif any(f.severity == "error" for f in findings):
        code = ExitCode.CHECK_FAILED
    else:
        code = ExitCode.OK
    out_of_date = [OutOfDate(asset=a, stage=s.stage, status=s.status, reason=s.reason) for a, s in late]
    return Outcome(CheckData(assets=assets, stages=stages, project_checks=arguments.all, out_of_date=out_of_date),
                   findings, code)


class PreviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    stage: str | None = Field(None, description="The Stage to preview; default is the last done Stage with an image.")
    overlay: Literal["masks", "walkable", "reachable", "layers"] | None = Field(
        None, description="Tint each Mask over the image, or the walkable ground (the place Stage's output), or the "
                          "ground the Body can reach (the reach Stage's), or each Layer's alpha (the layers Stage's "
                          "output as built, one awaiting review too).")
    layer: str | None = Field(None, description="With --overlay layers: tint only this Layer.")
    brighten: float = Field(1.0, description="Multiply the image's colour by this before any tint, clipped; for looking "
                                             "at a dark room. 1 changes nothing. Only the preview file sees it.")
    zoom: int = Field(4, ge=1, le=16, description="Whole-number zoom, nearest neighbour.")
    region: str | None = Field(None, description="x,y,width,height in target pixels: crop to it before the zoom.")
    grid: int | None = Field(None, ge=1, description="A line every N target pixels, from the room's origin, drawn "
                                                      "after the zoom; every fifth is stronger.")


class PreviewRegion(BaseModel):
    x: int
    y: int
    width: int
    height: int


class PreviewLayer(BaseModel):
    id: str
    colour: str = Field(description="The tint, as #rrggbb.")


class PreviewData(BaseModel):
    asset: str
    stage: str
    path: str = Field(description="The PNG, relative to the Project.")
    width: int
    height: int
    zoom: int
    masks: list[str] = Field(description="The Masks tinted over the image, when an overlay was asked for.")
    overlay: str | None = None
    region: PreviewRegion | None = Field(None, description="The target pixels shown: pixel (i, j) of the PNG is target "
                                                           "pixel (x + i // zoom, y + j // zoom).")
    grid: int | None = None
    brighten: float = 1.0
    layers: list[PreviewLayer] = Field(default_factory=list, description="The Layers tinted, each with its colour, when "
                                                                           "the layers overlay was asked for.")
    awaiting_review: bool | None = Field(None, description="For the layers overlay: whether the Layers Stage's build "
                                                           "awaits the owner's review.")

    def text(self) -> str:
        return self.path


@command(
    "preview",
    summary="Write a Stage's image to .kiripix/previews/ at an integer zoom, and print its path.",
    input=PreviewInput,
    output=PreviewData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset",)),
)
def preview(arguments: PreviewInput, context: Context) -> Outcome[PreviewData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    cache = HashCache(project.state_dir)
    made = write_preview(project, asset, cache, arguments.stage, arguments.overlay, arguments.zoom,
                         arguments.region, arguments.grid, arguments.layer, arguments.brighten)
    cache.save()
    region = None
    if made.region is not None:
        x, y, width, height = made.region
        region = PreviewRegion(x=x, y=y, width=width, height=height)
    return Outcome(PreviewData(asset=asset.id, stage=made.stage, path=project.relative(made.path), width=made.width,
                               height=made.height, zoom=arguments.zoom, masks=made.masks, overlay=made.overlay,
                               region=region, grid=made.grid, brighten=arguments.brighten,
                               layers=[PreviewLayer(id=i, colour=c) for i, c in made.layers],
                               awaiting_review=made.awaiting_review), list(made.findings))
