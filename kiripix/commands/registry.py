"""The Command registry (ADR 0006). Every operation is declared here once; the adapters are generated from it."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel

from kiripix.commands.contract import Context, Outcome

CommandKind = Literal["writing", "probe", "owner-only"]
McpExposure = Literal["exposed", "hidden", "owner-only"]  # owner-only: never an MCP tool (spec §10.3)

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


@dataclass(frozen=True)
class CliMeta:
    """How the generated CLI presents a Command: which fields are positional, and option names other than
    `--field-name` (for example `{"view": ("--view", "-v")}`)."""

    positional: tuple[str, ...] = ()
    options: dict[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class LockNeeds:
    """The locks core takes before the Command runs. `asset` reads the Asset ID from the input (None: no lock)."""

    project: bool = False
    asset: Callable[[Any], str | None] | None = None
    gpu: bool = False


@dataclass(frozen=True)
class Command(Generic[I, O]):
    path: tuple[str, ...]
    summary: str
    input: type[I]
    output: type[O]
    handler: Callable[[I, Context], Outcome[O]]
    kind: CommandKind
    mcp: McpExposure
    cli: CliMeta = CliMeta()
    locks: LockNeeds = LockNeeds()
    group_summary: str | None = None
    files: tuple[str, ...] = ()  # input fields that are files: over REST, multipart parts of the request

    @property
    def name(self) -> str:
        return " ".join(self.path)


REGISTRY: dict[str, Command[Any, Any]] = {}


def command(
    path: str,
    *,
    summary: str,
    input: type[I],
    output: type[O],
    kind: CommandKind,
    mcp: McpExposure,
    cli: CliMeta = CliMeta(),
    locks: LockNeeds = LockNeeds(),
    group_summary: str | None = None,
    files: tuple[str, ...] = (),
) -> Callable[[Callable[[I, Context], Outcome[O]]], Callable[[I, Context], Outcome[O]]]:
    """Register the decorated handler as the Command `path` (`"op quantize"` for a grouped Command)."""

    def register(handler: Callable[[I, Context], Outcome[O]]) -> Callable[[I, Context], Outcome[O]]:
        cmd = Command(tuple(path.split()), summary, input, output, handler, kind, mcp, cli, locks, group_summary,
                      files)
        if unknown := set(files) - set(input.model_fields):
            raise ValueError(f"Command {cmd.name}: file inputs {sorted(unknown)} aren't input fields")
        if (kind == "owner-only") != (mcp == "owner-only"):
            raise ValueError(f"Command {cmd.name}: an owner-only Command, and only one, has mcp='owner-only'")
        if cmd.name in REGISTRY:
            raise ValueError(f"Command {cmd.name} registered twice")
        REGISTRY[cmd.name] = cmd
        return handler

    return register
