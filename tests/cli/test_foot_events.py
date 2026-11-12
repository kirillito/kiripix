"""Foot contact frames (ticket 0172, spec §6.3 and §9): the `clips` Stage finds the frames where a foot plants from the foot
bones' height and speed, and `character.json` carries them as each clip's `events`. The CLI tests run on the fake Blender, whose
clip-source file says each action's `feet`; the marked test runs the real Blender 5.2 on a two-step clip made from the fixture rig."""

import json
from pathlib import Path
from typing import Any

import pytest
from conftest import Kiripix
from test_character_clips import FIXTURES, HERO, IDLE, add_source, blender_script, clip, clips_json, real_hero, rigged_hero
from test_export import godot_project, set_target
from test_export_character import built

FRAMES = list(range(31))
HIGH = 0.5  # a foot in the air, in a rig 2.0 high
STEP = {"name": "step", "source": "steps/steps", "start": 0, "end": 30, "fps": 10, "loop": True}


def foot(down: range, *, speed: float = 0.0, still: float = 0.0) -> dict[str, Any]:
    """A foot on the ground (z 0) over the frames `down`, else in the air; `speed` is its speed in the air, `still` on the ground."""
    return {"z": [0.0 if f in down else HIGH for f in FRAMES], "speed": [still if f in down else speed for f in FRAMES]}


def steps(project: Kiripix, *, speed: float = 0.0, still: float = 0.0, travel: float = 0.0) -> None:
    """A source `steps` whose action touches the ground twice, once with each foot, and `standing`, which never leaves it."""
    add_source(project, "steps", height=2.0, actions=[
        {"name": "steps", "start": 0, "end": 30, "travel": travel,
         "feet": {"frames": FRAMES, "left": foot(range(3, 7), speed=speed, still=still),
                  "right": foot(range(18, 22), speed=speed, still=still)}},
        {"name": "standing", "start": 0, "end": 30, "travel": 0.0,
         "feet": {"frames": FRAMES, "left": foot(range(0, 31)), "right": foot(range(0, 31))}}])


def events(folder: Path) -> dict[str, list[int]]:
    return {c["name"]: c["events"]["foot"] for c in clips_json(folder)["clips"]}


def with_steps(project: Kiripix) -> Path:
    """A rigged hero with the clips `idle` and `step`, built through `clips`."""
    folder = rigged_hero(project)
    steps(project)
    for data in (IDLE, STEP):
        clip(project, data)
    project.json("run", HERO, "clips")
    return folder


def test_a_walk_that_touches_the_ground_twice_has_two_foot_frames_and_an_idle_none(project: Kiripix) -> None:
    folder = with_steps(project)

    document = clips_json(folder)
    assert document["schema_version"] == 2
    assert [c for c in document["clips"] if c["name"] == "step"][0]["frames"] == [0, 3, 6, 9, 12, 15, 18, 21, 24, 27]
    assert events(folder) == {"idle": [], "step": [1, 6]}  # frames 3 (left) and 18 (right): the first frame of each run


def test_a_clip_whose_feet_stay_down_has_no_foot_frame(project: Kiripix) -> None:
    folder = rigged_hero(project)
    steps(project)
    clip(project, {**STEP, "name": "stand", "source": "steps/standing"})

    project.json("run", HERO, "clips")

    assert events(folder) == {"stand": []}


def test_a_foot_still_falling_plants_where_it_stops(project: Kiripix) -> None:
    folder = rigged_hero(project)
    z = [HIGH] * 3 + [0.05, 0.02, 0.0, 0.0] + [HIGH] * 24  # within 3 % of 2.0 (0.06) of the lowest: frames 3 to 6 are down
    add_source(project, "slow", height=2.0, actions=[{"name": "slow", "start": 0, "end": 30, "travel": 0.0, "feet": {
        "frames": FRAMES, "left": {"z": z, "speed": [0.0] * 31}}}])
    clip(project, {**STEP, "source": "slow", "fps": 30, "loop": False})

    project.json("run", HERO, "clips")

    assert events(folder) == {"step": [5]}  # it is still lower at 3 and 4


def test_with_root_motion_a_foot_that_slides_is_not_planted(project: Kiripix) -> None:
    folder = rigged_hero(project)
    clip(project, STEP)
    steps(project, speed=3.0, still=0.0, travel=1.5)  # the root travels: a foot on the ground is still in the world
    project.json("run", HERO, "clips")
    assert events(folder) == {"step": [1, 6]}

    steps(project, speed=3.0, still=3.0, travel=1.5)  # on the ground but moving at 1.5 heights a second: it slides
    project.json("run", HERO, "clips")
    assert events(folder) == {"step": []}


