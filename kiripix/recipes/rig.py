"""The character's `rig` Stage (spec §6.3, ticket 0102): a humanoid armature with the bones `clips` and `render` need, by
Mixamo's names or a `bone` Decision's mapping, from the Model's own rig or from the file that came back from Mixamo.

Without a rig the Stage is needs-input, with the Mixamo steps and the file Kiripix wrote for upload (the `model` Stage
writes it beside `model.blend`). The rigged file is checked against the Model it was made from, so a rig made from another
Model is caught.

A character made from a base (ADR 0012) carries the base's skeleton in its own Model, so it needs no rigged file and no
Mixamo trip: its armature is compared with the base's `rig.json` by bone names and parents, never by rest proportions, which
a generated Model changes on purpose. Every bone of the base must be there under its exact name (a clip binds by name) with
the same parent; more bones (a skirt's, a hair chain's) are allowed. The base's roles are taken over, so a `bone` Decision made
on the base holds for the character too.
"""

import json
import re
from pathlib import Path
from typing import Any

from kiripix.recipes.base import DecisionSpec, NeedsInput, StageFailure, StageRun
from kiripix.recipes.blender_launcher import launch

# 2: `parents`, each bone's parent (null for a root), and `height`, the rest-pose height of the file that carries the rig, in
# Blender units as imported: both for a character made from this one (ADR 0012)
RIG_SCHEMA_VERSION = 2
MODEL_SCHEMA_VERSION = 2  # the `model.json` this Stage reads
BASE_STAGE = "rig"  # the base's Stage whose built `rig.json` a character made from it is compared with
UPLOAD = "mixamo_upload.fbx"  # beside the `model` Stage's `model.blend`
RIGGED_PREFIX = "src/rigged/"
VERTEX_TOLERANCE = 0.01  # of the Model's distinct points: a round trip may weld or split a few
PROPORTION_TOLERANCE = 0.05  # of the longest side, per side

# The roles `clips` and `render` need, each with the bone names it goes by once a rig's name is reduced to letters and
# digits in lower case with Mixamo's `mixamorig:` prefix gone. The feet are asked for, not required: they give the pivot
# a second look when the root bone isn't at the ground.
REQUIRED = {
    "hips": ("hips", "pelvis"),
    "spine": ("spine",),
    "head": ("head",),
    "left_arm": ("leftarm", "leftupperarm"),
    "right_arm": ("rightarm", "rightupperarm"),
    "left_leg": ("leftupleg", "leftupperleg", "leftthigh"),
    "right_leg": ("rightupleg", "rightupperleg", "rightthigh"),
}
OPTIONAL = {
    "left_foot": ("leftfoot",),
    "right_foot": ("rightfoot",),
}
ROLES = [*REQUIRED, *OPTIONAL]

BONE = DecisionSpec(
    name="bone",
    description="Map a role to a bone of the rig, for a rig that doesn't use Mixamo's names. The latest mapping of a role "
                "wins.",
    entry_schema={
        "type": "object",
        "properties": {"role": {"enum": ROLES}, "bone": {"type": "string", "minLength": 1}},
        "required": ["role", "bone"],
        "additionalProperties": False,
    },
)


def _plain(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.split(":")[-1].lower())


