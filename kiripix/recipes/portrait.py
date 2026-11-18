"""The portrait Recipe (spec §6.7, tickets 0240-0243): a character's dialogue portraits, one image per emotion.

One Asset is one character's set. The picked Source is the **neutral** image, whose ID in the set is `neutral` (`NEUTRAL`).
Every other member is an **emotion**, declared on the `source` Stage by an `emotion` Decision (an ID), which gets its Variants
with `import --emotion` (stored in `src/emotions/<folder>/`) and its image with `pick --emotion`. An emotion is made as an
edit of the neutral image, so its Pick records the neutral Source it was made on (`source`, as a Look's does): a new neutral
Source puts every emotion's Pick in needs-input ("the edit was made on another Source").

An emotion's ID is its name in the game, frozen at its first export (ADR 0003). `emotion_remove` and `emotion_rename` change
it before that; `apply_edits` replays them (`StageSpec.decisions_view`), as a Prop's state edits are, and a rename keeps the
folder the Variants were imported into (`folder`). The image Stages after `source` are `portrait_set` (0243); `export` is 0244: `<id>.png` for each
emotion (and `neutral.png`) and `portrait.json`.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from PIL import Image

from kiripix.checks import Finding, Position
from kiripix.recipes.base import (
    PICK,
    CheckSpec,
    CurrentDecision,
    DecisionSpec,
    KindSpec,
    NeedsInput,
    ParamSpec,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
)
from kiripix.recipes.common import run_source, source_needs_input
from kiripix.recipes.portrait_set import (  # noqa: F401 (the names are this module's too)
    EMOTIONS_OUT,
    FINISH,
    FIT,
    NEUTRAL,
    STAGES,
    ids_of,
    image_file,
    read_record,
)
from kiripix.recipes.prop import NO_TARGET, export_needs_input

SOURCE_STAGE = "source"
BRIEF_STAGE = "brief"
EMOTIONS_DIR = "src/emotions"  # an emotion's Variants: `src/emotions/<folder>/<hash>.png`
EMOTIONS_RECORD = "emotions.json"
BRIEF_SCHEMA_VERSION = 1  # 1: width, height, anchor and fallback (ticket 0242)
PORTRAIT_FILE = "portrait.json"  # the export Stage's record; its images are `<id>.png` beside it
PORTRAIT_SCHEMA_VERSION = 1  # 1: asset, canvas, anchor, fallback, emotions (ticket 0244)
EMOTIONS_SCHEMA_VERSION = 1  # 1: `neutral` and `emotions`, the IDs in declaration order (ticket 0242)
EMOTION_ID = "^[a-z][a-z0-9]*(_[a-z0-9]+)*$"  # snake_case

_ID: dict[str, Any] = {"type": "string", "pattern": EMOTION_ID}

EMOTION = DecisionSpec(
    name="emotion",
    description="Declare an emotion of the portrait set (`happy`): `id` is its name in the game, lower-case snake_case, "
                f"unique among the set's emotions and never `{NEUTRAL}` (the picked Source's), frozen at its first export. "
                "Import its image, an edit of the neutral one, with `kiripix import <asset> <png> --emotion <id>` and pick it "
                "with `kiripix pick <asset> <variant> --emotion <id>`.",
    entry_schema={"type": "object", "properties": {"id": _ID}, "required": ["id"], "additionalProperties": False},
)

EMOTION_REMOVE = DecisionSpec(
    name="emotion_remove",
    description="Take an emotion away: it and every Decision before this one that names it stop applying (its imported "
                "Variants stay in `src/emotions/`). Refused for an emotion the game's Manifest lists (its ID is frozen). Undo "
                "brings it back.",
    entry_schema={"type": "object", "properties": {"id": _ID}, "required": ["id"], "additionalProperties": False},
)

EMOTION_RENAME = DecisionSpec(
    name="emotion_rename",
    description="Give an emotion another ID, `to` (free among the set's emotions, and not `neutral`). Refused for an emotion "
                "the game's Manifest lists (its ID is frozen). Undo brings the old ID back.",
    entry_schema={"type": "object", "properties": {"id": _ID, "to": _ID}, "required": ["id", "to"],
                  "additionalProperties": False},
)

EMOTION_PICK = DecisionSpec(
    name="emotion_pick",
    description="Choose one Variant (`src/emotions/<emotion>/<variant>.png`) as an emotion's image. `source` is the neutral "
                "Source (its Variant name) the edit was made on: a Pick whose `source` isn't the set's current neutral Source "
                "doesn't apply (needs-input), because an edit of the old picture must never be mixed with the new one. "
                "`kiripix pick <asset> <variant> --emotion <id>` records it with the right `source`.",
    entry_schema={"type": "object",
                  "properties": {"emotion": _ID, "variant": {"type": "string"}, "source": {"type": "string"}},
                  "required": ["emotion", "variant", "source"], "additionalProperties": False},
)

DECISIONS = (EMOTION, EMOTION_REMOVE, EMOTION_RENAME, EMOTION_PICK)
EDITS = (EMOTION_REMOVE.name, EMOTION_RENAME.name)

CHECKS = (
    CheckSpec(code="portrait.emotion_unknown", description="Every emotion a Variant or Pick names is declared (an `emotion` "
                                                           "Decision)."),
    CheckSpec(code="portrait.emotion_unpicked", description="Every declared emotion has an image picked on the current neutral "
                                                            "Source (needs-input)."),
    CheckSpec(code="portrait.emotion_duplicate", description="An emotion's ID is its set's only once, and isn't `neutral`."),
    CheckSpec(code="portrait.fallback_unknown", description="The brief's fallback emotion is `neutral` or a declared emotion."),
)


@dataclass(frozen=True)
class DeclaredEmotion:
    """A declared emotion as the Stage reads it: its ID, and the folder under `src/emotions/` holding its Variants."""

    id: str
    folder: str


def _key(decision: CurrentDecision) -> str | None:
    value = decision.data.get("id" if decision.name in (EMOTION.name, EMOTION_REMOVE.name, EMOTION_RENAME.name) else "emotion")
    return value if isinstance(value, str) else None


def apply_edits(decisions: tuple[CurrentDecision, ...]) -> tuple[CurrentDecision, ...]:
    """The Decisions with each `emotion_remove` and `emotion_rename` replayed in order (`StageSpec.decisions_view`): a remove
    drops the emotion's earlier Decisions, a rename gives them the new ID, and neither is in the result. A renamed `emotion`
    keeps its Variants' folder under `folder`."""
    kept: list[CurrentDecision] = []
    for decision in decisions:
        if decision.name == EMOTION_REMOVE.name:
            kept = [d for d in kept if _key(d) != decision.data["id"]]
        elif decision.name == EMOTION_RENAME.name:
            old, new = decision.data["id"], decision.data["to"]
            renamed: list[CurrentDecision] = []
            for d in kept:
                if _key(d) != old:
                    renamed.append(d)
                elif d.name == EMOTION.name:
                    renamed.append(replace(d, data={**d.data, "id": new, "folder": d.data.get("folder", old)}))
                else:
                    renamed.append(replace(d, data={**d.data, "emotion": new}))
            kept = renamed
        else:
            kept.append(decision)
    return tuple(kept)


