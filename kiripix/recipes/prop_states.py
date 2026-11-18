"""A Prop's states (ticket 0257, 0258): a bin standing, toppled, dented.

The picked Source is the **default state**, whose ID is the brief's `state` (default `default`). Every other state is
declared on the `source` Stage by a `state` Decision (an ID and a size), gets its Variants with `import --state` (stored in
`src/states/<folder>/`) and its Source with `pick --state`. A state is not an edit of the default, so a new default Source
doesn't touch it. Each Stage after `source` runs once per state (0259): the default state's outputs are where
they always were, a state's are under `states/<id>/` in the Stage's output folder (`STATES_OUT`), and a Stage finds its
states by the folders of its upstream's output (`state_ids`).

A state's ID is its name in the game, frozen at its first export (ADR 0003). `state_remove` and `state_rename` change it
before that. They are replayed by `apply_edits` (`StageSpec.decisions_view`), the way a Loop's are: a rename keeps the
folder the Variants were imported into (`folder`), because a rename moves no file.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position
from kiripix.recipes.base import CheckSpec, CurrentDecision, DecisionSpec, NeedsInput, StageFailure, StageRun

SOURCE_STAGE = "source"
BRIEF_STAGE = "brief"
STATES_DIR = "src/states"  # a Prop's other states' Variants: `src/states/<folder>/<hash>.png`
STATES_OUT = "states"  # in a Stage's output folder: `states/<id>/<the Stage's files>`
STATE_RECORD = "state.json"  # `source` records a state's size here; `cutout` passes it on to `fit`
DEFAULT_STATE = "default"
STATE_ID = "^[a-z][a-z0-9]*(_[a-z0-9]+)*$"  # snake_case

_ID: dict[str, Any] = {"type": "string", "pattern": STATE_ID}

STATE = DecisionSpec(
    name="state",
    description="Declare another state of the Prop (a bin toppled): `id` is its name in the game, lower-case snake_case, "
                "unique among the Prop's states and never the default state's (the brief's `state`), frozen at its first "
                "export; `width` and `height` are its size in px, within the project's resolution. Import its image with "
                "`kiripix import <asset> <png> --state <id>` and pick it with `kiripix pick <asset> <variant> --state <id>`.",
    entry_schema={"type": "object",
                  "properties": {"id": _ID, "width": {"type": "integer", "minimum": 1},
                                 "height": {"type": "integer", "minimum": 1}},
                  "required": ["id", "width", "height"], "additionalProperties": False},
)

STATE_REMOVE = DecisionSpec(
    name="state_remove",
    description="Take a state away: it and every Decision before this one that names it stop applying (its imported "
                "Variants stay in `src/states/`). Refused for a state the game's Manifest lists (its ID is frozen). Undo "
                "brings it back.",
    entry_schema={"type": "object", "properties": {"id": _ID}, "required": ["id"], "additionalProperties": False},
)

STATE_RENAME = DecisionSpec(
    name="state_rename",
    description="Give a state another ID, `to` (free among the Prop's states, and not the default's). Refused for a state "
                "the game's Manifest lists (its ID is frozen). Undo brings the old ID back.",
    entry_schema={"type": "object", "properties": {"id": _ID, "to": _ID}, "required": ["id", "to"],
                  "additionalProperties": False},
)

STATE_PICK = DecisionSpec(
    name="state_pick",
    description="Choose one Variant (`src/states/<state>/<variant>.png`) as a state's Source. "
                "`kiripix pick <asset> <variant> --state <id>` records it.",
    entry_schema={"type": "object", "properties": {"state": _ID, "variant": {"type": "string"}},
                  "required": ["state", "variant"], "additionalProperties": False},
)

STATE_OFFSET = DecisionSpec(
    name="state_offset",
    description="Where a state's crop starts in `downscale` mode, in Source pixels from the top left (the `fit` "
                "parameters `offset_x` and `offset_y` are the default state's). The latest one of a state counts.",
    entry_schema={"type": "object",
                  "properties": {"state": _ID, "offset_x": {"type": "integer", "minimum": 0},
                                 "offset_y": {"type": "integer", "minimum": 0}},
                  "required": ["state", "offset_x", "offset_y"], "additionalProperties": False},
)

DECISIONS = (STATE, STATE_REMOVE, STATE_RENAME, STATE_PICK)
EDITS = (STATE_REMOVE.name, STATE_RENAME.name)

CHECKS = (
    CheckSpec(code="prop.state_unknown", description="Every state a Variant or Pick names is declared (a `state` Decision)."),
    CheckSpec(code="prop.state_unpicked", description="Every declared state has a picked Variant (needs-input)."),
    CheckSpec(code="prop.state_duplicate", description="A state's ID is its Prop's only once, and isn't the default's."),
)


@dataclass(frozen=True)
class DeclaredState:
    """A declared state as the Stage reads it: its size, and the folder under `src/states/` holding its Variants."""

    id: str
    width: int
    height: int
    folder: str


def _key(decision: CurrentDecision) -> str | None:
    value = decision.data.get("id" if decision.name in (STATE.name, STATE_REMOVE.name, STATE_RENAME.name) else "state")
    return value if isinstance(value, str) else None


def apply_edits(decisions: tuple[CurrentDecision, ...]) -> tuple[CurrentDecision, ...]:
    """The Decisions with each `state_remove` and `state_rename` replayed in order (`StageSpec.decisions_view`): a remove
    drops the state's earlier Decisions, a rename gives them the new ID, and neither is in the result. A renamed `state`
    keeps its Variants' folder under `folder`."""
    kept: list[CurrentDecision] = []
    for decision in decisions:
        if decision.name == STATE_REMOVE.name:
            kept = [d for d in kept if _key(d) != decision.data["id"]]
        elif decision.name == STATE_RENAME.name:
            old, new = decision.data["id"], decision.data["to"]
            renamed: list[CurrentDecision] = []
            for d in kept:
                if _key(d) != old:
                    renamed.append(d)
                elif d.name == STATE.name:
                    renamed.append(replace(d, data={**d.data, "id": new, "folder": d.data.get("folder", old)}))
                else:
                    renamed.append(replace(d, data={**d.data, "state": new}))
            kept = renamed
        else:
            kept.append(decision)
    return tuple(kept)


