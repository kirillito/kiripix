"""NPCs in bulk from a seed (ticket 0359, ADR 0015, spec §6.3): `new npc <prefix> --base … --count N --seed S` and
`new npc <id> --reroll`.

A crowd is N ordinary `npc` Assets, `<prefix>_01` … `<prefix>_NN`; nothing about the crowd is stored. What makes it a crowd
is the ID pattern, which `status --match 'npc.<prefix>_*'` and `cast-sheet --match` already read. Each NPC's choice is written
the way a person writes it, as `choose`'s `wearables` and `colours` parameters (`kiripix set`).

**What is picked from** is the command's flags, defaulting to every Wearable worn on the base and every named colour choice of
every Part of the ramp table. A Wearable has no slot (only an `order`), so "one per slot" can't hold: each NPC wears a random
subset of the allowed Wearables (a count from none to all, then that many chosen), stacked by their `order`. Each Part that has
choices gets one of its allowed choices. `--choices hair=auburn,blond` narrows that Part; Parts not named stay open.

**Same seed, same Project, same NPCs.** Every pick draws from `random.Random` seeded by a string of the seed, the base, the
prefix, the NPC's number and the try, over lists sorted by ID or name or in the ramp table's row order: no dict or set
order, no filesystem order, no hash seed. An NPC's pick doesn't depend on how many follow it.

**Passing the Checks.** A pick is judged by 0357's own pure functions (`check_wearable_body`, `check_colour_choice`, and
`stack_findings` for `npc.stack`), before anything is made, so the Assets need no build of `choose` and the Wearables'
sheets need not exist: the choice is parameters. `npc.stack` reads the `render` folders of the base and the Wearables, as the
Check does, and is silent for what is not rendered; the result then says so (`new.crowd_stack_unchecked`, info). A pick
with an error or an `npc.stack` warning is re-picked, up to `MAX_TRIES` times; a pick equal to another NPC on the same base is
re-picked the same way. If no try passes, the best one is kept and a warning `new.crowd_unsatisfied` names what failed.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

from kiripix.checks import Finding, Position, check_colour_choice, check_wearable_body
from kiripix.core import editing
from kiripix.core.assets import Asset, check_base, create_asset, list_assets, load_asset, parse_asset_id
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.recipes.npc import COLOURS, WEARABLES, parse_colours, parse_wearables, stack_findings
from kiripix.recipes.wearable_stack import read_render_frame
from kiripix.recipes.wearable_sheet import DEFAULT_ORDER

MAX_TRIES = 12  # picks tried for one NPC before the best is kept with a finding
KIND = "npc"
STAGE = "choose"

Ramp = list[list[int]]


@dataclass(frozen=True)
class Choice:
    """One NPC's choice: Wearable IDs in stack order, and (Part, choice) pairs in the ramp table's row order."""

    wearables: tuple[str, ...]
    colours: tuple[tuple[str, str], ...]

    @property
    def key(self) -> tuple[tuple[str, ...], tuple[tuple[str, str], ...]]:
        return tuple(sorted(self.wearables)), tuple(sorted(self.colours))

    def assignments(self) -> list[str]:
        return [f"{WEARABLES}={','.join(self.wearables)}", f"{COLOURS}={','.join(f'{p}={c}' for p, c in self.colours)}"]


@dataclass(frozen=True)
class Allowed:
    wearables: tuple[str, ...]  # sorted by ID
    parts: tuple[tuple[str, tuple[str, ...]], ...]  # (Part, its allowed choice names sorted), in the ramp table's row order


@dataclass
class Made:
    asset: str
    choice: Choice
    tries: int
    changed: bool = True


@dataclass
class CrowdResult:
    members: list[Made] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    created: list[str] = field(default_factory=list)


def _table(project: Project) -> list[tuple[str, dict[str, Ramp]]]:
    return [(row.name, {name: [list(c) for c in ramp] for name, ramp in row.choices.items()})
            for row in project.settings.character.ramps]


def _listed(text: str) -> list[str]:
    return [part.strip() for part in text.split(",") if part.strip()]


def allowed_choices(project: Project, base: str, wearables: str | None, choices: Sequence[str] | None) -> Allowed:
    """What a pick may use: the flags, or by default every Wearable on `base` and every choice of every Part."""
    on_base = sorted(a.id for a in list_assets(project)[0] if a.settings.params.get("body") == base and a.kind == "wearable")
    if wearables is None:
        worn = tuple(on_base)
    else:
        patterns = _listed(wearables)
        unmatched = [p for p in patterns if not any(fnmatchcase(w, p) for w in on_base)]
        if unmatched or not patterns:
            known = ", ".join(on_base) or "none"
            raise fail("new.crowd_wearables_unknown",
                       f"--wearables {', '.join(unmatched) or '(empty)'} matches no Wearable worn on {base} (its Wearables: {known})",
                       fix="kiripix status --kind wearable")
        worn = tuple(w for w in on_base if any(fnmatchcase(w, p) for p in patterns))
    table = _table(project)
    narrowed: dict[str, list[str]] = {}
    for item in choices or []:
        part, equals, names = item.partition("=")
        row = dict(table).get(part.strip())
        wanted = _listed(names)
        if not equals or not wanted:
            raise fail("new.crowd_choice_unknown", f"--choices '{item}' is not part=a,b", fix="kiripix describe project")
        if not row:
            raise fail("new.crowd_choice_unknown", f"--choices: '{part.strip()}' is not a Part of the ramp table with choices "
                       f"({', '.join(p for p, c in table if c) or 'none have any'})", fix="kiripix describe project")
        if part.strip() in narrowed:
            raise fail("new.crowd_choice_unknown", f"--choices names '{part.strip()}' twice", fix="kiripix describe project")
        missing = [n for n in wanted if n not in row]
        if missing:
            raise fail("new.crowd_choice_unknown", f"--choices: '{part.strip()}' has no choice {', '.join(missing)} "
                       f"(its choices: {', '.join(sorted(row))})", fix="kiripix describe project")
        narrowed[part.strip()] = sorted(set(wanted))
    parts = tuple((part, tuple(narrowed.get(part, sorted(row)))) for part, row in table if row)
    return Allowed(worn, parts)


def _order(asset: Asset) -> int:
    """The Wearable's stacking order for its next build: its `sheet` parameter `order`."""
    value = asset.settings.stages.get("sheet", {}).get("order", DEFAULT_ORDER)
    return value if isinstance(value, int) and not isinstance(value, bool) else DEFAULT_ORDER


