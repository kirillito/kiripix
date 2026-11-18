"""The CLI adapter: a Typer app generated from the Command registry. It holds no logic of its own.

It parses arguments into the Command's input, calls `invoke`, and renders the result as text or, with `--json`, as
exactly one JSON object on stdout. The exit code comes from the result. Uses only `kiripix.commands`.
"""

from __future__ import annotations

import inspect
import shlex
import signal
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from types import NoneType, UnionType
from typing import TYPE_CHECKING, Any, Literal, Union, get_args, get_origin

import typer

from kiripix.commands import INDEX

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

    from kiripix.commands import CliMeta, Command, Context, Envelope, Launcher, ProgressEvent

# Nothing else of `kiripix.commands` loads at import: `--help` and the root's and a group's listing need only the
# static index, so they skip pydantic and the stage graph. What runs imports what it needs (ticket 0277).

_JSON = "kpx_json"
_PROGRESS = "kpx_progress"
_WAIT = "kpx_wait"


class _State:
    exit_code = 0


def _command_line() -> str:
    return shlex.join(["kiripix", *sys.argv[1:]])


def _stdin_is_terminal() -> bool:
    """Whether stdin is an interactive terminal, for owner-only Commands. On Windows `isatty` is true for the NUL
    device too, so stdin must also be a console."""
    if sys.stdin is None or not sys.stdin.isatty():
        return False
    if sys.platform != "win32":
        return True
    import ctypes
    import msvcrt

    mode = ctypes.c_uint32()
    return bool(ctypes.windll.kernel32.GetConsoleMode(msvcrt.get_osfhandle(sys.stdin.fileno()), ctypes.byref(mode)))


def _write(stream: Any, text: str) -> None:
    stream.write(text)
    stream.flush()


def _render(envelope: Envelope[Any], as_json: bool) -> None:
    if as_json:
        _write(sys.stdout, envelope.model_dump_json() + "\n")
        return
    data = envelope.data
    if data is not None:
        text = data.text() if hasattr(data, "text") else data.model_dump_json(indent=2)
        _write(sys.stdout, text + "\n")
    for finding in envelope.findings:
        remedy = f"  fix: {finding.fix}" if finding.fix else f"  owner: {finding.owner_action}"
        _write(sys.stderr, f"{finding.severity} {finding.code}: {finding.message}\n{remedy}\n")


def _progress_sink(mode: str) -> Any:
    def emit(event: ProgressEvent) -> None:
        _write(sys.stderr, event.model_dump_json() + "\n")

    def ignore(event: ProgressEvent) -> None:
        pass

    return emit if mode == "jsonl" else ignore


def _unwrap(annotation: Any) -> tuple[Any, bool]:
    """Strip `X | None`, returning X and whether None was allowed."""
    if get_origin(annotation) in (Union, UnionType):
        args = [a for a in get_args(annotation) if a is not NoneType]
        if len(args) == 1:
            return args[0], True
    return annotation, False


def _parameter(name: str, field: FieldInfo, cli: CliMeta) -> inspect.Parameter:
    annotation, optional = _unwrap(field.annotation)
    default = ... if field.is_required() else field.default
    if name in cli.positional:
        info = typer.Argument(default, help=field.description, metavar=name.upper(),
                              show_default=default is not None and default is not ...)
    else:
        declarations = cli.options.get(name, (f"--{name.replace('_', '-')}",))
        info = typer.Option(default, *declarations, help=field.description,
                            show_default=default is not None and default is not ...)
    return inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=info,
                             annotation=annotation | None if optional else annotation)


def _callback(command: Command[Any, Any]) -> Any:
    parameters = [_parameter(name, field, command.cli) for name, field in command.input.model_fields.items()]
    parameters.append(inspect.Parameter(_JSON, inspect.Parameter.KEYWORD_ONLY, annotation=bool,
                                        default=typer.Option(False, "--json", help="Print one JSON object.")))
    parameters.append(inspect.Parameter(
        _PROGRESS, inspect.Parameter.KEYWORD_ONLY, annotation=Literal["none", "jsonl"],
        default=typer.Option("none", "--progress",
                             help="jsonl streams progress events on stderr."),
    ))
    if command.kind in ("writing", "owner-only"):
        parameters.append(inspect.Parameter(
            _WAIT, inspect.Parameter.KEYWORD_ONLY, annotation=float,
            default=typer.Option(0.0, "--wait", min=0, help="Wait up to this many seconds for a held lock."),
        ))

    def callback(**values: Any) -> None:
        as_json = values.pop(_JSON)
        progress = values.pop(_PROGRESS)
        wait = values.pop(_WAIT, 0.0)
        from kiripix.commands import Context

        context = Context(cwd=Path.cwd(), command_line=_command_line(), wait=wait, progress=_progress_sink(progress),
                          interactive=_stdin_is_terminal())
        envelope, exit_code = _invoke_cancellable(command, values, context)
        _render(envelope, as_json)
        _State.exit_code = int(exit_code)

    callback.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    callback.__annotations__ = {p.name: p.annotation for p in parameters}
    callback.__name__ = command.path[-1]
    callback.__doc__ = command.summary
    return callback


