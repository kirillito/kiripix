"""`kiripix export`: an Asset's final outputs into the Godot project, under the Manifest's rules (spec §9, ADR 0003)."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core.assets import Asset, is_asset_id, list_assets, load_asset
from kiripix.core.hashing import HashCache
from kiripix.core.locks import asset_lock, hold
from kiripix.core.project import find_project
from kiripix.export import EXPORTERS, ExportOptions, ExportResult, export_assets


class ExportInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str | None = Field(None, description="The Asset ID, such as room.queen_west_alley. Omit with --all.")
    all: bool = Field(False, description="Export every room, or none: Exit pairing must hold and no file may be refused.")
    force: bool = Field(False, description="Back up and overwrite files the Manifest lists that the game changed.")
    adopt: bool = Field(False, description="Back up and take over files at the target paths that the Manifest doesn't list.")
    dry_run: bool = Field(False, description="Write nothing; list what would be written and what would be refused.")

    @model_validator(mode="after")
    def _asset_or_all(self) -> Self:
        if self.all == (self.asset is not None):
            raise ValueError("give an Asset ID or --all, not both")
        return self


class ExportedAsset(BaseModel):
    asset: str
    written: list[str] = Field(description="The files written, as res:// paths.")
    unchanged: list[str] = Field(description="The files that already held what export would write.")
    manifest: str = Field(description="The Manifest's res:// path.")
    counter: int = Field(description="Goes up each time what this Asset exports changes.")


class ExportData(BaseModel):
    asset: str | None = Field(description="The Asset, or null with --all (see `assets`).")
    dry_run: bool
    written: list[str] = Field(description="The files written, as res:// paths. Empty in a dry run.")
    would_write: list[str] = Field(description="In a dry run, the files that would be written.")
    unchanged: list[str] = Field(description="The files that already held what export would write.")
    backed_up: list[str] = Field(description="The files saved to .kiripix/backups/ before being overwritten, or in a "
                                             "dry run, those that would be.")
    changed: list[str] = Field(description="Files the Manifest lists that the game changed, which --force would take.")
    unmanaged: list[str] = Field(description="Files the Manifest doesn't list, which --adopt would take.")
    manifest: str | None = Field(description="The Manifest's res:// path; null with --all.")
    counter: int | None = Field(description="Goes up each time what the Asset exports changes; null with --all.")
    assets: list[ExportedAsset] = Field(description="Each Asset exported, in ID order.")

    def text(self) -> str:
        wrote = len(self.would_write) if self.dry_run else len(self.written)
        verb = "would write" if self.dry_run else "wrote"
        who = self.asset or f"{len(self.assets)} Asset(s)"
        counter = f", counter {self.counter}" if self.counter is not None else ""
        return f"{who}: {verb} {wrote} file(s), {len(self.unchanged)} unchanged{counter}"


def _data(asset: str | None, dry_run: bool, results: list[ExportResult]) -> ExportData:
    def joined(name: str) -> list[str]:
        return [res for result in results for res in getattr(result, name)]
    single = results[0] if asset is not None else None
    return ExportData(
        asset=asset, dry_run=dry_run, written=joined("written"), would_write=joined("would_write"),
        unchanged=joined("unchanged"), backed_up=joined("backed_up"), changed=joined("changed"),
        unmanaged=joined("unmanaged"), manifest=single.manifest if single else None,
        counter=single.counter if single else None,
        assets=[ExportedAsset(asset=r.asset, written=r.written, unchanged=r.unchanged, manifest=r.manifest,
                              counter=r.counter) for r in results])


@command(
    "export",
    summary="Write fully built Assets into the Godot project: scene, images and Manifest. Refuses to overwrite the "
            "game's work without --force or --adopt.",
    input=ExportInput,
    output=ExportData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset",)),
    locks=LockNeeds(project=True, asset=lambda a: a.asset if is_asset_id(a.asset) else None),
)
def export(arguments: ExportInput, context: Context) -> Outcome[ExportData]:
    project = find_project(context.cwd)
    cache = HashCache(project.state_dir)
    options = ExportOptions(force=arguments.force, adopt=arguments.adopt, dry_run=arguments.dry_run)
    if arguments.asset is not None:
        assets: list[Asset] | None = [load_asset(project, arguments.asset)]
        results, findings = export_assets(project, assets, cache, options)
    else:
        # The project lock is held; take every room's lock too, so none is being built while its files are read.
        rooms = [asset for asset in list_assets(project)[0] if asset.kind in EXPORTERS]
        with hold(project.state_dir, [asset_lock(asset.id) for asset in rooms], context.wait, context.command_line):
            results, findings = export_assets(project, None, cache, options)
    cache.save()
    return Outcome(_data(arguments.asset, arguments.dry_run, results), findings)