def _pick(rng: random.Random, allowed: Allowed, orders: Mapping[str, int]) -> Choice:
    count = rng.randint(0, len(allowed.wearables))
    worn = sorted(rng.sample(list(allowed.wearables), count), key=lambda w: (orders[w], w))
    colours = tuple((part, rng.choice(names)) for part, names in allowed.parts)
    return Choice(tuple(worn), colours)


def _read_choice(asset: Asset) -> Choice:
    params = asset.settings.stages.get(STAGE, {})
    return Choice(tuple(a for a, _, _ in parse_wearables(params.get(WEARABLES, ""))),
                  tuple(sorted(parse_colours(params.get(COLOURS, "")) or [])))


class _Judge:
    """0357's Checks on a pick that isn't built: the same pure functions, over what the Project holds now."""

    def __init__(self, project: Project, base: str, table: list[tuple[str, dict[str, Ramp]]], check_cancel: Callable[[], None]):
        self.project, self.base, self.table, self.check_cancel = project, base, dict(table), check_cancel
        cache = HashCache(project.state_dir)
        self.render: dict[str, Path] = {}
        self.assets: dict[str, Asset] = {}
        self._cache = cache
        self._memo: dict[Any, list[Finding]] = {}
        self._frames: dict[Any, Any] = {}
        self.unrendered: list[str] = []

    def _folder(self, asset: Asset) -> Path | None:
        graph = AssetGraph(self.project, asset, self._cache)
        folder = graph.output_dir(graph.spec("render"))
        return folder if (folder / "render.json").is_file() else None

    def prepare(self, wearables: Sequence[str]) -> None:
        for asset_id in (self.base, *wearables):
            asset = load_asset(self.project, asset_id)
            self.assets[asset_id] = asset
            folder = self._folder(asset)
            if folder is None:
                self.unrendered.append(asset_id)
            else:
                self.render[asset_id] = folder

    def _read(self, folder: Path, files: dict[str, str]) -> Any:
        key = (folder, tuple(sorted(files.items())))
        if key not in self._frames:
            self._frames[key] = read_render_frame(folder, files)
        return self._frames[key]

    def __call__(self, npc: str, choice: Choice) -> list[Finding]:
        """The errors and `npc.stack` warnings of the pick; `npc.part_unset` is information, never a reason to re-pick."""
        if choice.key in self._memo:
            return self._memo[choice.key]
        again = f"kiripix new npc {npc} --reroll"
        worn = [(w, self.assets[w].settings.params.get("body")) for w in choice.wearables]
        built = {p: (c, self.table[p][c]) for p, c in choice.colours}
        findings = [
            *check_wearable_body(npc, self.base, [(w, str(b) if b is not None else None) for w, b in worn],
                                 {w: again for w, _ in worn}),
            *check_colour_choice(npc, built, self.table, {p: again for p, _ in choice.colours}, again),
        ]
        folders = {w: self.render[w] for w in choice.wearables if w in self.render}
        if self.base in self.render and folders:
            findings += stack_findings(npc, self.render[self.base], folders, self.check_cancel, again, self._read)
        self._memo[choice.key] = findings
        return findings


