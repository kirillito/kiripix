"""The character Recipe (spec §6.3): model, rig, clips, render, palette, finish, sheet, export."""

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.recipes.base import (
    BASE_PARAM,
    BaseInputs,
    NeedsInput,
    StageFailure,
    StageRun,
    PALETTE_PARAMS,
    PICK,
    CheckSpec,
    KindSpec,
    ParamSpec,
    StageInputs,
    StageSpec,
    chain,
)
from kiripix.recipes.blender_launcher import SETTING as BLENDER_SETTING
from kiripix.recipes.blender_launcher import VERSION_SETTING as BLENDER_VERSION_SETTING
from kiripix.recipes.blender_launcher import ScriptFailure, launch_file
from kiripix.recipes.wearable_stack import check_render_stack
from kiripix.recipes.character_finish import check_character_finish, run_character_finish
from kiripix.recipes.character_palette import check_character_palette, palette_generated_params, run_character_palette
from kiripix.recipes.character_sheet import check_character_sheet, run_body_sheet
from kiripix.recipes.render import FORMAT_SETTING as RENDER_FORMAT_SETTING, render_generated_params, run_render
from kiripix.recipes.blender_launcher import launch
from kiripix.recipes.common import picked, source_needs_input, variants
from kiripix.recipes.character_export import check_character_export, export_needs_input, run_character_export
from kiripix.recipes.clips import CLIP, REMOVE, TRANSITION, apply_clip_edits, check_clips, clips_needs_input, run_clips
from kiripix.recipes.rig import BASE_STAGE as RIG_STAGE, BONE, UPLOAD, rig_needs_input, run_rig

MODEL_HEIGHT = 2.0  # the normalised Model's height in Blender units: `render` frames it, so this is only a known size
# 2: `vertices` and `upload` (read by the `rig` Stage); `facing`, `ignored`, `fps`, `source_height` (the Model's height as
# imported, ADR 0012), and a generated Model's `generator` and `generated` (ticket 0224) are additive keys
MODEL_SCHEMA_VERSION = 2
STILL = "still.png"  # a 256 px preview of the Model (facing applied) for the UI; nothing below `model` reads it
FACINGS = ["-y", "+y", "-x", "+x"]  # the way the Model faces in the file; `model` turns it to face -Y, toward the camera
PARAMETERS = "src/parameters/"  # a generated character's parameter file: its Source, in place of a picked Variant
GENERATORS_SETTING = "character.generators"  # `[character.generators.<name>]` in kiripix.toml: {script, library}
GENERATED_MODEL = "generated.glb"  # what the generator wrote, in the Stage's output, before it is normalised
TAIL_LINES = 20  # of a failed generator's output, in its finding


def _parameter_files(run: StageRun) -> list[Path]:
    return [path for name, path in sorted(run.files.items()) if name.startswith(PARAMETERS)]


def _imported_models(run: StageRun) -> StageRun:
    """The run with only the imported Models as its files, the way the Source functions of `common` read them."""
    return replace(run, files={name: path for name, path in run.files.items() if not name.startswith(PARAMETERS)})


def _generator(run: StageRun) -> tuple[str, dict[str, Any]] | str:
    """The Project's generator that builds this character, by name, with its settings; or why there is none: the `generator`
    parameter names it, and a Project with one generator needs no name."""
    known: dict[str, dict[str, Any]] = run.settings.get(GENERATORS_SETTING) or {}
    wanted = str(run.params.get("generator") or "")
    if wanted:
        if wanted not in known:
            return f"the Project has no generator {wanted} (its generators are {', '.join(sorted(known)) or 'none'})"
        return wanted, known[wanted]
    if len(known) == 1:
        return next(iter(known.items()))
    if not known:
        return "the Project has no generator to build the Model from the parameter file"
    return f"the Project has several generators ({', '.join(sorted(known))}), and the character names none"


