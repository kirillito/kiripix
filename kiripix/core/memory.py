"""What `serve` remembers of the Project (spec §10.6, ticket 0373): each Asset's derived state, worked out at most once.

`kiripix serve` is one long-lived process, and `status` and `queue` work every Asset out from scratch. A `Memory` keeps
what they work out, per Asset and per layer (`recall`), and the Project's Assets read from their `asset.toml` files
(`assets`). It is memory only, never a file (ADR 0005): the computation caches under it (`HashCache`, the Check cache)
stay as they are, and a process that ends loses nothing.

Never older than a change Kiripix recorded (`kiripix.core.changes`): every `status`, `queue` and list call first `sync`s,
reading the change files from where the last call stopped, so a write that was recorded before the call is seen by it,
whichever process wrote it. A recorded path drops what it touches:

- a path inside an Asset's folder drops that Asset's entries, every entry that read it (a base's characters and NPCs, an
  NPC's chosen Wearables, a Wearable's body, a body's Wearables), and, for a changed `asset.toml`, the entries of the Assets
  it names now and named before;
- a path outside `assets/<kind>/<name>/` (`kiripix.toml`, the palette, the style references, a file a Check reads) drops
  everything, as does a `refresh` token that is new (the UI's Reload and focus refresh, for a file changed outside Kiripix).

A computation that was running when anything dropped is not kept: its callers get their answer, the next call works it out
again. Two calls that need the same entry at once wait for one computation (single flight). When in doubt an entry is
dropped: the cost is a recomputation, never an old answer.
"""

import re
import threading
from collections.abc import Callable, Hashable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar, cast

from kiripix.checks import Finding
from kiripix.core import cancel, changes
from kiripix.core.assets import ASSET_FILE, Asset, load_listed
from kiripix.core.errors import KiripixError
from kiripix.core.kinds import all_kinds
from kiripix.core.project import Project

T = TypeVar("T")

_REFERENCE = re.compile(r"[a-z][a-z0-9_]*\.[a-z0-9_]+")
_WAIT_SECONDS = 0.05


def named_assets(asset: Asset) -> set[str]:
    """The IDs of the Assets that `asset`'s parameters name (a base, a body, the chosen Wearables, in `asset.toml`'s
    `[params]` or any Stage's table): what its Stages may read of other Assets. A word that looks like an ID but isn't an
    Asset is harmless here, a dependency on nothing."""
    values: list[object] = list(asset.settings.params.values())
    for table in asset.settings.stages.values():
        values.extend(table.values())
    kinds = all_kinds()
    found = {word for value in values if isinstance(value, str) for word in _REFERENCE.findall(value)
             if word.partition(".")[0] in kinds}
    found.discard(asset.id)
    return found


@dataclass
class _Entry:
    value: Any
    deps: frozenset[str]
    stamp: Hashable


@dataclass
class _Flight:
    stamp: Hashable
    done: threading.Event = field(default_factory=threading.Event)
    value: Any = None
    error: BaseException | None = None


