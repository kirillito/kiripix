"""`gen`: painting through a Provider (tickets 0379, 0378, 0381, 0380, 0143; spec §10 "Spend").

A call is planned first (`plan`): what it is for (a Source, a Look's edit, a Prop's state, a portrait's emotion, or the
next `extend` piece), its prompt, its input images, the Provider, model, size, quality and count, and its estimate. The
plan is refused before anything is sent or written when it passes a limit: the images per call, the calls per day, or the
month's budget. With `[providers] approve = "each"` the plan is written as a pending call (`.kiripix/calls/<id>.json`) for
the Owner's `kiripix approve <id>`; with `"none"` it is sent at once. Sending (`send`) checks the input images haven't
changed, calls the Provider, appends the cost ledger line, stores each image as a Variant the way `import` does (an
`extend` piece as a candidate, joined by no one), and logs the call in `history.jsonl`. `gen` never picks.

A sprite is painted through an operation, not an image call (ticket 0388, `kiripix.core.gen_sprite`): a character, a state,
or motion. Its plan is a list of jobs (PixelLab's endpoints) under one pending call, one approval and one estimate (the
jobs' sum); `send` sends them in order, one ledger line each, and stores what came back as a sheet.

The key is read from the Project's `.env` only (`OPENAI_API_KEY=...`), never from the environment, and it is written
nowhere. The caller holds the Asset lock (`approve`: the Project lock).
"""

from __future__ import annotations

import io
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from kiripix.checks import Finding, Position
from kiripix.core import atomic, cancel, changes, emotions, extend, journal, ledger, sources
from kiripix.core.assets import HISTORY_FILE, Asset, load_asset
from kiripix.core.errors import ExitCode, fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.images import load_rgba, png_bytes, read_as_png
from kiripix.core.kinds import all_providers
from kiripix.core.project import Project
from kiripix.core.settings import ProviderChoice
from kiripix.providers import InputImage, Provider, ProviderError, ProviderRequest
from kiripix.recipes.room_prompt import BIBLE, PROMPT_FILE, PROMPTS

PROVIDER_LOCK = "providers"  # held around a call's last limit check and its send, so two calls can't both pass the cap
CALLS_DIR = "calls"
CALL_SCHEMA_VERSION = 2  # 2 (ticket 0388): the operation, its non-image inputs and its jobs; a version-1 call is a plain image call
ENV_FILE = ".env"
IMPORT_PROVIDER = "import"
GEN_KINDS = ("room", "prop", "portrait", "sprite")
DEFAULT_SQUARE = (1024, 1024)  # what a Prop or a portrait is painted at when `[providers.<id>] size` is empty
DEFAULT_EDIT = "Edit this image. Keep everything exactly the same except: {edit}"  # Lost-and-Found's wording (ticket 0143)
STRIP_EDGE = {"east": "left", "west": "right", "south": "top", "north": "bottom"}

Target = Literal["source", "look", "state", "emotion", "extend", "character", "sprite_state", "motion"]
Notice = Callable[[str], None]


class CallInput(BaseModel):
    """An image sent with the call: where it is (relative to the Project when inside it) and its hash when planned."""

    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    role: Literal["edited", "canvas", "reference", "frame"]


class PlannedJob(BaseModel):
    """One job of an operation's plan (ticket 0388): a Provider operation, its endpoint, the direction it is for, its estimate,
    its inputs that aren't images (`params`), the images it sends (role -> index into the call's `inputs`) and, when it
    needs what an earlier job gave (a rig, keypoints), that job's index. Everything is fixed at planning; `send` only feeds
    a job its earlier job's answer."""

    model_config = ConfigDict(extra="forbid")

    operation: str = Field(description="The Provider's operation: create_character, create_state, estimate_rig, ...")
    endpoint: str = Field(description="The Provider's own endpoint, which the ledger line names.")
    direction: str | None = Field(None, description="The direction it is for (s, e, ...), when it is for one.")
    estimate_usd: float
    params: dict[str, Any] = Field({}, description="Its inputs that aren't images: a character ID, a description, a frame "
                                                   "count, keypoints.")
    images: dict[str, int] = Field({}, description="The images it sends: their role -> an index into the call's `inputs`.")
    needs: int | None = Field(None, description="The index of an earlier job whose answer it is fed (a rig, keypoints).")


