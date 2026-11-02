"""Exit codes and the error every layer above raises to end a Command with findings."""

from enum import IntEnum

from pydantic import BaseModel

from kiripix.checks import Finding, Position


class ExitCode(IntEnum):
    OK = 0
    ERROR = 1
    CHECK_FAILED = 2
    NEEDS_OWNER = 3
    BUSY = 4


class KiripixError(Exception):
    """Ends a Command with these findings and this exit code; `data` goes into the result when there is any."""

    def __init__(
        self,
        findings: list[Finding],
        exit_code: ExitCode = ExitCode.ERROR,
        data: BaseModel | None = None,
    ) -> None:
        super().__init__("; ".join(f.message for f in findings))
        self.findings = findings
        self.exit_code = exit_code
        self.data = data


def fail(
    code: str,
    message: str,
    *,
    fix: str | None = None,
    owner_action: str | None = None,
    position: Position | None = None,
    exit_code: ExitCode = ExitCode.ERROR,
) -> KiripixError:
    """Build a one-finding error, for `raise fail(...)`."""
    finding = Finding(code=code, message=message, fix=fix, owner_action=owner_action, position=position)
    return KiripixError([finding], exit_code)
