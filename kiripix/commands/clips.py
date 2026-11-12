"""The Commands for a character's clips: copy."""

from pydantic import BaseModel, ConfigDict, Field

from kiripix.checks import Finding, Position
from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import clipcopy
from kiripix.core.assets import is_asset_id, load_asset
from kiripix.core.project import find_project

CLIPS_GROUP = "A character's clips (spec §6.3)."


class CopyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The character to copy the clips to, such as character.hero_b.")
    source_asset: str = Field(description="The character to copy the clips from. It is only read.")
    clip: str | None = Field(None, description="Only these clips, by name, separated by commas (default: all of them).")
    replace: bool = Field(False, description="Decide again a clip the character already has, and replace a clip source "
                                             "of the same name that is another file. Without it such a clip is skipped "
                                             "with a warning.")
    dry_run: bool = Field(False, description="Write nothing; list the Decisions and files a copy would add.")


class CopyData(BaseModel):
    asset: str
    source_asset: str
    dry_run: bool
    copied: list[str] = Field(description="The clips added, by name, in the order they were decided.")
    replaced: list[str] = Field(description="With --replace: the clips the character had, decided again.")
    skipped: list[str] = Field(description="The clips the character already has, left as they are.")
    files: list[str] = Field(description="The clip-source files added (in a dry run, that would be), relative to the "
                                         "Project.")

    def text(self) -> str:
        would = "would copy" if self.dry_run else "copied"
        parts = [f"{self.asset}: {would} {len(self.copied)} clip(s) from {self.source_asset}"]
        if self.replaced:
            parts.append(f"{'would replace' if self.dry_run else 'replaced'} {', '.join(self.replaced)}")
        if self.skipped:
            parts.append(f"skipped {', '.join(self.skipped)}")
        if self.files:
            parts.append(f"{len(self.files)} clip source file(s)")
        return "; ".join(parts)


def _lock(arguments: CopyInput) -> str | None:
    return arguments.asset if is_asset_id(arguments.asset) else None


@command(
    "clips copy",
    summary="Copy another character's clips to this one: each as a `clip` Decision (undo takes them back one by one), "
            "with the clip-source files they name. A clip it already has is skipped, or with --replace decided "
            "again. Nothing links the two afterwards.",
    input=CopyInput,
    output=CopyData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset",), options={"source_asset": ("--from",)}),
    locks=LockNeeds(asset=_lock),
    group_summary=CLIPS_GROUP,
)
def clips_copy(arguments: CopyInput, context: Context) -> Outcome[CopyData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    other = load_asset(project, arguments.source_asset)
    names = [n.strip() for n in arguments.clip.split(",") if n.strip()] if arguments.clip is not None else None
    result = clipcopy.plan(project, asset, other, names, arguments.replace)
    files = [asset.dir / "src" / "clips" / path.name for path in result.files]
    if not arguments.dry_run:
        files = clipcopy.apply(asset, other, project, result)
    findings = [Finding(code="clips.copy_skipped", severity="warning",
                        message=f"{asset.id} already has the clip {name}, so it was left as it is",
                        fix=f"kiripix clips copy {asset.id} --from {other.id} --clip {name} --replace",
                        position=Position(asset=asset.id, stage=clipcopy.CLIPS_STAGE))
                for name in result.skipped]
    return Outcome(CopyData(asset=asset.id, source_asset=other.id, dry_run=arguments.dry_run, copied=result.copied,
                            replaced=result.replaced, skipped=result.skipped,
                            files=[project.relative(path) for path in files]), findings)