class PendingCall(BaseModel):
    """A planned call, everything the Provider will be sent and what it is estimated to cost. Written to
    `.kiripix/calls/<id>.json` while it waits for the Owner (ticket 0381)."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = CALL_SCHEMA_VERSION
    id: str
    time: str
    asset: str
    target: Target = Field(description="What the images are for: source, look, state, emotion or extend; for a sprite: "
                                       "character, sprite_state or motion.")
    look: str | None = None
    state: str | None = None
    emotion: str | None = None
    sides: list[str] | None = Field(None, description="With extend: the canvas's sides.")
    provider: str
    model: str
    size: str = Field(description="WIDTHxHEIGHT asked for.")
    quality: str
    count: int
    prompt: str
    inputs: list[CallInput]
    estimated_usd: float
    remaining_usd: float = Field(description="The month's budget left before this call, UTC.")
    budget_usd_month: float
    fill: str | None = Field(None, description="With extend: the canvas's fill colour, #rrggbb, where the mask lets the "
                                               "Provider paint.")
    mask_sha256: str | None = Field(None, description="With extend: the SHA-256 of the mask, at the size sent.")
    input_fidelity: str | None = Field(None, description="The input_fidelity sent with the edit; None: left out.")
    again: str = Field(description="The `gen` command that plans this call again.")
    operation: str | None = Field(None, description="For a sprite: character, state or motion; None: a plain image call.")
    params: dict[str, Any] = Field({}, description="For an operation: its inputs that aren't images (the character's ID, "
                                                   "the canvas, the directions, the frame count, the state name), as planned.")
    jobs: list[PlannedJob] = Field([], description="For an operation: its jobs in the order they are sent. `estimated_usd` "
                                                   "is their sum.")


class Candidate(BaseModel):
    """An `extend` piece `gen` kept for the Owner to join (`extend add`), or not (ticket 0380)."""

    piece: str = Field(description="The piece's name, the start of its hash.")
    file: str = Field(description="Its PNG, relative to the Project.")
    add: str = Field(description="The command that joins it.")


class Sent(BaseModel):
    """What a sent call stored."""

    call: str
    usd: float
    estimated: bool
    usage: dict[str, int] = Field(description="The token counts the Provider reported; empty when it reported none.")
    month_spent_usd: float = Field(description="This month's spend (UTC), this call included.")
    variants: list[str] = Field(description="The new Variants' names (an extend call: none).")
    files: list[str] = Field(description="Every image stored, relative to the Project.")
    candidates: list[Candidate] = Field([], description="With extend: the pieces kept, joined by no one.")
    generations: float | None = Field(None, description="What a Provider that charges in generations charged, summed over "
                                                        "the jobs sent; None when it charged in USD.")
    jobs_sent: int = Field(0, description="For an operation: the jobs sent (a failed one included).")
    sheet: str | None = Field(None, description="For a sprite: the sheet stored in `src/sheets/` (its name), if the call made one.")
    clips: list[str] = Field([], description="For a sprite: the clips the sheet holds.")
    character_id: str | None = Field(None, description="For a sprite's character: its PixelLab ID, kept in `[sprite.pixellab]`.")
    replaced_character_id: str | None = Field(None, description="The character this call's replaced in `[sprite.pixellab]`.")
    next: str | None = Field(None, description="For a sprite: the command that goes on (`frames` reads the sheet).")


# planning


def _env_key(project: Project, name: str) -> str | None:
    """`name` from the Project's `.env` (`NAME=value`, `export NAME=value`, quotes stripped); None when it isn't there."""
    path = project.root / ENV_FILE
    if not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        text = text.removeprefix("export ").strip()
        key, sep, value = text.partition("=")
        if sep and key.strip() == name:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            return value or None
    return None


def key_for(project: Project, provider: Provider) -> str | None:
    """The Provider's key from the Project's `.env`, or the refusal `provider.key_missing`. None for a Provider with none."""
    if provider.key_name is None:
        return None
    key = _env_key(project, provider.key_name)
    if key is None:
        raise fail("provider.key_missing", f"the {provider.id} Provider needs {provider.key_name}, and the Project's "
                   f"{ENV_FILE} doesn't have it",
                   owner_action=f"Put a line {provider.key_name}=<your key> in {ENV_FILE} at the Project's root "
                                f"({ENV_FILE} is git-ignored; the key is never written anywhere else).",
                   exit_code=ExitCode.NEEDS_OWNER)
    return key


def provider_for(project: Project, name: str | None, again: str) -> Provider:
    chosen = name or project.settings.providers.default
    known = all_providers()
    if chosen == IMPORT_PROVIDER:
        raise fail("provider.not_generating", "the import Provider paints nothing: it is the Owner's own images, "
                   "brought in with `kiripix import`",
                   owner_action=f"Name a Provider that paints: {again} --provider {next(iter(sorted(known)), 'openai')}, "
                                "or set [providers] default in kiripix.toml.",
                   exit_code=ExitCode.NEEDS_OWNER)
    if chosen not in known:
        raise fail("provider.unknown", f"no Provider '{chosen}'; the Providers are {', '.join(sorted(known))}",
                   fix=f"{again} --provider {next(iter(sorted(known)), 'openai')}")
    return known[chosen]


def _fidelity(project: Project, provider: Provider, model: str, target: Target) -> str | None:
    """The input_fidelity an edit sends: `[providers.<id>] input_fidelity`, where `auto` asks for `high` on an `extend`
    piece and a Look's edit when the model takes it, and leaves it out otherwise."""
    section = getattr(project.settings.providers, provider.id, None)
    chosen = section.input_fidelity if isinstance(section, ProviderChoice) else "auto"
    if chosen == "off":
        return None
    if chosen != "auto":
        return chosen
    return "high" if target in ("extend", "look") and "high" in provider.fidelities(model) else None