def _invoke_cancellable(command: Command[Any, Any], values: dict[str, Any], context: Context) -> Any:
    """`invoke`, with Ctrl+C setting the cancel token as well as raising KeyboardInterrupt on this thread."""

    def interrupted(signum: int, frame: Any) -> None:
        context.cancel.cancel()
        raise KeyboardInterrupt

    from kiripix.commands import invoke

    previous = signal.signal(signal.SIGINT, interrupted)
    try:
        return invoke(command, values, context)
    finally:
        signal.signal(signal.SIGINT, previous)


def _launcher_callback(launcher: Launcher) -> Any:
    from kiripix.commands import CliMeta

    parameters = [_parameter(name, field, CliMeta()) for name, field in launcher.input.model_fields.items()]

    def callback(**values: Any) -> None:
        _State.exit_code = int(launcher.run(launcher.input.model_validate(values), Path.cwd()))

    callback.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    callback.__annotations__ = {p.name: p.annotation for p in parameters}
    callback.__name__ = launcher.name
    callback.__doc__ = launcher.summary
    return callback


def _stub() -> Any:
    """A Command's place in the help, without its parameters: `--help` of the root or of a group shows only names and
    summaries, so the Command's module isn't imported for it (ticket 0277)."""

    def callback() -> None:
        raise RuntimeError("a Command that was not loaded was called")

    return callback


def called_command(argv: Sequence[str]) -> Command[Any, Any] | None:
    """The Command the arguments name (`status`, `op quantize`), loading only its module, or None for the root's or a
    group's help, a Launcher or a typo, which the stub app answers."""
    words = [word for word in argv[:2] if not word.startswith("-")] if argv and not argv[0].startswith("-") else []
    for name in (" ".join(words), words[0] if words else ""):
        if name in INDEX:
            from kiripix.commands import REGISTRY

            return REGISTRY[name]
    return None


def build_app(listing: Sequence[tuple[str, str]], launchers: Callable[[], Sequence[Launcher]], *,
              only: Command[Any, Any] | None = None, launcher: str | None = None,
              all_commands: bool = False) -> typer.Typer:
    """The Typer app. Every Command and Launcher is listed from static data; only `only` (the Command that runs), the
    Launcher named `launcher`, or with `all_commands` every one gets its real parameters, because only what runs needs
    them."""
    app = typer.Typer(name="kiripix", help="Kiripix: a local pixel asset studio for Godot games.",
                      no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False,
                      rich_markup_mode=None)  # plain help: agents read it, and CI must not get colour codes
    groups: dict[str, typer.Typer] = {}
    for name, entry in INDEX.items():
        path = tuple(name.split())
        target = app
        if len(path) == 2:
            group = path[0]
            if group not in groups:
                groups[group] = typer.Typer(help=entry.group_summary, no_args_is_help=True, rich_markup_mode=None)
                app.add_typer(groups[group], name=group)
            target = groups[group]
        if all_commands or (only is not None and only.name == name):
            from kiripix.commands import REGISTRY

            command = REGISTRY[name]
            target.command(name=path[-1], help=command.summary)(_callback(command))
        else:
            target.command(name=path[-1], help=entry.summary)(_stub())
    wanted = all_commands or launcher in {name for name, _ in listing}
    loaded = {item.name: item for item in launchers()} if wanted else {}
    for name, summary in listing:
        if name in loaded and (all_commands or name == launcher):
            app.command(name=name, help=summary)(_launcher_callback(loaded[name]))
        else:
            app.command(name=name, help=summary)(_stub())
    return app


def _usage_error(error: typer.TyperException) -> int:
    from kiripix.commands import Envelope, ExitCode, Finding

    context = getattr(error, "ctx", None)
    command = context.command_path if context else "kiripix"
    finding = Finding(code="input.invalid", message=error.format_message(), fix=f"{command} --help")
    envelope: Envelope[Any] = Envelope(ok=False, findings=[finding])
    _render(envelope, "--json" in sys.argv)
    return int(ExitCode.ERROR)


def main(listing: Sequence[tuple[str, str]] = (),
         launchers: Callable[[], Sequence[Launcher]] = lambda: ()) -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    argv = sys.argv[1:]
    app = build_app(listing, launchers, only=called_command(argv), launcher=argv[0] if argv else None)
    try:
        result = app(prog_name="kiripix", standalone_mode=False)
    except typer.Abort:
        sys.exit(1)
    except typer.TyperException as error:
        context = getattr(error, "ctx", None)
        if type(error).__name__ == "NoArgsIsHelpError" and context is not None:
            _write(sys.stdout, context.get_help() + "\n")
            sys.exit(0)
        sys.exit(_usage_error(error))
    if isinstance(result, int) and result != 0:
        sys.exit(result)
    sys.exit(_State.exit_code)
