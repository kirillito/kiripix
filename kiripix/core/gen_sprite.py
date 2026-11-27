"""`gen` for a sprite (ticket 0388, spec §6.4 and §10 "Spend"; parent 0386): PixelLab paints a character, a state of it, or motion.

A sprite is painted through the Provider's operations, not its image call. `plan` turns what `gen` was asked into one
`PendingCall` whose `jobs` are the operation's whole plan, in order, each with its endpoint, direction, estimate, its inputs
that aren't images (`params`) and the images it sends (role -> an index into the call's `inputs`, which are the sprite's
frames, hashed as every call's inputs are). The estimate is the jobs' sum, the limits check that sum, and the daily limit
counts the call once. `send` sends the jobs in order: a job that needs what an earlier one gave (a rig, keypoints) is fed it
when its turn comes (`PlannedJob.needs`); a failed or cancelled job stops the rest; each job sent is its own ledger line;
what came back is stored. Nothing here knows a Provider's endpoint: `Provider.endpoints` names them.

The targets (the Commands' flags in brackets):

- a character from text (`--prompt "<who>" [--canvas N]`): `create_character`; its ZIP's rotations are stored as the sheet's
  clip `idle` (PixelLab's `Idle`);
- a character from the sprite's own frames (`--from-frames [--from <clip>] [--view V]`): `create_character` with the clip's
  first frame in each direction; the directions the sprite lacks are made and stored as a sheet (ticket 0390, below), and when
  it has them all the pixels come back as sent and no sheet is stored, only `[sprite.pixellab]`;
- a state (`--state <name> --prompt "<the pose>" [--canvas N]`): `create_state`; the sheet holds only the new state's
  rotations, as clip `<name>` (`<name>_2`... when the sheets already hold the name);
- motion by PixelLab's rig (`--clip <name> --motion rig --prompt "<the action>"`): per direction `estimate_rig` on the first
  frame of `--from`, then `animate_skeleton` with `write_motion_frames`; frames in `animations/<name>/<direction>/frame_NNN.png`.

Every sheet is repacked in PixelLab's own layout (so `sprite_names` reads it unchanged), stored by hash in `src/sheets/` as
`import --role sheet` stores one (the same ZIP checks) and recorded in `imported.jsonl` with the Provider and the call. The
whole answer is kept for the record in `.kiripix/calls/sent/<call>/`, never read by a Stage.

- motion between two of the sprite's own frames (`--clip <name> --motion keyframes --from <clip> --to <clip> --prompt "<the
  action>" [--frames N]`, ticket 0391): per direction one job, `animate_keyframes`, the first frame of `--from` as the start and
  the first frame of `--to` as the end, never text alone (`gen.keyframes_need_end`). Only for a sprite marked faceless
  (`[sprite.pixellab] faces = false`, else `gen.keyframes_faces`): the text-driven call melts faces. No PixelLab character is
  needed. Stored as a rig's clip is.
- an image of the figure (`--image --prompt "<what>" [--style <asset>[:<clip>] | --style <png>] [--canvas N] [-n N]`, ticket 0390):
  the Provider's plain image call, not an operation: a plain pending call whose candidates are stored in `src/` as the
  sprite's image Variants; `pick` (`gen_sprite.pick`) turns the one chosen into a one-direction sheet, clip `idle`
  (`idle_2`... when held), recorded with the Provider and the call. `--style` is the call's style image: the first south
  frame of a sprite's clip, of a character's `render`, or a PNG of the Project.
- more facings (`--from-frames`, ticket 0390): the directions the sprite has, south at least, are sent; when the sprite
  wants more, the call makes them and they are stored as a sheet under the next free name of the `--from` clip (`idle_2`),
  the sent frames as drawn. The made facings come from `generate_rotations` on the south frame, then `create_character` from
  all the frames (the owner's trial of ticket 0390 chose it over `create_character` with the south frame alone: its back
  views were grey blobs).
- `[sprite.pixellab] view` (ticket 0390): the camera view of the character, set by `--prompt` and `--from-frames` (`--view`),
  and sent where the endpoint takes one: rotations, a rig or a skeleton motion (`animate_skeleton`). PixelLab's state call,
  `animate-with-text-v3` and the image call have none, so `--view` is refused for `--image`, `--state` and `--clip`.
- motion by a character's render (`--clip <name> --motion skeleton --render <character> [--render-clip <clip>]`, ticket 0389):
  per direction `estimate_skeleton` on the first frame of `--from`, then `animate_skeleton` with keypoints made from the render's
  points (`gen_skeleton`, `kiripix.providers.keypoints`). The render's keypoints are fixed at planning, in the animate job's
  `params["keypoints"]` with the data to move them (`params["retarget"]`); the retarget onto the sprite's own skeleton can only
  happen once the estimate has answered, so `_feed` does it at send time, deterministically, from what the Owner approved.
  Stored as a rig's clip is. `--preview` plans nothing: `preview` writes the overlay and keypoints.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from kiripix.checks import Position
from kiripix.core import atomic, cancel, gen, gen_skeleton, journal, ledger, sheets, sources
from kiripix.core.assets import ASSET_FILE, HISTORY_FILE, Asset, is_asset_id, load_asset
from kiripix.core.errors import ExitCode, KiripixError, fail
from kiripix.core.gen import CALLS_DIR, CallInput, PendingCall, PlannedJob, Sent, Target
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.images import load_rgba
from kiripix.core.project import Project
from kiripix.core.settings import DEFAULT_VIEW, VIEWS, PixelLabCharacter, SpriteSettings, save_settings
from kiripix.providers import InputImage, OperationRequest, OperationResult, Provider, ProviderError, keypoints
from kiripix.recipes.clips import NAME_PATTERN
from kiripix.recipes.sprite_frames import FRAMES_FILE, SHEET, expected_directions, latest_by_name
from kiripix.recipes.sprite_names import METADATA, PIXELLAB_WORDS, place, snake_case

KIND = "sprite"
PROVIDER = "pixellab"
SENT_DIR = "sent"
WORD_OF = {ours: word for word, ours in PIXELLAB_WORDS.items()}  # s -> south
DEFAULT_CANVAS = 32
CANVAS_RANGE = (32, 256)  # a character's square, in px
FRAMES_RANGE = (1, 15)  # with PixelLab's own rig
SKELETON_FRAMES_RANGE = gen_skeleton.FRAMES_RANGE  # with keypoints (0389)
DEFAULT_FRAMES = 8
DEFAULT_FROM = "idle"
TEXT_CLIP = "Idle"  # PixelLab names a character's first state Idle; the naming rule reads it as the clip `idle`
MOTIONS = ("rig", "skeleton", "keyframes")
KEYFRAMES_FRAMES = (4, 16)  # PixelLab's animate-with-text-v3, even
KEYFRAMES_PIXELS = 524_288  # its budget: width x height x frames
IMAGE_CANVAS = 64  # an image call's default square, in px


def takes(asset: Asset) -> bool:
    """A sprite is painted by `plan` here, not by `gen.plan`."""
    return asset.kind == KIND


# planning


def _table(asset: Asset) -> PixelLabCharacter | None:
    """`[sprite.pixellab]`, whether or not it holds a character."""
    return asset.settings.pixellab


def _stored(asset: Asset) -> PixelLabCharacter | None:
    """The sprite's PixelLab character: the table when it holds one."""
    table = _table(asset)
    return table if table is not None and table.character_id is not None else None


