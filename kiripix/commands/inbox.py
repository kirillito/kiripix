"""inbox: file the images the Owner made elsewhere, by their file names (ticket 0350). All the work is in
`kiripix.core.inbox`; the file names are those `to-paint` wrote into its index (`kiripix.core.paint`)."""

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import extend, inbox
from kiripix.core.assets import Asset
from kiripix.core.inbox import FiledAction, FiledOutcome
from kiripix.core.locks import asset_lock, hold
from kiripix.core.project import find_project


class InboxInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    folder: str | None = Field(None, description="The folder to read, relative to the working directory; `[inbox] folder` in "
                                                 "kiripix.toml by default (`inbox/` in the Project).")
    dry_run: bool = Field(False, description="List what would happen and change nothing.")
    file: Path | None = Field(None, description="File this one image instead of the folder, into --asset, whatever its name: "
                                                "what a drop on a waiting room in the UI does. It isn't moved.")
    asset: str | None = Field(None, description="With --file: the Asset to file it into.")
    sides: list[str] = Field([], description="With --file: the side the piece extends, as `to-paint` "
                                                               "gives a room mid-`extend`; none imports it as a Variant.")
    max_residual: float | None = Field(None, description="The registration limit, px, of each piece joined on, as `extend add "
                                                         "--max-residual`: `[extend] max_residual` (0.5) by default, at most 1.0.")

    @model_validator(mode="after")
    def _one_file_or_the_folder(self) -> Self:
        if self.file is not None and (self.asset is None or self.folder is not None or self.dry_run):
            raise ValueError("--file takes --asset, and no --folder or --dry-run")
        if self.file is None and (self.asset is not None or self.sides):
            raise ValueError("--asset and --sides go with --file")
        return self


class InboxFile(BaseModel):
    file: str = Field(description="The file, relative to the Project when it lies inside it.")
    outcome: FiledOutcome = Field(description="imported: filed (and moved). would_import: with --dry-run, it would be. unmatched: no "
                                      "Asset has that name (`inbox.unmatched`). ambiguous: several do (`inbox.ambiguous`). "
                                      "failed: the import was refused; the finding is the Command's own and the file stays.")
    asset: str | None = Field(None, description="The Asset it is (or would be) filed to.")
    action: FiledAction | None = Field(None, description="import: a Variant (`import`). extend: a piece joined on (`extend add`).")
    sides: list[str] = Field(default_factory=list, description="With extend: the side or corner the piece extends.")
    variant: str | None = Field(None, description="With import: the Variant's name.")
    piece: str | None = Field(None, description="With extend: the piece's name.")
    created: bool | None = Field(None, description="With import: false when the Asset already had that image.")
    moved_to: str | None = Field(None, description="Where the file went, `<folder>/imported/<date>/`.")
    candidates: list[str] = Field(default_factory=list, description="With ambiguous: the Assets that match.")
    code: str | None = Field(None, description="With unmatched, ambiguous or failed: the finding's code.")


class LoneVariant(BaseModel):
    asset: str
    variant: str = Field(description="Its only Variant, not picked.")
    pick: str = Field(description="The command that picks it.")


class InboxData(BaseModel):
    folder: str = Field(description="The folder read, relative to the Project when it lies inside it.")
    dry_run: bool
    files: list[InboxFile] = Field(description="Each image in the folder, by name, and what became of it.")
    imported: int = Field(description="How many were filed (with --dry-run, how many would be).")
    left: int = Field(description="How many stay in the folder: unmatched, ambiguous or failed.")
    lone_variants: list[LoneVariant] = Field(
        description="The rooms that now have exactly one Variant, not picked. Importing never picks; a session may pick it.")

    def text(self) -> str:
        lines = [f"{f.file}: {f.outcome}" + (f" -> {f.asset} ({f.action})" if f.asset else "") for f in self.files]
        lines += [f"{lone.asset}: one Variant, pick it with {lone.pick}" for lone in self.lone_variants]
        verb = "would file" if self.dry_run else "filed"
        return "\n".join(lines + [f"{verb} {self.imported}, left {self.left} in {self.folder}"])


@command(
    "inbox",
    summary="File the PNG and JPEG images the Owner made elsewhere, by their file names (those `to-paint` lists): "
            "`<room>.png` or `<room>-<anything>.png` is imported as a Variant, `<room>.<side>.png` is joined on with "
            "`extend add`. A name that matches no Asset, or several, stays in the folder with a finding. Filed images move "
            "to `<folder>/imported/<date>/`. Never picks. `--dry-run` changes nothing.",
    input=InboxInput,
    output=InboxData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(),
    locks=LockNeeds(project=True),
    files=("file",),
)
def inbox_command(arguments: InboxInput, context: Context) -> Outcome[InboxData]:
    project = find_project(context.cwd)
    where = inbox.folder(project, arguments.folder, context.cwd)
    if arguments.max_residual is not None:  # refused once, before any file
        extend.residual_limit(project, arguments.max_residual, "kiripix inbox")

    def hold_asset(asset: Asset) -> AbstractContextManager[None]:
        return hold(project.state_dir, [asset_lock(asset.id)], context.wait, context.command_line)

    if arguments.file is not None and arguments.asset is not None:
        file = arguments.file if arguments.file.is_absolute() else context.cwd / arguments.file
        done = inbox.file_one(project, arguments.asset, file, project.relative(file), arguments.sides, hold_asset,
                               arguments.max_residual)
    else:
        done = inbox.run(project, where, arguments.dry_run, hold_asset, arguments.max_residual)
    files = [InboxFile.model_validate(vars(f)) for f in done.files]
    lone = [LoneVariant(asset=a, variant=v, pick=f"kiripix pick {a} {v}") for a, v in done.lone]
    filed = sum(1 for f in files if f.outcome in ("imported", "would_import"))
    data = InboxData(folder=project.relative(where), dry_run=arguments.dry_run, files=files, imported=filed,
                     left=len(files) - filed, lone_variants=lone)
    return Outcome(data, done.findings, done.exit_code)
