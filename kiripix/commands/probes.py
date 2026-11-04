"""Probes (spec §10.1): read-only questions about an Asset. They record nothing, are never pinned, and take no Asset lock.
One that loads a Runner takes the GPU lock, as anything loading a Runner does.

`kiripix probe <name> <id> <args...>` runs one. Over REST the server keeps whatever makes a Probe fast (a warm Runner,
a cached embedding); in the CLI a Probe works too, only slower. A Probe is registered with `@probe(name)`.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, command
from kiripix.core.assets import Asset, load_asset
from kiripix.core.errors import fail
from kiripix.core.project import find_project
from kiripix.core.segmenting import segment_preview
from kiripix.ops import mask_runs
from kiripix.recipes.base import ClickPoint

class ProbeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="The Probe's name, such as segment-preview or echo.")
    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    args: list[str] = Field([], description="The Probe's own arguments. segment-preview takes clicks in target pixels: "
                                            "x,y for a positive one and x,y,neg for a negative one.")
    cpu: bool = Field(False, description="Run any Runner on the CPU, without the GPU lock.")


ProbeFunction = Callable[[Asset, ProbeInput, Context], dict[str, Any]]


@dataclass(frozen=True)
class Probe:
    name: str
    summary: str
    run: ProbeFunction


PROBES: dict[str, Probe] = {}


def probe(name: str, *, summary: str) -> Callable[[ProbeFunction], ProbeFunction]:
    def register(function: ProbeFunction) -> ProbeFunction:
        if name in PROBES:
            raise ValueError(f"Probe {name} registered twice")
        PROBES[name] = Probe(name, summary, function)
        return function

    return register


@probe("echo", summary="Answer with the Asset's Kind and the arguments given: proves the Probe path.")
def _echo(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    return {"kind": asset.kind, "args": arguments.args}


def _click_point(text: str, asset: Asset) -> ClickPoint:
    parts = text.split(",")
    sign = parts[2] if len(parts) == 3 else ""
    if len(parts) not in (2, 3) or sign not in ("", "neg") or not (parts[0].isdecimal() and parts[1].isdecimal()):
        raise fail("input.invalid", f"'{text}' isn't a click: give x,y for a positive one, or x,y,neg for a negative one",
                   fix=f"kiripix probe segment-preview {asset.id} 10,12")
    return int(parts[0]), int(parts[1]), sign != "neg"


@probe("segment-preview", summary="The Mask a click would make, as runs of [y, x, length], on the target grid.")
def _segment_preview(asset: Asset, arguments: ProbeInput, context: Context) -> dict[str, Any]:
    if not arguments.args:
        raise fail("input.invalid", "segment-preview needs at least one click",
                   fix=f"kiripix probe segment-preview {asset.id} 10,12")
    points = [_click_point(text, asset) for text in arguments.args]
    made = segment_preview(find_project(context.cwd), asset, points, keep_warm=context.via == "rest", cpu=arguments.cpu,
                           wait=context.wait, command_line=context.command_line, progress=context.progress)
    return {
        "width": made.mask.shape[1],
        "height": made.mask.shape[0],
        "pixels": int(made.mask.sum()),
        "runs": mask_runs(made.mask),
        "embedding": "computed" if made.computed else "cached",
        "device": made.device,
    }


class ProbeData(BaseModel):
    probe: str
    asset: str
    result: dict[str, Any]

    def text(self) -> str:
        return f"{self.probe} {self.asset}: {self.result}"


@command(
    "probe",
    summary="Run a Probe: a read-only question about an Asset, such as segment-preview. Records nothing.",
    input=ProbeInput,
    output=ProbeData,
    kind="probe",
    mcp="hidden",
    cli=CliMeta(positional=("name", "asset", "args")),
)
def run_probe(arguments: ProbeInput, context: Context) -> Outcome[ProbeData]:
    chosen = PROBES.get(arguments.name)
    if chosen is None:
        raise fail("probe.unknown", f"no Probe '{arguments.name}'; the Probes are {', '.join(sorted(PROBES))}",
                   fix="kiripix probe echo <asset>")
    asset = load_asset(find_project(context.cwd), arguments.asset)
    return Outcome(ProbeData(probe=chosen.name, asset=asset.id, result=chosen.run(asset, arguments, context)))
