"""The CLI adapter: a Typer app generated from the Command registry. It holds no logic of its own.

It parses arguments into the Command's input, calls `invoke`, and renders the result as text or, with `--json`, as
exactly one JSON object on stdout. The exit code comes from the result. Uses only `kiripix.commands`.
"""

import inspect
import shlex
import sys
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, Literal, Union, get_args, get_origin

import typer
from pydantic.fields import FieldInfo

from kiripix.commands import REGISTRY, Command, Context, Envelope, ExitCode, Finding, ProgressEvent, invoke

_JSON = "kpx_json"
_PROGRESS = "kpx_progress"
_WAIT = "kpx_wait"


class _State:
    exit_code = int(ExitCode.OK)


def _command_line() -> str:
    return shlex.join(["kiripix", *sys.argv[1:]])


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


def _parameter(name: str, field: FieldInfo, command: Command[Any, Any]) -> inspect.Parameter:
    annotation, optional = _unwrap(field.annotation)
    default = ... if field.is_required() else field.default
    if name in command.cli.positional:
        info = typer.Argument(default, help=field.description, metavar=name.upper(),
                              show_default=default is not None and default is not ...)
    else:
        declarations = command.cli.options.get(name, (f"--{name.replace('_', '-')}",))
        info = typer.Option(default, *declarations, help=field.description,
                            show_default=default is not None and default is not ...)
    return inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=info,
                             annotation=annotation | None if optional else annotation)


def _callback(command: Command[Any, Any]) -> Any:
    parameters = [_parameter(name, field, command) for name, field in command.input.model_fields.items()]
    parameters.append(inspect.Parameter(_JSON, inspect.Parameter.KEYWORD_ONLY, annotation=bool,
                                        default=typer.Option(False, "--json", help="Print one JSON object.")))
    parameters.append(inspect.Parameter(
        _PROGRESS, inspect.Parameter.KEYWORD_ONLY, annotation=Literal["none", "jsonl"],
        default=typer.Option("none", "--progress",
                             help="jsonl streams progress events on stderr."),
    ))
    if command.kind == "writing":
        parameters.append(inspect.Parameter(
            _WAIT, inspect.Parameter.KEYWORD_ONLY, annotation=float,
            default=typer.Option(0.0, "--wait", min=0, help="Wait up to this many seconds for a held lock."),
        ))

    def callback(**values: Any) -> None:
        as_json = values.pop(_JSON)
        progress = values.pop(_PROGRESS)
        wait = values.pop(_WAIT, 0.0)
        context = Context(cwd=Path.cwd(), command_line=_command_line(), wait=wait, progress=_progress_sink(progress))
        envelope, exit_code = invoke(command, values, context)
        _render(envelope, as_json)
        _State.exit_code = int(exit_code)

    callback.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    callback.__annotations__ = {p.name: p.annotation for p in parameters}
    callback.__name__ = command.path[-1]
    callback.__doc__ = command.summary
    return callback


def build_app() -> typer.Typer:
    app = typer.Typer(name="kiripix", help="Kiripix: a local pixel asset studio for Godot games.",
                      no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)
    groups: dict[str, typer.Typer] = {}
    for command in REGISTRY.values():
        target = app
        if len(command.path) == 2:
            group = command.path[0]
            if group not in groups:
                groups[group] = typer.Typer(help=command.group_summary, no_args_is_help=True)
                app.add_typer(groups[group], name=group)
            target = groups[group]
        target.command(name=command.path[-1], help=command.summary)(_callback(command))
    return app


def _usage_error(error: typer.TyperException) -> int:
    context = getattr(error, "ctx", None)
    command = context.command_path if context else "kiripix"
    finding = Finding(code="input.invalid", message=error.format_message(), fix=f"{command} --help")
    envelope: Envelope[Any] = Envelope(ok=False, findings=[finding])
    _render(envelope, "--json" in sys.argv)
    return int(ExitCode.ERROR)


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8")
    app = build_app()
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
