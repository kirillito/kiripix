"""The Check findings of a built Stage, kept until something the Check reads changes (ticket 0367, ADR 0005).

A Check reads a built output, and a built output doesn't change until its Stage runs again, so the same Check gives the same
findings until something it reads changes. This is the one place that reads and writes that cache, in `.kiripix/derived-cache.json`
(`HashCache.derived` / `remember`). It keeps a Check's own findings, never a status, and deleting `.kiripix/` loses nothing but
time. An entry that doesn't parse as today's `Finding` is a miss. The advisers (`graph._ADVISERS`) run after it on every call.

What the key holds, so a change to any of it is a miss:
- the Stage's output as built: its stamp's content, size and time (a rebuild with the same input hash still writes a new one) and
  every file in the folder by size and time (an output edited by hand, with no rebuild, is a miss); the same for each upstream
  Stage's output folder (a Check reads them through `StageRun.upstream`);
- the Stage's current input hash (parameters, Decisions, declared files, settings, Project files, base and body hashes);
- the Stage's `version` and the size and time of the source files its Checks can reach: the module that declares its Check, the Ops
  and the Checks (not every recipe, ticket 0372);
- the Asset's own folder, except the output folders (`work/`, `out/`) and its history: every file's size and time (a file
  changed less than two seconds ago is also kept by its content, which a hit checks, so a quick second write can't be missed);
- the whole folder of each Asset it is related to (its base, its body, the Wearables of a body, the Assets it chose);
- `kiripix.toml` and the palette file;
- what the Stage declares in `StageSpec.check_reads`, Project files by path (a folder stands for every file under it).

A Check that reads anything else must declare it in `check_reads`, or the Stage sets `check_cache=False`.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

from pydantic import ValidationError

import kiripix.checks as checks_package
import kiripix.ops as ops_package
from kiripix.checks import Finding
from kiripix.core.assets import HISTORY_FILE
from kiripix.core.hashing import HashCache, hash_bytes, hash_json

if TYPE_CHECKING:
    from kiripix.core.graph import AssetGraph
    from kiripix.recipes.base import StageSpec

_RACY_SECONDS = 2.0
_OUTPUT_ROOTS = frozenset({"work", "out"})


def _code(cache: HashCache, spec: StageSpec) -> list[list[Any]]:
    """The source files a Stage's Checks can reach, by name, size and time: the module that declares its Check (and its
    `check_reads`), the Checks and the Ops. Not every recipe (ticket 0372): an update that leaves this Stage's recipe alone keeps
    its findings. Worked out once per HashCache."""
    if "check-code" not in cache.memo:
        folders = [Path(p.__file__ or "").parent for p in (ops_package, checks_package)]
        cache.memo["check-code"] = [
            [f"{p.parent.name}/{p.name}", p.stat().st_size, p.stat().st_mtime_ns]
            for folder in folders for p in sorted(folder.rglob("*.py"))]
    modules: dict[str, list[Any]] = cache.memo.setdefault("check-modules", {})
    own: list[list[Any]] = []
    for function in (spec.check, spec.check_reads):
        name = getattr(function, "__module__", None)
        if name is None:
            continue
        if name not in modules:
            file = getattr(sys.modules.get(name), "__file__", None)
            stat = Path(file).stat() if file else None
            modules[name] = [name, stat.st_size, stat.st_mtime_ns] if stat else [name]
        own.append(modules[name])
    code: list[list[Any]] = cache.memo["check-code"]
    return [*code, *own]


def _tree(cache: HashCache, root: Path, *, outputs: bool) -> tuple[str, list[str]]:
    """The hash of every file under `root` by path, size and time, and the files changed within the last two seconds (a rewrite
    with the same size and time could be missed, so `keep` records their content too). `outputs=False` leaves out the Stages' output folders and the Asset's history. Worked out once for a
    folder per Command (`forget_trees` after a rebuild): a Stage's key reads the same body or upstream folder again and again."""
    trees: dict[tuple[str, bool], tuple[str, list[str]]] = cache.memo.setdefault("check-trees", {})
    memo_key = (str(root), outputs)
    if memo_key in trees:
        return trees[memo_key]
    now = time.time()
    found: list[list[Any]] = []
    recent: list[str] = []

    def walk(folder: str, prefix: str, top: bool) -> None:
        try:
            entries = sorted(os.scandir(folder), key=lambda e: e.name)  # DirEntry.stat is read with the listing on Windows
        except OSError:
            return
        for entry in entries:
            name = entry.name
            try:
                if entry.is_dir(follow_symlinks=False):
                    if not (top and not outputs and name in _OUTPUT_ROOTS):
                        walk(entry.path, f"{prefix}{name}/", False)
                    continue
                if top and not outputs and name == HISTORY_FILE:
                    continue
                stat = entry.stat()
                if now - stat.st_mtime < _RACY_SECONDS:
                    recent.append(entry.path)
                found.append([f"{prefix}{name}", stat.st_size, stat.st_mtime_ns])
            except OSError:
                found.append([f"{prefix}{name}", None, None])

    walk(str(root), "", True)
    trees[memo_key] = result = (hash_json(found), recent)
    return result