def model_project_files(run: StageRun) -> list[str]:
    """The generator's script and library, for a character with a parameter file (`StageSpec.project_files`)."""
    found = _generator(run) if _parameter_files(run) else ""
    if isinstance(found, str):
        return []
    return [str(found[1]["script"]), *(str(path) for path in found[1].get("library", []))]


def model_needs_input(run: StageRun) -> NeedsInput | None:
    """A picked Model, or else a parameter file and the generator that builds the Model from it (ticket 0224)."""
    parameters = _parameter_files(run)
    models = _imported_models(run)
    if not parameters:
        return source_needs_input(models)
    if models.files or len(parameters) > 1:
        return NeedsInput(
            "the character has a parameter file and an imported Model" if models.files else "the character has several "
            "parameter files",
            owner_action=f"Keep one Source in assets/character/{run.asset_id.split('.', 1)[1]}/src/: either the one file in "
                         "parameters/, which a generator builds the Model from, or the imported Models.")
    found = _generator(run)
    if isinstance(found, str):
        return NeedsInput(found, owner_action="Add the generator to kiripix.toml as [character.generators.<name>] with "
                                              "its `script` (and `library`), or name one of the Project's: "
                                              f"kiripix set {run.asset_id} model generator=<name>.")
    name, _ = found
    gone = [shown for shown, path in run.project_files.items() if not path.exists()]
    if gone:
        return NeedsInput(f"the generator {name} names {', '.join(gone)}, which the Project doesn't have",
                          owner_action=f"Correct `script` and `library` under [character.generators.{name}] in kiripix.toml: "
                                       "paths in the Project, relative to its root.")
    return None


def _generated_values(result: dict[str, Any], failed: Callable[[str], StageFailure]) -> dict[str, Any]:
    """What the generator said of the Model, checked: `materials` (names), `parts` and `eyes` (text, or names joined by
    commas) and `height` (the Model's height over its base body's). Only these keys are kept."""
    made: dict[str, Any] = {}
    for key in ("parts", "eyes"):
        if key in result:
            value = result[key]
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                value = ",".join(value)
            if not isinstance(value, str):
                raise failed(f"its JSON's `{key}` is neither text nor a list of names")
            made[key] = value
    if "height" in result:
        value = result["height"]
        if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
            raise failed("its JSON's `height` is not a number above 0 (the Model's height over its base body's)")
        made["height"] = float(value)
    if "materials" in result:
        value = result["materials"]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise failed("its JSON's `materials` is not a list of names")
        made["materials"] = value
    return made


def _generate(run: StageRun, parameters: Path) -> tuple[Path, str, dict[str, Any]]:
    """Run the Project's generator on the parameter file. Returns the Model it wrote, its name and what it said of the
    Model. A generator that fails, or ends without the Model or its JSON, is `model.generator_failed`."""
    found = _generator(run)
    assert not isinstance(found, str)  # `model_needs_input` holds the Stage back until there is one
    name, settings = found
    shown = str(settings["script"])
    target = run.output_dir / GENERATED_MODEL

    def failed(why: str) -> StageFailure:
        return StageFailure(
            f"the generator {name} ({shown}) {why}", code="model.generator_failed",
            owner_action=f"Fix {shown} or the parameter file {parameters.name}, then run it again: "
                         f"kiripix run {run.asset_id} model")

    run.progress(0, 2, f"running the generator {name}")
    args = {"parameters": str(parameters), "model": str(target),
            "library": [str(run.project_files[str(path)]) for path in settings.get("library", [])]}
    try:
        result = launch_file(run, run.project_files[shown], args)
    except ScriptFailure as error:
        said = "\n".join(error.tail[-TAIL_LINES:]) or "(it printed nothing)"
        if error.exit_code == 0:
            raise failed(f"ended without writing its JSON (the second path after `--`); its last lines:\n{said}") from None
        raise failed(f"failed (exit {error.exit_code}); its last lines:\n{said}") from None
    except StageFailure as error:
        if error.code is not None or error.owner_action is not None:
            raise  # Blender itself is missing or the wrong version: that finding says so
        raise failed(f"failed: {error}") from None
    if not target.is_file():
        raise failed(f"ended without writing the Model (the `model` path of its arguments, {GENERATED_MODEL})")
    return target, name, _generated_values(result, failed)


