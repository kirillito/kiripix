"""show, a Probe: one Asset as a UI needs it, with what `status` leaves out. Nothing here writes to the Project."""

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from kiripix.commands.contract import Context, Outcome
from kiripix.commands.decisions import DecisionOut, NoteOut, current_decisions
from kiripix.commands.registry import CliMeta, command
from kiripix.core import emotions, notes, sheets, sources, things
from kiripix.core.assets import Asset, load_asset, wearables_of
from kiripix.core.graph import STAMP_FILE, AssetGraph, Status
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project, find_project
from kiripix.export import export_command
from kiripix.recipes.base import Scalar, SortPosition, StageSpec
from kiripix.recipes.portrait_set import EMOTIONS_OUT
from kiripix.recipes.prop_states import STATES_OUT

ParamOrigin = Literal["asset", "generated", "base", "default"]


class ShowInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset: str = Field(description="The Asset ID, such as room.queen_west_alley.")


class VariantOut(BaseModel):
    name: str
    file: str = Field(description="The file, relative to the Project.")
    imported_as: str | None = Field(
        description="The file name it was imported with, or null if it was imported before Kiripix recorded names.")
    size: int = Field(description="The stored file's size in bytes.")


class ClipSourceOut(VariantOut):
    from_base: bool = Field(description="The file is the base's, in the base's folder: the Asset has none of that name.")


class SheetOut(VariantOut):
    png_count: int | None = Field(description="A ZIP sheet's PNG count; null for a PNG sheet.")


class LookOut(BaseModel):
    look: str = Field(description="The Look's ID.")
    variants: list[VariantOut] = Field(description="The Look's stored edits, named by hash.")
    picked: str | None = Field(description="The edit the `looks` Stage cuts the Look from; null without a Pick.")


class ThingMaterialOut(BaseModel):
    name: str
    number: int = Field(description="The material's place among the things' materials, from 1, in numbering order (the "
                                    "things in the order they were first imported, a thing's own materials sorted by name).")
    index: int | None = Field(description="Its number in the material pass: the Model's material count plus `number`; "
                                          "null while `render` hasn't built (the Model's count isn't known yet).")


class ThingOut(BaseModel):
    thing: str = Field(description="The thing's ID.")
    variants: list[VariantOut] = Field(description="The thing's stored meshes, named by hash.")
    current: str = Field(description="The Variant a render holds: the newest imported.")
    materials: list[ThingMaterialOut] = Field(description="The current Variant's materials, numbered after the Model's.")
    materials_known: bool = Field(description="False for a .blend made without Blender: the render reads its materials.")
    attached_by: list[str] = Field(description="The clips whose `attach` holds the thing; it can't be removed while any does.")
    from_base: bool = Field(False, description="The thing is the base's, in the base's folder: the Asset has none of that ID.")


class StateImageOut(BaseModel):
    stage: str
    image: str | None = Field(description="The Stage's built image for this state, relative to the Project.")
    input_image: str | None = Field(description="The built image of this state that the Stage is made from.")


class EmotionOut(BaseModel):
    emotion: str = Field(description="The emotion's ID.")
    variants: list[VariantOut] = Field(description="The emotion's stored images, named by hash.")
    picked: str | None = Field(description="The Variant picked as the emotion's image; null without a Pick.")
    made_on: str | None = Field(description="The neutral Source (Variant name) the picked image was made on; null without a Pick.")
    current: bool = Field(description="The picked image was made on the portrait's current neutral Source. False: the emotion "
                                      "is in needs-input until it is made again from the new Source.")
    images: list[StateImageOut] = Field(
        [], description="Per Stage that has an image, the emotion's built image (`<stage>/emotions/<id>.png`) and the "
                        "built image of the same emotion that the Stage is made from, as `stages` gives the neutral's. "
                        "A Stage that hasn't built the emotion isn't listed.")


class StateOut(BaseModel):
    state: str = Field(description="The state's ID.")
    width: int = Field(description="The size declared for the state, in px.")
    height: int
    variants: list[VariantOut] = Field(description="The state's imported images, named by hash.")
    picked: str | None = Field(description="The Variant the state is cut from; null without a Pick.")
    images: list[StateImageOut] = Field(
        [], description="Per Stage that has an image, the state's built image and input image, as `stages` gives the "
                        "default's. A Stage's findings about this state carry it as `position.state`.")


