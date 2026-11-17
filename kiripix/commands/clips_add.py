"""The Project clip table (ticket 0239, spec §6.3): `clips-add` appends clips a character decided and built to
`[[character.clips]]` in `kiripix.toml`, so every body plays the same frames, fps and loop. `check --all` and `export --all` run
`clips.timing_differs` against it. An agent may run it: the table makes nothing stale, and a row
that differs from one already there is refused, never changed."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.clip_table import CLIPS_EXAMPLE, ClipRow
from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import cliptable
from kiripix.core.assets import load_asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import PROJECT_FILE, find_project
from kiripix.core.settings import ClipSpec, layout_lost, save_settings


class ClipsAddInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    character: str = Field(description="The character Asset whose decided and built clips are taken, such as character.hero.")
    clips: str = Field(min_length=1, description=f"The clips to add, comma-separated, each named as the character decided it. "
                                                 f"Example: `{CLIPS_EXAMPLE}`.")
    foot: str = Field("", description="Of those, the clips that must have foot frames (comma-separated); the character's clip "
                                      "must have them.")
    dry_run: bool = Field(False, description="Write nothing; show the table that would be written.")


class ClipsAddData(BaseModel):
    character: str
    dry_run: bool
    wrote: bool = Field(description="Whether kiripix.toml changed.")
    added: list[str] = Field(description="The clips appended to the table.")
    unchanged: list[str] = Field(description="The clips already in the table with the same frames, fps and loop.")
    table: list[ClipRow] = Field(description="The table after the Command (the one it would write, with dry_run).")

    def text(self) -> str:
        verb = "would add" if self.dry_run else "added"
        if not self.added:
            return f"The clip table already holds {', '.join(self.unchanged)}: nothing to write"
        return f"{verb} {', '.join(self.added)} to the clip table ({len(self.table)} rows in all)"


def _names(text: str) -> list[str]:
    return list(dict.fromkeys(n.strip() for n in text.split(",") if n.strip()))


@command(
    "clips-add",
    summary="Append clips a character decided to the Project's clip table.",
    input=ClipsAddInput,
    output=ClipsAddData,
    kind="writing",
    mcp="exposed",
    locks=LockNeeds(project=True),
    cli=CliMeta(positional=("character",)),
)
def clips_add(arguments: ClipsAddInput, context: Context) -> Outcome[ClipsAddData]:
    """Example: `kiripix clips-add character.hero --clips idle,walk --foot walk`; every other body's `idle` and `walk` must then
    match their frames, fps and loop."""
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.character)
    if asset.kind != cliptable.CHARACTER_KIND:
        raise fail("clips.not_character", f"{asset.id} is a {asset.kind}, and only a character's decided clips fill the table",
                   fix="kiripix describe project")
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    decided = {str(d.data.get("name")) for d in graph.decisions(graph.spec(cliptable.CLIPS_STAGE))
               if d.name in ("clip", "transition")}
    names = _names(arguments.clips)
    if not names:
        raise fail("clips.names_missing", "no clip named in --clips", owner_action="Name clips, such as --clips idle,walk.")
    foot = _names(arguments.foot)
    for name in dict.fromkeys(names):
        if name not in decided:
            have = ", ".join(sorted(decided)) or "none"
            raise fail("clips.not_decided", f"{asset.id} hasn't decided a clip '{name}'; its clips are: {have}",
                       owner_action=f"Name a clip the character has, or decide it first: kiripix decide {asset.id} clips.")
    if stray := [n for n in foot if n not in names]:
        raise fail("clips.foot_not_named", f"--foot names {', '.join(stray)}, which --clips doesn't",
                   owner_action="Name the clip in --clips too.")
    built = cliptable.built_clips(graph)
    unbuilt = [n for n in names if built is None or n not in built]
    if unbuilt:
        raise fail("clips.not_built", f"{asset.id}'s `clips` Stage hasn't built {', '.join(unbuilt)}, so its frames aren't known",
                   fix=f"kiripix run {asset.id} clips")
    assert built is not None
    table = list(project.settings.character.clips)
    in_table = {c.name: c for c in table}
    added: list[ClipSpec] = []
    unchanged: list[str] = []
    for name in dict.fromkeys(names):
        clip = built[name]
        if name in foot and not clip.foot:
            raise fail("clips.no_foot_frames", f"{asset.id}'s '{name}' has no foot frames, so the table can't ask for them",
                       owner_action=f"Choose a range of '{name}' where a foot plants (kiripix decide {asset.id} clips), or "
                                    "leave it out of --foot.")
        existing = in_table.get(name)
        if existing is not None:
            differs = list(cliptable.differences(existing, clip, foot=False).values())
            if name in foot and not existing.foot:
                differs.append("foot is not set in the table")
            if differs:
                raise fail("clips.row_differs", f"'{name}' is already in the clip table, and differs: {'; '.join(differs)}",
                           owner_action=f"Edit [[character.clips]] '{name}' in {PROJECT_FILE}, or change the character's clip "
                                        "to match.")
            unchanged.append(name)
            continue
        spec = ClipSpec(name=name, frames=clip.frames, fps=clip.fps, loop=clip.loop, foot=name in foot)
        table.append(spec)
        in_table[name] = spec
        added.append(spec)
    updated = project.settings.model_copy(update={
        "character": project.settings.character.model_copy(update={"clips": table})})
    wrote = bool(added) and not arguments.dry_run
    kept = True
    if wrote:
        kept = save_settings(project.root / PROJECT_FILE, updated)
    return Outcome(ClipsAddData(character=asset.id, dry_run=arguments.dry_run, wrote=wrote, added=[c.name for c in added],
                                unchanged=unchanged, table=[ClipRow.from_spec(c) for c in table]),
                   findings=[] if kept else [layout_lost(PROJECT_FILE)])