# the size sent: an edited image is placed into it, top-left, at scale 1 when it fits and shrunk to fit when it doesn't,
# its right and bottom edges repeated into the rest; each result is cropped back to the placed image and scaled back. So a
# result lines up with the input pixel for pixel, and registration never fights a stretch the call itself made.


def _placement(size: tuple[int, int], sent: tuple[int, int]) -> tuple[float, tuple[int, int]]:
    width, height = size
    scale = 1.0 if width <= sent[0] and height <= sent[1] else min(sent[0] / width, sent[1] / height)
    return scale, (min(sent[0], max(1, round(width * scale))), min(sent[1], max(1, round(height * scale))))


def _resized(rgba: Any, size: tuple[int, int], nearest: bool = False) -> Any:
    import numpy as np
    from PIL import Image

    if (rgba.shape[1], rgba.shape[0]) == size:
        return rgba
    image = Image.fromarray(rgba, "RGBA").resize(size, Image.Resampling.NEAREST if nearest else Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.uint8).copy()


def place_for_call(rgba: Any, sent: tuple[int, int]) -> Any:
    """The edited image as it is sent: placed into the size sent."""
    import numpy as np

    _, (width, height) = _placement((rgba.shape[1], rgba.shape[0]), sent)
    placed = _resized(rgba, (width, height))
    return np.pad(placed, ((0, sent[1] - height), (0, sent[0] - width), (0, 0)), mode="edge")


def edit_mask(canvas: Any, fill: tuple[int, int, int], sent: tuple[int, int]) -> Any:
    """The mask sent with an `extend` canvas: alpha 0 (paint) over the fill and over the padding, 255 (keep) over the kept
    strips; for a corner canvas both strips, the L. Black elsewhere, at the size sent."""
    import numpy as np

    kept = ~np.all(canvas[..., :3] == np.array(fill, dtype=np.uint8), axis=-1)
    alpha = np.zeros((*kept.shape, 4), dtype=np.uint8)
    alpha[..., 3] = np.where(kept, 255, 0).astype(np.uint8)
    _, (width, height) = _placement((canvas.shape[1], canvas.shape[0]), sent)
    placed = _resized(alpha, (width, height), nearest=True)
    return np.pad(placed, ((0, sent[1] - height), (0, sent[0] - width), (0, 0)), constant_values=0)


def unplace(result: Any, size: tuple[int, int], sent: tuple[int, int]) -> Any:
    """A result mapped back onto the edited image: brought to the size sent if the Provider answered another, cropped to
    where the image was placed, and scaled back to its size."""
    _, (width, height) = _placement(size, sent)
    return _resized(_resized(result, sent)[:height, :width], size)


def _hex(colour: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{c:02x}" for c in colour)


def _colour(text: str) -> tuple[int, int, int]:
    return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)


def _choice(project: Project, provider: Provider) -> tuple[str, str, str]:
    """The Owner's model, quality and size for the Provider (`[providers.<id>]`), or the Provider's defaults."""
    section = getattr(project.settings.providers, provider.id, None)
    if not isinstance(section, ProviderChoice):  # no section for this Provider (or a key of [providers] by that name)
        section = ProviderChoice()
    model = section.model or provider.default_model
    quality = section.quality or provider.default_quality
    size = section.size
    if provider.qualities and quality not in provider.qualities:
        raise fail("provider.quality_invalid", f"[providers.{provider.id}] quality '{quality}' is not one of "
                   f"{', '.join(provider.qualities)}",
                   owner_action=f"Set [providers.{provider.id}] quality to one of {', '.join(provider.qualities)}.")
    return model, quality, size


def _relative_or_absolute(project: Project, path: Path) -> str:
    shown = project.relative(path)
    return shown if not Path(shown).is_absolute() else path.resolve().as_posix()


def _resolve(project: Project, shown: str) -> Path:
    path = Path(shown)
    return path if path.is_absolute() else project.root / path


def _input(project: Project, path: Path, role: Literal["edited", "canvas", "reference", "frame"]) -> CallInput:
    try:
        data = path.read_bytes()
    except (FileNotFoundError, IsADirectoryError, PermissionError):
        raise fail("gen.input_not_found", f"no image at {project.relative(path)}",
                   owner_action=f"Check the path {project.relative(path)}.") from None
    return CallInput(path=_relative_or_absolute(project, path), sha256=hash_bytes(data), role=role)


def _image_size(path: Path, shown: str) -> tuple[int, int]:
    rgba = load_rgba(path, shown)
    return int(rgba.shape[1]), int(rgba.shape[0])


def _template(root: Path, stem: str) -> Path | None:
    folder = root / PROMPTS
    if not folder.is_dir():
        return None
    found = sorted(p for p in folder.iterdir() if p.is_file() and p.stem == stem)
    return found[0] if found else None