def _held_names(project: Project, asset: Asset) -> set[str]:
    """Every clip name the sprite holds or would hold, so a new state or clip never joins one: the ZIP sheets' raw folder
    names (a state's, an animation's, `idle`), the `sheet` Decisions' names (a PNG's `clip`, a ZIP's `clips` renames), and
    the clips of the last built `frames.json`. A name held only because a Decision renamed it away still counts: the
    Owner may undo that."""
    names: set[str] = set()
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    spec = graph.spec("frames")
    for decision in latest_by_name(graph.decisions(spec), SHEET.name, "file").values():
        if isinstance(decision.data.get("clip"), str):
            names.add(snake_case(decision.data["clip"]))
        renames = decision.data.get("clips")
        if isinstance(renames, dict):
            names.update(snake_case(str(v)) for v in renames.values())
    try:
        document = json.loads((graph.output_dir(spec) / FRAMES_FILE).read_text(encoding="utf-8"))
        names.update(str(c["name"]) for c in document.get("clips", []) if isinstance(c, dict) and "name" in c)
    except (OSError, ValueError):
        pass
    for path in sheets.sheets(asset).values():
        if path.suffix != ".zip":
            continue
        try:
            with zipfile.ZipFile(path) as archive:
                for info in archive.infolist():
                    placed = place(info.filename) if not info.is_dir() else None
                    if placed is not None:
                        names.add(snake_case(placed.raw))
        except (zipfile.BadZipFile, OSError):
            continue
    return names


def _who(asset: Asset) -> str:
    """What the character looks like: the last text character call's words, else the Asset's name."""
    path = asset.dir / HISTORY_FILE
    found = ""
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict) and entry.get("target") != "motion" and entry.get("operation") == "character" \
                    and entry.get("outcome") == "done" and isinstance(entry.get("prompt"), str) and entry["prompt"]:
                found = entry["prompt"]
    return found or asset.name.replace("_", " ")