def declared_emotions(decisions: tuple[CurrentDecision, ...]) -> dict[str, DeclaredEmotion]:
    """The set's declared emotions by ID, in declaration order, from Decisions as the Stage reads them."""
    found: dict[str, DeclaredEmotion] = {}
    for d in decisions:
        if d.name == EMOTION.name:
            found.setdefault(str(d.data["id"]), DeclaredEmotion(str(d.data["id"]), str(d.data.get("folder", d.data["id"]))))
    return found


def duplicate_emotions(decisions: tuple[CurrentDecision, ...]) -> list[str]:
    """The IDs declared more than once, or declared as `neutral`, sorted."""
    seen: set[str] = set()
    found: set[str] = set()
    for d in decisions:
        if d.name == EMOTION.name:
            one = str(d.data["id"])
            if one in seen or one == NEUTRAL:
                found.add(one)
            seen.add(one)
    return sorted(found)


def emotion_picks(decisions: tuple[CurrentDecision, ...]) -> dict[str, tuple[str, str]]:
    """Each emotion's current Pick as (Variant, the neutral Source it was made on); the latest Pick of an emotion counts."""
    return {str(d.data["emotion"]): (str(d.data["variant"]), str(d.data["source"]))
            for d in decisions if d.name == EMOTION_PICK.name}


