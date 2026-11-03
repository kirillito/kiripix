"""Probes (spec §10.1): read-only questions about an Asset. They record nothing, are never pinned, and take no lock.

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

ProbeFunction = Callable[[Asset, list[str], Context], dict[str, Any]]


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
def _echo(asset: Asset, args: list[str], context: Context) -> dict[str, Any]:
    return {"kind": asset.kind, "args": args}


class ProbeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(description="The Probe's name, such as segment-preview or echo.")
    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")
    args: list[str] = Field([], description="The Probe's own arguments.")


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
    return Outcome(ProbeData(probe=chosen.name, asset=asset.id, result=chosen.run(asset, arguments.args, context)))