def _render(project: Project, template: Path, fields: dict[str, Any]) -> str:
    """A prompt template rendered as the brief renders the room's (ticket 0348): sandboxed, a missing field an error."""
    from jinja2 import StrictUndefined, TemplateError, UndefinedError
    from jinja2.sandbox import SandboxedEnvironment

    try:
        import jinja2  # noqa: F401
    except ImportError:
        raise fail("setup.missing_dependency", "jinja2, which renders prompt templates, isn't installed in the environment "
                   "running kiripix: it was set up before jinja2 was a dependency and not synced since",
                   fix="uv sync  (in the Kiripix repository; then run kiripix through `uv run`)") from None
    shown = project.relative(template)
    bible = project.root / BIBLE
    fields = {**fields, "bible": bible.read_text(encoding="utf-8") if bible.is_file() else ""}
    env = SandboxedEnvironment(undefined=StrictUndefined, keep_trailing_newline=True, autoescape=False)
    try:
        return env.from_string(template.read_text(encoding="utf-8")).render(fields)
    except UndefinedError as error:
        raise fail("gen.prompt_field", f"{shown} uses a field gen doesn't have: {error.message}",
                   owner_action=f"Correct {shown}, or use one of: {', '.join(sorted(fields))}.",
                   exit_code=ExitCode.NEEDS_OWNER) from error
    except TemplateError as error:
        raise fail("gen.prompt_template", f"{shown} doesn't render: {error}",
                   owner_action=f"Correct the Jinja2 syntax in {shown}.", exit_code=ExitCode.NEEDS_OWNER) from error


def _edit_prompt(project: Project, asset: Asset, words: str | None, what: dict[str, str], again: str) -> str:
    """An edit's prompt: `style/prompts/<kind>-edit.<ext>` with the words as `edit`, else Lost-and-Found's wording."""
    if not words:
        raise fail("gen.prompt_needed", "an edit needs the words that say what changes", fix=f'{again} --prompt "<what changes>"')
    template = _template(project.root, f"{asset.kind}-edit")
    if template is None:
        return DEFAULT_EDIT.format(edit=words)
    return _render(project, template, {"asset": asset.id, "edit": words, **what})


def _room_prompt(graph: AssetGraph) -> str:
    """The room's prompt, as its brief built it (ticket 0348)."""
    asset = graph.asset.id
    state = graph.state("brief")
    if state.status != "done":
        why = {"stale": "its brief is out of date", "failed": "its brief failed"}.get(state.status, "its brief isn't built")
        raise fail("gen.no_prompt", f"{asset} has no prompt to paint from: {why}", fix=f"kiripix run {asset} brief")
    path = graph.output_dir(graph.spec("brief")) / PROMPT_FILE
    if not path.is_file():
        raise fail("gen.no_prompt", f"{asset}'s brief has no prompt: the Project has no {PROMPTS}/room.<ext>",
                   owner_action=f"Write the room template, {PROMPTS}/room.j2 (spec §4), or give the prompt: "
                                f'kiripix gen {asset} --prompt "<what to paint>".',
                   exit_code=ExitCode.NEEDS_OWNER)
    return path.read_text(encoding="utf-8")


def _picked_path(graph: AssetGraph, what: str, again: str) -> Path:
    asset = graph.asset
    found = sources.variants(asset)
    name = emotions.neutral_source(graph) if emotions.is_portrait(asset) else sources.picked(graph)
    if name is None or name not in found:
        if found:
            raise fail("gen.needs_source", f"{asset.id} has no picked Source for {what} to be made on",
                       fix=f"kiripix pick {asset.id} {next(iter(found))}")
        raise fail("gen.needs_source", f"{asset.id} has no Source for {what} to be made on",
                   owner_action=f"Make the Source first (kiripix gen {asset.id}, or kiripix import {asset.id} <png>), "
                                "then pick it.")
    return found[name]


def _extend_prompt(project: Project, graph: AssetGraph, sides: list[str], words: str | None) -> str:
    """The prompt for the next piece: `style/prompts/room-extend.<ext>`, else what the canvas is, the room's prompt and the
    words saying what the new area holds."""
    room_prompt = _room_prompt(graph)
    template = _template(project.root, "room-extend")
    if template is not None:
        return _render(project, template, {"asset": graph.asset.id, "prompt": room_prompt, "sides": sides,
                                           "edit": words or ""})
    edges = " and ".join(STRIP_EDGE[s] for s in sides)
    toward = " and ".join(sides)
    head = (f"The attached image is a canvas for the next part of a game room. The strip at its {edges} edge is part of "
            f"the finished painting; continue the painting {toward} over the flat fill, keeping the strip's content, "
            "camera, scale, light and style exactly, so the two join without a seam.")
    tail = f"\n\nThe new area holds: {words}" if words else ""
    return f"{head}\n\n{room_prompt.rstrip()}{tail}\n"


def _size_text(size: tuple[int, int]) -> str:
    return f"{size[0]}x{size[1]}"


def _parse_size(text: str) -> tuple[int, int]:
    width, _, height = text.partition("x")
    return int(width), int(height)


def notice_line(call: PendingCall) -> str:
    """The line `gen` shows before sending (ticket 0378)."""
    if call.operation is not None:
        jobs = "job" if len(call.jobs) == 1 else "jobs"
        return (f"gen: {call.asset}, {call.operation} ({len(call.jobs)} {jobs}), est. ${call.estimated_usd:.2f}; "
                f"${call.remaining_usd:.2f} of ${call.budget_usd_month:.2f} left this month")
    images = "image" if call.count == 1 else "images"
    return (f"gen: {call.asset}, {call.count} {images}, est. ${call.estimated_usd:.2f}; "
            f"${call.remaining_usd:.2f} of ${call.budget_usd_month:.2f} left this month")