def neutral_source(decisions: tuple[CurrentDecision, ...]) -> str | None:
    """The Variant the neutral Pick names; None without a Pick."""
    picks = [d for d in decisions if d.name == PICK.name]
    return str(picks[-1].data["variant"]) if picks else None


def top_files(run: StageRun) -> StageRun:
    """The run as the neutral Source reads it: `src/<hash>.png` only, not an emotion's Variants."""
    return replace(run, files={n: p for n, p in run.files.items() if not n.startswith(EMOTIONS_DIR + "/")})


def emotion_files(files: dict[str, Path]) -> dict[str, dict[str, Path]]:
    """The Variants of each folder of `src/emotions/`, by Variant name."""
    found: dict[str, dict[str, Path]] = {}
    for name, path in files.items():
        parts = name.split("/")
        if len(parts) == 4 and name.startswith(EMOTIONS_DIR + "/"):
            found.setdefault(parts[2], {})[Path(parts[3]).stem] = path
    return found


def declare_command(asset: str, emotion: str) -> str:
    """The `decide` that declares an emotion."""
    entry = json.dumps({"decision": EMOTION.name, "data": {"id": emotion}})
    return f"kiripix decide {asset} {SOURCE_STAGE} --decision '{entry}'"


def emotion_needs_input(run: StageRun) -> NeedsInput | None:
    """Why a declared emotion holds the `source` Stage back: its ID is taken, it has no image picked, its picked Variant is
    gone, or the image was made on another neutral Source."""
    declared = declared_emotions(run.decisions)
    if (taken := duplicate_emotions(run.decisions)):
        return NeedsInput(f"the emotion {taken[0]} is declared twice, or is `{NEUTRAL}`", code="portrait.emotion_duplicate",
                          owner_action=f"Rename or remove the extra emotion (kiripix decide {run.asset_id} {SOURCE_STAGE} "
                                       "--decision with an emotion_rename or emotion_remove).")
    if not declared:
        return None
    source = neutral_source(run.decisions)
    picks, files = emotion_picks(run.decisions), emotion_files(run.files)
    other = [e for e in declared if e in picks and picks[e][1] != source]
    if other:
        remake = "; ".join(f"kiripix import {run.asset_id} <png> --emotion {e}, then kiripix pick {run.asset_id} "
                           f"<variant> --emotion {e}" for e in other)
        return NeedsInput("the edit was made on another Source", code="portrait.emotion_unpicked",
                          data={"emotion": other[0], "emotions": other},
                          owner_action=f"Re-make the emotion {', '.join(other)} from the new neutral Source ({remake}).")
    for emotion in declared.values():
        found = sorted(files.get(emotion.folder, {}))
        chosen = picks.get(emotion.id)
        if chosen is not None and chosen[0] in found:
            continue
        reason = (f"no image is picked for the emotion {emotion.id}" if chosen is None
                  else f"the picked Variant {chosen[0]} of the emotion {emotion.id} was deleted")
        if not found:
            return NeedsInput(reason, code="portrait.emotion_unpicked", data={"emotion": emotion.id},
                              owner_action=f"Make the emotion {emotion.id} as an edit of the neutral image and import it "
                                           f"(kiripix import {run.asset_id} <png> --emotion {emotion.id}), then pick it "
                                           f"(kiripix pick {run.asset_id} <variant> --emotion {emotion.id}).")
        if len(found) == 1:  # a lone Variant is no choice: an agent may pick it
            return NeedsInput(reason, code="portrait.emotion_unpicked", data={"emotion": emotion.id},
                              command=f"kiripix pick {run.asset_id} {found[0]} --emotion {emotion.id}")
        return NeedsInput(reason, code="portrait.emotion_unpicked", data={"emotion": emotion.id},
                          owner_action=f"Pick one of the Variants {', '.join(found)}: "
                                       f"kiripix pick {run.asset_id} <variant> --emotion {emotion.id}")
    return None