TWIN = "new.crowd_twin"  # a reason in `new.crowd_unsatisfied`'s `data.reasons`: the pick repeats another NPC's on the base


def _crowd_pick(*, judge: _Judge, allowed: Allowed, orders: Mapping[str, int], npc: str, label: str, taken: set[Any]) -> tuple[Choice, int, list[Finding]]:
    best: tuple[tuple[int, int], Choice, list[str]] | None = None
    for attempt in range(MAX_TRIES):
        rng = random.Random(f"kiripix-npc|{label}|{attempt}")
        choice = _pick(rng, allowed, orders)
        problems = judge(npc, choice)
        twin = choice.key in taken
        if not problems and not twin:
            return choice, attempt + 1, []
        reasons = [f.code for f in problems] + ([TWIN] if twin else [])  # finding codes, and TWIN for a repeat
        score = (len(problems), int(twin))
        if best is None or score < best[0]:
            best = (score, choice, reasons)
    assert best is not None
    _, choice, reasons = best
    said = ", ".join("the same choice as another NPC on this base" if r == TWIN else r for r in dict.fromkeys(reasons))
    finding = Finding(
        code="new.crowd_unsatisfied", severity="warning",
        message=f"{npc} could not be picked clean in {MAX_TRIES} tries; kept the closest ({said}); "
                "widen --wearables or --choices, or re-roll it",
        position=Position(asset=npc, stage=STAGE), fix=f"kiripix new npc {npc} --reroll",
        data={"tries": MAX_TRIES, "reasons": list(dict.fromkeys(reasons))})
    return choice, MAX_TRIES, [finding]


def _unchecked(judge: _Judge, base: str) -> list[Finding]:
    if not judge.unrendered:
        return []
    first = judge.unrendered[0]
    return [Finding(code="new.crowd_stack_unchecked", severity="info",
                    message=f"{', '.join(judge.unrendered)} has no built render, so `npc.stack` could not judge the stack of "
                            f"{base}'s crowd; the NPCs are made, and `kiripix check --match 'npc.*'` judges them once it is built",
                    fix=f"kiripix run {first} render")]


def _others(project: Project, base: str, skip: set[str]) -> set[Any]:
    return {_read_choice(a).key for a in list_assets(project)[0]
            if a.kind == KIND and a.id not in skip and a.settings.params.get("base") == base}