def check_limits(project: Project, provider: Provider, count: int, inputs: int, estimate: float, again: str) -> float:
    """Refuse a call past a limit, before anything is written or sent (tickets 0378, 0381). Returns the month's budget
    left before the call."""
    limits = project.settings.providers
    most = min(limits.max_images_per_call, provider.max_count)
    if count > most:
        source = (f"[providers] max_images_per_call is {limits.max_images_per_call}"
                  if most == limits.max_images_per_call else f"the {provider.id} Provider takes at most {most}")
        raise fail("provider.too_many_images", f"-n {count} asks for more images than one call may: {source}",
                   fix=f"{again} -n {most}")
    if inputs > provider.max_images_in:
        raise fail("provider.too_many_inputs", f"the call sends {inputs} images and the {provider.id} Provider takes "
                   f"{provider.max_images_in}", fix=again.split(" --reference ")[0])
    now = ledger.now()
    day = now.strftime("%Y-%m-%d")
    if ledger.calls_on_day(project, day) >= limits.max_calls_per_day:
        raise fail("provider.daily_limit", f"{limits.max_calls_per_day} Provider calls were sent today (UTC), the most "
                   "[providers] max_calls_per_day allows",
                   owner_action="Wait for tomorrow (UTC), or raise [providers] max_calls_per_day in kiripix.toml.",
                   exit_code=ExitCode.NEEDS_OWNER)
    month = now.strftime("%Y-%m")
    budget = limits.budget_usd_month
    spent = ledger.spent_in_month(project, month)
    remaining = round(budget - spent, ledger.CENTS)
    if round(spent + estimate, ledger.CENTS) > budget:
        raise fail("cost.budget_exceeded", f"the call is estimated at ${estimate:.4f} and ${max(remaining, 0):.4f} of the "
                   f"${budget:.2f} budget is left this month (UTC): it would go over the cap, so it wasn't sent",
                   owner_action="Raise [providers] budget_usd_month in kiripix.toml, or wait for next month.",
                   exit_code=ExitCode.NEEDS_OWNER)
    return remaining


def plan(project: Project, asset: Asset, *, count: int, provider_name: str | None, prompt: str | None,
         look: str | None, state: str | None, emotion: str | None, side: str | None, references: list[Path],
         again: str) -> PendingCall:
    """The call `gen` would send, checked against every limit. Writes nothing, except the `extend` canvas it sends."""
    if asset.kind not in GEN_KINDS:
        raise fail("gen.kind_unsupported", f"gen paints a room, a Prop, a portrait or a sprite; {asset.id} is a {asset.kind}",
                   owner_action=f"Make the {asset.kind}'s image elsewhere and bring it in with kiripix import.")
    chosen = [n for n, v in (("--look", look), ("--state", state), ("--emotion", emotion), ("--side", side)) if v]
    if len(chosen) > 1:
        raise fail("gen.one_target", f"{' and '.join(chosen)} are two things to paint: use one", fix=f"kiripix gen {asset.id}")
    provider = provider_for(project, provider_name, again)
    if chosen and not provider.edits:  # it would paint a new, unrelated image and bill it
        others = [p for p, v in all_providers().items() if v.edits]
        raise fail("gen.provider_cannot_edit", f"{provider.id} can't edit an image or extend a canvas ({chosen[0]})",
                   fix=f"{re.sub(r' --provider \S+', '', again)} --provider {others[0]}" if others else None,
                   owner_action=None if others else "No Provider here edits images.")
    model, quality, size_choice = _choice(project, provider)
    key_for(project, provider)
    graph = AssetGraph(project, asset, HashCache(project.state_dir))
    inputs: list[CallInput] = []
    target: Target
    sides: list[str] | None = None
    planned: extend.PlannedCanvas | None = None
    if side:
        if asset.kind != "room":
            raise fail("gen.side_needs_room", f"--side extends a room; {asset.id} is a {asset.kind}",
                       fix=f"kiripix gen {asset.id} --prompt \"<what to paint>\"")
        target = "extend"
        sides = extend.parse_sides(asset, side, f"kiripix gen {asset.id} --side east")
        canvas = project.settings.extend.canvas
        planned = extend.plan_canvas(project, asset, sides, canvas, None, 0, f"kiripix gen {asset.id}")
        canvas_png = png_bytes(planned.image)
        inputs.append(CallInput(path=project.relative(extend.folder(asset) / extend.CANVAS_PNG),
                                sha256=hash_bytes(canvas_png), role="canvas"))
        text = _extend_prompt(project, graph, sides, prompt)
        wanted = canvas
    elif look or state or emotion:
        if look:
            if asset.kind != "room":
                raise fail("gen.look_needs_room", f"--look is for a room; {asset.id} is a {asset.kind}",
                           fix=f"kiripix gen {asset.id} --prompt \"<what to paint>\"")
            sources.check_look_id(asset, look)
            target, what = "look", {"look": look}
        elif state:
            sources.declared_state(graph, state, "gen")
            target, what = "state", {"state": state}
        else:
            emotions.declared_emotion(graph, str(emotion), "gen")
            target, what = "emotion", {"emotion": str(emotion)}
        edited = _picked_path(graph, f"the {target}", again)
        inputs.append(_input(project, edited, "edited"))
        text = _edit_prompt(project, asset, prompt, what, again)
        wanted = _image_size(edited, project.relative(edited))
    else:
        target = "source"
        if prompt:
            text = prompt
        elif asset.kind == "room":
            text = _room_prompt(graph)
        else:
            raise fail("gen.prompt_needed", f"a {asset.kind} has no prompt template: give the words for the image",
                       fix=f'{again} --prompt "<what to paint>"')
        if asset.kind == "room":
            brief = graph.params(graph.spec("brief"))
            wanted = (int(str(brief.get("canvas_width", 1376))), int(str(brief.get("canvas_height", 768))))
        else:
            wanted = DEFAULT_SQUARE
    inputs += [_input(project, reference, "reference") for reference in references]
    size = provider.fit_size(model, _parse_size(size_choice) if size_choice else wanted)
    estimate = round(provider.estimate_usd(model, size, quality, count, len(inputs), len(text)), ledger.CENTS)
    remaining = check_limits(project, provider, count, len(inputs), estimate, again)
    fill = mask_sha256 = None
    if planned is not None and sides is not None:  # the canvas is written only once the call passed every limit
        extend.store_canvas(project, asset, sides, canvas, planned)
        fill = _hex(planned.fill)
        mask_sha256 = hash_bytes(png_bytes(edit_mask(planned.image, planned.fill, size)))
    fidelity = _fidelity(project, provider, model, target) if inputs and inputs[0].role != "reference" else None
    return PendingCall(
        id=journal.new_ulid(), time=ledger.now().isoformat(timespec="seconds"), asset=asset.id, target=target,
        look=look, state=state, emotion=emotion, sides=sides, provider=provider.id, model=model, size=_size_text(size),
        quality=quality, count=count, prompt=text, inputs=inputs, estimated_usd=estimate, remaining_usd=remaining,
        budget_usd_month=project.settings.providers.budget_usd_month, fill=fill, mask_sha256=mask_sha256,
        input_fidelity=fidelity, again=again)