def edit_problems(asset: str, decisions: tuple[CurrentDecision, ...], documents: list[tuple[str, dict[str, Any]]]
                  ) -> tuple[list[Finding], list[str]]:
    """What refuses an emotion Decision before it is recorded, in order: `decisions` are the `source` Decisions as the Stage
    reads them. Also gives the emotions removed or renamed, for the ID freeze (which only the Manifest knows)."""
    where = Position(asset=asset, stage=SOURCE_STAGE)
    emotions = set(declared_emotions(decisions))
    found: list[Finding] = []
    edited: list[str] = []
    for name, data in documents:
        if name == EMOTION.name and isinstance(data.get("id"), str):
            new = str(data["id"])
            if new == NEUTRAL or new in emotions:
                found.append(Finding(
                    code="portrait.emotion_duplicate",
                    message=f"{asset} has an emotion {new} already" if new in emotions else
                            f"{new} is the neutral image's ID, so it isn't an emotion",
                    position=where, owner_action=f"Give the emotion an ID the set doesn't have (not {NEUTRAL}, not "
                                                 f"{', '.join(sorted(emotions)) or 'a declared one'})."))
            emotions.add(new)
        elif name in (EMOTION_REMOVE.name, EMOTION_RENAME.name, EMOTION_PICK.name):
            emotion = data.get("id" if name != EMOTION_PICK.name else "emotion")
            if not isinstance(emotion, str):
                continue  # the Decision's schema refuses it
            if emotion not in emotions:
                found.append(Finding(
                    code="portrait.emotion_unknown", message=f"{asset} has no emotion {emotion}"
                    + (f"; its emotions are {', '.join(sorted(emotions))}" if emotions else ""), position=where,
                    fix=declare_command(asset, emotion) if name == EMOTION_PICK.name else None,
                    owner_action=None if name == EMOTION_PICK.name else "Declare it first, or use one of its emotions."))
                continue
            if name == EMOTION_PICK.name:
                continue
            edited.append(emotion)
            emotions.discard(emotion)
            if name == EMOTION_RENAME.name:
                new = str(data.get("to"))
                if new == emotion:
                    found.append(Finding(code="portrait.emotion_duplicate", message=f"the emotion {emotion} is renamed to its "
                                         "own ID", position=where, owner_action="Give the emotion another ID, or leave it."))
                elif new == NEUTRAL or new in emotions:
                    found.append(Finding(
                        code="portrait.emotion_duplicate",
                        message=f"{asset} has an emotion {new} already" if new in emotions else
                                f"{new} is the neutral image's ID, so it isn't an emotion",
                        position=where, owner_action=f"Rename {emotion} to an ID the set doesn't have."))
                emotions.add(new)
    return found, edited


# brief: the canvas (the Project's `[portrait] canvas` unless set), the anchor, the fallback emotion


def _canvas(run: StageRun) -> tuple[int, int]:
    width, height = int(run.params["width"]), int(run.params["height"])
    canvas = run.settings["portrait.canvas"]
    return (width or int(canvas[0]), height or int(canvas[1]))


def _anchor(run: StageRun, canvas: tuple[int, int]) -> tuple[int, int]:
    """The anchor: the brief's, else the Project's, else the canvas's bottom centre."""
    x, y = int(run.params["anchor_x"]), int(run.params["anchor_y"])
    project = run.settings["portrait.anchor"]
    return (x if x >= 0 else int(project[0]) if project else canvas[0] // 2,
            y if y >= 0 else int(project[1]) if project else canvas[1] - 1)


