"""The Commands for an Asset's Variants: import and pick."""

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.registry import CliMeta, LockNeeds, command
from kiripix.core import editof, emotions, gen_sprite, loopedits, loopkit, sheets, sounds, sources, things
from kiripix.core.errors import fail
from kiripix.core.assets import Asset, is_asset_id, load_asset
from kiripix.core.graph import AssetGraph, ProgressEvent, StageState
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project, find_project


class _AssetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")


def _asset_lock(arguments: _AssetInput) -> str | None:
    return arguments.asset if is_asset_id(arguments.asset) else None


# import


class ImportInput(_AssetInput):
    file: Path = Field(description="A room's or Prop's PNG or JPEG (a JPEG is stored as a PNG); a character's .glb, "
                                   ".fbx or .blend, or its parameter file (.toml or .json); a sprite's PNG or ZIP of PNGs.")
    role: Literal["variant", "clip-source", "rigged", "parameters", "sheet", "thing"] | None = Field(
        None, description="What the file is. variant: a Source to pick (the default, except for a sprite). "
                          "clip-source: an animation file (a Mixamo .fbx) that a `clip` Decision's `source` names by "
                          "its file stem. rigged: the rigged file that comes back from Mixamo. parameters: the file the "
                          "Project's generator builds the character's Model from ([character.generators] in "
                          "kiripix.toml), stored under its own name in src/parameters/ in place of any other; it is the "
                          "Source, so nothing is picked, and it replaces importing a Model. These three are for a "
                          "character. thing: a mesh (.glb or .blend) a clip holds, with --thing <id>. sheet: a sprite's PNG sheet or ZIP of PNGs, stored whole in src/sheets/ (the "
                          "default for a sprite; a ZIP with an unsafe or non-PNG entry is refused whole).")
    thing: str | None = Field(None, description="With --role thing: the held thing's ID (lower-case letters, digits and "
                                                "underscores). The mesh is stored in src/things/<id>/ as a Variant; importing "
                                                "again under the same ID adds a Variant, and the newest is the one rendered. "
                                                "The file's origin and axes are the grip: a clip's `attach` `offset` and `turn` "
                                                "adjust them. Its materials are numbered after the Model's.")
    look: str | None = Field(None, description="A room's Look: store the image as an edit Variant of that Look "
                                               "(src/looks/<look>/), made on the room's picked Source, instead of as a "
                                               "Source. The room's source Stage stays done.")
    loop: str | None = Field(None, description="A room's frame Loop: import painted frames (the FILE, and any more PNGs "
                                               "after it) as its frames 1 to N-1, in name order, each exactly the size "
                                               "of the Loop's region box (`kiripix loop kit` writes a kit). Frame 0 is "
                                               "always the room's: a frame_000.png among them is skipped. Records the "
                                               "fit and the palette they were painted on.")
    frames: list[Path] = Field([], description="With --loop: more frames to import with FILE. A file input that can "
                                               "repeat: over REST, send one `frames` part per frame, each with its file "
                                               "name (frames are taken in name order).")
    kit: Path | None = Field(None, description="With --loop: the kit's kit.json, read as if it sat beside the frames "
                                               "(CLI --kit). It keeps the kit's checks: a region that changed since, "
                                               "and the fit and palette the frames were painted on. Without it, a "
                                               "kit.json beside FILE is used, else the room as it is now (a warning).")
    frame: int | None = Field(None, ge=0, description="With --loop: FILE is an edit of the room's Source, a Variant of "
                                                      "this frame (from 1: frame 0 is the room's and is refused), "
                                                      "instead of a painted kit frame. Made from the Source, never from "
                                                      "another edit (`import.edit_of_an_edit`). Pick it with `kiripix "
                                                      "pick <asset> <variant> --loop <loop> --frame <n>`. One image; "
                                                      "not with --kit or more frames.")
    state: str | None = Field(None, description="A Prop's other state: store the image as a Variant of that state "
                                                "(src/states/<state>/), declared first by a `state` Decision on `source` "
                                                "(`prop.state_unknown` gives the command). Not the default state's ID: that "
                                                "is the Source. Pick it with `kiripix pick <asset> <variant> --state <state>`.")
    emotion: str | None = Field(None, description="A portrait's emotion: store the image as a Variant of that emotion "
                                                  "(src/emotions/<emotion>/), an edit of the neutral image, declared first by "
                                                  "an `emotion` Decision on `source` (`portrait.emotion_unknown` gives the "
                                                  "command). Not `neutral`: that is the Source. Pick it with `kiripix pick "
                                                  "<asset> <variant> --emotion <emotion>`.")
    url: str | None = Field(None, description="For a sound's recording: where it came from (a URL or a name). Recorded on the "
                                              "file's line in imported.jsonl, with --author and --licence; importing the same "
                                              "file again with them adds a newer line and no Variant. Text, never interpreted.")
    author: str | None = Field(None, description="For a sound's recording: who made it.")
    licence: str | None = Field(None, description="For a sound's recording: its licence, as text (CC0, CC-BY 4.0, own recording). "
                                                  "Export refuses a recording with no author or licence "
                                                  "(`sound.provenance_missing`).")
    of: str | None = Field(None, description="With --look, or --loop with --frame: the edit was made on a piece or a crop "
                                             "of the room, not on its whole Source. A crop `kiripix extend "
                                             "<room> crop --box ...` wrote (its name, the start of its hash in "
                                             "`extend/crops/`; `crop` is the latest); or a piece's name (the start of its hash in "
                                             "`extend/pieces/`) or a Variant's. Kiripix finds where it lies in the "
                                             "Source, registers the edit there, and stores an edit of the whole "
                                             "Source: the Source's own pixels outside the edit. Without it, the edit is "
                                             "of the whole Source (an image model resizes a big Source to its own "
                                             "size, which blurs the edit).")


