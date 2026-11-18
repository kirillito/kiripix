"""The Command registry (ADR 0006). Every operation is declared here once; the adapters are generated from it."""

import importlib
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Literal, TypeVar

from pydantic import BaseModel

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.index import INDEX

if TYPE_CHECKING:
    from _collections_abc import dict_items, dict_keys, dict_values

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
    assets: Callable[[Any], list[str]] | None = None  # for a Command on several Assets; core takes them in a fixed order
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


class Registry(dict[str, Command[Any, Any]]):
    """The registry, filled on demand from the static index (`kiripix.commands.index`, ticket 0277).

    A Command's module is imported when that Command is looked up by name, or all of them when the registry is
    iterated (`schema`, `describe`, the server). So a call that runs one Command imports one module, not fifty.
    Registering (`command`) writes with the plain `dict` methods, so it never triggers a load.
    """

    def load(self, name: str) -> None:
        """Import the module that declares `name`, if the index knows it and it isn't registered yet."""
        if not dict.__contains__(self, name) and name in INDEX:
            importlib.import_module(INDEX[name].module)

    def load_all(self) -> None:
        if dict.__len__(self) == len(INDEX) and all(dict.__contains__(self, n) for n in INDEX):
            return
        for module in dict.fromkeys(entry.module for entry in INDEX.values()):
            importlib.import_module(module)
        ordered = {n: dict.__getitem__(self, n) for n in INDEX if dict.__contains__(self, n)}
        ordered.update((n, c) for n, c in dict.items(self) if n not in ordered)  # not in the index: a test finds it
        dict.clear(self)
        dict.update(self, ordered)

    def __getitem__(self, name: str) -> Command[Any, Any]:
        self.load(name)
        return dict.__getitem__(self, name)

    def __contains__(self, name: object) -> bool:
        return dict.__contains__(self, name) or name in INDEX

    def get(self, name: str, default: Any = None) -> Any:
        self.load(name)
        return dict.get(self, name, default)

    def __iter__(self) -> Iterator[str]:
        self.load_all()
        return dict.__iter__(self)

    def __len__(self) -> int:
        self.load_all()
        return dict.__len__(self)

    def keys(self) -> "dict_keys[str, Command[Any, Any]]":
        self.load_all()
        return dict.keys(self)

    def values(self) -> "dict_values[str, Command[Any, Any]]":
        self.load_all()
        return dict.values(self)

    def items(self) -> "dict_items[str, Command[Any, Any]]":
        self.load_all()
        return dict.items(self)


REGISTRY = Registry()


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
        if dict.__contains__(REGISTRY, cmd.name):
            raise ValueError(f"Command {cmd.name} registered twice")
        REGISTRY[cmd.name] = cmd
        return handler

    return register