# pending calls


def calls_dir(project: Project) -> Path:
    return project.state_dir / CALLS_DIR


def write_pending(project: Project, call: PendingCall) -> Path:
    path = calls_dir(project) / f"{call.id}.json"
    atomic.write_json(path, call.model_dump(mode="json"))
    return path


def _pending_path(project: Project, call_id: str) -> Path:
    if re.fullmatch(r"[0-9A-Z]{26}", call_id) is None:
        raise fail("provider.call_unknown", f"'{call_id}' is not a pending call's ID", fix="kiripix approve --list")
    return calls_dir(project) / f"{call_id}.json"


def _existing(project: Project, call_id: str) -> Path:
    path = _pending_path(project, call_id)
    if not path.is_file():
        raise fail("provider.call_unknown", f"no pending call {call_id}: it was sent, rejected, or never written",
                   fix="kiripix approve --list")
    return path


def read_pending(project: Project, call_id: str) -> PendingCall:
    path = _existing(project, call_id)
    invalid = f".kiripix/{CALLS_DIR}/{call_id}.json"
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, dict):
            raise ValueError("it is not an object")
        if document.get("schema_version") == 1:  # a version-1 call is a plain image call: no operation, no jobs
            document = {**document, "schema_version": CALL_SCHEMA_VERSION}
        call = PendingCall.model_validate(document)
    except ValidationError as error:
        raise fail("provider.call_invalid", f"{invalid} is not valid: {error.errors()[0]['msg']}",
                   fix=f"kiripix reject {call_id}") from None
    except ValueError as error:
        raise fail("provider.call_invalid", f"{invalid} is not valid: {error}", fix=f"kiripix reject {call_id}") from None
    if call.schema_version != CALL_SCHEMA_VERSION:
        raise fail("provider.call_invalid", f"{invalid} has schema_version {call.schema_version}; "
                   f"this Kiripix reads {CALL_SCHEMA_VERSION}", fix=f"kiripix reject {call_id}")
    return call


def list_pending(project: Project) -> list[PendingCall]:
    folder = calls_dir(project)
    if not folder.is_dir():
        return []
    return [read_pending(project, p.stem) for p in sorted(folder.glob("*.json"))]


def remove_pending(project: Project, call_id: str) -> None:
    changes.remove(_existing(project, call_id))


def recheck(project: Project, call: PendingCall) -> PendingCall:
    """A pending call's limits again, with the ledger as it is now (the month may have moved, other calls sent)."""
    provider = provider_for(project, call.provider, call.again)
    key_for(project, provider)
    if call.operation is not None:  # an operation's images are its jobs', not a call's reference images
        remaining = check_limits(project, provider, 1, 0, call.estimated_usd, call.again)
    else:
        remaining = check_limits(project, provider, call.count, len(call.inputs), call.estimated_usd, call.again)
    return call.model_copy(update={"remaining_usd": remaining,
                                   "budget_usd_month": project.settings.providers.budget_usd_month})