class StageDetail(BaseModel):
    stage: str
    status: Status
    reason: str | None
    failure_code: str | None = Field(
        None, description="While the Stage is failed: the code of the finding its last run gave, such as rig.base_mismatch; "
                          "stage.failed unless the Stage gave its own. `reason` is that finding's message.")
    params: dict[str, Scalar] = Field(description="The Stage's current parameters: its defaults and what `set` set; for "
                                                  "an Asset made from a base, also what its base set.")
    param_sources: dict[str, ParamOrigin] = Field(
        default_factory=dict,
        description="Where each of `params` comes from. asset: the Asset's own asset.toml (`set`). generated: its Model's "
                    "generator gave it, as far as the Model is built. base: its base's asset.toml. default: nobody set it.")
    decisions: list[DecisionOut] = Field(description="The Stage's current Decisions as recorded, the journal replayed: "
                                                     "what `undo` and `redo` step through. For an Asset made from a base, "
                                                     "the base's come first, each marked `from_base`.")
    decisions_as_read: list[DecisionOut] = Field(
        description="The Stage's current Decisions as the Stage reads them: `decisions` through the Stage's own reading, "
                    "where it has one. A Loop's `remove` drops the Loop's Decisions and a `rename` gives them the new ID; "
                    "on `clips`, one `clip` and one `transition` per name, the latest winning, without the ones a "
                    "`remove` took away, and each `remove` that found nothing first. Each keeps `from_base`: a clip "
                    "the Asset decided again over the base's is its own.")
    notes: list[NoteOut] = Field(default_factory=list, description="The Stage's hand-over notes (`note`), oldest first, "
                                                                  "each with `live`: no newer Decision or `accept` yet.")
    image: str | None = Field(description="The Stage's built image, relative to the Project.")
    input_image: str | None = Field(description="The built image this Stage is made from, relative to the Project.")
    outputs: list[str] = Field(description="The files of the Stage's built output, relative to the Project.")
    markers: list[dict[str, Any]] = Field(description="The Markers its Decisions place, whether built yet or not.")
    sort: list[SortPosition] = Field(
        description="Each Layer's sort position (layer, above, marker, y, slope), as its Decisions give it, whether built "
                    "yet or not. A Layer with no y-sort line and not above isn't listed: `check` reports it.")


class BodyOut(BaseModel):
    size: tuple[int, int] = Field(description="The Body's footprint in px: width and height.")
    dash: int = Field(description="The widest pit it can dash over, in px.")


class WearableOut(BaseModel):
    asset: str = Field(description="The Wearable's Asset ID.")
    order: int = Field(description="Its default stacking order over the body (the Wearable's `sheet` parameter `order`); the "
                                   "body is 0.")