def forget_trees(cache: HashCache) -> None:
    """Forget the folders' hashes worked out so far, after a Stage rebuilt its output."""
    cache.memo.pop("check-trees", None)


def _settings_hash(graph: AssetGraph) -> str:
    if "check-settings" not in graph.cache.memo:
        graph.cache.memo["check-settings"] = hash_json(graph._settings)
    return str(graph.cache.memo["check-settings"])


def _stamp(graph: AssetGraph, spec: StageSpec) -> list[Any]:
    from kiripix.core.graph import STAMP_FILE

    path = graph.output_dir(spec) / STAMP_FILE
    try:
        stat = path.stat()
        return [hash_bytes(path.read_bytes()), stat.st_size, stat.st_mtime_ns]
    except OSError:
        return []


class Key(NamedTuple):
    """What the Check's findings are kept under: the hash of everything it reads, and the files among them changed in the last
    two seconds (`keep` records their content, `lookup` checks it)."""

    hash: str
    recent: list[str]


def _key(graph: AssetGraph, spec: StageSpec) -> Key:
    cache = graph.cache
    related: dict[str, Path] = {}
    if graph.base_asset is not None:
        related[graph.base_asset.id] = graph.base_asset.dir
    if graph.body is not None:
        related[graph.body.asset.id] = graph.body.asset.dir
    for asset_id, other in graph._chosen_graphs(spec).items():
        related[asset_id] = other.asset.dir
    if spec.worn_stage is not None:
        for wearable, output in graph._wearing(spec)[0].items():
            related[wearable] = output.parents[1]
    palette = graph.palette_path()
    reads: dict[str, str | None] = {}
    if spec.check_reads is not None:
        names = spec.check_reads(graph._run(spec, graph.output_dir(spec), None))
        files: dict[str, Path] = {}
        for name in names:
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError(f"the Check of '{spec.name}' names {name}, which is not a path inside the Project")
            files[name] = graph.project.root / name
        reads = graph._project_hashes(files)
    trees = {
        "output": _tree(cache, graph.output_dir(spec), outputs=True),  # an output edited by hand, with no rebuild, is a miss
        "asset": _tree(cache, graph.asset.dir, outputs=False),
        **{f"upstream:{name}": _tree(cache, graph.output_dir(graph.spec(name)), outputs=True) for name in spec.inputs.upstream},
        **{f"related:{name}": _tree(cache, folder, outputs=True) for name, folder in sorted(related.items())},
    }
    digest = hash_json({
        "code": _code(cache, spec), "kind": graph.kind.name, "stage": spec.name, "version": spec.version,
        "stamp": _stamp(graph, spec),
        "upstream": {name: _stamp(graph, graph.spec(name)) for name in spec.inputs.upstream},
        "trees": {name: found[0] for name, found in trees.items()},
        "input": graph.input_hash(spec.name),
        "settings": _settings_hash(graph),
        "palette": cache.file_hash(palette) if palette.is_file() else None,
        "reads": reads,
    })
    return Key(digest, sorted({path for found in trees.values() for path in found[1]}))


def _name(graph: AssetGraph, spec: StageSpec) -> str:
    return f"check:{graph.asset.id}:{spec.name}"


def lookup(graph: AssetGraph, spec: StageSpec) -> tuple[Key | None, list[Finding] | None]:
    """The key of the Stage's Check now, and the findings kept for it. The key is None when the Stage is left out of the cache
    or the key can't be worked out; the findings, None when there is nothing kept (or what is kept isn't a `Finding`)."""
    if not spec.check_cache:
        return None, None
    try:
        key = _key(graph, spec)
    except Exception:  # noqa: BLE001 - a read that fails now fails in the Check, which says why; this is only a cache
        return None, None
    stored = graph.cache.derived(_name(graph, spec), key.hash)
    try:
        if not isinstance(stored, dict):
            return key, None
        for name, hashed in stored["recent"].items():  # files that were new when kept: their content must be the same still
            path = graph.project.root / name
            if not path.is_file() or graph.cache.file_hash(path) != hashed:
                return key, None
        return key, [Finding.model_validate(item) for item in stored["findings"]]
    except (ValidationError, ValueError, TypeError, KeyError, AttributeError, OSError):
        return key, None


def keep(graph: AssetGraph, spec: StageSpec, key: Key, found: list[Finding]) -> None:
    """Keep the Check's findings for `key`; findings that don't come back as they went in are not kept."""
    dumped = [f.model_dump(mode="json") for f in found]
    try:
        if [Finding.model_validate(item).model_dump(mode="json") for item in dumped] != dumped:
            return
        recent = {Path(path).relative_to(graph.project.root).as_posix(): graph.cache.file_hash(Path(path))
                  for path in key.recent}
    except (ValidationError, ValueError, TypeError, OSError):
        return
    graph.cache.remember(_name(graph, spec), key.hash, {"findings": dumped, "recent": recent})
