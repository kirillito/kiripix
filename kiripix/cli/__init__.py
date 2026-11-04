"""The CLI adapter: a Typer app generated from the Command registry. It holds no logic of its own.

It parses arguments into the Command's input, calls `invoke`, and renders the result as text or, with `--json`, as
exactly one JSON object on stdout. The exit code comes from the result. Uses only `kiripix.commands`.
"""

import inspect
import shlex
import signal
import sys
from collections.abc import Sequence
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

import typer
from pydantic.fields import FieldInfo

from kiripix.commands import (
    REGISTRY, CliMeta, Command, Context, Envelope, ExitCode, Finding, Launcher, ProgressEvent, invoke,
)

_JSON = "kpx_json"
_PROGRESS = "kpx_progress"
_WAIT = "kpx_wait"


class _State:
    exit_code = int(ExitCode.OK)


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

    previous = signal.signal(signal.SIGINT, interrupted)
    try:
        return invoke(command, values, context)
    finally:
        signal.signal(signal.SIGINT, previous)


def _launcher_callback(launcher: Launcher) -> Any:
    parameters = [_parameter(name, field, CliMeta()) for name, field in launcher.input.model_fields.items()]

    def callback(**values: Any) -> None:
        _State.exit_code = int(launcher.run(launcher.input.model_validate(values), Path.cwd()))

    callback.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    callback.__annotations__ = {p.name: p.annotation for p in parameters}
    callback.__name__ = launcher.name
    callback.__doc__ = launcher.summary
    return callback


def build_app(launchers: Sequence[Launcher] = ()) -> typer.Typer:
    app = typer.Typer(name="kiripix", help="Kiripix: a local pixel asset studio for Godot games.",
                      no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False,
                      rich_markup_mode=None)  # plain help: agents read it, and CI must not get colour codes
    groups: dict[str, typer.Typer] = {}
    for command in REGISTRY.values():
        target = app
        if len(command.path) == 2:
            group = command.path[0]
            if group not in groups:
                groups[group] = typer.Typer(help=command.group_summary, no_args_is_help=True,
                                            rich_markup_mode=None)
                app.add_typer(groups[group], name=group)
            target = groups[group]
        target.command(name=command.path[-1], help=command.summary)(_callback(command))
    for launcher in launchers:
        app.command(name=launcher.name, help=launcher.summary)(_launcher_callback(launcher))
    return app


def _usage_error(error: typer.TyperException) -> int:
    context = getattr(error, "ctx", None)
    command = context.command_path if context else "kiripix"
    finding = Finding(code="input.invalid", message=error.format_message(), fix=f"{command} --help")
    envelope: Envelope[Any] = Envelope(ok=False, findings=[finding])
    _render(envelope, "--json" in sys.argv)
    return int(ExitCode.ERROR)


def main(launchers: Sequence[Launcher] = ()) -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    app = build_app(launchers)
    try:
        result = app(prog_name="kiripix", standalone_mode=False)
    except typer.Abort:
        sys.exit(int(ExitCode.ERROR))
    except typer.TyperException as error:
        context = getattr(error, "ctx", None)
        if type(error).__name__ == "NoArgsIsHelpError" and context is not None:
            _write(sys.stdout, context.get_help() + "\n")
            sys.exit(0)
        sys.exit(_usage_error(error))
    if isinstance(result, int) and result != 0:
        sys.exit(result)
    sys.exit(_State.exit_code)