class ShowData(BaseModel):
    asset: str
    kind: str
    params: dict[str, Scalar] = Field(description="The Asset's own parameters, such as a room's view.")
    base: str | None = Field(None, description="The Asset this one is made from (a character's `base` parameter), or null.")
    resolution: tuple[int, int] = Field(description="The game's internal resolution, from kiripix.toml.")
    body: BodyOut = Field(description="The stand-in player, from kiripix.toml.")
    tile: int = Field(description="The Project's tile in px, from kiripix.toml (`project.tile`).")
    wearables: list[WearableOut] = Field(
        [], description="A body's Wearables, by stacking order and then ID. Empty for an Asset that has none.")
    variants: list[VariantOut]
    picked: str | None
    looks: list[LookOut] = Field(description="A room's Looks that have a stored edit (`import --look`): their edits and "
                                             "the picked one, or null.")
    default_state: str | None = Field(None, description="A Prop's default state: its picked Source's ID (the brief's "
                                                        "`state`). Null for another Kind.")
    states: list[StateOut] = Field([], description="A Prop's other states, as declared (`state` Decision on `source`): "
                                                   "each with its Variants and Pick. Empty for a Prop with none.")
    emotions: list[EmotionOut] = Field([], description="A portrait's emotions, as declared (`emotion` Decision on `source`): "
                                                       "each with its Variants and Pick. The neutral image is `picked`. Empty "
                                                       "for a portrait with none and for another Kind.")
    things: list[ThingOut] = Field([], description="A character's held things (`import --role thing`), in numbering order: "
                                                   "each with its Variants, current Variant, materials and the clips that "
                                                   "attach it. Empty without any.")
    clip_sources: list[ClipSourceOut] = Field(description="A character's animation files, named by file stem; for one made "
                                                       "from a base, also the base's, which stay in the base's folder.")
    rigged: VariantOut | None = Field(description="A character's rigged file.")
    parameters: VariantOut | None = Field(None, description="A generated character's parameter file, which the Project's "
                                                            "generator builds its Model from.")
    sheets: list[SheetOut] = Field(description="A sprite's imported sheets (PNGs and ZIPs), named by hash.")
    stages: list[StageDetail]
    export_command: str | None = Field(
        None, description="While every Stage is done and the game doesn't have what is built: the Command that exports it.")

    def text(self) -> str:
        lines = [f"{self.asset} ({self.kind})" + (f", made from {self.base}" if self.base else "")]
        lines += [f"  variant {v.name}{' (picked)' if v.name == self.picked else ''}" for v in self.variants]
        for state in self.states:
            lines.append(f"  state {state.state} ({state.width}x{state.height})"
                         + (f", picked {state.picked}" if state.picked else ", no Source picked"))
            lines += [f"    variant {v.name}{' (picked)' if v.name == state.picked else ''}" for v in state.variants]
        for emotion in self.emotions:
            lines.append(f"  emotion {emotion.emotion}" + (f", picked {emotion.picked}" if emotion.picked else ", no image picked")
                         + ("" if emotion.current or emotion.picked is None else " (made on another Source)"))
            lines += [f"    variant {v.name}{' (picked)' if v.name == emotion.picked else ''}" for v in emotion.variants]
        lines += [f"  parameters {self.parameters.file}"] if self.parameters is not None else []
        for t in self.things:
            lines.append(f"  thing {t.thing}, current {t.current}" + (" (base)" if t.from_base else "") + (f", held by {', '.join(t.attached_by)}" if t.attached_by else ""))
            lines += [f"    material {m.number} {m.name}" + (f" (pass {m.index})" if m.index is not None else "")
                      for m in t.materials]
            lines += [] if t.materials_known else ["    materials: read at the first render"]
        lines += [f"  clip source {c.name}" for c in self.clip_sources]
        lines += [f"  rigged {self.rigged.file}"] if self.rigged is not None else []
        lines += [f"  sheet {s.name} ({s.imported_as or s.file}, {s.size} bytes"
                  + (f", {s.png_count} PNGs" if s.png_count is not None else "") + ")" for s in self.sheets]
        for stage in self.stages:
            marks = {"generated": " (generated)", "base": " (base)"}  # who set a value, when it wasn't the Asset or nobody
            params = ", ".join(f"{k}={v}{marks.get(stage.param_sources.get(k, ''), '')}" for k, v in stage.params.items())
            lines.append(f"  {stage.stage:<10} {stage.status}" + (f"  {params}" if params else ""))
        if self.export_command:
            lines.append(f"  built, but not in the game yet: {self.export_command}")
        return "\n".join(lines)


def _variant(project: Project, asset: Asset, names: dict[str, str], name: str, path: Path) -> VariantOut:
    return VariantOut(name=name, file=project.relative(path),
                      imported_as=names.get(path.relative_to(asset.dir).as_posix()), size=path.stat().st_size)


def _wearables(project: Project, asset: Asset, cache: HashCache) -> list[WearableOut]:
    """The Wearables whose body is the Asset, with their `order` (ticket 0296)."""
    found: list[WearableOut] = []
    for wearable in wearables_of(project, asset.id):
        theirs = AssetGraph(project, load_asset(project, wearable), cache)
        found.append(WearableOut(asset=wearable, order=theirs.worn_order()))
    return sorted(found, key=lambda w: (w.order, w.asset))