def _brief(run: StageRun) -> None:
    width, height = _canvas(run)
    anchor = _anchor(run, (width, height))
    brief = {"schema_version": BRIEF_SCHEMA_VERSION, "width": width, "height": height, "anchor": list(anchor),
             "fallback": str(run.params["fallback"])}
    (run.output_dir / "brief.json").write_text(json.dumps(brief, indent=2) + "\n", encoding="utf-8")


def _check_brief(run: StageRun) -> list[Finding]:
    brief = json.loads((run.output_dir / "brief.json").read_text(encoding="utf-8"))
    width, height = int(brief["width"]), int(brief["height"])
    anchor_x, anchor_y = (int(v) for v in brief["anchor"])
    limit_width, limit_height = (int(v) for v in run.settings["project.resolution"])
    findings: list[Finding] = []
    if width > limit_width or height > limit_height:
        findings.append(Finding(
            code="brief.larger_than_resolution",
            message=f"the portrait's canvas {width}x{height} is larger than the project's resolution "
                    f"{limit_width}x{limit_height}",
            position=Position(asset=run.asset_id, stage="brief", field="stages.brief.width" if width > limit_width
                              else "stages.brief.height"),
            fix=f"kiripix set {run.asset_id} brief width={min(width, limit_width)} height={min(height, limit_height)}"))
    if not (0 <= anchor_x < width and 0 <= anchor_y < height):
        findings.append(Finding(
            code="brief.anchor_outside",
            message=f"the anchor ({anchor_x}, {anchor_y}) is not a pixel of the {width}x{height} canvas",
            position=Position(asset=run.asset_id, stage="brief", field="stages.brief.anchor_x"),
            fix=f"kiripix set {run.asset_id} brief anchor_x={width // 2} anchor_y={height - 1}"))
    fallback = str(brief["fallback"])
    if not re.fullmatch(EMOTION_ID, fallback):
        findings.append(Finding(
            code="brief.fallback_invalid", message=f"the fallback emotion {fallback!r} isn't lower-case snake_case",
            position=Position(asset=run.asset_id, stage="brief", field="stages.brief.fallback"),
            fix=f"kiripix set {run.asset_id} brief fallback={NEUTRAL}"))
    return findings


# source: the neutral Source from `src/<hash>.png`, and each declared emotion's picked image under `emotions/<id>.png`


def _source(run: StageRun) -> None:
    run_source(top_files(run))
    picks, files = emotion_picks(run.decisions), emotion_files(run.files)
    declared = declared_emotions(run.decisions)
    if declared:
        (run.output_dir / EMOTIONS_OUT).mkdir()
    for emotion in declared.values():
        chosen = picks[emotion.id][0]  # `emotion_needs_input` holds the Stage back until each has one
        path = files[emotion.folder][chosen]
        if not hashlib.sha256(path.read_bytes()).hexdigest().startswith(chosen):
            raise StageFailure(f"the Variant {path.name} of the emotion {emotion.id} was changed after it was imported, and "
                               "Variants are immutable; import the changed image as a new Variant and pick that")
        shutil.copyfile(path, run.output_dir / EMOTIONS_OUT / f"{emotion.id}.png")
    record = {"schema_version": EMOTIONS_SCHEMA_VERSION, "neutral": NEUTRAL, "emotions": list(declared)}
    (run.output_dir / EMOTIONS_RECORD).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _source_needs_input(run: StageRun) -> NeedsInput | None:
    return source_needs_input(top_files(run)) or emotion_needs_input(run)


