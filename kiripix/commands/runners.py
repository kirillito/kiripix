"""`kiripix runners`: the local Runners, and their weights in `.kiripix/weights/` (spec §8)."""

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import cancel
from kiripix.core.errors import fail
from kiripix.core.kinds import all_runners
from kiripix.core.project import find_project
from kiripix.runners import Runner, RunnerError, missing_weights, pull, remove, weights_dir

RUNNERS_GROUP = "Manage the local Runners and their weights."


class RunnerRow(BaseModel):
    id: str
    description: str
    licence: str
    weights_hash: str
    size: int = Field(description="The size of its weights, in bytes.")
    pulled: bool


class ListInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListData(BaseModel):
    runners: list[RunnerRow]

    def text(self) -> str:
        return "\n".join(f"{r.id}  {r.licence}  {r.size / 1_000_000:.0f} MB  {'pulled' if r.pulled else 'not pulled'}"
                         for r in self.runners)


@command(
    "runners list",
    summary="List the Runners: licence, weights hash and size, and whether the weights are here.",
    input=ListInput,
    output=ListData,
    kind="probe",
    mcp="hidden",
    group_summary=RUNNERS_GROUP,
)
def runners_list(arguments: ListInput, context: Context) -> Outcome[ListData]:
    state_dir = find_project(context.cwd).state_dir
    rows = [
        RunnerRow(
            id=runner.id,
            description=runner.description,
            licence=runner.licence,
            weights_hash=runner.weights_hash,
            size=sum(weight.size for weight in runner.weights),
            pulled=not missing_weights(weights_dir(state_dir, runner), runner),
        )
        for _, runner in sorted(all_runners().items())
    ]
    return Outcome(ListData(runners=rows))


class RunnerInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runner: str = Field(description="The Runner's ID, as `kiripix runners list` shows it.")


def _runner(name: str) -> Runner:
    known = all_runners()
    runner = known.get(name)
    if runner is None:
        raise fail("runner.unknown", f"no Runner '{name}'; the Runners are {', '.join(sorted(known))}",
                   fix="kiripix runners list")
    return runner


class PullData(BaseModel):
    runner: str
    downloaded: list[str] = Field(description="The weight files downloaded; empty when all were already here.")

    def text(self) -> str:
        return f"{self.runner}: downloaded {len(self.downloaded)} file(s)"


@command(
    "runners pull",
    summary="Download a Runner's weights now, rather than on first use.",
    input=RunnerInput,
    output=PullData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("runner",)),
    group_summary=RUNNERS_GROUP,
)
def runners_pull(arguments: RunnerInput, context: Context) -> Outcome[PullData]:
    runner = _runner(arguments.runner)
    directory = weights_dir(find_project(context.cwd).state_dir, runner)
    try:
        downloaded = pull(directory, runner, cancel.check)
    except RunnerError as error:
        raise fail("runner.download_failed", str(error), fix=f"kiripix runners pull {runner.id}") from None
    return Outcome(PullData(runner=runner.id, downloaded=downloaded))


class RemoveData(BaseModel):
    runner: str
    removed: bool = Field(description="False when no weights were here.")

    def text(self) -> str:
        return f"{self.runner}: {'removed its weights' if self.removed else 'no weights here'}"


@command(
    "runners rm",
    summary="Delete a Runner's downloaded weights. Pinned results stay, and a rebuild doesn't need the weights.",
    input=RunnerInput,
    output=RemoveData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("runner",)),
    locks=LockNeeds(gpu=True),  # a loaded Runner may be using them
    group_summary=RUNNERS_GROUP,
)
def runners_rm(arguments: RunnerInput, context: Context) -> Outcome[RemoveData]:
    runner = _runner(arguments.runner)
    try:
        removed = remove(weights_dir(find_project(context.cwd).state_dir, runner))
    except OSError as error:  # a --cpu call holds no GPU lock, and on Windows a file in use can't be deleted
        raise fail("runner.remove_failed", f"can't delete all of {runner.id}'s weights: {error}",
                   fix=f"kiripix runners rm {runner.id}") from None
    return Outcome(RemoveData(runner=runner.id, removed=removed))
