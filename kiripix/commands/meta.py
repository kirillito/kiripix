"""`kiripix schema`: the JSON Schemas of every Command's input and output, from the same types the Commands use."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import API_VERSION, FINDING_STATUS, HTTP_STATUS, Context, Envelope, Outcome
from kiripix.commands.registry import REGISTRY, CliMeta, CommandKind, McpExposure, command
from kiripix.core.errors import fail


class SchemaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command: str | None = Field(None, description="One Command, such as 'run' or 'op quantize'; all by default.")


class CommandSchema(BaseModel):
    summary: str
    kind: CommandKind
    mcp: McpExposure
    input: dict[str, Any]
    output: dict[str, Any]


class SchemaData(BaseModel):
    api_version: int
    http_status: dict[str, int] = Field(description="The HTTP status REST answers with, by exit code.")
    finding_status: dict[str, int] = Field(description="Findings that name a more exact HTTP status, by code.")
    commands: dict[str, CommandSchema]


def _envelope(output: type[BaseModel]) -> type[BaseModel]:
    generic: Any = Envelope
    envelope: type[BaseModel] = generic[output]
    return envelope


@command(
    "schema",
    summary="Print the JSON Schemas of Command inputs and outputs (the output is the whole result envelope).",
    input=SchemaInput,
    output=SchemaData,
    kind="probe",
    mcp="hidden",
    cli=CliMeta(positional=("command",)),
)
def schema(arguments: SchemaInput, context: Context) -> Outcome[SchemaData]:
    names = sorted(REGISTRY)
    if arguments.command is not None:
        wanted = arguments.command.replace(".", " ")
        if wanted not in REGISTRY:
            raise fail(
                "command.unknown",
                f"no Command '{arguments.command}'; the Commands are {', '.join(names)}",
                fix="kiripix schema",
            )
        names = [wanted]
    commands = {
        name: CommandSchema(
            summary=REGISTRY[name].summary,
            kind=REGISTRY[name].kind,
            mcp=REGISTRY[name].mcp,
            input=REGISTRY[name].input.model_json_schema(),
            output=_envelope(REGISTRY[name].output).model_json_schema(),
        )
        for name in names
    }
    return Outcome(SchemaData(api_version=API_VERSION, http_status={str(int(k)): v for k, v in HTTP_STATUS.items()},
                                finding_status=FINDING_STATUS, commands=commands))