def _check_source(run: StageRun) -> list[Finding]:
    where = Position(asset=run.asset_id, stage=SOURCE_STAGE)
    declared = set(declared_emotions(run.decisions))
    findings = [Finding(code="portrait.emotion_unknown", message=f"{run.asset_id} has no emotion {emotion}", position=where,
                        fix=declare_command(run.asset_id, emotion))
                for emotion in sorted(set(emotion_picks(run.decisions)) - declared)]
    brief = json.loads((run.upstream[BRIEF_STAGE] / "brief.json").read_text(encoding="utf-8"))
    fallback = str(brief["fallback"])
    if fallback != NEUTRAL and fallback not in declared and re.fullmatch(EMOTION_ID, fallback):
        findings.append(Finding(
            code="portrait.fallback_unknown", message=f"the fallback emotion {fallback} is neither {NEUTRAL} nor an emotion "
                                                      f"of {run.asset_id}",
            position=Position(asset=run.asset_id, stage=BRIEF_STAGE, field="stages.brief.fallback"),
            fix=f"kiripix set {run.asset_id} brief fallback={NEUTRAL}"))
    return findings


def _export(run: StageRun) -> None:
    """What the game gets: the finished images as `<id>.png` (the neutral's is `neutral.png`) and `portrait.json`. No scene:
    the game's portrait UI loads the PNGs."""
    brief = json.loads((run.upstream[BRIEF_STAGE] / "brief.json").read_text(encoding="utf-8"))
    ids = [NEUTRAL, *ids_of(run.upstream[FINISH], FINISH)]
    for one in ids:
        shutil.copyfile(image_file(run.upstream[FINISH], FINISH, one), run.output_dir / f"{one}.png")
    record = {"schema_version": PORTRAIT_SCHEMA_VERSION, "asset": run.asset_id, "canvas": [brief["width"], brief["height"]],
              "anchor": brief["anchor"], "fallback": brief["fallback"],
              "emotions": [{"id": one, "file": f"{one}.png"} for one in ids]}
    (run.output_dir / PORTRAIT_FILE).write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


def _check_export(run: StageRun) -> list[Finding]:
    """`export.no_target`; every image the canvas's size with binary alpha, on the Grid's anchor (`export.portrait_canvas`);
    the fallback an emotion of the set."""
    where = Position(asset=run.asset_id, stage="export")
    findings: list[Finding] = []
    if not run.settings["export.godot"].get("project"):
        findings.append(Finding(code="export.no_target", message="no Godot project to export into", position=where,
                                owner_action=NO_TARGET))
    record = json.loads((run.output_dir / PORTRAIT_FILE).read_text(encoding="utf-8"))
    width, height = (int(v) for v in record["canvas"])
    figure = read_record(run.upstream[FIT], FIT, run.asset_id)["figure"]
    anchor_x, anchor_y = (int(v) for v in record["anchor"])
    if figure and (abs(float(figure["centre_x"]) - anchor_x) > 1 or abs(int(figure["foot_y"]) - anchor_y) > 1):
        findings.append(Finding(
            code="export.portrait_canvas", severity="warning", position=where,
            message=f"the neutral figure stands with its centre at x {figure['centre_x']:g} and its foot at y "
                    f"{figure['foot_y']}, more than a pixel off the anchor ({anchor_x}, {anchor_y}): the crop offset is "
                    "set, or the source image ends before the figure can reach the anchor",
            owner_action=f"Nothing is needed if the offset is meant. Otherwise let `fit` place the figure (kiripix set "
                         f"{run.asset_id} fit offset_x=-1 offset_y=-1), or move the anchor (kiripix set {run.asset_id} brief "
                         f"anchor_x=.. anchor_y=..)."))
    ids = [str(e["id"]) for e in record["emotions"]]
    for one in ids:
        with Image.open(run.output_dir / f"{one}.png") as opened:
            rgba = opened.convert("RGBA")
        if rgba.size != (width, height):
            findings.append(Finding(
                code="export.portrait_canvas", position=where,
                message=f"{one}.png is {rgba.size[0]}x{rgba.size[1]}, not the canvas {width}x{height}",
                fix=f"kiripix run {run.asset_id} fit --force"))
        if sum(rgba.getchannel("A").histogram()[1:255]):
            findings.append(Finding(code="image.partial_alpha", position=where,
                                    message=f"{one}.png has partly transparent pixels: a portrait's alpha is binary",
                                    fix=f"kiripix run {run.asset_id} finish --force"))
    if str(record["fallback"]) not in ids:
        findings.append(Finding(
            code="portrait.fallback_unknown", position=where,
            message=f"the fallback emotion {record['fallback']} is not in the set ({', '.join(ids)})",
            fix=f"kiripix set {run.asset_id} brief fallback={NEUTRAL}"))
    return findings