def _frames_of(project: Project, asset: Asset, graph: AssetGraph, clip: str, directions: list[str],
               *, south_only: bool = False) -> dict[str, Path]:
    """The first frame of `clip` in each of `directions`, from the `frames` Stage's output (`gen.frames_needed` when it
    hasn't run). With `south_only` the directions the clip lacks are left out, and only south is needed (0390)."""
    state = graph.state("frames")
    if state.status != "done":
        raise fail("gen.frames_needed", f"{asset.id}'s frames aren't built ({state.status}), and gen reads the sprite's own "
                   f"frames", fix=f"kiripix run {asset.id} frames")
    out = graph.output_dir(graph.spec("frames"))
    try:
        document = json.loads((out / FRAMES_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise fail("gen.frames_needed", f"{asset.id}'s frames.json can't be read", fix=f"kiripix run {asset.id} frames --force") \
            from None
    clips = {str(c["name"]): c for c in document.get("clips", [])}
    if clip not in clips:
        raise fail("gen.clip_unknown", f"{asset.id} has no clip '{clip}'; its clips are {', '.join(sorted(clips)) or 'none'}",
                   fix=f"kiripix show {asset.id}")
    found: dict[str, Path] = {}
    for direction in directions:
        frames = clips[clip].get("directions", {}).get(direction) or []
        if not frames and south_only and direction != "s":
            continue
        if not frames:
            raise fail("gen.direction_missing", f"clip '{clip}' of {asset.id} has no frame in direction {direction}",
                       fix=f"kiripix show {asset.id}")
        first = min(frames, key=lambda f: int(f["index"]))
        path = out / str(first["file"])
        if not path.is_file():
            raise fail("gen.frames_needed", f"{asset.id}'s frame {first['file']} isn't there",
                       fix=f"kiripix run {asset.id} frames --force")
        found[direction] = path
    return found


def _estimate(provider: Provider, operation: str, params: dict[str, Any], roles: list[str]) -> float:
    request = OperationRequest(operation, params, {role: b"" for role in roles})
    return round(provider.estimate_operation(request), ledger.CENTS)


def _size(path: Path, shown: str) -> tuple[int, int]:
    rgba = load_rgba(path, shown)
    return int(rgba.shape[1]), int(rgba.shape[0])


def _refuse(code: str, message: str, fix: str) -> KiripixError:
    return fail(code, message, fix=fix)


def _without(again: str, *flags: str) -> str:
    """`again` with each named flag and its value taken out, every other flag kept (a fix replaces only the faulty one). A
    value is a word or a JSON string (`--prompt "..."`); a flag with no value (`--from-frames`) goes alone."""
    for flag in flags:
        again = re.sub(rf' {re.escape(flag)}(?= |$)(?: (?!--)(?:"(?:[^"\\]|\\.)*"|\S+))?', "", again)
    return again


def _new_name(held: set[str], name: str) -> str:
    """`name`, or `name_2`, `name_3`... when the sprite already holds it: a retry is a new name, not a replacement (0386)."""
    sent, number = name, 1
    while sent in held:
        number += 1
        sent = f"{name}_{number}"
    return sent


def plan(project: Project, asset: Asset, *, provider_name: str | None, prompt: str | None, canvas: int | None,
         from_frames: bool, from_clip: str | None, state: str | None, clip: str | None, motion: str | None,
         frames: int | None, directions: str | None, count: int, look: str | None, emotion: str | None,
         side: str | None, references: list[Path], render: str | None, render_clip: str | None,
         again: str, image: bool = False, style: str | None = None, view: str | None = None,
         to_clip: str | None = None, cwd: Path | None = None) -> PendingCall:
    """The sprite call `gen` would send, checked against every flag and limit. Writes nothing."""
    base = f"kiripix gen {asset.id}"
    unfit = [name for name, value in (("--look", look), ("--emotion", emotion), ("--side", side)) if value]
    unfit += ["--reference"] * bool(references) + ["-n"] * (count != 1 and not image)
    if unfit:
        raise _refuse("gen.flag_unsupported", f"{', '.join(unfit)} don't fit a sprite: gen paints a sprite as a character "
                      f"(--prompt, --from-frames), a state (--state) or motion (--clip --motion)",
                      f'{base} --prompt "<who>"')
    if provider_name not in (None, PROVIDER):
        raise _refuse("gen.provider_unsupported", f"a sprite is painted by the {PROVIDER} Provider only, not "
                      f"'{provider_name}'", re.sub(r" --provider \S+", f" --provider {PROVIDER}", again))
    if sum(bool(v) for v in (from_frames, state, clip, image)) > 1:
        raise _refuse("gen.one_target", "--image, --from-frames, --state and --clip are four things to paint: use one", base)
    if from_frames and (prompt or canvas or motion or frames is not None or directions):
        raise _refuse("gen.flag_unsupported", "--from-frames takes only --from and --view: the character is the "
                      "sprite's frames as drawn", f"{base} --from-frames")
    if style and not image:
        raise _refuse("gen.flag_unsupported", "--style is the style image of --image", _without(again, "--style"))
    if view is not None and (image or state or clip):
        raise _refuse("gen.flag_unsupported", "--view is the camera of a character, set when it is made (--prompt or "
                      "--from-frames) and sent by every later state and motion; PixelLab's image call has no view",
                      _without(again, "--view"))
    if view is not None and view not in VIEWS:
        raise _refuse("input.invalid", f"--view {view}: PixelLab's views are {', '.join(VIEWS)}",
                      f'{_without(again, "--view")} --view "{DEFAULT_VIEW}"')
    if from_clip and not (from_frames or clip):
        raise _refuse("gen.flag_unsupported", "--from names the clip whose first frames --from-frames or --clip start from",
                      f"{base} --from-frames --from {from_clip}")
    if to_clip and motion != "keyframes":
        raise _refuse("gen.flag_unsupported", "--to names the clip whose first frame ends the motion of --motion keyframes",
                      _without(again, "--to"))
    if (render or render_clip) and motion != "skeleton":
        raise _refuse("gen.flag_unsupported", "--render and --render-clip name the character whose render is the motion: they are "
                      "for --motion skeleton", _without(again, "--render", "--render-clip"))
    if (motion or frames is not None or directions) and not clip:
        raise _refuse("gen.clip_needed", "--motion, --frames and --directions are for --clip, the clip to make",
                      f'{base} --clip <name> --motion rig --prompt "<the action>"')
    if clip and (canvas or state):
        raise _refuse("gen.flag_unsupported", "--canvas is for a character or a state, not for motion",
                      _without(again, "--canvas"))
    if state and (motion or frames is not None or directions or from_clip):
        raise _refuse("gen.flag_unsupported", "--motion, --frames, --directions and --from are for --clip, not --state",
                      f"{base} --state {state}" + (f" --prompt {json.dumps(prompt)}" if prompt else ""))
    if clip:
        if motion is None:
            raise _refuse("gen.motion_needed", f"--clip {clip} needs --motion: rig (PixelLab's own rig) or skeleton (a "
                          "character's render)", f"{again} --motion rig")
        if motion not in MOTIONS:
            raise _refuse("input.invalid", f"--motion {motion} is not one of {', '.join(MOTIONS)}", f"{_without(again, '--motion')} --motion rig")
        if motion == "keyframes" and not to_clip:
            raise _refuse("gen.keyframes_need_end", "--motion keyframes goes from one of the sprite's frames to another: name the "
                          "clip whose first frame ends it, no call is made from one frame and text", f"{again} --to <clip>")
        if motion == "keyframes" and (_table(asset) or PixelLabCharacter()).faces:
            raise fail("gen.keyframes_faces", f"{asset.id} may have a face, and text-driven motion melts faces: --motion keyframes "
                       "is for a sprite marked faceless", exit_code=ExitCode.NEEDS_OWNER,
                       owner_action=f"If {asset.id} has no face, mark it: kiripix set {asset.id} pixellab faces=false")
        if motion == "skeleton" and not render:
            raise _refuse("gen.render_needed", "--motion skeleton takes the motion from a character's render: name the "
                          "character", f"{again} --render character.<name>")
        if not re.fullmatch(NAME_PATTERN, clip):
            raise _refuse("gen.clip_invalid", f"'{clip}' is not a clip name: lower-case letters, digits and underscores, not "
                          f"ending in a direction", f"{base} --clip {snake_case(clip)} --motion {motion}")
        low, high = {"skeleton": SKELETON_FRAMES_RANGE, "keyframes": KEYFRAMES_FRAMES}.get(motion, FRAMES_RANGE)
        if frames is not None and (not low <= frames <= high or motion == "keyframes" and frames % 2):
            word = {"skeleton": "skeleton motion", "keyframes": "motion between two frames"}.get(motion, "own rig")
            raise _refuse("gen.frames_range", f"--frames {frames}: PixelLab's {word} takes {'an even ' if motion == 'keyframes' else ''}"
                          f"{low} to {high} frames", f"{_without(again, '--frames')} --frames {DEFAULT_FRAMES}")
    if canvas is not None and not CANVAS_RANGE[0] <= canvas <= CANVAS_RANGE[1]:
        raise _refuse("gen.canvas_range", f"--canvas {canvas}: a character's canvas is {CANVAS_RANGE[0]} to "
                      f"{CANVAS_RANGE[1]} px", f"{_without(again, '--canvas')} --canvas {DEFAULT_CANVAS}")
    if image and not prompt:
        raise _refuse("gen.prompt_needed", "--image needs the words that say what the image shows",
                      f'{again} --prompt "<what to paint>"')
    if not (from_frames or state or clip or prompt):
        raise _refuse("gen.prompt_needed", f"{asset.id} is painted as an image (--image), as a character from text (--prompt), "
                      "from its own frames (--from-frames), as a state (--state) or as motion (--clip --motion)",
                      f'{base} --prompt "<who>"')
    if (state or clip) and not prompt and motion != "skeleton":  # a skeleton's action defaults to the clip's name
        raise _refuse("gen.prompt_needed", f"a {'state' if state else 'clip'} needs the words that say "
                      f"{'the pose' if state else 'the action'}", f'{again} --prompt "<the {"pose" if state else "action"}>"')

    provider = gen.provider_for(project, PROVIDER, again)
    gen.key_for(project, provider)
    if image:
        assert prompt is not None
        return _plan_image(project, asset, provider, prompt, style, canvas, count, cwd or project.root, again)
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    wanted = expected_directions(graph.params(graph.spec("frames")))
    n_directions = 8 if len(wanted) == 8 else 4
    stored = _stored(asset)

    if from_frames:
        return _plan_from_frames(project, asset, graph, provider, wanted, n_directions, from_clip or DEFAULT_FROM,
                                 view or DEFAULT_VIEW, again)
    if clip and motion == "keyframes":
        assert to_clip is not None
        return _plan_keyframes(project, asset, graph, provider, wanted, clip, prompt or "", frames or DEFAULT_FRAMES, directions,
                               from_clip or DEFAULT_FROM, to_clip, again)
    if clip and motion == "skeleton":
        assert render is not None
        return _plan_skeleton(project, asset, graph, provider, wanted, clip, prompt, frames or DEFAULT_FRAMES, directions,
                              from_clip or DEFAULT_FROM, render, render_clip or clip, (_table(asset) or PixelLabCharacter()).view,
                              again)
    if clip:
        assert prompt is not None and motion == "rig"
        return _plan_rig(project, asset, graph, provider, stored, wanted, clip, prompt, frames or DEFAULT_FRAMES, directions,
                         from_clip or DEFAULT_FROM, again)
    if state:
        assert prompt is not None
        return _plan_state(project, asset, provider, stored, state, prompt, canvas, again)
    assert prompt is not None
    params = {"description": prompt, "canvas": canvas or DEFAULT_CANVAS, "n_directions": n_directions,
              "view": view or DEFAULT_VIEW}
    job = PlannedJob(operation="create_character", endpoint=provider.endpoints["create_character"], estimate_usd=_estimate(
        provider, "create_character", params, []), params=params)
    size = f"{params['canvas']}x{params['canvas']}"
    return _call(project, asset, provider, target="character", operation="character", size=size, prompt=prompt, jobs=[job],
                 inputs=[], count=n_directions, model=job.endpoint, again=again, state=None,
                 params={"made_from": "text", "canvas": params["canvas"], "n_directions": n_directions,
                         "view": params["view"], "replaces": stored.character_id if stored else None})


def _plan_from_frames(project: Project, asset: Asset, graph: AssetGraph, provider: Provider, wanted: list[str],
                      n_directions: int, from_clip: str, view: str, again: str) -> PendingCall:
    """A character from the sprite's own frames: the directions it has (south at least) are sent as drawn; the ones it wants
    and lacks are made (ticket 0390: the rotations of the south frame, then the character from all the frames) and stored as a
    sheet under a new clip name."""
    found = _frames_of(project, asset, graph, from_clip, wanted, south_only=True)
    inputs: list[CallInput] = []
    images: dict[str, int] = {}
    sizes: set[tuple[int, int]] = set()
    for direction, path in found.items():
        inputs.append(gen._input(project, path, "frame"))
        if direction != "s":  # south is the `reference`; PixelLab takes the others as `direction_images`
            images[WORD_OF[direction]] = len(inputs) - 1
        else:
            images["reference"] = len(inputs) - 1
        sizes.add(_size(path, project.relative(path)))
    if len(sizes) != 1:
        raise fail("gen.frames_differ", f"the first frames of '{from_clip}' have different sizes "
                   f"({', '.join(f'{w}x{h}' for w, h in sorted(sizes))}): PixelLab takes one canvas",
                   fix=f"kiripix show {asset.id}")
    (width, height), = sizes
    if max(width, height) > CANVAS_RANGE[1]:
        raise fail("gen.canvas_range", f"the frames are {width}x{height} px: a character's canvas is at most "
                   f"{CANVAS_RANGE[1]} px", fix=f"kiripix show {asset.id}")
    made = [d for d in wanted if d not in found]
    description = _who(asset)
    params: dict[str, Any] = {"description": description, "n_directions": n_directions, "view": view}
    jobs: list[PlannedJob] = []
    if made:  # the rotations first, then a character from all the frames
        rotation = {"description": description, "view": view, "first_frame_direction": "south"}
        jobs.append(PlannedJob(operation="generate_rotations", endpoint=provider.endpoints["generate_rotations"],
                               estimate_usd=_estimate(provider, "generate_rotations", rotation, ["first_frame"]), params=rotation,
                               images={"first_frame": images["reference"]}))
        params["rotated"] = [WORD_OF[d] for d in made]
        sent_roles = [*images, *params["rotated"]]
        jobs.append(PlannedJob(operation="create_character", endpoint=provider.endpoints["create_character"],
                               estimate_usd=_estimate(provider, "create_character", params, sent_roles), params=params,
                               images=images, needs=0))
    else:  # every facing is ours: the character is only imported
        jobs.append(PlannedJob(operation="create_character", endpoint=provider.endpoints["create_character"],
                               estimate_usd=_estimate(provider, "create_character", params, list(images)), params=params,
                               images=images))
    stored = _stored(asset)
    clip = _new_name(_held_names(project, asset), from_clip) if made else None
    return _call(project, asset, provider, target="character", operation="character", size=f"{width}x{height}",
                 prompt=description, jobs=jobs, inputs=inputs, count=len(found), model=jobs[-1].endpoint, again=again, state=None,
                 params={"made_from": "frames", "from_clip": from_clip, "n_directions": n_directions, "view": view,
                         "directions": list(found), "canvas": f"{width}x{height}", "made": made, "clip": clip,
                         "replaces": stored.character_id if stored else None})


def _plan_image(project: Project, asset: Asset, provider: Provider, prompt: str, style: str | None, canvas: int | None,
                count: int, cwd: Path, again: str) -> PendingCall:
    """`--image` (ticket 0390): the Provider's plain image call, its style image a frame of another Asset or a PNG; the
    candidates come back as the sprite's image Variants."""
    inputs: list[CallInput] = []
    edge = canvas or IMAGE_CANVAS
    if style:
        path = _style_path(project, style, cwd, again)
        width, height = _size(path, project.relative(path))
        if max(width, height) > CANVAS_RANGE[1]:
            raise fail("gen.style_too_large", f"the style image {project.relative(path)} is {width}x{height} px: PixelLab takes at "
                       f"most {CANVAS_RANGE[1]}", fix=_without(again, "--style"))
        inputs.append(gen._input(project, path, "reference"))
    model, quality, _ = gen._choice(project, provider)
    size = provider.fit_size(model, (edge, edge))
    estimate = round(provider.estimate_usd(model, size, quality, count, len(inputs), len(prompt)), ledger.CENTS)
    remaining = gen.check_limits(project, provider, count, len(inputs), estimate, again)
    return PendingCall(
        id=journal.new_ulid(), time=ledger.now().isoformat(timespec="seconds"), asset=asset.id, target="source",
        provider=provider.id, model=model, size=f"{size[0]}x{size[1]}", quality=quality, count=count, prompt=prompt,
        inputs=inputs, estimated_usd=estimate, remaining_usd=remaining,
        budget_usd_month=project.settings.providers.budget_usd_month, again=again)


def _style_path(project: Project, style: str, cwd: Path, again: str) -> Path:
    """`--style`: `<asset>[:<clip>]` (the first south frame of a sprite's clip, or of a character's render; `idle` by
    default) or a PNG of the Project."""
    name, _, clip = style.partition(":")
    if is_asset_id(name) and not (cwd / style).is_file():
        try:
            other = load_asset(project, name)
        except KiripixError:
            raise fail("gen.style_unknown", f"--style {style}: no Asset {name}, and no file {style}",
                       fix=_without(again, "--style")) from None
        clip = clip or DEFAULT_FROM
        if other.kind == "character":
            return gen_skeleton.first_frame(project, other.id, clip)
        if other.kind != KIND:
            raise fail("gen.style_kind", f"--style {name}: a {other.kind} has no frames to take a style from (a sprite's frames "
                       "or a character's render do)", fix=_without(again, "--style"))
        return _frames_of(project, other, AssetGraph(project, other, HashCache(project.state_dir)), clip, ["s"])["s"]
    path = Path(style) if Path(style).is_absolute() else cwd / style
    if not path.is_file():
        raise fail("gen.style_unknown", f"--style {style} is neither an Asset nor a file of the Project",
                   fix=_without(again, "--style"))
    return path


def _plan_state(project: Project, asset: Asset, provider: Provider, stored: PixelLabCharacter | None, state: str,
                prompt: str, canvas: int | None, again: str) -> PendingCall:
    if stored is None:
        has_sheet = bool(sheets.sheets(asset))
        raise fail("gen.character_needed", f"{asset.id} has no PixelLab character to make a state of: "
                   "[sprite.pixellab] is empty",
                   fix=f"kiripix gen {asset.id} --from-frames" if has_sheet else f'kiripix gen {asset.id} --prompt "<who>"')
    if not re.fullmatch(NAME_PATTERN, state):
        raise fail("gen.state_invalid", f"'{state}' is not a state name: lower-case letters, digits and underscores, not "
                   "ending in a direction",
                   fix=f"kiripix gen {asset.id} --state {snake_case(state)} --prompt {json.dumps(prompt)}")
    sent_name = _new_name(_held_names(project, asset), state)
    params: dict[str, Any] = {"character_id": stored.character_id, "description": prompt, "state_name": sent_name,
                              "view": stored.view}
    if canvas is not None:
        params["canvas"] = canvas
    assert stored.canvas is not None
    edge = canvas or max(int(v) for v in stored.canvas.split("x"))
    job = PlannedJob(operation="create_state", endpoint=provider.endpoints["create_state"],
                     estimate_usd=_estimate(provider, "create_state", {**params, "canvas": edge}, []), params=params)
    size = f"{canvas}x{canvas}" if canvas else stored.canvas
    return _call(project, asset, provider, target="sprite_state", operation="state", size=size, prompt=prompt, jobs=[job],
                 inputs=[], count=1, model=job.endpoint, again=again, state=sent_name,
                 params={"character_id": stored.character_id, "state_name": sent_name, "asked": state,
                         "canvas": canvas})


def _directions(asset: Asset, wanted: list[str], directions: str | None, again: str) -> list[str]:
    """The directions asked for with `--directions` (default: all the sprite asks for), each one the sprite asks for."""
    chosen = [d.strip() for d in directions.split(",") if d.strip()] if directions else list(wanted)
    unknown = [d for d in chosen if d not in wanted]
    if not chosen or unknown or len(set(chosen)) != len(chosen):
        raise fail("gen.direction_unknown", f"--directions {directions}: {asset.id} asks for {', '.join(wanted)}"
                   + (f", not {', '.join(unknown)}" if unknown else ""),
                   fix=f"{_without(again, '--directions')} --directions {','.join(wanted)}")
    return chosen


def _plan_rig(project: Project, asset: Asset, graph: AssetGraph, provider: Provider, stored: PixelLabCharacter | None,
              wanted: list[str], clip: str, prompt: str, frames: int, directions: str | None, from_clip: str,
              again: str) -> PendingCall:
    if stored is None:
        has_sheet = bool(sheets.sheets(asset))
        raise fail("gen.character_needed", f"{asset.id} has no PixelLab character to animate: [sprite.pixellab] is empty",
                   fix=f"kiripix gen {asset.id} --from-frames" if has_sheet else f'kiripix gen {asset.id} --prompt "<who>"')
    chosen = _directions(asset, wanted, directions, again)
    found = _frames_of(project, asset, graph, from_clip, chosen)
    sent_clip = _new_name(_held_names(project, asset), clip)  # a retry is `walk_2`, not a duplicate `walk`
    description = _who(asset)
    inputs: list[CallInput] = []
    jobs: list[PlannedJob] = []
    size = ""
    for direction in chosen:
        path = found[direction]
        inputs.append(gen._input(project, path, "frame"))
        index = len(inputs) - 1
        width, height = _size(path, project.relative(path))
        size = size or f"{width}x{height}"
        word = WORD_OF[direction]
        rig_params = {"direction": word, "description": description, "action": prompt, "view": stored.view}
        jobs.append(PlannedJob(operation="estimate_rig", endpoint=provider.endpoints["estimate_rig"], direction=direction,
                               estimate_usd=_estimate(provider, "estimate_rig", rig_params, ["frame_0"]), params=rig_params,
                               images={"frame_0": index}))
        animate = {"direction": word, "description": description, "action": prompt, "write_motion_frames": frames,
                   "view": stored.view}
        jobs.append(PlannedJob(operation="animate_skeleton", endpoint=provider.endpoints["animate_skeleton"],
                               direction=direction, estimate_usd=_estimate(provider, "animate_skeleton", animate, ["first_frame"]),
                               params=animate, images={"first_frame": index}, needs=len(jobs) - 1))
    return _call(project, asset, provider, target="motion", operation="motion", size=size, prompt=prompt, jobs=jobs,
                 inputs=inputs, count=len(chosen), model=provider.endpoints["animate_skeleton"], again=again, state=None,
                 params={"clip": sent_clip, "asked": clip, "motion": "rig",
                         "frames": frames, "directions": chosen, "from_clip": from_clip,
                         "character_id": stored.character_id})


def _plan_keyframes(project: Project, asset: Asset, graph: AssetGraph, provider: Provider, wanted: list[str], clip: str,
                    prompt: str, frames: int, directions: str | None, from_clip: str, to_clip: str, again: str) -> PendingCall:
    """Motion between two of the sprite's own frames (0391): per direction one `animate_keyframes` job, the first frame of
    `from_clip` as its start and the first frame of `to_clip` as its end."""
    chosen = _directions(asset, wanted, directions, again)
    starts = _frames_of(project, asset, graph, from_clip, chosen)
    ends = _frames_of(project, asset, graph, to_clip, chosen)
    sent_clip = _new_name(_held_names(project, asset), clip)  # a retry is `topple_2`, not a duplicate `topple`
    inputs: list[CallInput] = []
    jobs: list[PlannedJob] = []
    size = ""
    for direction in chosen:
        first, last = _size(starts[direction], project.relative(starts[direction])), _size(ends[direction], project.relative(ends[direction]))
        if first != last:
            raise fail("gen.frames_differ", f"the first frames of '{from_clip}' ({first[0]}x{first[1]}) and '{to_clip}' "
                       f"({last[0]}x{last[1]}) in {direction} differ in size: PixelLab's motion between two frames takes one size",
                       fix=f"kiripix show {asset.id}")
        if max(first) > CANVAS_RANGE[1]:
            raise fail("gen.canvas_range", f"the frames of {asset.id} are {first[0]}x{first[1]} px: PixelLab's motion between two "
                       f"frames takes at most {CANVAS_RANGE[1]} px", fix=f"kiripix show {asset.id}")
        if first[0] * first[1] * frames > KEYFRAMES_PIXELS:
            raise fail("gen.frames_range", f"{first[0]}x{first[1]} px at {frames} frames is over PixelLab's limit (width x height "
                       f"x frames at most {KEYFRAMES_PIXELS})",
                       fix=f"{_without(again, '--frames')} --frames {KEYFRAMES_FRAMES[0]}")
        size = size or f"{first[0]}x{first[1]}"
        inputs += [gen._input(project, starts[direction], "frame"), gen._input(project, ends[direction], "frame")]
        params = {"action": prompt, "frame_count": frames}
        jobs.append(PlannedJob(operation="animate_keyframes", endpoint=provider.endpoints["animate_keyframes"], direction=direction,
                               estimate_usd=_estimate(provider, "animate_keyframes", params, ["first_frame", "last_frame"]),
                               params=params, images={"first_frame": len(inputs) - 2, "last_frame": len(inputs) - 1}))
    return _call(project, asset, provider, target="motion", operation="motion", size=size, prompt=prompt, jobs=jobs,
                 inputs=inputs, count=len(chosen), model=provider.endpoints["animate_keyframes"], again=again, state=None,
                 params={"clip": sent_clip, "asked": clip, "motion": "keyframes", "frames": frames, "directions": chosen,
                         "from_clip": from_clip, "to_clip": to_clip})


def _plan_skeleton(project: Project, asset: Asset, graph: AssetGraph, provider: Provider, wanted: list[str], clip: str,
                   prompt: str | None, frames: int, directions: str | None, from_clip: str, render: str, render_clip: str,
                   view: str, again: str) -> PendingCall:
    """Motion from a character's render (0389): per direction `estimate_skeleton` on the sprite's frame, then `animate_skeleton`
    with the render's keypoints (not yet moved onto the sprite: `_feed` does that when the estimate has answered)."""
    chosen = _directions(asset, wanted, directions, again)
    found = _frames_of(project, asset, graph, from_clip, chosen)
    sent_clip = _new_name(_held_names(project, asset), clip)  # a retry is `walk_2`, not a duplicate `walk`
    made = gen_skeleton.read(project, render, render_clip, chosen, frames, again)
    description = _who(asset)
    action = prompt or clip.replace("_", " ")
    inputs: list[CallInput] = []
    jobs: list[PlannedJob] = []
    size = ""
    for direction in chosen:
        path = found[direction]
        inputs.append(gen._input(project, path, "frame"))
        index = len(inputs) - 1
        width, height = _size(path, project.relative(path))
        size = size or f"{width}x{height}"
        jobs.append(PlannedJob(operation="estimate_skeleton", endpoint=provider.endpoints["estimate_skeleton"],
                               direction=direction, estimate_usd=_estimate(provider, "estimate_skeleton", {}, ["image"]),
                               params={}, images={"image": index}))
        plan = made.directions[direction]
        animate: dict[str, Any] = {"direction": WORD_OF[direction], "description": description, "action": action,
                                   "view": view, "keypoints": plan.frames,
                                   "retarget": {"first": plan.first, "size": list(made.size), "target": [width, height]}}
        jobs.append(PlannedJob(operation="animate_skeleton", endpoint=provider.endpoints["animate_skeleton"],
                               direction=direction, estimate_usd=_estimate(provider, "animate_skeleton", animate, ["first_frame"]),
                               params=animate, images={"first_frame": index}, needs=len(jobs) - 1))
    return _call(project, asset, provider, target="motion", operation="motion", size=size, prompt=action, jobs=jobs,
                 inputs=inputs, count=len(chosen), model=provider.endpoints["animate_skeleton"], again=again, state=None,
                 params={"clip": sent_clip, "asked": clip, "motion": "skeleton",
                         "frames": len(next(iter(made.directions.values())).frames),
                         "directions": chosen, "from_clip": from_clip, "render": render, "render_clip": render_clip})


def preview(project: Project, asset: Asset, *, clip: str | None, motion: str | None, render: str | None,
            render_clip: str | None, frames: int | None, directions: str | None, from_clip: str | None, again: str,
            ) -> tuple[gen_skeleton.RenderPlan, list[tuple[str, str]]]:
    """`gen --preview`: the keypoints and overlay of the render, written under `.kiripix/calls/preview/<sprite>/`; nothing is
    planned, estimated or sent, and no key is read. Returns the render's plan and (JSON, overlay) per direction."""
    if not clip or motion != "skeleton" or not render:
        raise _refuse("gen.preview_needs_skeleton", "--preview shows the keypoints of --motion skeleton: it needs --clip, "
                      "--motion skeleton and --render", f"{_without(again, '--clip', '--motion', '--render')} --clip {clip or '<name>'} --motion skeleton "
                      f"--render {render or 'character.<name>'} --preview")
    if frames is not None and not SKELETON_FRAMES_RANGE[0] <= frames <= SKELETON_FRAMES_RANGE[1]:
        raise _refuse("gen.frames_range", f"--frames {frames}: PixelLab's skeleton motion takes {SKELETON_FRAMES_RANGE[0]} to "
                      f"{SKELETON_FRAMES_RANGE[1]} frames", f"{_without(again, '--frames')} --frames {DEFAULT_FRAMES}")
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    wanted = expected_directions(graph.params(graph.spec("frames")))
    chosen = _directions(asset, wanted, directions, again)
    _frames_of(project, asset, graph, from_clip or DEFAULT_FROM, chosen)  # the same refusals as the plan
    made = gen_skeleton.read(project, render, render_clip or clip, chosen, frames or DEFAULT_FRAMES, again)
    return made, gen_skeleton.write_preview(project, asset, made)


def _call(project: Project, asset: Asset, provider: Provider, *, target: Target, operation: str, size: str, prompt: str,
          jobs: list[PlannedJob], inputs: list[CallInput], count: int, model: str, again: str, state: str | None,
          params: dict[str, Any]) -> PendingCall:
    estimate = round(sum(job.estimate_usd for job in jobs), ledger.CENTS)
    remaining = gen.check_limits(project, provider, 1, 0, estimate, again)  # one operation: one call, its images its jobs'
    return PendingCall(
        id=journal.new_ulid(), time=ledger.now().isoformat(timespec="seconds"), asset=asset.id,
        target=target, state=state, provider=provider.id, model=model, size=size,
        quality=provider.default_quality, count=count, prompt=prompt, inputs=inputs, estimated_usd=estimate,
        remaining_usd=remaining, budget_usd_month=project.settings.providers.budget_usd_month, again=again,
        operation=operation, params=params, jobs=jobs)


# sending


class _Unfed(Exception):
    """A job's earlier job gave nothing to feed it."""


def _feed(job: PlannedJob, results: dict[int, OperationResult]) -> dict[str, Any]:
    """The job's params, plus what its earlier job gave: a rig and the first frame's keypoints (`estimate_rig`), or the
    first frame's keypoints (`estimate_skeleton`; with a `retarget` in the params, the render's keypoints are moved onto that
    skeleton, 0389)."""
    params = dict(job.params)
    if job.needs is None:
        return params
    prior = results[job.needs]
    if prior.name == "estimate_rig":
        rig = prior.data.get("rig")
        listed = prior.data.get("frames") or []
        if not rig or not listed or not listed[0]:
            raise _Unfed(f"PixelLab's rig estimate for direction {job.direction} has no rig or no keypoints")
        params["rig"] = rig
        params["first_frame_keypoints"] = listed[0]
    elif prior.name == "estimate_skeleton":
        estimate = prior.data.get("keypoints")
        if not estimate:
            raise _Unfed(f"PixelLab's skeleton estimate for direction {job.direction} has no keypoints")
        retarget = params.pop("retarget", None)
        if retarget is None:
            params["first_frame_keypoints"] = estimate
        else:
            try:
                actor = keypoints.joints_of(estimate)
                target = (int(retarget["target"][0]), int(retarget["target"][1]))
                params["keypoints"] = keypoints.retarget(retarget["first"], params["keypoints"],
                                                         (int(retarget["size"][0]), int(retarget["size"][1])), actor, target)
            except ValueError as error:
                raise _Unfed(f"PixelLab's skeleton estimate for direction {job.direction} can't be used: {error}") from None
            params["first_frame_keypoints"] = [{"x": j["x"], "y": j["y"], "label": j["label"], "z_index": j["z_index"]}
                                               for j in actor]
    return params


def _fed_images(job: PlannedJob, results: dict[int, OperationResult]) -> dict[str, bytes]:
    """The images an earlier job made that this job sends (`params["rotated"]`: the directions to take from a
    `generate_rotations` answer, by PixelLab's word), by role."""
    if job.needs is None or "rotated" not in job.params:
        return {}
    prior = results[job.needs]
    made = dict(zip(prior.data.get("directions", []), prior.images, strict=False))
    return {word: made[word] for word in job.params["rotated"] if word in made}


def _zip(entries: dict[str, bytes]) -> bytes:
    """A ZIP of `entries`, the same bytes for the same content (a fixed time, sorted), so the sheet's hash is its content's."""
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as archive:
        for name in sorted(entries):
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, entries[name])
    return out.getvalue()


def _rotations(archive: bytes, wanted: str | None, shown: str, position: Position) -> dict[str, bytes]:
    """The rotations of one state in a character's ZIP, by our direction. `wanted` is the state's name (a state call: it must
    be there); None is a text character's first state (a top-level `rotations/`, else the state `idle`, else the first)."""
    sheets.check(archive, shown, position)
    groups: dict[str | None, dict[str, bytes]] = {}
    with zipfile.ZipFile(io.BytesIO(archive)) as opened:
        for info in opened.infolist():
            if info.is_dir() or info.filename == METADATA:
                continue
            placed = place(info.filename)
            if placed is not None and placed.animation is None:
                groups.setdefault(placed.state, {})[placed.direction] = opened.read(info)
    if wanted is not None:
        chosen = next((g for k, g in groups.items() if k is not None and snake_case(k) == snake_case(wanted)), None)
        if chosen is None:
            held = ", ".join(sorted(str(k) for k in groups if k)) or "none"
            raise fail("gen.state_missing", f"PixelLab's ZIP has no state '{wanted}' (it holds {held}): the call was "
                       "billed and its whole answer is kept under .kiripix/calls/sent/", fix="kiripix cost")
        return chosen
    if None in groups:
        return groups[None]
    named = [k for k in groups if k is not None and snake_case(k) == "idle"]
    pick = named[0] if named else next(iter(sorted(str(k) for k in groups if k)), None)
    if pick is None:
        raise fail("gen.rotations_missing", "PixelLab's ZIP has no rotations: the call was billed and its whole answer is kept "
                   "under .kiripix/calls/sent/", fix="kiripix cost")
    return groups[pick]


@dataclass
class _Stored:
    sheet: str | None = None
    clips: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    character_id: str | None = None
    replaced: str | None = None
    missing: str | None = None  # why a made and charged character's or state's ZIP isn't stored
    zip_of: str | None = None  # the PixelLab character whose ZIP that is


def _keep_answers(project: Project, call: PendingCall, done: list[tuple[int, PlannedJob, OperationResult]]) -> None:
    """The whole answer of every job done, for the record, under `.kiripix/calls/sent/<call>/` (never read by a Stage)."""
    folder = project.state_dir / CALLS_DIR / SENT_DIR / call.id
    for index, job, result in done:
        stem = f"{index:02d}-{job.endpoint}" + (f"-{job.direction}" if job.direction else "")
        if result.archive is not None:
            atomic.write_bytes(folder / f"{stem}.zip", result.archive)
        for number, png in enumerate(result.images):
            atomic.write_bytes(folder / stem / f"frame_{number:03d}.png", png)
        record = {"operation": result.name, "endpoint": job.endpoint, "direction": job.direction, "usd": result.usd,
                  "generations": result.generations, "character_id": result.character_id, "job_ids": result.job_ids,
                  "data": result.data}
        atomic.write_bytes(folder / f"{stem}.json", json.dumps(record, indent=2, default=str).encode("utf-8") + b"\n")


def _store(project: Project, asset: Asset, call: PendingCall, provider: Provider,
           done: list[tuple[int, PlannedJob, OperationResult]]) -> _Stored:
    stored = _Stored()
    if not done:
        return stored
    _keep_answers(project, call, done)
    shown = f"gen-{call.id}.zip"
    position = Position(asset=asset.id, file=shown)
    if call.operation == "motion":
        clip = str(call.params["clip"])
        entries: dict[str, bytes] = {}
        for _, job, result in done:
            if job.operation in ("animate_skeleton", "animate_keyframes") and job.direction is not None:
                for number, png in enumerate(result.images):
                    entries[f"animations/{clip}/{WORD_OF[job.direction]}/frame_{number:03d}.png"] = png
        if entries:
            name, path, _ = sources.import_generated_sheet(asset, _zip(entries), shown, provider.id, call.id)
            stored.sheet, stored.clips, stored.files = name, [clip], [project.relative(path)]
        return stored
    characters = [r for _, j, r in done if j.operation in ("create_character", "create_state")]
    if not characters:  # the rotations were made and charged, the character wasn't: only the answers are kept
        return stored
    result = characters[0]
    if not result.character_id:
        raise fail("gen.archive_missing", "PixelLab gave no character: the call was billed and its answer is kept "
                   "under .kiripix/calls/sent/", fix="kiripix cost")
    if call.operation == "character":
        previous = _stored(asset)
        table = _table(asset)
        made = PixelLabCharacter(character_id=result.character_id, canvas=call.size,
                                 made_from=call.params["made_from"],
                                 view=call.params.get("view") or DEFAULT_VIEW, faces=table.faces if table else True)
        settings = asset.settings.model_copy(update={"sprite": SpriteSettings(pixellab=made)})
        save_settings(asset.dir / ASSET_FILE, settings)
        stored.character_id = made.character_id
        stored.replaced = previous.character_id if previous is not None else None
        if call.params["made_from"] == "frames":
            if not call.params.get("made"):
                return stored  # the pixels come back as sent, and every facing was ours: no sheet
            folder = clip = str(call.params["clip"])
        else:
            folder, clip = TEXT_CLIP, "idle"
    else:
        folder = clip = str(call.state)
        stored.character_id = str(call.params["character_id"])
    if result.archive is None:  # made and charged, but the ZIP couldn't be fetched: the character is kept all the same
        made_what = f"character {result.character_id}" if call.operation == "character" else f"state {folder}"
        why = result.data.get("zip_missing", "no reason given")
        stored.missing = f"PixelLab made {made_what} and charged it, but its ZIP wasn't fetched ({why})"
        stored.zip_of = result.character_id
        return stored
    rotations = _rotations(result.archive, None if call.operation == "character" else folder, shown, position)
    if call.operation == "character" and call.params["made_from"] == "frames":  # the sent frames stay as drawn (0390)
        sent = gen._read_inputs(project, call)
        drawn = {d: sent[n].png for n, d in enumerate(call.params["directions"])}
        lacking = [d for d in call.params["made"] if d not in rotations]
        if lacking:
            raise fail("gen.rotations_missing", f"PixelLab's ZIP has no rotation in {', '.join(lacking)}: the call was billed and "
                       "its whole answer is kept under .kiripix/calls/sent/", fix="kiripix cost")
        rotations = {d: drawn.get(d, rotations.get(d, b"")) for d in [*call.params["directions"], *call.params["made"]]}
    entries = {f"{folder}/rotations/{WORD_OF[d]}.png": png for d, png in rotations.items()}
    name, path, _ = sources.import_generated_sheet(asset, _zip(entries), shown, provider.id, call.id)
    stored.sheet, stored.clips, stored.files = name, [clip], [project.relative(path)]
    return stored


def pick(project: Project, asset: Asset, variant: str) -> tuple[str, str]:
    """`pick` on a sprite (ticket 0390): the image candidate `variant` (`gen --image`) stored as a one-direction sheet in
    PixelLab's layout, clip `idle` (`idle_2`... when the sprite holds one), recorded in `imported.jsonl` with the Provider and
    the call that made the image. Returns the sheet's name and the clip."""
    known = sources.variants(asset)
    if variant not in known:
        position = Position(asset=asset.id, stage="frames")
        if not known:
            raise fail("pick.unknown_variant", f"{asset.id} has no image candidates yet", position=position,
                       fix=f'kiripix gen {asset.id} --image --prompt "<what to paint>"')
        raise fail("pick.unknown_variant", f"{asset.id} has no image candidate '{variant}'; its candidates are "
                   f"{', '.join(known)}", position=position, owner_action=f"Pick one of them: kiripix pick {asset.id} <variant>")
    clip = _new_name(_held_names(project, asset), DEFAULT_FROM)
    made = sources.imported_record(asset, known[variant])
    shown = f"pick-{variant}.zip"
    data = _zip({f"{clip}/rotations/south.png": known[variant].read_bytes()})
    name, _, _ = sources.import_generated_sheet(asset, data, shown, made.provider if made else None,
                                                made.call if made else None)
    return name, clip


def _line(project: Project, call: PendingCall, provider: Provider, job: PlannedJob, usd: float | None,
          generations: float | None, images: int, outcome: Literal["done", "failed", "cancelled"]) -> tuple[float, bool]:
    estimated = usd is None
    cost = round(job.estimate_usd if usd is None else usd, ledger.CENTS)
    ledger.append(project, ledger.LedgerLine(
        time=ledger.now().isoformat(timespec="seconds"), call=call.id, asset=call.asset, provider=call.provider,
        model=job.endpoint, size=call.size, quality=call.quality, count=1, images=images, usd=cost, estimated=estimated,
        prices_date=provider.prices_date, generations=generations, operation=job.endpoint,
        outcome=outcome))
    return cost, estimated


def send(project: Project, asset: Asset, call: PendingCall, provider: Provider, key: str | None) -> Sent:
    """Send the operation's jobs in order. Each job sent is a ledger line (a cancelled one at its estimate, a failed one only
    when the Provider says it billed it); a failed or cancelled job stops the rest; what came back is stored. The caller holds
    the Provider lock and the Asset lock."""
    images: list[InputImage] = gen._read_inputs(project, call)
    results: dict[int, OperationResult] = {}
    done: list[tuple[int, PlannedJob, OperationResult]] = []
    total = 0.0
    generations: float | None = None
    estimated = False
    sent_jobs = 0
    stopped: BaseException | None = None
    problem: tuple[str, str] | None = None
    for index, job in enumerate(call.jobs):
        try:
            cancel.check()
        except (KeyboardInterrupt, cancel.Cancelled) as stop:
            stopped = stop
            break
        try:
            request = OperationRequest(job.operation, _feed(job, results),
                                       {**{role: images[at].png for role, at in job.images.items()},
                                        **_fed_images(job, results)})
        except _Unfed as error:
            problem = ("gen.rig_unreadable", str(error))
            break
        sent_jobs += 1
        try:
            result = provider.operate(request, key, cancel.check, cancel.sleep)
        except (KeyboardInterrupt, cancel.Cancelled) as stop:
            cost, _ = _line(project, call, provider, job, None, None, 0, "cancelled")
            total, estimated, stopped = total + cost, True, stop
            break
        except ProviderError as error:
            message = str(error)
            if key:
                message = message.replace(key, "<key>")
            if error.billed_usd is not None:
                cost, _ = _line(project, call, provider, job, error.billed_usd, error.billed_generations, 0, "failed")
                total += cost
                if error.billed_generations is not None:
                    generations = round((generations or 0.0) + error.billed_generations, ledger.CENTS)
            problem = ("provider.call_failed", f"the {provider.id} {job.endpoint} job for {call.asset} failed: {message}")
            break
        cost, guessed = _line(project, call, provider, job, result.usd, result.generations, len(result.images), "done")
        total, estimated = total + cost, estimated or guessed
        if result.generations is not None:
            generations = round((generations or 0.0) + result.generations, ledger.CENTS)
        results[index] = result
        done.append((index, job, result))
        if result.data.get("cancelled"):  # made and charged, then cancelled while its ZIP was built: keep it, then stop
            stopped = cancel.Cancelled()
            break
    total = round(total, ledger.CENTS)
    try:
        stored = _store(project, asset, call, provider, done)
    except KiripixError as error:
        gen._history(asset, call, "failed", usd=total, estimated=estimated, message=error.findings[0].message)
        raise
    month = ledger.spent_in_month(project, ledger.now().strftime("%Y-%m"))
    if stopped is not None:
        gen._history(asset, call, "cancelled", usd=total, estimated=True, jobs_sent=sent_jobs, sheet=stored.sheet)
        raise stopped
    if problem is None and stored.missing is not None:
        gen._history(asset, call, "failed", usd=total, estimated=estimated, jobs_sent=sent_jobs,
                     character_id=stored.character_id, message=stored.missing)
        raise fail("gen.archive_missing", stored.missing + (f"; the character is kept in [sprite.pixellab]"
                                                            if call.operation == "character" else ""),
                   owner_action=f"Download character {stored.zip_of}'s ZIP from pixellab.ai and import it: kiripix import "
                   f"{asset.id} <file.zip> --role sheet (leave out the states already held with the `sheet` Decision's "
                   f"leave_out), then reject this call if it still waits, so it isn't sent again: kiripix reject {call.id}",
                   exit_code=ExitCode.NEEDS_OWNER)
    if problem is not None:
        code, message = problem
        came = (f"; the directions that came back were stored as sheet {stored.sheet}" if stored.sheet else "")
        gen._history(asset, call, "failed", usd=total, estimated=estimated, jobs_sent=sent_jobs, sheet=stored.sheet,
                     message=message)
        if code == "provider.call_failed":
            raise fail(code, message + came, owner_action="Read the message; when it is fixed, plan the call again "
                       f"(reject this one: kiripix reject {call.id}): {call.again}", exit_code=ExitCode.NEEDS_OWNER)
        raise fail(code, message + came, owner_action=f"Plan the call again (reject this one: kiripix reject {call.id}): "
                   f"{call.again}", exit_code=ExitCode.NEEDS_OWNER)
    gen._history(asset, call, "done", usd=total, estimated=estimated, jobs_sent=sent_jobs, sheet=stored.sheet,
                 clips=stored.clips, character_id=stored.character_id, generations=generations)
    nxt = (f"kiripix run {asset.id} frames" if stored.sheet
           else f'kiripix gen {asset.id} --state <name> --prompt "<the pose>"')
    return Sent(call=call.id, usd=total, estimated=estimated, usage={}, month_spent_usd=month, variants=[],
                files=stored.files, generations=generations, jobs_sent=sent_jobs, sheet=stored.sheet, clips=stored.clips,
                character_id=stored.character_id,
                replaced_character_id=stored.replaced, next=nxt)


__all__ = ["KIND", "plan", "preview", "send", "takes"]
