"""`kiripix manifest`: merging the game's Manifests across git branches, and repairing a conflicted one (spec §9, ADR 0003)."""

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core.project import find_project
from kiripix.export import (
    apply_repairs, install_driver, merge_files, plan_repairs, resolve_target,
)

MANIFEST_GROUP = "Merge and repair the game's Manifests (spec §9)."


class MergeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base: str = Field(description="The common ancestor's Manifest (git's %O). Not read: the rule doesn't need it.")
    ours: str = Field(description="Our Manifest (git's %A). The merge is written here.")
    theirs: str = Field(description="Their Manifest (git's %B).")


class MergeData(BaseModel):
    ours: str = Field(description="The file the merge was written to.")
    asset: str
    counter: int = Field(description="The higher of the two counters, plus one.")

    def text(self) -> str:
        return f"{self.asset}: merged into {self.ours}, counter {self.counter}"


@command(
    "manifest merge",
    summary="The git merge driver for a Manifest: the higher counter plus one, the union of the IDs, our files with "
            "theirs accepted too. Needs no Project. Git runs it; `manifest install` sets that up.",
    input=MergeInput,
    output=MergeData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("base", "ours", "theirs")),
    group_summary=MANIFEST_GROUP,
)
def manifest_merge(arguments: MergeInput, context: Context) -> Outcome[MergeData]:
    ours = context.cwd / arguments.ours
    merged = merge_files(ours, context.cwd / arguments.theirs)
    return Outcome(MergeData(ours=str(Path(arguments.ours)), asset=merged.asset, counter=merged.counter))


class InstallInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class InstallData(BaseModel):
    changed: list[str] = Field(description="What was set up: the `.gitattributes` (res:// path) and/or `git config`. "
                                           "Empty when the driver was already installed.")

    def text(self) -> str:
        return f"installed: {', '.join(self.changed)}" if self.changed else "the merge driver was already installed"


@command(
    "manifest install",
    summary="Install the Manifest merge driver in the game's git clone: a .gitattributes in the Manifest folder, and the "
            "clone's git config. Run it once per clone.",
    input=InstallInput,
    output=InstallData,
    kind="writing",
    mcp="hidden",
    locks=LockNeeds(project=True),
    group_summary=MANIFEST_GROUP,
)
def manifest_install(arguments: InstallInput, context: Context) -> Outcome[InstallData]:
    target = resolve_target(find_project(context.cwd))
    return Outcome(InstallData(changed=install_driver(target)))


class RepairInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RepairData(BaseModel):
    repaired: list[str] = Field(description="The Manifests that had conflict markers and were merged, as res:// paths.")

    def text(self) -> str:
        return f"repaired {len(self.repaired)} Manifest(s)"


@command(
    "manifest repair",
    summary="Merge a Manifest that was committed with git conflict markers in it, by the merge driver's rule. A Manifest "
            "without markers is left alone.",
    input=RepairInput,
    output=RepairData,
    kind="writing",
    mcp="hidden",
    locks=LockNeeds(project=True),
    group_summary=MANIFEST_GROUP,
)
def manifest_repair(arguments: RepairInput, context: Context) -> Outcome[RepairData]:
    plans = plan_repairs(resolve_target(find_project(context.cwd)))
    apply_repairs(plans)
    return Outcome(RepairData(repaired=[plan.res for plan in plans]))