def test_an_in_place_clip_ignores_the_speed(project: Kiripix) -> None:
    folder = rigged_hero(project)
    steps(project, speed=3.0, still=3.0)  # in place: the planted foot slides back at the walk's speed
    clip(project, STEP)

    project.json("run", HERO, "clips")

    assert events(folder) == {"step": [1, 6]}


def test_the_foot_bones_are_asked_for_by_the_rigs_mapping(project: Kiripix) -> None:
    rigged_hero(project)
    clip(project, IDLE)

    project.json("run", HERO, "clips")

    [call] = [json.loads(line) for line in (project.cwd / "blender-calls.jsonl").read_text("utf-8").splitlines()
              if '"read_actions"' in line]
    assert call["args"]["feet"] == {"left": "mixamorig:LeftFoot", "right": "mixamorig:RightFoot"}


def test_the_events_reach_character_json(project: Kiripix) -> None:
    folder = with_steps(project)
    godot_project(project)
    set_target(project)

    project.json("run", HERO)

    character = built(folder)
    clips = {c["name"]: c for c in character["clips"]}
    assert character["schema_version"] == 4
    assert clips["step"]["events"] == {"foot": [1, 6]} and clips["idle"]["events"] == {"foot": []}


def test_an_older_clips_json_is_refused_by_export_with_the_rebuild(project: Kiripix) -> None:
    folder = with_steps(project)
    godot_project(project)
    set_target(project)
    project.json("run", HERO)
    path = folder / "work" / "clips" / "clips.json"
    path.write_text(json.dumps({**clips_json(folder), "schema_version": 1}), "utf-8")

    result = project.json("run", HERO, "export", "--force", expect=1)

    assert "clips --force" in json.dumps(result["findings"])


@pytest.mark.blender
def test_a_two_step_clip_has_two_plants_on_real_blender(project: Kiripix) -> None:
    folder = real_hero(project)
    two_steps = project.cwd / "two_steps.blend"
    blender_script(project, (
        "import bpy\n"
        "from mathutils import Vector\n"
        f"bpy.ops.import_scene.fbx(filepath={str(FIXTURES / 'rigged.fbx')!r})\n"
        "rig = [o for o in bpy.data.objects if o.type == 'ARMATURE'][0]\n"
        "for a in list(bpy.data.actions):\n"
        "    bpy.data.actions.remove(a)\n"
        "action = bpy.data.actions.new('steps')\n"
        "rig.animation_data_create()\n"
        "rig.animation_data.action = action\n"
        "if hasattr(action, 'slots'):\n"
        "    rig.animation_data.action_slot = action.slots.new('OBJECT', 'steps')\n"
        "bpy.context.view_layer.objects.active = rig\n"
        "bpy.ops.object.mode_set(mode='POSE')\n"
        "names = {b.name.split(':')[-1].lower(): b.name for b in rig.pose.bones}\n"
        "left, right = rig.pose.bones[names['leftfoot']], rig.pose.bones[names['rightfoot']]\n"
        "zs = [(rig.matrix_world @ b.head_local).z for b in rig.data.bones]\n"
        "lift = 0.2 * (max(zs) - min(zs))\n"
        "up = rig.matrix_world.to_3x3().inverted() @ Vector((0, 0, lift))\n"
        # in bone space, so that whatever the bone's roll, it goes up in the world
        "ups = {bone.name: bone.bone.matrix_local.to_3x3().inverted() @ up for bone in (left, right)}\n"
        # the left foot is down in 1-8 and 24-36, up in 12-20; the right foot the other way round
        "for frame, a, b in ((1, 0, 1), (8, 0, 1), (12, 1, 0), (20, 1, 0), (24, 0, 1), (36, 0, 1)):\n"
        "    for bone, lifted in ((left, a), (right, b)):\n"
        "        bone.location = ups[bone.name] * lifted\n"
        "        bone.keyframe_insert('location', frame=frame)\n"
        "bpy.ops.object.mode_set(mode='OBJECT')\n"
        "action.use_fake_user = True\n"
        f"bpy.ops.wm.save_as_mainfile(filepath={str(two_steps)!r})\n"), "make_two_steps")  # a .blend keeps the action's range
    project.json("import", HERO, str(two_steps), "--role", "clip-source", test_recipes=False)
    clip(project, {"name": "steps", "source": "two_steps", "start": 1, "end": 36, "fps": 12, "loop": True},
         test_recipes=False)

    project.json("run", HERO, "clips", test_recipes=False, timeout=900)

    [built_clip] = clips_json(folder)["clips"]
    assert len(built_clip["events"]["foot"]) == 2, built_clip
    assert built_clip["events"]["foot"] == sorted(built_clip["events"]["foot"])