def map_bones(bones: list[str], chosen: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """The bone of each role, and the required roles with none. `chosen` is the Owner's mapping, which wins over the
    names; a role mapped to a bone the rig lacks stays missing."""
    plain: dict[str, str] = {}
    for bone in bones:
        plain.setdefault(_plain(bone), bone)
    mapping: dict[str, str] = {}
    for role, names in {**REQUIRED, **OPTIONAL}.items():
        if role in chosen:
            if chosen[role] in bones:
                mapping[role] = chosen[role]
            continue
        found = next((plain[n] for n in names if n in plain), None)
        if found is not None:
            mapping[role] = found
    return mapping, [role for role in REQUIRED if role not in mapping]


def chosen_bones(run: StageRun) -> dict[str, str]:
    return {str(d.data["role"]): str(d.data["bone"]) for d in run.decisions if d.name == BONE.name}


def rigged_file(run: StageRun) -> Path | None:
    found = sorted(path for name, path in run.files.items() if name.startswith(RIGGED_PREFIX))
    return found[-1] if found else None


def read_model(run: StageRun) -> dict[str, Any] | None:
    path = run.upstream["model"] / "model.json"
    if not path.is_file():
        return None
    document: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return document


def _shown(run: StageRun, path: Path) -> str:
    try:
        return path.relative_to(run.asset_dir.parent.parent.parent).as_posix()
    except ValueError:
        return path.as_posix()


def mixamo_steps(run: StageRun) -> str:
    upload = _shown(run, run.upstream["model"] / UPLOAD)
    return (
        f"Rig the Model with Mixamo (https://www.mixamo.com, a free Adobe account). 1. Upload {upload}, which Kiripix wrote "
        "from the normalised Model. 2. Place the markers on chin, wrists, elbows, knees and groin, and choose the "
        "Standard Skeleton (65 bones) with symmetry on. 3. Download with Format FBX Binary (.fbx), Pose T-pose and "
        "With Skin; no animation is needed here. 4. Add the file: "
        f"kiripix import {run.asset_id} <downloaded.fbx> --role rigged"
    )


def base_rig(run: StageRun) -> dict[str, Any] | None:
    """The base's `rig.json`, for a character made from a base; None without a base or when it can't be read."""
    if run.base is None:
        return None
    try:
        document: dict[str, Any] = json.loads((run.base.built[BASE_STAGE] / "rig.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document


def _base_rig_is_old(run: StageRun) -> NeedsInput | None:
    """A base whose `rig.json` was built before it recorded the bones' parents has to build it again first."""
    if run.base is None:
        return None
    theirs = base_rig(run)
    if (theirs is not None and theirs.get("schema_version") == RIG_SCHEMA_VERSION and isinstance(theirs.get("parents"), dict)
            and isinstance(theirs.get("height"), int | float)):
        return None
    return NeedsInput(f"the rig.json of its base {run.base.asset_id} is from an older Kiripix and doesn't record each bone's "
                      "parent and the rig's height", command=f"kiripix run {run.base.asset_id} {BASE_STAGE} --force")


def rig_needs_input(run: StageRun) -> NeedsInput | None:
    """No rig anywhere: the Model has no armature and no rigged file came back. Nothing is asked until `model` is built. A
    character made from a base is never sent to Mixamo: its Model carries the base's skeleton, or `rig` fails."""
    if run.base is not None:
        return _base_rig_is_old(run)
    if rigged_file(run) is not None:
        return None
    model = read_model(run)
    if model is None or model.get("armature") or not model.get("upload", False):
        return None  # built with a rig, or not built yet (or by an older `model`, which fails with its own message)
    return NeedsInput("the Model has no rig: rig it on Mixamo and add the rigged file", owner_action=mixamo_steps(run))


def base_mismatch(theirs: dict[str, Any], parents: dict[str, Any]) -> tuple[list[str], list[str]]:
    """How an armature (`parents`: each bone's parent) differs from the base's `rig.json`: the base's bones it lacks, and
    the ones it has under another parent, each said as `bone (under A, the base has it under B)`. More bones are fine."""
    wanted: dict[str, Any] = theirs["parents"]
    missing = [bone for bone in wanted if bone not in parents]

    def under(parent: Any) -> str:
        return f"under {parent}" if parent is not None else "as a root"

    moved = [f"{bone} ({under(parents[bone])}, the base has it {under(wanted[bone])})"
             for bone in wanted if bone in parents and parents[bone] != wanted[bone]]
    return missing, moved


def _listed(names: list[str], most: int = 12) -> str:
    return ", ".join(names[:most]) + (f" and {len(names) - most} more" if len(names) > most else "")


def _proportions(size: list[float]) -> list[float]:
    ordered = sorted(size, reverse=True)
    return [side / (ordered[0] or 1.0) for side in ordered]


def _mismatch(model: dict[str, Any], found: dict[str, Any]) -> str | None:
    """Why a rigged file isn't made from the Model, or None."""
    wanted, got = int(model["vertices"]), int(found["vertices"])
    if abs(got - wanted) > VERTEX_TOLERANCE * wanted:
        return f"it has {got} distinct points and the Model {wanted}"
    low, high = model["bounds"]["min"], model["bounds"]["max"]
    ours = _proportions([top - bottom for bottom, top in zip(low, high)])
    theirs = _proportions([float(v) for v in found["size"]])
    if any(abs(a - b) > PROPORTION_TOLERANCE for a, b in zip(ours, theirs)):
        return (f"its proportions ({', '.join(f'{v:.2f}' for v in theirs)}) differ from the Model's "
                f"({', '.join(f'{v:.2f}' for v in ours)})")
    return None


def run_rig(run: StageRun) -> None:
    model = read_model(run)
    if model is None or model.get("schema_version") != MODEL_SCHEMA_VERSION:
        raise StageFailure("model.json is missing or from an older Kiripix",
                           fix=f"kiripix run {run.asset_id} model --force")
    rigged = rigged_file(run)
    theirs: dict[str, Any] | None = None
    on_base = ""
    if run.base is not None:
        theirs = base_rig(run)
        if theirs is None or _base_rig_is_old(run) is not None:
            raise StageFailure(f"the rig.json of the base {run.base.asset_id} is missing or from an older Kiripix",
                               fix=f"kiripix run {run.base.asset_id} {BASE_STAGE} --force")
        on_base = (f"Build the Model on the skeleton of its base {run.base.asset_id}: every bone of the base, under its "
                   "exact name and the same parent. Its rest pose (bone lengths, posture) may differ.")
    if rigged is None and not model.get("armature"):
        if run.base is not None:
            raise StageFailure(f"the Model has no armature, and a character made from {run.base.asset_id} carries that "
                               "base's skeleton in its own Model", code="rig.missing", owner_action=on_base)
        raise StageFailure("the Model has no rig and no rigged file was added", code="rig.missing",
                           owner_action=mixamo_steps(run))
    source = rigged if rigged is not None else run.upstream["model"] / "model.blend"
    if rigged is None and not isinstance(model.get("source_height"), int | float):
        raise StageFailure("model.json was built before Kiripix recorded the Model's own height, which rig.json passes on",
                           fix=f"kiripix run {run.asset_id} model --force")
    run.progress(0, 1, "reading the rig")
    found = launch(run, "validate_rig", {"input": str(source)})
    if not found.get("armature"):
        raise StageFailure(f"{source.name} has no armature", code="rig.missing",
                           owner_action=on_base or (mixamo_steps(run) if rigged is not None else
                                                    "Add a Model with an armature as the Source."))
    parents: dict[str, Any] = dict(found.get("parents") or {})
    if set(parents) != set(found["bones"]):
        raise StageFailure("Blender read the armature without each bone's parent")
    if theirs is not None and run.base is not None:
        missing_bones, moved = base_mismatch(theirs, parents)
        if missing_bones or moved:
            said = [f"it lacks {_listed(missing_bones)}"] if missing_bones else []
            said += [f"it has {_listed(moved)}"] if moved else []
            raise StageFailure(
                f"the skeleton of {source.name} isn't the one of its base {run.base.asset_id}: {'; '.join(said)}",
                code="rig.base_mismatch", owner_action=on_base)
    if rigged is not None:
        problem = _mismatch(model, found)
        if problem is not None:
            raise StageFailure(
                f"the rigged file wasn't made from this Model: {problem}", code="rig.model_mismatch",
                owner_action=f"Upload {_shown(run, run.upstream['model'] / UPLOAD)} to Mixamo again, then add the "
                             f"download: kiripix import {run.asset_id} <downloaded.fbx> --role rigged")
    # The base's roles hold here too: every one of its bones is in this armature. The character's own `bone` Decisions win.
    inherited = {str(role): str(bone) for role, bone in (theirs or {}).get("mapping", {}).items()}
    mapping, missing = map_bones(list(found["bones"]), {**inherited, **chosen_bones(run)})
    if missing:
        example = json.dumps({"decision": "bone", "data": {"role": missing[0], "bone": "<bone name>"}})
        shown = ", ".join(found["bones"][:12]) + ("..." if len(found["bones"]) > 12 else "")
        raise StageFailure(
            f"the rig has no bone for {', '.join(missing)} (its bones are {shown})", code="rig.bone_missing",
            fix=f"kiripix decide {run.asset_id} rig --decision '{example}'")
    document = {
        "schema_version": RIG_SCHEMA_VERSION,
        "source": "rigged" if rigged is not None else "model",
        "file": source.name,
        "armature": found["armature"],
        "mapping": mapping,
        "bones": len(found["bones"]),
        "parents": {bone: parents[bone] for bone in found["bones"]},
        # The height of the file the rig is in, as Blender imported it, in the rest pose: the rigged file's own (Mixamo's
        # comes back at the size of the upload, not of the Model's file), else the Model's before it was normalised.
        "height": round(float(found["size"][2]), 6) if rigged is not None else float(model["source_height"]),
        "vertices": found["vertices"],
    }
    (run.output_dir / "rig.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