def declared_states(decisions: tuple[CurrentDecision, ...]) -> dict[str, DeclaredState]:
    """The Prop's declared states by ID, in declaration order, from Decisions as the Stage reads them."""
    found: dict[str, DeclaredState] = {}
    for d in decisions:
        if d.name == STATE.name:
            found[str(d.data["id"])] = DeclaredState(str(d.data["id"]), int(d.data["width"]), int(d.data["height"]),
                                                     str(d.data.get("folder", d.data["id"])))
    return found


def state_picks(decisions: tuple[CurrentDecision, ...]) -> dict[str, str]:
    """Each state's picked Variant, the latest Pick of a state counting."""
    return {str(d.data["state"]): str(d.data["variant"]) for d in decisions if d.name == STATE_PICK.name}


def default_state(run: StageRun) -> str:
    """The default state's ID: the brief's `state`, which `brief.json` records only when it isn't `default`."""
    path = run.upstream[BRIEF_STAGE] / "brief.json" if BRIEF_STAGE in run.upstream else None
    if path is None or not path.is_file():
        return DEFAULT_STATE
    return str(json.loads(path.read_text(encoding="utf-8")).get("state", DEFAULT_STATE))


def state_files(run: StageRun) -> dict[str, dict[str, Path]]:
    """The Variants of each folder of `src/states/`, by Variant name."""
    found: dict[str, dict[str, Path]] = {}
    for name, path in run.files.items():
        parts = name.split("/")
        if len(parts) == 4 and name.startswith(STATES_DIR + "/"):
            found.setdefault(parts[2], {})[Path(parts[3]).stem] = path
    return found


def top_files(run: StageRun) -> StageRun:
    """The run as the default state's Source reads it: `src/<hash>.png` only, not a state's Variants."""
    return replace(run, files={n: p for n, p in run.files.items() if not n.startswith(STATES_DIR + "/")})