class Memory:
    """The in-memory derived state of one Project, shared by the Commands `serve` runs on their job threads."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.RLock()
        self._sync_lock = threading.Lock()
        self._reader = changes.ChangeReader(root)
        self._values: dict[tuple[str, str], _Entry] = {}
        self._flights: dict[tuple[str, str], _Flight] = {}
        self._project: Project | None = None
        self._table: dict[tuple[str, str], Asset | list[Finding]] | None = None
        self._listed: tuple[list[Asset], list[Finding]] | None = None
        self._referrers: dict[str, set[str]] | None = None
        self._token: str | None = None

    # keeping in step

    def sync(self) -> None:
        """Read what Kiripix recorded since the last call and drop what it touches. Every call that answers from memory
        starts with this, so it sees every write recorded before it began."""
        with self._sync_lock:
            paths = self._reader.read()
            if paths:
                self._apply(paths)

    def refresh(self, token: str | None) -> None:
        """Forget everything when `token` is one this Memory hasn't seen. The UI makes up one token for each full refresh
        and sends it with every call of that refresh, so the first drops and the others (which may already be working
        something out) keep what they have. None: nothing."""
        if token is None:
            return
        with self._sync_lock:
            if token == self._token:
                return
            self._token = token
            self._drop_all()

    def forget(self, asset_ids: Iterable[str]) -> None:
        """Forget these Assets as if each had changed (its `asset.toml` read again, and every entry that reads it dropped):
        a refresh that must see a file changed outside Kiripix in the rows it shows, without forgetting the rest."""
        paths = [f"assets/{kind}/{name}/{ASSET_FILE}" for kind, dot, name in (a.partition(".") for a in asset_ids)
                 if dot and kind and name and "/" not in name]
        if paths:
            with self._sync_lock:
                self._apply(paths)

    def drop_all(self) -> None:
        with self._sync_lock:
            self._drop_all()

    def _drop_all(self) -> None:
        with self._lock:
            self._values.clear()
            self._flights.clear()
            self._table = None
            self._listed = None
            self._referrers = None

    def _apply(self, paths: Iterable[str]) -> None:
        touched: set[str] = set()
        members: set[tuple[str, str]] = set()
        for path in paths:
            parts = path.split("/")
            if parts[0] != "assets" or len(parts) < 3:  # the Project's own: anything may have read it
                self._drop_all()
                return
            touched.add(f"{parts[1]}.{parts[2]}")
            if len(parts) == 3 or parts[3] == ASSET_FILE:  # the Asset itself came, went or changed its parameters
                members.add((parts[1], parts[2]))
        with self._lock:
            self._flights.clear()  # what is being worked out may have read what changed
            named: set[str] = set()
            if self._table is not None and self._project is not None:
                for key in members:
                    named |= self._named(self._table.get(key))
                    found = self._read(self._project, *key)
                    if found is None:
                        self._table.pop(key, None)
                    else:
                        self._table[key] = found
                        named |= self._named(found)
                if members:
                    self._listed = None
                    self._referrers = None
            for key in [k for k, e in self._values.items() if k[1] in named or not touched.isdisjoint(e.deps)]:
                del self._values[key]

    @staticmethod
    def _named(found: Asset | list[Finding] | None) -> set[str]:
        return named_assets(found) if isinstance(found, Asset) else set()

    # the Assets

    @staticmethod
    def _read(project: Project, kind: str, name: str) -> Asset | list[Finding] | None:
        if not (project.root / "assets" / kind / name / ASSET_FILE).is_file():
            return None
        try:
            return load_listed(project, kind, name)
        except KiripixError as error:
            return list(error.findings)

    def _ensure_table(self, project: Project) -> dict[tuple[str, str], Asset | list[Finding]]:
        if self._table is None or self._project is None:
            self._project = project
            self._table = {}
            self._listed = None
            self._referrers = None
            for file in sorted((project.root / "assets").glob(f"*/*/{ASSET_FILE}")):
                key = (file.parent.parent.name, file.parent.name)
                found = self._read(project, *key)
                if found is not None:
                    self._table[key] = found
        return self._table

    def assets(self, project: Project) -> tuple[list[Asset], list[Finding]]:
        """Every Asset sorted by ID, and a finding for each that can't be read: what `list_assets` answers, read once and
        then kept in step with the Project's `asset.toml` files."""
        with self._lock:
            table = self._ensure_table(project)
            if self._listed is None:
                assets: list[Asset] = []
                findings: list[Finding] = []
                for key in sorted(table):
                    found = table[key]
                    if isinstance(found, Asset):
                        assets.append(found)
                    else:
                        findings.extend(found)
                self._listed = (assets, findings)
            assets, findings = self._listed
            return list(assets), list(findings)

    def _referrers_of(self, asset_id: str) -> set[str]:
        if self._referrers is None:
            index: dict[str, set[str]] = {}
            for found in (self._table or {}).values():
                if isinstance(found, Asset):
                    for target in named_assets(found):
                        index.setdefault(target, set()).add(found.id)
            self._referrers = index
        return self._referrers.get(asset_id, set())

    def _deps(self, asset: Asset) -> frozenset[str]:
        """What an entry of `asset` may read: the Asset, all it names directly or through what it names, and the Assets
        that name it (a body's Wearables)."""
        with self._lock:
            by_id = {f.id: f for f in (self._table or {}).values() if isinstance(f, Asset)}
            seen = {asset.id}
            stack = [asset]
            while stack:
                for target in named_assets(stack.pop()):
                    if target not in seen:
                        seen.add(target)
                        if target in by_id:
                            stack.append(by_id[target])
            return frozenset(seen | self._referrers_of(asset.id))

    # one computation per entry

    def recall(self, layer: str, asset: Asset, compute: Callable[[], T], *,
               stamp: Callable[[frozenset[str]], Hashable] | None = None) -> T:
        """The `layer` of `asset`'s derived state: what `compute` answered, kept until a change drops it.

        `stamp(deps)` is something outside the record that the answer also depends on, asked on every call (such as the
        game's Manifest files, which Kiripix doesn't record); an entry made under another stamp is worked out again. Two
        calls that need the same entry at once wait for one `compute`. A cancelled caller stops waiting."""
        key = (layer, asset.id)
        while True:
            with self._lock:
                entry = self._values.get(key)
                deps = entry.deps if entry is not None else self._deps(asset)
            now = stamp(deps) if stamp is not None else None
            with self._lock:
                entry = self._values.get(key)
                if entry is not None and entry.stamp == now:
                    return cast(T, entry.value)
                flight = self._flights.get(key)
                mine = flight is None or flight.stamp != now
                if mine:
                    flight = _Flight(now)
                    self._flights[key] = flight
            assert flight is not None
            if mine:
                return self._work(key, flight, deps, compute)
            while not flight.done.wait(_WAIT_SECONDS):
                cancel.check()
            if flight.error is None:
                return cast(T, flight.value)  # worked out after the last drop: as new as a call of its own would be
            # the one working it out failed or was cancelled: take it up

    def _work(self, key: tuple[str, str], flight: _Flight, deps: frozenset[str], compute: Callable[[], T]) -> T:
        try:
            value = compute()
        except BaseException as error:
            with self._lock:
                if self._flights.get(key) is flight:
                    del self._flights[key]
            flight.error = error
            flight.done.set()
            raise
        with self._lock:
            flight.value = value
            if self._flights.get(key) is flight:  # nothing dropped meanwhile
                del self._flights[key]
                self._values[key] = _Entry(value, deps, flight.stamp)
        flight.done.set()
        return value