def _things(project: Project, graph: AssetGraph, names: dict[str, str]) -> list[ThingOut]:
    """A character's things with their materials numbered after the Model's (ticket 0301): its base's first (ticket 0312)."""
    asset = graph.asset
    if asset.kind != "character":
        return []
    model = things.model_material_count(graph)
    held = things.attachments(graph)  # once, not per thing
    theirs = sources.imported_names(graph.base.asset) if graph.base is not None else {}
    found: list[ThingOut] = []
    for info in things.listed(asset, graph.base_asset):
        own, journal = (graph.base.asset, theirs) if info.from_base and graph.base is not None else (asset, names)
        found.append(ThingOut(
            thing=info.thing, current=info.path.stem, from_base=info.from_base,
            variants=[_variant(project, own, journal, name, path) for name, path in info.variants.items()],
            materials=[ThingMaterialOut(name=name, number=info.first + i, index=None if model is None else model + info.first + i)
                       for i, name in enumerate(info.materials or [])],
            materials_known=info.materials is not None,
            attached_by=held.get(info.thing, [])))
    return found


def _clip_sources(project: Project, graph: AssetGraph, names: dict[str, str]) -> list[ClipSourceOut]:
    """The character's clip sources, and its base's that it has no file of the same name for (ADR 0012), by name."""
    found = {name: ClipSourceOut(**_variant(project, graph.asset, names, name, path).model_dump(), from_base=False)
             for name, path in sources.clip_sources(graph.asset).items()}
    if graph.base is not None:
        theirs = sources.imported_names(graph.base.asset)
        for name, path in sources.clip_sources(graph.base.asset).items():
            if name not in found:
                found[name] = ClipSourceOut(**_variant(project, graph.base.asset, theirs, name, path).model_dump(),
                                            from_base=True)
    return [found[name] for name in sorted(found)]


def _params(graph: AssetGraph, spec: StageSpec) -> tuple[dict[str, Scalar], dict[str, ParamOrigin]]:
    """The Stage's parameters as it will read them, and where each comes from: a value its Model's generator gave stands in
    for one the Asset didn't set itself (`StageSpec.generated_params`)."""
    params = graph.params(spec)
    found: dict[str, ParamOrigin] = dict(graph.param_sources(spec))
    if spec.generated_params is not None:
        for name, value in spec.generated_params(graph.stage_run(spec, graph.output_dir(spec))).items():
            if found.get(name) != "asset":
                params[name], found[name] = value, "generated"
    return params, found


def _outputs(project: Project, folder: Path) -> list[str]:
    if not (folder / STAMP_FILE).is_file():
        return []
    return [project.relative(path) for path in sorted(folder.iterdir()) if path.is_file() and path.name != STAMP_FILE]


def _state_images(project: Project, graph: AssetGraph, state: str) -> list[StateImageOut]:
    """A Prop's state's images: each Stage writes them under `states/<id>/` of its output folder (ticket 0259)."""
    found: list[StateImageOut] = []
    for spec in graph.kind.stages:
        if spec.image is None:
            continue
        image = graph.output_dir(spec) / STATES_OUT / state / spec.image
        source = graph.input_image(spec)
        before = source[1].parent / STATES_OUT / state / source[1].name if source is not None else None
        if image.is_file() or (before is not None and before.is_file()):
            found.append(StateImageOut(stage=spec.name, image=project.relative(image) if image.is_file() else None,
                                       input_image=project.relative(before)
                                       if before is not None and before.is_file() else None))
    return found


def _emotion_images(project: Project, graph: AssetGraph, emotion: str) -> list[StateImageOut]:
    """A portrait emotion's images: each Stage writes them as `emotions/<id>.png` in its output folder (ticket 0243)."""
    found: list[StateImageOut] = []
    name = f"{emotion}.png"
    for spec in graph.kind.stages:
        if spec.image is None:
            continue
        image = graph.output_dir(spec) / EMOTIONS_OUT / name
        source = graph.input_image(spec)
        before = source[1].parent / EMOTIONS_OUT / name if source is not None else None
        if image.is_file() or (before is not None and before.is_file()):
            found.append(StateImageOut(stage=spec.name, image=project.relative(image) if image.is_file() else None,
                                       input_image=project.relative(before)
                                       if before is not None and before.is_file() else None))
    return found