def state_needs_input(run: StageRun) -> NeedsInput | None:
    """Why a declared state holds the `source` Stage back: it is the default's ID, or it has no Source picked."""
    declared = declared_states(run.decisions)
    if not declared:
        return None
    default = default_state(run)
    if default in declared:
        return NeedsInput(f"the state {default} is the default state's ID", code="prop.state_duplicate",
                          owner_action=f"Rename the state (kiripix decide {run.asset_id} source --decision "
                                       f"'{json.dumps({'decision': STATE_RENAME.name, 'data': {'id': default, 'to': 'other'}})}')"
                                       f", or give the default state another ID (kiripix set {run.asset_id} brief state=<id>).")
    picks, files = state_picks(run.decisions), state_files(run)
    for state in declared.values():
        found = sorted(files.get(state.folder, {}))
        chosen = picks.get(state.id)
        if chosen is not None and chosen in found:
            continue
        reason = (f"no Source is picked for the state {state.id}" if chosen is None
                  else f"the picked Variant {chosen} of the state {state.id} was deleted")
        if not found:
            return NeedsInput(reason, code="prop.state_unpicked",
                              command=f"kiripix import {run.asset_id} <file> --state {state.id}")
        if len(found) == 1:
            return NeedsInput(reason, code="prop.state_unpicked",
                              command=f"kiripix pick {run.asset_id} {found[0]} --state {state.id}")
        return NeedsInput(reason, code="prop.state_unpicked",
                          owner_action=f"Pick one of the Variants {', '.join(found)}: "
                                       f"kiripix pick {run.asset_id} <variant> --state {state.id}")
    return None


def declare_command(asset: str, state: str, width: int, height: int) -> str:
    """The `decide` that declares a state."""
    entry = json.dumps({"decision": STATE.name, "data": {"id": state, "width": width, "height": height}})
    return f"kiripix decide {asset} {SOURCE_STAGE} --decision '{entry}'"


def edit_problems(asset: str, decisions: tuple[CurrentDecision, ...], default: str, resolution: tuple[int, int],
                  documents: list[tuple[str, dict[str, Any]]], size: tuple[int, int]) -> tuple[list[Finding], list[str]]:
    """What refuses a state Decision before it is recorded, in order: `decisions` are the `source` Decisions as the Stage
    reads them, `default` the default state's ID, `resolution` the project's, `size` the brief's (for a fix). Also gives
    the states removed or renamed, for the ID freeze."""
    where = Position(asset=asset, stage=SOURCE_STAGE)
    states = set(declared_states(decisions))
    found: list[Finding] = []
    edited: list[str] = []
    for name, data in documents:
        if name == STATE.name and isinstance(data.get("id"), str):
            new = str(data["id"])
            if new == default or new in states:
                found.append(Finding(
                    code="prop.state_duplicate",
                    message=f"{asset} has a state {new} already" if new in states else
                            f"{new} is the default state's ID (the brief's `state`), so it isn't another state",
                    position=where, owner_action=f"Give the state an ID the Prop doesn't have (not {default}, not "
                                                 f"{', '.join(sorted(states)) or 'a declared one'})."))
            elif int(data.get("width", 1)) > resolution[0] or int(data.get("height", 1)) > resolution[1]:
                found.append(Finding(
                    code="prop.state_larger_than_resolution",
                    message=f"the state {new}'s size {data.get('width')}x{data.get('height')} is larger than the "
                            f"project's resolution {resolution[0]}x{resolution[1]}",
                    position=where, fix=declare_command(asset, new, min(int(data["width"]), resolution[0]),
                                                        min(int(data["height"]), resolution[1]))))
            states.add(new)
        elif name in (STATE_REMOVE.name, STATE_RENAME.name, STATE_PICK.name):
            state = data.get("id" if name != STATE_PICK.name else "state")
            if not isinstance(state, str):
                continue  # the Decision's schema refuses it
            if state not in states:
                found.append(Finding(
                    code="prop.state_unknown", message=f"{asset} has no state {state}"
                    + (f"; its states are {', '.join(sorted(states))}" if states else ""), position=where,
                    fix=declare_command(asset, state, size[0], size[1]) if name == STATE_PICK.name else None,
                    owner_action=None if name == STATE_PICK.name else f"Declare it first, or use one of its states."))
                continue
            if name == STATE_PICK.name:
                continue
            edited.append(state)
            states.discard(state)
            if name == STATE_RENAME.name:
                new = str(data.get("to"))
                if new == state:
                    found.append(Finding(code="prop.state_duplicate", message=f"the state {state} is renamed to its own ID",
                                         position=where, owner_action="Give the state another ID, or leave it."))
                elif new == default or new in states:
                    found.append(Finding(
                        code="prop.state_duplicate",
                        message=f"{asset} has a state {new} already" if new in states else
                                f"{new} is the default state's ID, so it isn't another state",
                        position=where, owner_action=f"Rename {state} to an ID the Prop doesn't have."))
                states.add(new)
    return found, edited