def make_crowd(project: Project, prefix: str, base: str, count: int, seed: int, wearables: str | None,
               choices: Sequence[str] | None, check_cancel: Callable[[], None]) -> CrowdResult:
    """Make `count` NPCs named `<prefix>_01`…, each picked by `seed` and judged by the Checks."""
    prefix = prefix.removeprefix(f"{KIND}.")
    width = max(2, len(str(count)))
    names = [f"{prefix}_{number:0{width}d}" for number in range(1, count + 1)]
    ids = [f"{KIND}.{n}" for n in names]
    for asset_id in ids:
        parse_asset_id(asset_id)  # a prefix that makes no ID is refused before anything is made
    taken_ids = [i for i in ids if (project.root / "assets" / KIND / i.split(".", 1)[1]).exists()]
    if taken_ids:
        raise fail("asset.duplicate_id", f"the Asset(s) {', '.join(taken_ids)} already exist; a crowd needs a prefix of its own",
                   fix=f"kiripix status --kind {KIND}")
    check_base(project, KIND, ids[0], base, fix="kiripix status --kind character")
    allowed = allowed_choices(project, base, wearables, choices)
    judge = _Judge(project, base, _table(project), check_cancel)
    judge.prepare(allowed.wearables)
    orders = {w: _order(judge.assets[w]) for w in allowed.wearables}
    taken = _others(project, base, set())
    picked: list[tuple[str, Choice, int]] = []
    result = CrowdResult(findings=_unchecked(judge, base))
    for index, asset_id in enumerate(ids, start=1):
        check_cancel()
        label = f"{seed}|{base}|{prefix}|{index}"
        choice, tries, found = _crowd_pick(judge=judge, allowed=allowed, orders=orders, npc=asset_id, label=label, taken=taken)
        taken.add(choice.key)
        picked.append((asset_id, choice, tries))
        result.findings += found
    for asset_id, choice, tries in picked:  # everything is picked and checked: now write
        asset, created = create_asset(project, KIND, asset_id.split(".", 1)[1], {"base": base})
        result.created += created
        assignments = [a for a in choice.assignments() if not a.endswith("=")]
        if assignments:
            editing.set_params(project, asset, STAGE, assignments)
        result.members.append(Made(asset_id, choice, tries))
    return result


def reroll(project: Project, npc: str, seed: int | None, wearables: str | None, choices: Sequence[str] | None,
           check_cancel: Callable[[], None]) -> CrowdResult:
    """Pick one NPC's choice again, other than the one it has and those of the other NPCs on its base. Without a seed it is
    derived from the choice it has now, so the same command on the same NPC always gives the same next choice."""
    asset = load_asset(project, npc if "." in npc else f"{KIND}.{npc}")
    if asset.kind != KIND:
        raise fail("new.reroll_not_npc", f"{asset.id} is a {asset.kind}; only an npc can be re-rolled", fix=f"kiripix status --kind {KIND}")
    base = str(asset.settings.params.get("base", ""))
    current = _read_choice(asset)
    allowed = allowed_choices(project, base, wearables, choices)
    judge = _Judge(project, base, _table(project), check_cancel)
    judge.prepare(allowed.wearables)
    orders = {w: _order(judge.assets[w]) for w in allowed.wearables}
    taken = _others(project, base, {asset.id}) | {current.key}
    label = f"reroll|{seed}|{asset.id}" if seed is not None else f"reroll|{asset.id}|{current.key}"
    choice, tries, found = _crowd_pick(judge=judge, allowed=allowed, orders=orders, npc=asset.id, label=label, taken=taken)
    result = CrowdResult(findings=[*_unchecked(judge, base), *found])
    if choice.key == current.key:
        result.members.append(Made(asset.id, current, tries, changed=False))
        return result
    editing.set_params(project, asset, STAGE, choice.assignments())
    result.members.append(Made(asset.id, choice, tries))
    return result