# sending


def _read_inputs(project: Project, call: PendingCall) -> list[InputImage]:
    """The input images, refused whole if any changed since the call was planned (`provider.call_stale`)."""
    images = []
    for number, item in enumerate(call.inputs, 1):
        path = _resolve(project, item.path)
        try:
            data = path.read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            data = b""
        if not data or hash_bytes(data) != item.sha256:
            raise fail("provider.call_stale", f"{item.path} changed since call {call.id} was planned, so it would paint "
                       "on an image that isn't there any more", fix=call.again)
        png, _ = read_as_png(path, item.path)
        images.append(InputImage(name=f"input{number}.png", png=png))
    return images


def _history(asset: Asset, call: PendingCall, outcome: str, **extra: Any) -> None:
    stage = {"look": "looks", "extend": "extend", "character": "frames", "sprite_state": "frames",
             "motion": "frames"}.get(call.target, "source")
    entry: dict[str, Any] = {
        "time": ledger.now().isoformat(timespec="seconds"), "stage": stage, "provider": call.provider,
        "provider_model": call.model, "size": call.size, "quality": call.quality, "count": call.count, "call": call.id,
        "prompt": call.prompt, "inputs": [i.model_dump(mode="json") for i in call.inputs], "mask": call.mask_sha256,
        "input_fidelity": call.input_fidelity, "outcome": outcome}
    for name in ("look", "state", "emotion", "sides"):
        if getattr(call, name) is not None:
            entry[name] = getattr(call, name)
    if call.operation is not None:
        entry["operation"] = call.operation
        entry["params"] = call.params
        entry["jobs"] = [job.endpoint for job in call.jobs]
        if "character_id" in call.params:
            entry["character_id"] = call.params["character_id"]
    atomic.append_jsonl(asset.dir / HISTORY_FILE, {**entry, **extra})


def _ledger(project: Project, call: PendingCall, provider: Provider, usd: float | None, images: int,
            outcome: Literal["done", "failed", "cancelled"], usage: dict[str, int] | None = None,
            generations: float | None = None) -> tuple[float, bool]:
    estimated = usd is None
    cost = round(call.estimated_usd if usd is None else usd, ledger.CENTS)
    ledger.append(project, ledger.LedgerLine(
        time=ledger.now().isoformat(timespec="seconds"), call=call.id, asset=call.asset, provider=call.provider,
        model=call.model, size=call.size, quality=call.quality, count=call.count, images=images, usd=cost,
        estimated=estimated, prices_date=provider.prices_date, mask=call.mask_sha256,
        input_fidelity=call.input_fidelity, usage=usage or {}, generations=generations, outcome=outcome))
    return cost, estimated


def _store(project: Project, asset: Asset, call: PendingCall, provider: Provider, png: bytes, number: int,
           ) -> tuple[str, Path]:
    """One image stored as `import` stores it (named `gen-<call>-<n>.png` in `imported.jsonl`), or as an extend
    candidate."""
    temporary = project.state_dir / "gen" / f"gen-{call.id}-{number}.png"
    atomic.write_bytes(temporary, png)
    try:
        shown = temporary.name
        if call.target == "extend":
            data, _ = read_as_png(temporary, shown)
            name = hash_bytes(data)[:extend.HASH_LENGTH]
            folder = extend.folder(asset) / extend.CANDIDATES
            atomic.write_bytes(folder / f"{name}.png", data)
            record = extend.CandidateRecord(call=call.id, provider=provider.id, model=call.model, sides=call.sides or [],
                                     rerenders_kept_strip=provider.rerenders_kept_strip)
            atomic.write_json(folder / f"{name}.json", record.model_dump(mode="json"))
            return name, folder / f"{name}.png"
        if call.target == "look":
            name, path, _ = sources.import_look(project, asset, temporary, shown, "variant", str(call.look))
        elif call.target == "state":
            _, name, path, _ = sources.import_state(project, asset, temporary, shown, "variant", str(call.state))
        elif call.target == "emotion":
            _, name, path, _ = emotions.import_emotion(project, asset, temporary, shown, "variant", str(call.emotion))
        elif sources.takes_sheets(asset):  # a sprite's image candidate (0390): `pick` makes it a sheet
            name, path, _ = sources.import_generated_variant(asset, temporary, shown, provider.id, call.id)
        else:
            name, path, _ = sources.import_file(asset, temporary, shown, "variant")
        return name, path
    finally:
        temporary.unlink(missing_ok=True)