# the Stages per state (ticket 0259)


def write_state_sources(run: StageRun) -> None:
    """`source`: each declared state's picked Variant, as `states/<id>/source.png`, with its size in `state.json`."""
    picks, files = state_picks(run.decisions), state_files(run)
    for state in declared_states(run.decisions).values():
        chosen = picks[state.id]  # `state_needs_input` holds the Stage back until each has one
        path = files[state.folder][chosen]
        if not hashlib.sha256(path.read_bytes()).hexdigest().startswith(chosen):
            raise StageFailure(f"the Variant {path.name} of the state {state.id} was changed after it was imported, and "
                               "Variants are immutable; import the changed image as a new Variant and pick that")
        folder = run.output_dir / STATES_OUT / state.id
        folder.mkdir(parents=True)
        shutil.copyfile(path, folder / "source.png")
        (folder / STATE_RECORD).write_text(json.dumps({"width": state.width, "height": state.height}) + "\n",
                                           encoding="utf-8")


def state_ids(upstream: Path) -> list[str]:
    """The states a Stage's upstream built: the folders under `states/` in its output, in name order."""
    folder = upstream / STATES_OUT
    return sorted(p.name for p in folder.iterdir() if p.is_dir()) if folder.is_dir() else []


def state_size(upstream: Path, state: str) -> tuple[int, int]:
    """A state's declared size, from the `state.json` that `cutout` carried through."""
    record = json.loads((upstream / STATES_OUT / state / STATE_RECORD).read_text(encoding="utf-8"))
    return int(record["width"]), int(record["height"])


def state_view(run: StageRun, state: str) -> StageRun:
    """The run as a state's Stage reads it: it writes under `states/<id>/` and reads that folder of each upstream output
    (the `brief` has none), so the Stage's own function does the work unchanged."""
    out = run.output_dir / STATES_OUT / state
    out.mkdir(parents=True, exist_ok=True)
    upstream = {name: path if name == BRIEF_STAGE else path / STATES_OUT / state for name, path in run.upstream.items()}
    return replace(run, output_dir=out, upstream=upstream)


def each_state(run: StageRun, main: str, function: Callable[[StageRun], None]) -> None:
    """Run `function` for the default state, then for each state of the `main` upstream's output, checking for a cancel
    between states."""
    function(run)
    for state in state_ids(run.upstream[main]):
        run.check_cancel()
        function(state_view(run, state))


def about_state(findings: list[Finding], state: str) -> list[Finding]:
    """A state's findings, saying which state they are about (in the message and as `position.state`), and in which of
    the Stage's files."""
    for finding in findings:
        finding.message = f"the state {state}: {finding.message}"
        if finding.position is None:
            finding.position = Position(state=state)
        else:
            finding.position.state = state
            if finding.position.file is not None:
                finding.position.file = f"{STATES_OUT}/{state}/{finding.position.file}"
    return findings


def check_each_state(run: StageRun, check: Callable[[StageRun], list[Finding]]) -> list[Finding]:
    """The Stage's Checks for the default state, then for each state its output holds."""
    findings = check(run)
    for state in state_ids(run.output_dir):
        findings += about_state(check(state_view(run, state)), state)
    return findings


def state_offsets(run: StageRun, state: str) -> tuple[int, int] | None:
    """A state's own crop offsets (`state_offset`), the latest counting; None when it has none: the Stage's count."""
    found = [d for d in run.decisions if d.name == STATE_OFFSET.name and d.data.get("state") == state]
    return (int(found[-1].data["offset_x"]), int(found[-1].data["offset_y"])) if found else None