class SoundFile(BaseModel):
    """What `import` read of a sound's recording."""

    rate: int = Field(description="Its sample rate in Hz.")
    channels: int | None = Field(description="Its channels; null for a layout ffmpeg doesn't name.")
    duration_s: float | None = Field(description="Its length in seconds, as its header says.")
    codec: str
    url: str | None = Field(description="Its Provenance: where it came from.")
    author: str | None
    licence: str | None


class ImportData(BaseModel):
    asset: str
    sound: SoundFile | None = Field(None, description="For a sound's recording: what ffmpeg read of it and its Provenance.")
    look: str | None = Field(description="With --look: the Look the edit belongs to.")
    role: str
    variant: str | None = Field(description="With role variant: the Variant's name.")
    sheet: str | None = Field(description="With role sheet: the sheet's name, the start of its hash.")
    clip_source: str | None = Field(description="With role clip-source: its name, the file stem.")
    rigged: str | None = Field(description="With role rigged: the rigged file's name.")
    parameters: str | None = Field(None, description="With role parameters: the parameter file's name.")
    thing: str | None = Field(None, description="With role thing: the thing's ID.")
    thing_variants: list[str] = Field([], description="With role thing: the thing's Variants, by name; the one just "
                                                      "imported is the current one (`show` says which).")
    thing_materials: list[str] | None = Field(None, description="With role thing: the imported Variant's material names, "
                                                                "sorted; null when they aren't known until a render "
                                                                "(a .blend made without Blender).")
    file: str
    created: bool
    loop: str | None = Field(None, description="With --loop: the Loop whose frames were imported.")
    loop_frames: list[str] = Field([], description="With --loop: the stored frames' names, for frames 1 to N-1, in order.")
    frame: int | None = Field(None, description="With --loop --frame: the frame the edit is a Variant of.")
    skipped: list[str] = Field([], description="With --loop: the files left out because they are frame 0.")
    state: str | None = Field(None, description="With --state: the Prop's state the Variant belongs to.")
    emotion: str | None = Field(None, description="With --emotion: the portrait's emotion the Variant belongs to.")
    of: str | None = Field(None, description="With --of: what the edit was made on.")
    placed_scale: tuple[float, float] | None = Field(None, description="With --of: the edit's px per Source px.")
    placed_at: tuple[int, int] | None = Field(None, description="With --of: where the edit's top-left lies in the Source.")
    registration_residual: float | None = Field(None, description="With --of: the median miss of the registration, in Source px.")
    variants: list[str] = Field(description="The Asset's Variants; with --look, that Look's edits.")
    clip_sources: list[str]
    sheets: list[str]

    def text(self) -> str:
        added = "added" if self.created else "already had"
        if self.sound is not None:
            seconds = f", {self.sound.duration_s:g} s" if self.sound.duration_s is not None else ""
            return (f"{self.asset}: {added} the recording {self.variant} ({self.file}{seconds}, {self.sound.rate} Hz); pick it "
                    f"with kiripix pick {self.asset} {self.variant}")
        if self.emotion is not None:
            return (f"{self.asset}: {added} the Variant {self.variant} of emotion {self.emotion} ({self.file}); pick it with "
                    f"kiripix pick {self.asset} {self.variant} --emotion {self.emotion}")
        if self.state is not None:
            return (f"{self.asset}: {added} the Variant {self.variant} of state {self.state} ({self.file}); pick it with "
                    f"kiripix pick {self.asset} {self.variant} --state {self.state}")
        if self.loop is not None and self.frame is not None:
            return (f"{self.asset}: {added} the edit {self.variant} of frame {self.frame} of Loop {self.loop} ({self.file}); "
                    f"pick it with kiripix pick {self.asset} {self.variant} --loop {self.loop} --frame {self.frame}")
        if self.loop is not None:
            skipped = f" (left out {', '.join(self.skipped)}: frame 0 is the room's)" if self.skipped else ""
            return (f"{self.asset}: imported {len(self.loop_frames)} frames of Loop {self.loop} ({self.file} ...){skipped}")
        if self.look is not None:
            on = f", made on {self.of} and placed on the Source" if self.of else ""
            return (f"{self.asset}: {added} the edit {self.variant} of Look {self.look} ({self.file}{on}); pick it with "
                    f"kiripix pick {self.asset} {self.variant} --look {self.look}")
        if self.role == "sheet":
            return f"{self.asset}: {added} the sheet {self.sheet} ({self.file})"
        if self.role == "variant":
            return (f"{self.asset}: {added} the Variant {self.variant} ({self.file}); pick it with "
                    f"kiripix pick {self.asset} {self.variant}")
        if self.role == "thing":
            known = (f"; materials {', '.join(self.thing_materials) or 'none'}" if self.thing_materials is not None
                     else "; its materials are read at the first render")
            return f"{self.asset}: {added} a Variant of the thing {self.thing} ({self.file}), now current{known}"
        if self.role == "parameters":
            return (f"{self.asset}: {added} the parameter file {self.parameters} ({self.file}); the Project's generator "
                    f"builds the Model from it: kiripix run {self.asset}")
        what = f"the clip source {self.clip_source}" if self.role == "clip-source" else "the rigged file"
        return f"{self.asset}: {added} {what} ({self.file})"


