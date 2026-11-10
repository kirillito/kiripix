"""The character's `rig` Stage (spec §6.3, ticket 0102): a humanoid armature with the bones `clips` and `render` need, by
Mixamo's names or a `bone` Decision's mapping, from the Model's own rig or from the file that came back from Mixamo.

Without a rig the Stage is needs-input, with the Mixamo steps and the file Kiripix wrote for upload (the `model` Stage
writes it beside `model.blend`). The rigged file is checked against the Model it was made from, so a rig made from another
Model is caught.
"""

import json
import re
from pathlib import Path
from typing import Any

from kiripix.recipes.base import DecisionSpec, NeedsInput, StageFailure, StageRun
from kiripix.recipes.blender_launcher import launch

RIG_SCHEMA_VERSION = 1
MODEL_SCHEMA_VERSION = 2  # the `model.json` this Stage reads
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


def rig_needs_input(run: StageRun) -> NeedsInput | None:
    """No rig anywhere: the Model has no armature and no rigged file came back. Nothing is asked until `model` is built."""
    if rigged_file(run) is not None:
        return None
    model = read_model(run)
    if model is None or model.get("armature") or not model.get("upload", False):
        return None  # built with a rig, or not built yet (or by an older `model`, which fails with its own message)
    return NeedsInput("the Model has no rig: rig it on Mixamo and add the rigged file", owner_action=mixamo_steps(run))


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
    if rigged is None and not model.get("armature"):
        raise StageFailure("the Model has no rig and no rigged file was added", code="rig.missing",
                           owner_action=mixamo_steps(run))
    source = rigged if rigged is not None else run.upstream["model"] / "model.blend"
    run.progress(0, 1, "reading the rig")
    found = launch(run, "validate_rig", {"input": str(source)})
    if not found.get("armature"):
        raise StageFailure(f"{source.name} has no armature", code="rig.missing",
                           owner_action=mixamo_steps(run) if rigged is not None else
                           "Add a Model with an armature as the Source.")
    if rigged is not None:
        problem = _mismatch(model, found)
        if problem is not None:
            raise StageFailure(
                f"the rigged file wasn't made from this Model: {problem}", code="rig.model_mismatch",
                owner_action=f"Upload {_shown(run, run.upstream['model'] / UPLOAD)} to Mixamo again, then add the "
                             f"download: kiripix import {run.asset_id} <downloaded.fbx> --role rigged")
    mapping, missing = map_bones(list(found["bones"]), chosen_bones(run))
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
        "vertices": found["vertices"],
    }
    (run.output_dir / "rig.json").write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
