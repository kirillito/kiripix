"""The npc Recipe (ADR 0015, ticket 0356): choose, export.

A background figure is a choice, not a render: a base body (a character, ADR 0012), a few of the Wearables already rendered on
it and one named colour choice per Part, taken from the Project's ramp table (`[[character.ramps]]` and its `choices`). Nothing
renders and no Runner runs. `choose` writes `npc.json`; its input hash covers the base's and each chosen Wearable's `sheet` and
`palette`, so a re-render of the base or of a Wearable makes every NPC on it stale. The game draws the base's and the Wearables'
own exports; `export` (ticket 0358) writes the one small appearance file.

`choose`'s parameters are the choice (ADR 0015: parameters, not Decisions):

    wearables   Wearable IDs, comma-separated, such as `wearable.hair_a,wearable.coat@25`. They stack over the base by their
                `order` (the Wearable's `sheet` parameter, ties by ID); `id@<number>` gives this NPC another order for that one.
    colours     `part=choice` pairs, comma-separated, such as `hair=auburn,top=red`: a Part and the name of one of its row's
                `choices` in the ramp table.

and `npc.json` is

    {"schema_version": 1, "base": "character.body_m",
     "wearables": [{"id": "wearable.hair_a", "order": 10}, ...],          # in stack order, bottom to top
     "colours": {"hair": {"choice": "auburn", "rgb": [[r, g, b], ...]}}}  # by Part, in the ramp table's row order
"""

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kiripix.checks import (
    Finding,
    LayerFrame,
    buried_by_order,
    check_colour_choice,
    check_npc_stack,
    check_part_unset,
    check_wearable_body,
)
from kiripix.recipes.base import (
    BASE_PARAM,
    BaseInputs,
    CheckSpec,
    ChosenInputs,
    KindSpec,
    NeedsInput,
    ParamSpec,
    StageFailure,
    StageInputs,
    StageRun,
    StageSpec,
    chain,
)
from kiripix.recipes.character_export import check_character_export, export_needs_input
from kiripix.recipes.character_sheet import SHEET_FILE
from kiripix.recipes.wearable_sheet import DEFAULT_ORDER
from kiripix.recipes.wearable_stack import read_render_frame, render_frames

NPC_FILE = "npc.json"
NPC_SCHEMA_VERSION = 1  # a Stage's rebuilt output, refused when old (no migration)
RAMPS_SETTING = "character.ramps"
READS = ["sheet", "palette"]  # the Stages of the base and of each Wearable that `choose` follows
WEARABLES = "wearables"
COLOURS = "colours"


@dataclass(frozen=True)
class Problem:
    """Why the choice can't be made: a finding `code`, the message, and the command that puts it right."""

    code: str
    message: str
    fix: str


def parse_wearables(text: object) -> list[tuple[str, int | None, bool]]:
    """The Wearables a `wearables` value lists, each with the order it gives, if any (`id@25`), and whether what follows the
    `@` is a whole number."""
    found: list[tuple[str, int | None, bool]] = []
    if not isinstance(text, str):
        return found
    for item in text.split(","):
        if not item.strip():
            continue
        asset_id, at, order = item.partition("@")
        valid = order.strip().lstrip("-").isdigit()
        found.append((asset_id.strip(), int(order) if valid else None, valid or not at))
    return found


def parse_colours(text: object) -> list[tuple[str, str]] | None:
    """The `part=choice` pairs of a `colours` value, in the order given; None when an entry isn't one."""
    pairs: list[tuple[str, str]] = []
    if not isinstance(text, str):
        return pairs
    for item in text.split(","):
        if not item.strip():
            continue
        part, equals, choice = item.partition("=")
        if not equals or not part.strip() or not choice.strip():
            return None
        pairs.append((part.strip(), choice.strip()))
    return pairs


def _set(run: StageRun, parameter: str, value: str) -> str:
    return f"kiripix set {run.asset_id} choose {parameter}={value}"


