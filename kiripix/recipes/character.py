"""The character Recipe (spec §6.3): model, rig, clips, render, palette, finish, sheet, export."""

import json
from pathlib import Path

from kiripix.checks import Finding, Position
from kiripix.recipes.base import (
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
from kiripix.recipes.character_finish import check_character_finish, run_character_finish
from kiripix.recipes.character_palette import check_character_palette, run_character_palette
from kiripix.recipes.character_sheet import check_character_sheet, run_character_sheet
from kiripix.recipes.render import FORMAT_SETTING as RENDER_FORMAT_SETTING, run_render
from kiripix.recipes.blender_launcher import launch
from kiripix.recipes.common import picked, source_needs_input, variants
from kiripix.recipes.character_export import check_character_export, export_needs_input, run_character_export
from kiripix.recipes.clips import CLIP, check_clips, clips_needs_input, run_clips
from kiripix.recipes.rig import BONE, UPLOAD, rig_needs_input, run_rig

MODEL_HEIGHT = 2.0  # the normalised Model's height in Blender units: `render` frames it, so this is only a known size
MODEL_SCHEMA_VERSION = 2  # 2: `vertices` and `upload` (read by the `rig` Stage); `facing`, `ignored` and `fps` are additive keys
STILL = "still.png"  # a 256 px preview of the Model (facing applied) for the UI; nothing below `model` reads it
FACINGS = ["-y", "+y", "-x", "+x"]  # the way the Model faces in the file; `model` turns it to face -Y, toward the camera


def run_model(run: StageRun) -> None:
    """Import the picked Variant in Blender, normalise it, and write `model.blend`, `model.json` and `still.png`."""
    chosen = picked(run)
    assert chosen is not None  # `source_needs_input` holds the Stage back until there is a Pick
    path = variants(run)[chosen]
    run.progress(0, 1, "starting Blender")
    result = launch(run, "normalise_model", {"input": str(path), "output": str(run.output_dir / "model.blend"),
                                             "height": MODEL_HEIGHT, "upload": str(run.output_dir / UPLOAD),
                                             "facing": str(run.params.get("facing", "-y")),
                                             "still": str(run.output_dir / STILL)})
    if result.get("upload") and not (run.output_dir / UPLOAD).is_file():
        raise StageFailure("Blender finished without writing the file for Mixamo")
    if not (run.output_dir / STILL).is_file():
        raise StageFailure("Blender finished without writing the still of the Model")
    if not (run.output_dir / "model.blend").is_file():
        raise StageFailure("Blender finished without writing the normalised Model")
    document = {"schema_version": MODEL_SCHEMA_VERSION, "source": path.name, **result}
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
    return [
        Finding(
            code="model.unskinned_mesh", severity="warning",
            message=f"the mesh {item['name']} ({item['vertices']} vertices) is not skinned to the armature, so it was "
                    "dropped from the Model (it is left out of the height and bounds and is not rendered)",
            position=Position(asset=run.asset_id, stage="model"),
            owner_action=f"Remove the mesh {item['name']} from {shown} (a bone's custom shape is often "
                         "exported as a mesh), or import the file again with that mesh skinned to the armature.")
        for item in document.get("ignored", [])
    ]


CHARACTER = KindSpec(
    name="character",
    description="A character, NPC or enemy rendered from a 3D Model, so every animation stays on-model.",
    stages=chain(
        StageSpec(
            name="model",
            description="Imports .glb, .fbx or .blend; normalises scale and the up axis.",
            inputs=StageInputs(files=["src/*"], settings=[BLENDER_VERSION_SETTING], given=[BLENDER_SETTING]),
            params=(ParamSpec(name="facing", type="choice", choices=FACINGS, default="-y",
                              description="The way the Model faces in its file, as Blender sees it from above: -y toward "
                                          "the front view, +y away, -x or +x to a side. The Model is turned to face -y, "
                                          "so the render's `s` direction shows its front."),),
            decisions=(PICK,),
            run=run_model,
            checks=(CheckSpec(code="model.unskinned_mesh",
                              description="Every mesh of a rigged Model is skinned to its armature (a warning)."),),
            check=check_model,
            needs_input=source_needs_input,
            owner_input="Imports a Model (kiripix import <id> <file.glb|.fbx|.blend>) and picks it.",
            available_from="M3",
        ),
        StageSpec(
            name="rig",
            description="Validates a humanoid rig, or guides the Mixamo round trip.",
            inputs=StageInputs(files=["src/rigged/*"], settings=[BLENDER_VERSION_SETTING], given=[BLENDER_SETTING]),
            decisions=(BONE,),
            checks=(
                CheckSpec(code="rig.missing", description="The Model or the rigged file has an armature."),
                CheckSpec(code="rig.bone_missing", description="Hips, spine, head, both arms and both legs have a bone."),
                CheckSpec(code="rig.model_mismatch", description="The rigged file was made from the Model."),
            ),
            run=run_rig,
            needs_input=rig_needs_input,
            owner_input="The Mixamo round trip, when used: kiripix import <id> <rigged.fbx> --role rigged.",
            available_from="M3",
        ),
        StageSpec(
            name="clips",
            description="Maps named clips to animation sources, with frame range, frame rate and loop flag.",
            inputs=StageInputs(files=["src/clips/*"], upstream=["model", "rig"], settings=[BLENDER_VERSION_SETTING],
                               given=[BLENDER_SETTING]),
            decisions=(CLIP,),
            checks=(
                CheckSpec(code="clips.source_missing", description="Each clip's source is an action or a clip-source file."),
                CheckSpec(code="clips.range", description="Each clip's frames are inside its action's."),
                CheckSpec(code="clips.bad_name", description="A clip name is lower-case snake_case with no direction suffix."),
                CheckSpec(code="clips.root_motion", description="No clip moves its root (a warning: the render keeps the feet "
                                                                "at the pivot)."),
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
                               given=[BLENDER_SETTING]),
            params=(
                ParamSpec(
                    name="height",
                    type="int",
                    description="Target height in px; the Project's [character] height when unset.",
                    minimum=1,
                ),
                ParamSpec(
                    name="camera",
                    type="str",
                    description="The camera preset, by name, from [character.camera] in kiripix.toml.",
                    default="top34_8",
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
                    name="eyes",
                    type="str",
                    description="The Model's eye materials, comma-separated, such as eyes or eyes,iris,eyewhite: render then "
                                "also records where each eye is in every frame, for finish to stamp the eyes (eyes=stamp). "
                                "Empty: the eyes are not followed.",
                    default="",
                ),
            ),
            gpu=True,
            run=run_render,
            checks=(CheckSpec(code="render.camera_unknown", description="The camera preset exists in kiripix.toml."),),
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
                                "maybe its colours, such as skin,hair,top=jacket+hood. Empty: one palette for all.",
                    default="",
                ),
                *PALETTE_PARAMS,
            ),
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
            ),
            checks=(
                CheckSpec(code="normal.size_mismatch", description="Normal map size equals the colour frame's."),
                CheckSpec(code="palette.off_palette", description="Every colour pixel, outline included, is a Project palette colour."),
                CheckSpec(code="sheet.part_vanishes", description="A material seen in most frames of a clip and direction "
                                                                  "isn't missing from some (a warning)."),
            ),
            run=run_character_finish,
            check=check_character_finish,
            available_from="M3",
        ),
        StageSpec(
            name="sheet",
            description="Packs frames into an atlas with a fixed pivot per frame.",
            inputs=StageInputs(upstream=["finish", "clips"]),
            checks=(
                CheckSpec(code="sheet.pivot_drift", description="The feet don't move in a stationary clip."),
                CheckSpec(code="sheet.frame_overflow", description="Every frame fits its cell."),
                CheckSpec(code="sheet.frame_count", description="Frame counts match the clip."),
                CheckSpec(code="sheet.empty_frame", description="No frame is empty."),
            ),
            run=run_character_sheet,
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