@command(
    "import",
    summary="Add a file made elsewhere to an Asset: an image as a Variant (a PNG, named by its hash), for a "
            "character a Model, an animation file, the rigged file or a held thing, or for a sprite a PNG sheet or a ZIP of PNGs "
            "(--role).",
    input=ImportInput,
    output=ImportData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("asset", "file", "frames")),
    locks=LockNeeds(asset=_asset_lock),
    files=("file", "frames", "kit"),
)
def import_variant(arguments: ImportInput, context: Context) -> Outcome[ImportData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    if asset.kind == sources.SOUND:
        return _import_recording(project, asset, arguments, context)
    if (arguments.url, arguments.author, arguments.licence) != (None, None, None):
        raise fail("import.provenance_needs_sound", "--url, --author and --licence record a sound's Provenance; "
                   f"{asset.id} is a {asset.kind}", fix=f"kiripix import {asset.id} {arguments.file}")
    if arguments.thing is not None or arguments.role == "thing":
        if arguments.role != "thing" or arguments.thing is None:
            raise fail("import.thing_needs_role", "--role thing and --thing <id> go together",
                       fix=f"kiripix import {asset.id} {arguments.file} --role thing --thing "
                           f"{arguments.thing or '<id>'}")
        if (arguments.state is not None or arguments.emotion is not None or arguments.look is not None
                or arguments.loop is not None or arguments.frames or arguments.kit is not None
                or arguments.frame is not None or arguments.of is not None):
            raise fail("import.thing_takes_one_file", "a held thing is one mesh file: not with --state, --emotion, --look, "
                       "--loop, --frame, --kit, --of or more files",
                       fix=f"kiripix import {asset.id} {arguments.file} --role thing --thing {arguments.thing}")

        def progress(done: int, total: int, message: str) -> None:
            context.progress(ProgressEvent(event="probe_progress", stage=None, done=done, total=total, message=message))

        name, path, created, names = things.import_thing(
            project, asset, context.cwd / arguments.file, str(arguments.file), arguments.thing, progress=progress,
            check_cancel=context.cancel.check)
        return Outcome(ImportData(
            asset=asset.id, look=None, role="thing", variant=None, sheet=None, clip_source=None, rigged=None,
            file=project.relative(path), created=created, thing=arguments.thing,
            thing_variants=list(things.variants(asset, arguments.thing)), thing_materials=names,
            variants=list(sources.variants(asset)), clip_sources=list(sources.clip_sources(asset)), sheets=[]))
    if arguments.emotion is not None:
        if (arguments.state is not None or arguments.look is not None or arguments.loop is not None or arguments.frames
                or arguments.kit is not None or arguments.frame is not None or arguments.of is not None):
            raise fail("import.emotion_takes_one_image", "--emotion is one image for a portrait's emotion: not with --state, "
                       "--look, --loop, --frame, --kit, --of or more files",
                       fix=f"kiripix import {asset.id} {arguments.file} --emotion {arguments.emotion}")
        declared_emotion, name, path, created = emotions.import_emotion(
            project, asset, context.cwd / arguments.file, str(arguments.file), arguments.role or "variant", arguments.emotion)
        return Outcome(ImportData(
            asset=asset.id, look=None, role="variant", variant=name, sheet=None, clip_source=None, rigged=None,
            file=project.relative(path), created=created, emotion=declared_emotion.id,
            variants=list(emotions.emotion_variants(asset, declared_emotion)), clip_sources=[], sheets=[]))
    if arguments.state is not None:
        if (arguments.look is not None or arguments.loop is not None or arguments.frames or arguments.kit is not None
                or arguments.frame is not None or arguments.of is not None):
            raise fail("import.state_takes_one_image", "--state is one image for a Prop's state: not with --look, --loop, "
                       "--frame, --kit or more files",
                       fix=f"kiripix import {asset.id} {arguments.file} --state {arguments.state}")
        declared, name, path, created = sources.import_state(project, asset, context.cwd / arguments.file,
                                                             str(arguments.file), arguments.role or "variant",
                                                             arguments.state)
        return Outcome(ImportData(
            asset=asset.id, look=None, role="variant", variant=name, sheet=None, clip_source=None, rigged=None,
            file=project.relative(path), created=created, state=declared.id,
            variants=list(sources.state_variants(asset, declared)), clip_sources=[], sheets=[]))
    if arguments.kit is not None and arguments.loop is None:
        raise fail("import.kit_needs_loop", "--kit is for the frames of a Loop",
                   fix=f"kiripix import {asset.id} {arguments.file} --loop <loop> --kit {arguments.kit}")
    if arguments.frame is not None and arguments.loop is None:
        raise fail("import.frame_needs_loop", "--frame is for an edit frame of a Loop",
                   fix=f"kiripix import {asset.id} {arguments.file} --loop <loop> --frame {arguments.frame}")
    if arguments.of is not None and not (arguments.look is not None or arguments.frame is not None):
        raise fail("import.of_needs_look", "--of is for a Look's edit (--look) or a Loop's edit frame (--loop --frame)",
                   fix=f"kiripix import {asset.id} {arguments.file} --look <look> --of {arguments.of}")
    if arguments.loop is not None and arguments.frame is not None:
        if arguments.frames or arguments.kit is not None or arguments.look is not None                 or (arguments.role or "variant") != "variant":
            raise fail("import.edit_takes_one_image", "an edit frame is one image: not with more frames, --kit, --look or "
                       "another --role",
                       fix=f"kiripix import {asset.id} {arguments.file} --loop {arguments.loop} --frame {arguments.frame}")
        placed = None
        if arguments.of is None:
            edit = loopedits.import_edit(project, asset, context.cwd / arguments.file, str(arguments.file), arguments.loop,
                                         arguments.frame)
        else:
            with editof.placed_file(project, asset, context.cwd / arguments.file, str(arguments.file), arguments.of) as (
                    path, placed):
                edit = loopedits.import_edit(project, asset, path, str(arguments.file), arguments.loop, arguments.frame)
        return Outcome(ImportData(
            asset=asset.id, look=None, role="variant", variant=edit.name, sheet=None, clip_source=None, rigged=None,
            file=project.relative(edit.path), created=edit.created, variants=edit.variants, clip_sources=[], sheets=[],
            loop=arguments.loop, frame=arguments.frame, of=arguments.of,
            placed_scale=placed.scale if placed else None, placed_at=placed.origin if placed else None,
            registration_residual=placed.residual if placed else None),
            edit.findings + (placed.findings if placed else []))
    if arguments.loop is not None:
        shown = [arguments.file, *arguments.frames]
        if arguments.look is not None or (arguments.role or "variant") != "variant":
            raise fail("import.loop_takes_images", "--loop takes images only: not with --look or another --role",
                       fix=f"kiripix import {asset.id} {arguments.file} --loop {arguments.loop}")
        done = loopkit.import_frames(project, asset, [context.cwd / p for p in shown], [str(p) for p in shown],
                                     arguments.loop,
                                     None if arguments.kit is None else context.cwd / arguments.kit,
                                     None if arguments.kit is None else str(arguments.kit))
        return Outcome(ImportData(
            asset=asset.id, look=None, role="variant", variant=None, sheet=None, clip_source=None, rigged=None,
            file=project.relative(done.paths[0]), created=done.created, variants=[], clip_sources=[], sheets=[],
            loop=arguments.loop, loop_frames=done.names, skipped=done.skipped), done.findings)
    if arguments.frames:
        raise fail("import.frames_need_loop", "more than one file is imported only as the frames of a Loop",
                   fix=f"kiripix import {asset.id} {arguments.file} --loop <loop>")
    if arguments.look is not None:
        role = arguments.role or "variant"
        look_placed = None
        if arguments.of is None:
            name, path, created = sources.import_look(project, asset, context.cwd / arguments.file, str(arguments.file),
                                                      role, arguments.look)
        else:
            with editof.placed_file(project, asset, context.cwd / arguments.file, str(arguments.file), arguments.of) as (
                    temporary, look_placed):
                name, path, created = sources.import_look(project, asset, temporary, str(arguments.file), role,
                                                          arguments.look)
        return Outcome(ImportData(
            asset=asset.id, look=arguments.look, role=role, variant=name, sheet=None, clip_source=None, rigged=None,
            file=project.relative(path), created=created,
            variants=list(sources.look_variants(asset, arguments.look)), clip_sources=[], sheets=[],
            of=arguments.of, placed_scale=look_placed.scale if look_placed else None,
            placed_at=look_placed.origin if look_placed else None,
            registration_residual=look_placed.residual if look_placed else None),
            look_placed.findings if look_placed else [])
    role = arguments.role or ("sheet" if sources.takes_sheets(asset) else "variant")
    name, path, created = sources.import_file(asset, context.cwd / arguments.file, str(arguments.file), role)
    return Outcome(ImportData(
        asset=asset.id, look=None, role=role,
        variant=name if role == "variant" else None,
        sheet=name if role == "sheet" else None,
        clip_source=name if role == "clip-source" else None,
        rigged=name if role == "rigged" else None,
        parameters=name if role == "parameters" else None,
        file=project.relative(path), created=created,
        variants=list(sources.variants(asset)), clip_sources=list(sources.clip_sources(asset)),
        sheets=list(sheets.sheets(asset))))


def _import_recording(project: Project, asset: Asset, arguments: ImportInput, context: Context) -> Outcome[ImportData]:
    """A sound's recording, with its Provenance (ticket 0395)."""
    file = str(arguments.file)
    if (arguments.role or "variant") != "variant" or any(
            v is not None for v in (arguments.thing, arguments.look, arguments.loop, arguments.kit, arguments.frame,
                                    arguments.state, arguments.emotion, arguments.of)) or arguments.frames:
        raise fail("import.sound_takes_a_recording", f"{asset.id} is a sound: it takes one recording (a WAV, FLAC, MP3 or OGG), "
                   "with --url, --author and --licence", fix=f"kiripix import {asset.id} {file}")
    recording = sounds.import_recording(asset, context.cwd / arguments.file, file, url=arguments.url,
                                        author=arguments.author, licence=arguments.licence)
    found = recording.provenance or sounds.Provenance()
    return Outcome(ImportData(
        asset=asset.id, look=None, role="variant", variant=recording.name, sheet=None, clip_source=None, rigged=None,
        file=project.relative(recording.path), created=recording.created, variants=list(sources.variants(asset)),
        clip_sources=[], sheets=[],
        sound=SoundFile(rate=recording.info.rate, channels=recording.info.channels, duration_s=recording.info.duration_s,
                        codec=recording.info.codec, url=found.url, author=found.author, licence=found.licence)))


# pick


class PickInput(_AssetInput):
    variant: str = Field(description="The Variant to use as the Source; `kiripix next` lists them. With --look, one "
                                     "of that Look's edits.")
    look: str | None = Field(None, description="A room's Look: pick that Look's edit Variant (made on the room's "
                                               "current Source) instead of the room's Source.")
    loop: str | None = Field(None, description="A room's frame Loop, with --frame: pick that frame's edit Variant (made "
                                               "on the room's current Source) as the frame.")
    frame: int | None = Field(None, ge=0, description="With --loop: the frame, from 1 (frame 0 is the room's and is refused).")
    state: str | None = Field(None, description="A Prop's other state: pick that state's Variant (`import --state`) "
                                                "as the state's Source, instead of the default Source.")
    emotion: str | None = Field(None, description="A portrait's emotion: pick that emotion's Variant (`import --emotion`, "
                                                  "made on the portrait's current neutral Source) as the emotion's image, "
                                                  "instead of the neutral Source.")


class PickData(BaseModel):
    asset: str
    sheet: str | None = Field(None, description="For a sprite: the one-direction sheet the picked image was stored as.")
    clip: str | None = Field(None, description="For a sprite: the clip that sheet holds (`idle`, `idle_2`...).")
    state: str | None = Field(None, description="With --state: the state whose Variant was picked.")
    emotion: str | None = Field(None, description="With --emotion: the emotion whose Variant was picked.")
    look: str | None = Field(description="With --look: the Look whose edit was picked.")
    loop: str | None = Field(None, description="With --loop: the Loop whose frame was picked.")
    frame: int | None = Field(None, description="With --loop: the frame the edit was picked for.")
    stage: str
    variant: str
    id: str
    stages: list[StageState]

    def text(self) -> str:
        if self.sheet is not None:
            return (f"{self.asset}: picked {self.variant}, stored as sheet {self.sheet} (clip {self.clip}, south only); "
                    f"next: kiripix run {self.asset} frames")
        if self.emotion is not None:
            return f"{self.asset}: picked {self.variant} as the image of emotion {self.emotion} ({self.stage} Decision {self.id})"
        if self.state is not None:
            return f"{self.asset}: picked {self.variant} as the Source of state {self.state} ({self.stage} Decision {self.id})"
        if self.loop is not None:
            return (f"{self.asset}: picked {self.variant} as frame {self.frame} of Loop {self.loop} "
                    f"({self.stage} Decision {self.id})")
        if self.look is not None:
            return f"{self.asset}: picked {self.variant} as the edit of Look {self.look} ({self.stage} Decision {self.id})"
        return f"{self.asset}: picked {self.variant} as the Source ({self.stage} Decision {self.id})"


@command(
    "pick",
    summary="Pick one of an Asset's Variants as its Source (records the Pick Decision).",
    input=PickInput,
    output=PickData,
    kind="writing",
    mcp="exposed",
    cli=CliMeta(positional=("asset", "variant")),
    locks=LockNeeds(asset=_asset_lock),
)
def pick(arguments: PickInput, context: Context) -> Outcome[PickData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    if sources.takes_sheets(asset):  # a sprite's image candidate becomes a one-direction sheet (ticket 0390)
        if (arguments.state, arguments.emotion, arguments.look, arguments.loop, arguments.frame) != (None,) * 5:
            raise fail("pick.sprite_alone", "a sprite's pick takes only the candidate: --state, --emotion, --look, --loop and "
                       "--frame are for other Assets", fix=f"kiripix pick {asset.id} {arguments.variant}")
        sheet, clip = gen_sprite.pick(project, asset, arguments.variant)
        return Outcome(PickData(asset=asset.id, sheet=sheet, clip=clip, look=None, stage="frames", variant=arguments.variant,
                                id=sheet, stages=AssetGraph(project, asset, HashCache(project.state_dir)).states()))
    if arguments.emotion is not None:
        if (arguments.state is not None or arguments.look is not None or arguments.loop is not None
                or arguments.frame is not None):
            raise fail("pick.emotion_alone", "--emotion is a portrait's emotion: not with --state, --look, --loop or --frame",
                       fix=f"kiripix pick {asset.id} {arguments.variant} --emotion {arguments.emotion}")
        spec, entry = emotions.pick_emotion(project, asset, arguments.emotion, arguments.variant)
        stages = AssetGraph(project, asset, HashCache(project.state_dir)).states()
        return Outcome(PickData(asset=asset.id, emotion=arguments.emotion, look=None, stage=spec.name,
                                variant=arguments.variant, id=entry.id, stages=stages))
    if arguments.state is not None:
        if arguments.look is not None or arguments.loop is not None or arguments.frame is not None:
            raise fail("pick.state_alone", "--state is a Prop's state: not with --look, --loop or --frame",
                       fix=f"kiripix pick {asset.id} {arguments.variant} --state {arguments.state}")
        spec, entry = sources.pick_state(project, asset, arguments.state, arguments.variant)
        states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
        return Outcome(PickData(asset=asset.id, state=arguments.state, look=None, stage=spec.name,
                                variant=arguments.variant, id=entry.id, stages=states))
    if (arguments.loop is None) != (arguments.frame is None):
        raise fail("pick.loop_needs_frame", "--loop and --frame go together: a Loop's edit is picked for a frame",
                   fix=f"kiripix pick {asset.id} {arguments.variant} --loop {arguments.loop or '<loop>'} "
                       f"--frame {arguments.frame if arguments.frame is not None else 1}")
    if arguments.loop is not None and arguments.frame is not None:
        if arguments.look is not None:
            raise fail("pick.loop_or_look", "--loop and --look are two things to pick: use one",
                       fix=f"kiripix pick {asset.id} {arguments.variant} --loop {arguments.loop} --frame {arguments.frame}")
        spec, entry = loopedits.pick_edit(project, asset, arguments.loop, arguments.frame, arguments.variant)
    elif arguments.look is not None:
        spec, entry = sources.pick_look(project, asset, arguments.look, arguments.variant)
    else:
        spec, entry = sources.pick(project, asset, arguments.variant)
    states = AssetGraph(project, asset, HashCache(project.state_dir)).states()
    return Outcome(PickData(asset=asset.id, look=arguments.look, loop=arguments.loop, frame=arguments.frame,
                            stage=spec.name, variant=arguments.variant,
                            id=entry.id, stages=states))


# thing-remove


class ThingRemoveInput(_AssetInput):
    thing: str = Field(description="The held thing's ID, such as phone (`kiripix show <asset>` lists them).")


class ThingRemoveData(BaseModel):
    asset: str
    thing: str
    removed: list[str] = Field(description="The thing's stored files that were deleted, relative to the Project.")
    things: list[str] = Field(description="The Asset's things after the removal, in numbering order.")

    def text(self) -> str:
        return f"{self.asset}: removed the thing {self.thing} ({len(self.removed)} file(s))"


@command(
    "thing-remove",
    summary="Remove a held thing and all its Variants from a character. Refused while a clip's `attach` holds it.",
    input=ThingRemoveInput,
    output=ThingRemoveData,
    kind="writing",
    mcp="hidden",
    cli=CliMeta(positional=("asset", "thing")),
    locks=LockNeeds(asset=_asset_lock),
)
def thing_remove(arguments: ThingRemoveInput, context: Context) -> Outcome[ThingRemoveData]:
    """Example: `kiripix thing-remove character.hero phone`; `thing.attached` names the clips that still hold it."""
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    removed = things.remove_thing(project, asset, arguments.thing)
    return Outcome(ThingRemoveData(asset=asset.id, thing=arguments.thing, removed=[project.relative(p) for p in removed],
                                   things=things.thing_ids(asset)))