def _problem(run: StageRun) -> Problem | None:
    """The first thing wrong with the choice, from the parameters and what the Project holds."""
    listed = parse_wearables(run.params.get(WEARABLES, ""))
    seen: set[str] = set()
    for asset_id, _, valid in listed:
        view = run.chosen.get(asset_id)
        if view is None:
            return Problem("npc.wearable_unknown", f"{asset_id} is not an Asset of this Project",
                           "kiripix status --kind wearable")
        if view.body is None:
            return Problem("npc.wearable_unknown", f"{asset_id} is a {view.kind}, not a Wearable",
                           "kiripix status --kind wearable")
        if run.base is not None and view.body != run.base.asset_id:
            return Problem("npc.wearable_body", f"{asset_id} is worn on {view.body}, not on this NPC's base {run.base.asset_id}",
                           f"kiripix show {run.base.asset_id}")
        if asset_id in seen:
            return Problem("npc.wearable_twice", f"{asset_id} is listed twice", _set(run, WEARABLES, ",".join(
                dict.fromkeys(a for a, _, _ in listed))))
        seen.add(asset_id)
        if not valid:
            return Problem("npc.wearable_order", f"the order of {asset_id} isn't a whole number", _set(run, WEARABLES, asset_id))
    colours = parse_colours(run.params.get(COLOURS, ""))
    if colours is None:
        return Problem("npc.colours_invalid", f"`colours` is part=choice pairs, comma-separated; got {run.params.get(COLOURS)!r}",
                       _set(run, COLOURS, "hair=auburn"))
    rows = {str(row["name"]): row for row in run.settings.get(RAMPS_SETTING) or []}
    parts: set[str] = set()
    for part, choice in colours:
        row = rows.get(part)
        if row is None:
            return Problem("npc.part_unknown", f"'{part}' is not a part in the Project's ramp table "
                           f"({', '.join(rows) or 'it is empty'})", "kiripix describe project")
        if choice not in (row.get("choices") or {}):
            known = ", ".join(row.get("choices") or {}) or "none"
            return Problem("npc.choice_unknown", f"'{part}' has no choice '{choice}' in the ramp table (its choices: {known})",
                           "kiripix describe project")
        if part in parts:
            return Problem("npc.colours_invalid", f"'{part}' is given two choices", _set(run, COLOURS, f"{part}={choice}"))
        parts.add(part)
    return None


def choose_needs_input(run: StageRun) -> NeedsInput | None:
    problem = _problem(run)
    if problem is None:
        return None
    return NeedsInput(problem.message, command=problem.fix, code=problem.code)


def _order(run: StageRun, asset_id: str, given: int | None) -> int:
    if given is not None:
        return given
    try:
        document: dict[str, Any] = json.loads((run.chosen[asset_id].built["sheet"] / SHEET_FILE).read_text(encoding="utf-8"))
        return int(document.get("order", DEFAULT_ORDER))
    except (OSError, ValueError, KeyError, TypeError):
        raise StageFailure(f"{asset_id} has no built sheet; run it again",
                           fix=f"kiripix run {asset_id} sheet --force") from None


def run_choose(run: StageRun) -> None:
    problem = _problem(run)
    if problem is not None:
        raise StageFailure(problem.message, code=problem.code, fix=problem.fix)
    assert run.base is not None
    stack = sorted(((_order(run, asset_id, given), asset_id) for asset_id, given, _ in
                    parse_wearables(run.params.get(WEARABLES, ""))))
    chosen = dict(parse_colours(run.params.get(COLOURS, "")) or [])
    colours: dict[str, Any] = {}
    for row in run.settings.get(RAMPS_SETTING) or []:  # in the table's row order, whatever order they were given in
        if row["name"] in chosen:
            name = chosen[row["name"]]
            colours[row["name"]] = {"choice": name, "rgb": [list(c) for c in row["choices"][name]]}
    document = {"schema_version": NPC_SCHEMA_VERSION, "base": run.base.asset_id,
                "wearables": [{"id": asset_id, "order": order} for order, asset_id in stack], "colours": colours}
    (run.output_dir / NPC_FILE).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    run.progress(1, 1, f"{len(stack)} Wearables, {len(colours)} colours")


def _read_choice(run: StageRun) -> dict[str, Any]:
    """The built `npc.json`; a file that isn't there or is of another format is a rebuild, not a silent pass."""
    return _read_choice_from(run.output_dir, f"kiripix run {run.asset_id} choose --force")


