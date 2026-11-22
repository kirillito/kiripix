"""The room brief's generation prompt (spec §4, §6.1, ticket 0348): `style/prompts/room.<ext>` rendered with Jinja2 from the
brief's fields and `style/bible.md`. No Provider and no judgement: the same inputs give the same `prompt.txt`."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from kiripix.ops.masks import SIDES
from kiripix.recipes.base import StageFailure, StageRun

PROMPT_FILE = "prompt.txt"
PROMPTS = "style/prompts"
BIBLE = "style/bible.md"


def _root(asset_dir: Path) -> Path | None:
    """The Project's root: the nearest folder above the Asset's with a `kiripix.toml`."""
    for folder in asset_dir.parents:
        if (folder / "kiripix.toml").is_file():
            return folder
    return None


def template_in(root: Path) -> Path | None:
    """The room template: the first `style/prompts/room.<ext>` (by name), whatever its extension."""
    folder = root / PROMPTS
    if not folder.is_dir():
        return None
    found = sorted(p for p in folder.iterdir() if p.is_file() and p.stem == "room")
    return found[0] if found else None


def project_files(run: StageRun) -> list[str]:
    """What the prompt is built from, for the input hash: the template and the bible; none without a template, so a
    Project without one has the hashes it had before the brief rendered a prompt."""
    root = _root(run.asset_dir)
    template = template_in(root) if root is not None else None
    if root is None or template is None:
        return []
    return [template.relative_to(root).as_posix(), BIBLE]


def parse_exits(text: str, asset: str) -> list[dict[str, str]]:
    """`door:top, stairs:left` as [{"name": "door", "side": "top"}, ...]; a name without a side has side ""."""
    found = []
    for part in (p.strip() for p in text.split(",")):
        if not part:
            continue
        name, _, side = (s.strip() for s in part.partition(":"))
        if side and side not in SIDES:
            raise StageFailure(f"the brief's exit '{part}' names the side '{side}', not one of {', '.join(SIDES)}",
                               code="brief.exit_side",
                               fix=f"kiripix set {asset} brief exits=<name>:<side>[,...] with a side of {'|'.join(SIDES)}")
        found.append({"name": name, "side": side})
    return found


def context(run: StageRun, exits: list[dict[str, str]]) -> dict[str, Any]:
    """The fields a template may use."""
    width, height, tile = int(run.params["width"]), int(run.params["height"]), int(run.settings["project.tile"])
    canvas_w, canvas_h = int(run.params["canvas_width"]), int(run.params["canvas_height"])
    return {
        "asset": run.asset_id,
        "view": run.asset_params.get("view", ""),
        "width": width,
        "height": height,
        "tile": tile,
        "tiles_wide": -(-width // tile),
        "tiles_high": -(-height // tile),
        "aspect": round(width / height, 4),
        "canvas_width": canvas_w,
        "canvas_height": canvas_h,
        "canvas_aspect": round(canvas_w / canvas_h, 4),
        "mood": run.params["mood"],
        "notes": run.params["notes"],
        "exits": exits,
    }


def render_prompt(run: StageRun, exits: list[dict[str, str]]) -> None:
    """Writes `prompt.txt` when the Project has a room template; nothing, and no error, when it has none."""
    root = _root(run.asset_dir)
    template = template_in(root) if root is not None else None
    if root is None or template is None:
        return
    from jinja2 import StrictUndefined, TemplateError, UndefinedError
    from jinja2.sandbox import SandboxedEnvironment

    shown = template.relative_to(root).as_posix()
    fields = context(run, exits)
    bible = root / BIBLE
    if bible.is_file():
        fields["bible"] = bible.read_text(encoding="utf-8")
    env = SandboxedEnvironment(undefined=StrictUndefined, keep_trailing_newline=True, autoescape=False)
    try:
        text = env.from_string(template.read_text(encoding="utf-8")).render(fields)
    except UndefinedError as error:
        raise StageFailure(
            f"{shown} uses a field the brief doesn't have: {error.message}",
            code="brief.prompt_field",
            owner_action=f"Correct {shown}, or use one of: {', '.join(sorted(fields))}.",
        ) from error
    except TemplateError as error:
        raise StageFailure(f"{shown} doesn't render: {error}", code="brief.prompt_template",
                           owner_action=f"Correct the Jinja2 syntax in {shown}.") from error
    (run.output_dir / PROMPT_FILE).write_text(text.replace("\r\n", "\n"), encoding="utf-8", newline="\n")