PORTRAIT = KindSpec(
    name="portrait",
    description="A character's dialogue portraits: a neutral image and an emotion for each mood, all on one canvas with "
                "one anchor, so an emotion swap never moves the body.",
    stages=chain(
        StageSpec(
            name="brief",
            description="The canvas (the Project's `[portrait] canvas` unless set), the anchor (a pixel of the canvas; the "
                        "bottom centre by default) and the fallback emotion.",
            params=(
                ParamSpec(name="width", type="int", default=0, minimum=0,
                          description="The canvas's width in px. 0 takes the Project's `[portrait] canvas`."),
                ParamSpec(name="height", type="int", default=0, minimum=0,
                          description="The canvas's height in px. 0 takes the Project's `[portrait] canvas`."),
                ParamSpec(name="anchor_x", type="int", default=-1, minimum=-1,
                          description="The anchor's x, a canvas pixel. -1 takes the Project's `[portrait] anchor`, else the "
                                      "bottom centre."),
                ParamSpec(name="anchor_y", type="int", default=-1, minimum=-1,
                          description="The anchor's y, a canvas pixel. -1 takes the Project's `[portrait] anchor`, else the "
                                      "bottom centre."),
                ParamSpec(name="fallback", type="str", default=NEUTRAL,
                          description=f"The emotion the game shows for one it doesn't know: `{NEUTRAL}` or a declared emotion."),
            ),
            inputs=StageInputs(settings=["portrait.canvas", "portrait.anchor", "project.resolution"]),
            checks=(CheckSpec(code="brief.larger_than_resolution",
                              description="The canvas is no larger than the project's resolution."),
                    CheckSpec(code="brief.anchor_outside", description="The anchor is a pixel of the canvas."),
                    CheckSpec(code="brief.fallback_invalid", description="The fallback emotion is lower-case snake_case.")),
            owner_input="Writes the brief.",
            available_from="M5",
            version=2,  # 2: brief.json carries schema_version
            run=_brief,
            check=_check_brief,
        ),
        StageSpec(
            name="source",
            description="The neutral image (a Pick) and each emotion's image, an edit of it, picked on the neutral Source "
                        "it was made on.",
            inputs=StageInputs(files=["src/*.png", f"{EMOTIONS_DIR}/**/*.png"]),
            decisions=(PICK, *DECISIONS),
            checks=(CheckSpec(code="source.not_picked", description="A neutral Source has been picked."), *CHECKS),
            owner_input="Picks the neutral image, declares the emotions, imports and picks each one's image.",
            available_from="M5",
            image="source.png",
            run=_source,
            needs_input=_source_needs_input,
            check=_check_source,
            decisions_view=apply_edits,
        ),
        *STAGES,
        StageSpec(
            name="export",
            description="Builds what the game gets: `<id>.png` for the neutral and each emotion, and `portrait.json`. "
                        "`kiripix export` then writes them under the export root's `portraits/<name>/`.",
            version=2,  # 2: the Stage writes the images and `portrait.json` (ticket 0244); it was a stub
            inputs=StageInputs(upstream=[FINISH, FIT, BRIEF_STAGE], settings=["export.godot"]),
            checks=(CheckSpec(code="export.no_target", description="The export target is set."),
                    CheckSpec(code="export.portrait_canvas",
                              description="Every image is the canvas's size, on the same anchor."),
                    CheckSpec(code="image.partial_alpha", description="Alpha is binary."),
                    CheckSpec(code="portrait.fallback_unknown", description="The fallback names an emotion of the set.")),
            output_root="out",
            available_from="M5",
            run=_export,
            needs_input=export_needs_input,
            check=_check_export,
        ),
    ),
)