@command(
    "show",
    summary="Show one Asset: its Variants and Pick, and each Stage's status, parameters, Decisions and images.",
    input=ShowInput,
    output=ShowData,
    kind="probe",
    mcp="hidden",
    cli=CliMeta(positional=("asset",)),
)
def show(arguments: ShowInput, context: Context) -> Outcome[ShowData]:
    project = find_project(context.cwd)
    asset = load_asset(project, arguments.asset)
    cache = HashCache(project.state_dir)
    graph = AssetGraph(project, asset, cache)
    stages = []
    states = graph.states()
    held = notes.held_notes(asset)
    for state in states:
        spec = graph.spec(state.stage)
        image = graph.output_dir(spec) / spec.image if spec.image is not None else None
        source = graph.input_image(spec)
        params, origins = _params(graph, spec)
        theirs = graph.base_decisions(spec)
        base_ids = {d.id for d in theirs}  # Decision IDs are ULIDs: unique across Assets
        stages.append(StageDetail(
            stage=state.stage,
            status=state.status,
            reason=state.reason,
            failure_code=graph.failures.code(state.stage, graph.current_hashes(state.stage))
            if state.status == "failed" else None,
            params=params,
            param_sources=origins,
            decisions=[*current_decisions(theirs, from_base=True), *current_decisions(graph.replay(state.stage).current)],
            decisions_as_read=[DecisionOut(id=d.id, name=d.name, data=d.data, image_hash=d.image_hash,
                                           from_base=d.id in base_ids) for d in graph.decisions(spec)],
            notes=[NoteOut(id=h.note.id, stage=h.note.stage, text=h.note.text, input_hash=h.note.input_hash, live=h.live)
                   for h in held if h.note.stage == state.stage],
            image=project.relative(image) if image is not None and image.is_file() else None,
            input_image=project.relative(source[1]) if source is not None and source[1].is_file() else None,
            outputs=_outputs(project, graph.output_dir(spec)),
            markers=spec.markers(graph.replay(state.stage).current) if spec.markers is not None else [],
            sort=spec.sort(graph.replay(state.stage).current) if spec.sort is not None else [],
        ))
    takes_variants = sources.takes_pick(graph)
    variants = sources.variants(asset) if takes_variants else {}
    names = sources.imported_names(asset)
    look_picks = sources.picked_look_edits(graph)
    state_picks = sources.picked_states(graph)
    emotion_picks = emotions.picked_emotions(graph)
    neutral = emotions.neutral_source(graph)
    data = ShowData(
        asset=asset.id,
        kind=asset.kind,
        params=dict(asset.settings.params),
        base=graph.base.asset.id if graph.base is not None else None,
        resolution=project.settings.project.resolution,
        body=BodyOut(size=project.settings.body.size, dash=project.settings.body.dash),
        tile=project.settings.project.tile,
        wearables=_wearables(project, asset, cache),
        variants=[_variant(project, asset, names, name, path) for name, path in variants.items()],
        picked=sources.picked(graph) if takes_variants else None,
        looks=[LookOut(look=look, picked=look_picks.get(look),
                       variants=[_variant(project, asset, names, name, path)
                                 for name, path in sources.look_variants(asset, look).items()])
               for look in sources.looks_with_edits(asset)],
        default_state=sources.default_state(graph) if asset.kind == "prop" else None,
        states=[StateOut(state=state.id, width=state.width, height=state.height, picked=state_picks.get(state.id),
                         variants=[_variant(project, asset, names, name, path)
                                   for name, path in sources.state_variants(asset, state).items()],
                         images=_state_images(project, graph, state.id))
                for state in sources.declared_states(graph).values()],
        emotions=[EmotionOut(emotion=e.id, picked=emotion_picks[e.id][0] if e.id in emotion_picks else None,
                             made_on=emotion_picks[e.id][1] if e.id in emotion_picks else None,
                             current=e.id in emotion_picks and emotion_picks[e.id][1] == neutral,
                             variants=[_variant(project, asset, names, name, path)
                                       for name, path in emotions.emotion_variants(asset, e).items()],
                             images=_emotion_images(project, graph, e.id))
                  for e in emotions.declared_emotions(graph).values()],
        things=_things(project, graph, names),
        clip_sources=_clip_sources(project, graph, names),
        rigged=_variant(project, asset, names, rigged_path.stem, rigged_path)
        if (rigged_path := sources.rigged(asset)) is not None else None,
        parameters=_variant(project, asset, names, parameters_path.name, parameters_path)
        if (parameters_path := sources.parameters(asset)) is not None else None,
        sheets=[SheetOut(**_variant(project, asset, names, name, path).model_dump(), png_count=sheets.png_count(path))
                for name, path in sheets.sheets(asset).items()],
        stages=stages,
        export_command=export_command(project, asset, cache, states),
    )
    cache.save()
    return Outcome(data)