def send(project: Project, call: PendingCall) -> Sent:
    """Send the call, record what it cost, store its images. Nothing is recorded for a call cancelled or refused before
    the Provider was called; one cancelled during the Provider's call is recorded at its estimate (it may have been sent
    and billed), and one the Provider refused only when it says it billed it. The caller holds `PROVIDER_LOCK`, so the
    limits checked just before and the ledger line written here can't interleave with another call's."""
    asset = load_asset(project, call.asset)
    provider = provider_for(project, call.provider, call.again)
    key = key_for(project, provider)
    if call.operation is not None:
        from kiripix.core import gen_sprite

        return gen_sprite.send(project, asset, call, provider, key)
    images = _read_inputs(project, call)
    sent = _parse_size(call.size)
    edited: tuple[int, int] | None = None
    mask: bytes | None = None
    if call.inputs and call.inputs[0].role != "reference":  # the edited image goes at the size sent, the mask with it
        rgba = load_rgba(io.BytesIO(images[0].png), call.inputs[0].path)
        edited = (int(rgba.shape[1]), int(rgba.shape[0]))
        images[0] = InputImage(name=images[0].name, png=png_bytes(place_for_call(rgba, sent)))
        if call.fill is not None:
            mask = png_bytes(edit_mask(rgba, _colour(call.fill), sent))
            if hash_bytes(mask) != call.mask_sha256:
                raise fail("provider.call_stale", f"the mask for call {call.id} isn't the one planned", fix=call.again)
    request = ProviderRequest(prompt=call.prompt, model=call.model, size=sent, quality=call.quality, count=call.count,
                              images=tuple(images), mask=mask, input_fidelity=call.input_fidelity)
    cancel.check()
    try:
        result = provider.call(request, key, cancel.check, cancel.sleep)
    except (KeyboardInterrupt, cancel.Cancelled):
        cost, _ = _ledger(project, call, provider, None, 0, "cancelled")
        _history(asset, call, "cancelled", usd=cost, estimated=True)
        raise
    except ProviderError as error:
        message = str(error)
        if key:
            message = message.replace(key, "<key>")
        if error.billed_usd is not None:
            cost, _ = _ledger(project, call, provider, error.billed_usd, 0, "failed",
                              generations=error.billed_generations)
            _history(asset, call, "failed", usd=cost, estimated=False, message=message)
        else:
            _history(asset, call, "failed", message=message)
        raise fail("provider.call_failed", f"the {provider.id} call for {call.asset} failed: {message}",
                   owner_action=f"Read the message; when it is fixed, plan the call again: {call.again}",
                   exit_code=ExitCode.NEEDS_OWNER) from None
    cost, estimated = _ledger(project, call, provider, result.usd, len(result.images), "done", result.usage,
                              result.generations)
    month = ledger.spent_in_month(project, ledger.now().strftime("%Y-%m"))
    names: list[str] = []
    files: list[str] = []
    for number, png in enumerate(result.images, 1):
        if edited is not None:
            png = png_bytes(unplace(load_rgba(io.BytesIO(png), f"result {number}"), edited, sent))
        name, path = _store(project, asset, call, provider, png, number)
        names.append(name)
        files.append(project.relative(path))
    _history(asset, call, "done", usd=cost, estimated=estimated, usage=result.usage, variants=names,
             generations=result.generations)
    if call.target == "extend":
        candidates = [Candidate(piece=n, file=f, add=f"kiripix extend {asset.id} add {f}") for n, f in zip(names, files)]
        return Sent(call=call.id, usd=cost, estimated=estimated, usage=result.usage, month_spent_usd=month, variants=[],
                    files=files, candidates=candidates, generations=result.generations)
    return Sent(call=call.id, usd=cost, estimated=estimated, usage=result.usage, month_spent_usd=month, variants=names,
                files=files, generations=result.generations)


def sent_line(call: PendingCall, sent: Sent) -> str:
    """The line `gen` and `approve` show after the call: what it actually cost, its tokens, and the month so far."""
    if sent.jobs_sent:
        charged = f", {sent.generations:g} generations" if sent.generations is not None else ""
        return (f"gen: {call.asset}, call {call.id} cost ${sent.usd:.4f} ({sent.jobs_sent} job(s){charged}); "
                f"${sent.month_spent_usd:.2f} of ${call.budget_usd_month:.2f} spent this month")
    how = "estimated: no usage reported" if sent.estimated else "from the reported usage"
    shown = [f"{sent.usage[k]:,} {k.split('_')[0]}" for k in ("input_tokens", "output_tokens") if k in sent.usage]
    tokens = f"; tokens {', '.join(shown)}" if shown else ""
    if sent.generations is not None:
        tokens += f"; {sent.generations:g} generations"
    return (f"gen: {call.asset}, call {call.id} cost ${sent.usd:.4f} ({how}{tokens}); "
            f"${sent.month_spent_usd:.2f} of ${call.budget_usd_month:.2f} spent this month")


def approval_finding(call: PendingCall) -> Finding:
    what = (f"{call.operation} ({len(call.jobs)} job(s)) from {call.provider} at {call.size}" if call.operation is not None
            else f"{call.count} image(s) from {call.provider} {call.model} at {call.size}, {call.quality}")
    return Finding(code="provider.approval_needed",
                   message=f"call {call.id} for {call.asset} waits for the Owner: {what}, est. ${call.estimated_usd:.2f}",
                   owner_action=f"kiripix approve {call.id}  (or kiripix reject {call.id})",
                   position=Position(asset=call.asset), data={"call": call.id})