def _read_choice_from(folder: Path, rebuild: str) -> dict[str, Any]:
    try:
        document: dict[str, Any] = json.loads((folder / NPC_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise StageFailure(f"{NPC_FILE} can't be read; build it again", fix=rebuild) from None
    if not isinstance(document, dict) or document.get("schema_version") != NPC_SCHEMA_VERSION:
        raise StageFailure(f"{NPC_FILE} is not in format {NPC_SCHEMA_VERSION}; build it again", fix=rebuild)
    return document


def _without(run: StageRun, asset_id: str) -> str:
    kept = [f"{a}@{o}" if o is not None else a for a, o, _ in parse_wearables(run.params.get(WEARABLES, "")) if a != asset_id]
    return _set(run, WEARABLES, ",".join(kept))


def _colours_with(run: StageRun, part: str, choice: str | None) -> str:
    pairs = [(p, c) for p, c in parse_colours(run.params.get(COLOURS, "")) or [] if p != part]
    if choice is not None:
        pairs.append((part, choice))
    return _set(run, COLOURS, ",".join(f"{p}={c}" for p, c in pairs))


def _stack_frames(run: StageRun, document: dict[str, Any]) -> list[LayerFrame]:
    """Each Wearable of the choice in each frame of the base's `render`, with its pixels and those the order buries.

    The frames and depth passes are the `render` folders beside each `sheet` (`built` holds the Stages `choose` reads, and a
    re-render makes `sheet` stale, so `choose` is stale with it). The stack is the base, then the Wearables in `npc.json`'s order."""
    if run.base is None or "sheet" not in run.base.built:
        return []
    ids = [str(w["id"]) for w in document.get("wearables", []) if str(w["id"]) in run.chosen and "sheet" in run.chosen[str(w["id"])].built]
    folders = {asset_id: run.chosen[asset_id].built["sheet"].parent / "render" for asset_id in ids}
    return stack_frames(run.base.built["sheet"].parent / "render", folders, run.check_cancel)


def stack_frames(base_folder: Path, folders: dict[str, Path], check_cancel: Callable[[], None],
                 read: Callable[[Path, dict[str, str]], Any] = read_render_frame) -> list[LayerFrame]:
    """The layers of `_stack_frames` from the `render` folders themselves: the base's, and each Wearable's by ID in stack order.
    The bulk maker (ticket 0359) judges a choice with it before anything is built, so there is one stacking code; `read` may
    be a caching reader."""
    base, worn = render_frames(base_folder), {asset_id: render_frames(folder) for asset_id, folder in folders.items()}
    found: list[LayerFrame] = []
    if not base or not any(worn.values()):
        return found
    for key in sorted(base):
        clip, direction, index = key
        layers_read = [("", read(base_folder, base[key]))]  # the base is layer "", the Wearables follow in stack order
        layers_read += [(a, read(folders[a], frames[key])) for a, frames in worn.items() if key in frames]
        layers = [(a, p) for a, p in layers_read if p is not None]
        if len(layers) < 2 or any(p[0].shape != layers[0][1][0].shape for _, p in layers):
            continue  # a layer built for another cell is stale: `status` says so
        counts = buried_by_order([p[0] for _, p in layers], [p[1] for _, p in layers])
        found += [LayerFrame(wearable=a, clip=clip, direction=direction, index=index, opaque=o, buried=b)
                  for (a, _), (o, b) in zip(layers, counts, strict=True) if a]
        check_cancel()
    return found


def stack_findings(npc: str, base_folder: Path, folders: dict[str, Path], check_cancel: Callable[[], None], fix: str,
                   read: Callable[[Path, dict[str, str]], Any] = read_render_frame) -> list[Finding]:
    """`npc.stack` for a choice that isn't built yet: what `check_choose` would say of it (ticket 0359), each with `fix` (the bulk
    maker's is a re-roll)."""
    return check_npc_stack(npc, stack_frames(base_folder, folders, check_cancel, read), lambda _wearable: fix)


def on_top(npc: str, wearables: object, orders: dict[str, int], wearable: str) -> str:
    """The `set` that puts `wearable` over every other layer of the choice (one above the highest order), and leaves the
    other entries of the `wearables` value as they are: the fix of `npc.stack`."""
    top = max(orders.values(), default=0) + 1
    entries = [f"{a}@{top}" if a == wearable else (f"{a}@{o}" if o is not None else a) for a, o, _ in parse_wearables(wearables)]
    return f"kiripix set {npc} choose {WEARABLES}={','.join(entries)}"


def check_choose(run: StageRun) -> list[Finding]:
    """The Checks on `choose` (ticket 0357): `npc.wearable_body`, `npc.colour_choice`, `npc.part_unset` and `npc.stack`.

    They read `npc.json` against the Project now: a Wearable listed in it that is still chosen, the ramp table, the built
    `render` frames of the base and the Wearables. Everything outside the Asset's own folder is in the Check cache's key (the
    base's, the chosen Wearables' folders and `kiripix.toml`), so the Stage declares no `check_reads`. `npc.slot_twice` is left out:
    a Wearable has no slot."""
    document = _read_choice(run)
    base = run.base.asset_id if run.base is not None else str(document.get("base", ""))
    listed = [str(w["id"]) for w in document.get("wearables", [])]
    worn = [(a, run.chosen[a].body) for a in listed if a in run.chosen]  # one no longer chosen is a stale choice: `status` says so
    table: dict[str, dict[str, Any]] = {str(r["name"]): dict(r.get("choices") or {}) for r in run.settings.get(RAMPS_SETTING) or []}
    built = {str(p): (str(c["choice"]), [list(x) for x in c["rgb"]]) for p, c in document.get("colours", {}).items()}
    orders = {str(w["id"]): int(w["order"]) for w in document.get("wearables", [])}
    return [
        *check_wearable_body(run.asset_id, base, worn, {a: _without(run, a) for a in listed}),
        *check_colour_choice(run.asset_id, built, table, {p: _colours_with(run, p, None) for p in built},
                             f"kiripix run {run.asset_id} choose"),
        *check_part_unset(run.asset_id, list(built), table,
                          {p: _colours_with(run, p, next(iter(c))) for p, c in table.items() if c}),
        *check_npc_stack(run.asset_id, _stack_frames(run, document),
                         lambda w: on_top(run.asset_id, run.params.get(WEARABLES, ""), orders, w)),
    ]


def run_npc_export(run: StageRun) -> None:
    """The `export` Stage (ticket 0358): `choose`'s `npc.json`, checked and copied to `out/export/`. The paths the game finds the
    base's and the Wearables' exports at depend on the export root, so `kiripix.export` adds them and writes the game's file."""
    document = _read_choice_from(run.upstream["choose"], f"kiripix run {run.asset_id} choose --force")
    (run.output_dir / NPC_FILE).write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


NPC = KindSpec(
    name="npc",
    description="A background figure: a base body, some of the Wearables rendered on it and a named colour choice per part. "
                "Nothing renders; the game draws the base's and the Wearables' own exports.",
    params=(
        ParamSpec(name=BASE_PARAM, type="str", required=True,
                  description="The character this figure is made of (its ID, such as character.body_m; ADR 0015). It has no base "
                              "of its own, and a re-render of it makes the NPC stale. An NPC never changes the base's clips, "
                              "height, camera or cell."),
    ),
    takes_base=True,
    base_kind="character",
    base_refusal="npc.base_unknown",
    stages=chain(
        StageSpec(
            name="choose",
            description="The NPC's Wearables, their stacking order and one colour choice per part, written as npc.json. The "
                        "choice is these parameters; nothing is drawn. `preview --stage choose` shows the stacked, swapped figure.",
            inputs=StageInputs(settings=[RAMPS_SETTING], base=BaseInputs(built=READS),
                               chosen=ChosenInputs(param=WEARABLES, built=READS)),
            params=(
                ParamSpec(name=WEARABLES, type="str", default="",
                          description="The Wearables worn, comma-separated IDs such as wearable.hair_a,wearable.coat. They stack "
                                      "over the base by their own `order` (ties by ID); `id@25` gives this NPC another order "
                                      "for that Wearable. Each is worn on the base."),
                ParamSpec(name=COLOURS, type="str", default="",
                          description="One colour choice per part, `part=choice` pairs comma-separated, such as "
                                      "hair=auburn,top=red: a part of the Project's ramp table and the name of one of its "
                                      "`choices`. A part not named keeps the colours it was built with."),
            ),
            run=run_choose,
            check=check_choose,
            checks=(
                CheckSpec(code="npc.wearable_body", description="Error: a Wearable the built choice lists is worn on another body "
                                                                 "than the NPC's base. Its fix takes it out of the choice."),
                CheckSpec(code="npc.colour_choice", description="Error: a Part's built colour is no longer one of its choices in "
                                                                "the ramp table (the Part, the choice or its ramp changed)."),
                CheckSpec(code="npc.part_unset", description="Info: a Part with choices that the NPC keeps as it was built."),
                CheckSpec(code="npc.stack", description="Warning: a Wearable the order buries but the depth puts in front, in most "
                                                        "of its frames."),
            ),
            needs_input=choose_needs_input,
            preview_figure=True,
            available_from="M6",
        ),
        StageSpec(
            name="export",
            description="The NPC's appearance file for the game: its base, its Wearables in stack order with their exported "
                        "paths, and its colours by part with their ramps (ticket 0358).",
            inputs=StageInputs(upstream=["choose"], settings=["export.godot"]),
            checks=(CheckSpec(code="export.no_target", description="The export target is set."),
                    CheckSpec(code="npc.base_not_exported",
                              description="The base has been exported to the game (checked when exporting; one exported in the "
                                          "same call counts)."),
                    CheckSpec(code="npc.wearable_not_exported",
                              description="Each Wearable has been exported to the game (checked when exporting; one exported "
                                          "in the same call counts).")),
            output_root="out",
            available_from="M6",
            run=run_npc_export,
            needs_input=export_needs_input,
            check=check_character_export,
        ),
    ),
)

__all__ = ["NPC", "NPC_FILE", "NPC_SCHEMA_VERSION", "parse_colours", "parse_wearables", "stack_findings"]
