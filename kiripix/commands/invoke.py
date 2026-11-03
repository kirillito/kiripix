"""Calling a Command: validate the input, take its declared locks, run it, and wrap the result in the envelope.

Every adapter calls Commands through `invoke`, so validation, locking and errors behave the same everywhere.
"""

import os
import traceback
from contextlib import nullcontext
from typing import Any

from pydantic import BaseModel, ValidationError

from kiripix.checks import Finding, Position
from kiripix.commands.contract import Context, Envelope, Outcome
from kiripix.commands.registry import Command
from kiripix.core.errors import ExitCode, KiripixError
from kiripix.core.locks import GPU_LOCK, PROJECT_LOCK, asset_lock, hold
from kiripix.core.project import find_project


def _input_findings(error: ValidationError, command: Command[Any, Any]) -> list[Finding]:
    findings = []
    for item in error.errors():
        field = ".".join(str(part) for part in item["loc"])
        message = item["msg"].removeprefix("Value error, ")
        findings.append(
            Finding(
                code="input.invalid",
                message=f"{field}: {message}" if field else message,
                position=Position(field=field or None),
                fix=f"kiripix {command.name} --help",
            )
        )
    return findings


def _locks(command: Command[Any, Any], arguments: BaseModel) -> list[str]:
    needs = command.locks
    names = [PROJECT_LOCK] if needs.project else []
    asset = needs.asset(arguments) if needs.asset else None
    if asset:
        names.append(asset_lock(asset))
    if needs.gpu:
        names.append(GPU_LOCK)
    return names


def _owner_refusal(command: Command[Any, Any], context: Context) -> Outcome[Any] | None:
    """The owner-only guard (spec §10.3): a guardrail against an agent accepting its own work, not security.

    `KIRIPIX_TEST_OWNER=1` stands in for the Owner in the test harness, and nowhere else.
    """
    if command.kind != "owner-only" or context.interactive or os.environ.get("KIRIPIX_TEST_OWNER") == "1":
        return None
    if context.via == "rest":
        finding = Finding(
            code="owner.required",
            message=f"'{command.name}' is the Owner's own judgement, and this request has no valid session token",
            owner_action="Do it in the UI that `kiripix ui` opened, or run it yourself at an interactive terminal: "
                         f"{context.command_line}",
        )
        return Outcome(None, [finding], ExitCode.NEEDS_OWNER)
    finding = Finding(
        code="owner.required",
        message=f"'kiripix {command.name}' is the Owner's own judgement, and this isn't an interactive terminal",
        owner_action=f"Run it yourself at an interactive terminal, or in the UI: {context.command_line}",
    )
    return Outcome(None, [finding], ExitCode.NEEDS_OWNER)


def invoke(command: Command[Any, Any], raw: dict[str, Any], context: Context) -> tuple[Envelope[Any], ExitCode]:
    try:
        arguments = command.input.model_validate(raw)
        refusal = _owner_refusal(command, context)
        if refusal is not None:
            raise KiripixError(refusal.findings, refusal.exit_code)
        locks = _locks(command, arguments)
        guard = hold(find_project(context.cwd).state_dir, locks, context.wait, context.command_line) if locks \
            else nullcontext()
        with guard:
            outcome: Outcome[Any] = command.handler(arguments, context)
    except ValidationError as error:
        outcome = Outcome(None, _input_findings(error, command), ExitCode.ERROR)
    except KiripixError as error:
        outcome = Outcome(error.data, error.findings, error.exit_code)
    except KeyboardInterrupt:
        cancelled = Finding(
            code="run.cancelled",
            message="cancelled; no output was left half-written",
            fix=context.command_line,
        )
        outcome = Outcome(None, [cancelled], ExitCode.ERROR)
    except Exception as error:  # noqa: BLE001 - the contract holds even for Kiripix's own bugs
        where = traceback.extract_tb(error.__traceback__)[-1]
        internal = Finding(
            code="internal.error",
            message=f"{type(error).__name__}: {error} (at {where.filename}:{where.lineno})",
            owner_action="Report this Kiripix bug, with the command and this message.",
        )
        outcome = Outcome(None, [internal], ExitCode.ERROR)
    generic: Any = Envelope
    envelope: Envelope[Any] = generic[command.output](
        ok=outcome.exit_code == ExitCode.OK,
        data=outcome.data,
        findings=outcome.findings,
    )
    return envelope, outcome.exit_code