def run_model(run: StageRun) -> None:
    """Import the picked Variant in Blender, or the Model the Project's generator builds from the character's parameter
    file (ticket 0224), normalise it, and write `model.blend`, `model.json` and `still.png`."""
    extra: dict[str, Any] = {}
    parameters = _parameter_files(run)
    if parameters:
        path, generator, made = _generate(run, parameters[0])
        source = parameters[0].name
        extra = {"generator": generator, "generated": made}
    else:
        chosen = picked(run)
        assert chosen is not None  # `model_needs_input` holds the Stage back until there is a Pick
        path = variants(_imported_models(run))[chosen]
        source = path.name
    run.progress(1 if parameters else 0, 2 if parameters else 1, "starting Blender")
    arguments: dict[str, Any] = {"input": str(path), "output": str(run.output_dir / "model.blend"), "height": MODEL_HEIGHT,
                                 "upload": str(run.output_dir / UPLOAD), "facing": str(run.params.get("facing", "-y")),
                                 "still": str(run.output_dir / STILL)}
    if run.body is not None:  # a Wearable (ticket 0291): put on the body's skeleton, so it is turned and scaled as the body is
        arguments["like"] = str(run.body.built["model"] / "model.blend")
        del arguments["upload"]
    result = launch(run, "normalise_model", arguments)
    if result.get("upload") and not (run.output_dir / UPLOAD).is_file():
        raise StageFailure("Blender finished without writing the file for Mixamo")
    if not (run.output_dir / STILL).is_file():
        raise StageFailure("Blender finished without writing the still of the Model")
    if not (run.output_dir / "model.blend").is_file():
        raise StageFailure("Blender finished without writing the normalised Model")
    document = {"schema_version": MODEL_SCHEMA_VERSION, "source": source, **result, **extra}
    document.pop("still", None)  # the file is the record
    (run.output_dir / "model.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _imported_as(run: StageRun, source: str) -> str:
    """The name the Owner imported a stored file with, from the Asset's `imported.jsonl` (the newest line wins), or the
    stored name for a file imported before names were recorded. A Stage can't import core, so it reads the file itself."""
    stored = Path(source).name
    shown = source
    try:
        lines = (run.asset_dir / "imported.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return shown
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and Path(str(entry.get("file", ""))).name == stored and entry.get("imported_as"):
            shown = f"{entry['imported_as']} (stored as {source})"
    return shown


def check_model(run: StageRun) -> list[Finding]:
    """A mesh that isn't skinned to the armature was dropped from the Model: say so (the owner can fix the file)."""
    path = run.output_dir / "model.json"
    if not path.is_file():
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    shown = _imported_as(run, str(document["source"]))

    def advice(mesh: str) -> str:
        if document.get("generator"):
            return (f"Change the generator {document['generator']} so that the mesh {mesh} is skinned to the armature, or "
                    "isn't written to the Model.")
        return (f"Remove the mesh {mesh} from {shown} (a bone's custom shape is often "
                "exported as a mesh), or import the file again with that mesh skinned to the armature.")

    return [
        Finding(
            code="model.unskinned_mesh", severity="warning",
            message=f"the mesh {item['name']} ({item['vertices']} vertices) is not skinned to the armature, so it was "
                    "dropped from the Model (it is left out of the height and bounds and is not rendered)",
            position=Position(asset=run.asset_id, stage="model"),
            owner_action=advice(str(item["name"])))
        for item in document.get("ignored", [])
    ]


CHARACTER = KindSpec(
    name="character",
    description="A character, NPC or enemy rendered from a 3D Model, so every animation stays on-model.",
    params=(
        ParamSpec(name=BASE_PARAM, type="str",
                  description="Another character this one is made from (its ID, such as character.body_m; ADR 0012): this "
                              "one's Model carries the base's skeleton, so it needs no rigged file; it starts with the "
                              "base's clips and clip sources; and a Stage parameter it doesn't set takes the base's value. "
                              "The base has no base of its own."),
    ),
    takes_base=True,
    stages=chain(
        StageSpec(
            name="model",
            description="Imports .glb, .fbx or .blend, or builds the Model from a parameter file with the Project's "
                        "generator; normalises scale and the up axis.",
            inputs=StageInputs(files=["src/*", f"{PARAMETERS}*"], settings=[BLENDER_VERSION_SETTING],
                               given=[BLENDER_SETTING, GENERATORS_SETTING]),
            params=(ParamSpec(name="facing", type="choice", choices=FACINGS, default="-y", from_base=False,
                              description="The way the Model faces in its file, as Blender sees it from above: -y toward "
                                          "the front view, +y away, -x or +x to a side. The Model is turned to face -y, "
                                          "so the render's `s` direction shows its front."),
                    ParamSpec(name="generator", type="str", from_base=False,
                              description="For a character with a parameter file: the Project's generator that builds its "
                                          "Model, a name under [character.generators] in kiripix.toml. Needed only when "
                                          "the Project has more than one.")),
            decisions=(PICK,),
            run=run_model,
            checks=(CheckSpec(code="model.unskinned_mesh",
                              description="Every mesh of a rigged Model is skinned to its armature (a warning)."),
                    CheckSpec(code="model.generator_failed",
                              description="The Project's generator built the Model and wrote its JSON.")),
            check=check_model,
            needs_input=model_needs_input,
            project_files=model_project_files,
            owner_input="Imports a Model (kiripix import <id> <file.glb|.fbx|.blend>) and picks it; or a parameter file "
                        "(kiripix import <id> <file.toml> --role parameters), which needs no Pick.",
            available_from="M3",
        ),
        StageSpec(
            name="rig",
            description="Validates a humanoid rig, or guides the Mixamo round trip; for a character made from a base, "
                        "checks that its Model carries the base's skeleton.",
            inputs=StageInputs(files=["src/rigged/*"], settings=[BLENDER_VERSION_SETTING], given=[BLENDER_SETTING],
                               base=BaseInputs(built=[RIG_STAGE])),
            decisions=(BONE,),
            checks=(
                CheckSpec(code="rig.missing", description="The Model or the rigged file has an armature."),
                CheckSpec(code="rig.bone_missing", description="Hips, spine, head, both arms and both legs have a bone."),
                CheckSpec(code="rig.model_mismatch", description="The rigged file was made from the Model."),
                CheckSpec(code="rig.base_mismatch", description="A character made from a base has every bone of the base, "
                                                                "by its name and under the same parent."),
            ),
            run=run_rig,
            needs_input=rig_needs_input,
            owner_input="The Mixamo round trip, when used: kiripix import <id> <rigged.fbx> --role rigged.",
            available_from="M3",
        ),
        StageSpec(
            name="clips",
            description="Maps named clips to animation sources, with frame range, frame rate and loop flag. A character "
                        "made from a base starts with the base's clips and clip sources.",
            inputs=StageInputs(files=["src/clips/*"], upstream=["model", "rig"], settings=[BLENDER_VERSION_SETTING],
                               given=[BLENDER_SETTING], base=BaseInputs(files=["src/clips/*"], decisions=["clips"])),
            decisions=(CLIP, TRANSITION, REMOVE),
            decisions_view=apply_clip_edits,
            checks=(
                CheckSpec(code="clips.source_missing", description="Each clip's source is an action or a clip-source file."),
                CheckSpec(code="clips.range", description="Each clip's frames are inside its action's."),
                CheckSpec(code="clips.bad_name", description="A clip name is lower-case snake_case with no direction suffix."),
                CheckSpec(code="clips.root_motion", description="No clip moves its root (a warning: the render keeps the feet "
                                                                "at the pivot)."),
                CheckSpec(code="clips.transition_missing_clip", description="A transition's `from` and `to` name clips."),
                CheckSpec(code="clips.transition_frame", description="A transition's frames are frames of the clips it names."),
                CheckSpec(code="clips.transition_loop", description="A transition doesn't start or end on a transition."),
                CheckSpec(code="clips.duplicate_name", description="A transition doesn't take the name of a clip."),
                CheckSpec(code="clips.remove_unknown", description="A `remove` names a clip or a transition (a warning)."),
            ),
            run=run_clips,
            needs_input=clips_needs_input,
            check=check_clips,
            owner_input="Adds animation files (kiripix import <id> <file.fbx> --role clip-source) and chooses clips; a "
                        "clip's source is its file stem.",
            available_from="M3",
        ),
        StageSpec(
            name="render",
            description="Headless Blender render at the target pixel size: colour, normal, depth and mask passes.",
            inputs=StageInputs(upstream=["model", "rig", "clips"], files=["src/clips/*"],
                               settings=["character.camera", "character.height", BLENDER_VERSION_SETTING,
                                         RENDER_FORMAT_SETTING],
                               given=[BLENDER_SETTING], base=BaseInputs(files=["src/clips/*"], built=[RIG_STAGE])),
            params=(
                ParamSpec(
                    name="height",
                    type="int",
                    description="Target height in px; the Project's [character] height when unset. A character made from "
                                "a base is never given its base's value: unset, it is the base's height times its rig's "
                                "height over the base rig's (a generated Model's generator gives that ratio).",
                    minimum=1,
                    from_base=False,
                ),
                ParamSpec(
                    name="camera",
                    type="str",
                    description="The camera preset, by name, from [character.camera] in kiripix.toml.",
                    default="top34_8",
                ),
                ParamSpec(
                    name="cell_margin",
                    type="int",
                    description="Px of room kept round the poses on every side of the cell, beyond the pixel `finish`'s "
                                "outline needs: a Wearable that reaches past the body (a hat, a pack) fits the cell when "
                                "this is large enough (wearable.outside_cell says how large). 0 is the cell the poses "
                                "themselves need.",
                    default=0,
                    minimum=0,
                ),
                ParamSpec(
                    name="bands",
                    type="int",
                    description="Toon shading: the number of light bands on the colour pass.",
                    default=3,
                    minimum=2,
                    maximum=4,
                ),
                ParamSpec(
                    name="shadow",
                    type="float",
                    description="Toon shading: how much the darkest band darkens the colour (0 flat, 1 black).",
                    default=0.5,
                    minimum=0,
                    maximum=1,
                ),
                ParamSpec(
                    name="band_edge",
                    type="float",
                    description="Toon shading: where the light band ends, in half-Lambert (0 to 1). With 2 bands the shadow "
                                "starts there; more bands move every cut by the same amount. 0.5 is the plain cut.",
                    default=0.5,
                    minimum=0,
                    maximum=1,
                ),
                ParamSpec(
                    name="band_smooth",
                    type="float",
                    description="Toon shading: the sigma in px of the blur on the normals before they are lit, inside the "
                                "silhouette only, so the shadow is one large shape per part. 0 is no blur.",
                    default=0,
                    minimum=0,
                ),
                ParamSpec(
                    name="eyes",
                    type="str",
                    description="The Model's eye materials, comma-separated, such as eyes or eyes,iris,eyewhite: render then "
                                "also records where each eye is in every frame, for finish to stamp the eyes (eyes=stamp). "
                                "Empty: the eyes are not followed. Unset on a generated Model: the eye materials its "
                                "generator names.",
                    default="",
                ),
                ParamSpec(
                    name="points",
                    type="str",
                    description="Named points for the game, comma-separated <name>@<target>, such as "
                                "hand_r@mixamorig:RightHand,head@mixamorig:Head: a name of lower case letters, digits and "
                                "underscores, and a bone of the Model's armature (its head) or an Empty of the Model (a socket "
                                "parented to a bone, such as a grip). render records each point's place in every frame, and "
                                "character.json exports them relative to the pivot. Empty: none are recorded.",
                    default="",
                ),
            ),
            gpu=True,
            run=run_render,
            check=check_render_stack,
            worn_stage="render",
            generated_params=render_generated_params,
            checks=(CheckSpec(code="render.camera_unknown", description="The camera preset exists in kiripix.toml."),
                    CheckSpec(code="wearable.stack_differs",
                              description="Info, once a Wearable's render is built: where its Wearables stacked over the body "
                                          "by order differ from stacked by depth, per clip, with the worst frames' boxes.")),
            owner_input="Tunes the camera preset once per project.",
            available_from="M3",
        ),
        StageSpec(
            name="palette",
            description="One palette per character across all frames, and orphan cleanup.",
            inputs=StageInputs(settings=["palette", "character.ramps"]),
            params=(
                ParamSpec(
                    name="colors",
                    type="int",
                    description="How many Project palette colours the character uses, across all its frames. With `parts`, "
                                "this counts only the materials in no part.",
                    default=16,
                    minimum=1,
                ),
                ParamSpec(
                    name="parts",
                    type="str",
                    description="The swappable parts, comma-separated, each one of render's materials or several joined by "
                                "`+`, each with a ramp of palette colours of its own, dark to light, that no other part, "
                                "fixed colour or outline uses; `name=materials` names a part apart from its materials; "
                                "`name:n` sets a part's ramp length (render's `bands` when unset). For example "
                                "skin,hair,jacket+hood,jeans,boots or skin:4,hair. With the Project's ramp table "
                                "([[character.ramps]]) each part is a part of the table, which gives its length, its row and "
                                "maybe its colours, such as skin,hair,top=jacket+hood. Empty: one palette for all. Unset on "
                                "a generated Model: the parts its generator names.",
                    default="",
                ),
                ParamSpec(
                    name="part_lines",
                    type="bool",
                    description="With `parts`, each part's ramp has one more colour, its first, kept for the inner lines "
                                "(finish's inner_lines=dark) and never used in the frames, so the game's swap recolours the "
                                "lines with the part. With the Project's ramp table, the table's length counts that colour.",
                    default=False,
                ),
                *PALETTE_PARAMS,
            ),
            generated_params=palette_generated_params("render"),
            checks=(
                CheckSpec(code="palette.off_palette", description="Every pixel is a palette colour."),
                CheckSpec(code="palette.ramp_shared", description="No colour is in two parts' ramps, and no pixel of one "
                                                                  "part is in another part's ramp."),
            ),
            run=run_character_palette,
            check=check_character_palette,
            available_from="M3",
        ),
        StageSpec(
            name="finish",
            description="Outline after mapping; the normal pass quantised and aligned to the colour frames.",
            version=2,  # finish.json gains `line_depth` (ticket 0247)
            inputs=StageInputs(upstream=["palette", "render"], settings=["palette"]),
            params=(
                ParamSpec(name="outline", type="bool", description="Draw a 1 px outline round the silhouette.", default=True),
                ParamSpec(name="outline_colour", type="int", minimum=0, default=0,
                          description="The outline's colour: an index into the Project palette."),
                ParamSpec(name="placement", type="choice", choices=["outside", "edge"], default="outside",
                          description="outside: the outline is the pixels around the silhouette, which keeps its own "
                                      "(none where it touches the frame's edge); edge: it is the silhouette's edge pixels."),
                ParamSpec(name="normal_levels", type="int", minimum=1, maximum=256, default=8,
                          description="The normal pass keeps this many values per axis."),
                ParamSpec(name="watch_parts", type="str", default="",
                          description="sheet.part_vanishes watches these materials, comma-separated by name; all when empty."),
                ParamSpec(name="part_min_pixels", type="int", minimum=1, default=1,
                          description="A material with fewer pixels than this in a frame counts as missing from it."),
                ParamSpec(name="eyes", type="choice", choices=["render", "stamp", "pupils"], default="render",
                          description="render: the eyes are the render's pixels. stamp: they are painted over with a small "
                                      "fixed pattern, a pupil and a white, that sits on whole pixels and moves only when "
                                      "the head does (render's `eyes` parameter must name the eye materials); a clip's "
                                      "`blink` frames get closed eyes. pupils: the same without the whites."),
                ParamSpec(name="eye_colour", type="int", minimum=-1, default=-1,
                          description="The pupil's colour: an index into the Project palette; -1: the colour most of the "
                                      "rendered eyes' pixels have."),
                ParamSpec(name="eye_white", type="int", minimum=-1, default=-1,
                          description="The white's colour: an index into the Project palette; -1: its lightest colour."),
                ParamSpec(name="eye_gap", type="int", minimum=-3, maximum=4, default=0,
                          description="With stamped eyes: px added to the gap between the two eyes (negative takes them "
                                      "away; the gap stays at least 1). The pair stays centred where the Model's eyes are. "
                                      "Front views only: a face turned to a side keeps the Model's gap."),
                ParamSpec(name="inner_lines", type="choice", choices=["off", "outline", "dark"], default="off",
                          description="A 1 px line at the borders between the Model's materials, on the farther pixel of "
                                      "each border, after the eyes and before the outline. outline: in the outline's colour; "
                                      "dark: in a darker palette colour of the part it is drawn on (not with palette `parts`)."),
                ParamSpec(name="line_skip", type="str", default="",
                          description="Which borders get no inner line, comma-separated by material name: a+b is the border "
                                      "between two materials, a single name every border of that material, such as "
                                      "dragon+tee,sole+shoes."),
                ParamSpec(name="line_depth", type="float", minimum=0.0, default=0.0,
                          description="With inner_lines: also a line inside one material where the depth steps by more than "
                                      "this many px of the render's scale (so it means the same at any height), on the "
                                      "farther pixel, in the material's line colour. 0 is off. line_skip's single names skip "
                                      "a material's depth lines too."),
                ParamSpec(name="line_darkness", type="float", minimum=0.0, maximum=1.0, default=0.55,
                          description="With inner_lines=dark: how much darker than the part's dark colour the line is, "
                                      "0 to 1 (a share of its light)."),
            ),
            checks=(
                CheckSpec(code="normal.size_mismatch", description="Normal map size equals the colour frame's."),
                CheckSpec(code="palette.off_palette", description="Every colour pixel, outline included, is a Project palette colour."),
                CheckSpec(code="sheet.part_vanishes", description="A material seen in most frames of a clip and direction "
                                                                  "isn't missing from some (a warning)."),
                CheckSpec(code="sheet.eyes_covered", description="Both eyes of a front view are hidden behind another "
                                                                 "material in most frames, such as a hat brim (a warning)."),
            ),
            run=run_character_finish,
            check=check_character_finish,
            available_from="M3",
        ),
        StageSpec(
            name="sheet",
            description="Packs frames into colour, normal and depth atlases with a fixed pivot per frame.",
            version=2,  # depth.png, and `files.depth` in sheet.json (ticket 0296)
            inputs=StageInputs(upstream=["finish", "clips", "render"]),
            checks=(
                CheckSpec(code="sheet.pivot_drift", description="The feet don't move in a stationary clip."),
                CheckSpec(code="sheet.frame_overflow", description="Every frame fits its cell."),
                CheckSpec(code="sheet.frame_count", description="Frame counts match the clip."),
                CheckSpec(code="sheet.empty_frame", description="No frame is empty."),
            ),
            run=run_body_sheet,
            check=check_character_sheet,
            available_from="M3",
        ),
        StageSpec(
            name="export",
            description="SpriteFrames, a CanvasTexture with the normal map, and an AnimatedSprite2D scene.",
            inputs=StageInputs(upstream=["sheet", "palette", "clips"], settings=["export.godot"]),
            checks=(CheckSpec(code="export.no_target", description="The export target is set."),),
            output_root="out",
            available_from="M3",
            run=run_character_export,
            needs_input=export_needs_input,
            check=check_character_export,
        ),
    ),
)
