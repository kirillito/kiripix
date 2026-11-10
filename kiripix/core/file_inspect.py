"""The `inspect` Probe's work (ticket 0123): what a character's file holds, from Blender, remembered.

A file is a Model Variant, a clip source or the rigged file, by the name `show` gives it. Blender reads it once with
`read_actions.py`; the answer is kept in `.kiripix/file-reads/`, keyed by the file's content hash, the Blender version and
the script, so asking again starts no Blender. The cache is a cache: deleting it loses nothing.
"""

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kiripix.core import atomic, sources
from kiripix.core.assets import Asset
from kiripix.core.errors import ExitCode, fail
from kiripix.core.kinds import get_kind
from kiripix.core.project import Project
from kiripix.recipes.base import StageFailure
from kiripix.recipes import blender_launcher
from kiripix.recipes.blender_launcher import SCRIPTS, launch_for

CACHE_DIR = "file-reads"
RIGGED = "rigged"  # also names the rigged file, whose own name is a hash


def resolve(asset: Asset, name: str) -> tuple[str, Path]:
    """The file a name means, with what it is (`variant`, `clip-source` or `rigged`)."""
    if not sources.takes_models(asset):
        raise fail("inspect.not_character", f"{asset.id} is a {asset.kind}: only a character has Model files to inspect",
                   fix=f"kiripix show {asset.id}")
    variants = sources.variants(asset)
    clip_sources = sources.clip_sources(asset)
    rigged = sources.rigged(asset)
    if name in variants:
        return "variant", variants[name]
    if name in clip_sources:
        return "clip-source", clip_sources[name]
    if rigged is not None and name in (RIGGED, rigged.stem):
        return "rigged", rigged
    known = [*variants, *clip_sources, *([RIGGED] if rigged is not None else [])]
    raise fail("inspect.file_unknown", f"{asset.id} has no file named {name}; its files are {', '.join(known) or 'none'}",
               fix=f"kiripix show {asset.id}")


def _key(path: Path) -> str:
    content = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    script = hashlib.sha256((SCRIPTS / "read_actions.py").read_bytes()).hexdigest()[:8]
    version = blender_launcher.BLENDER_VERSION  # read now, not at import, so the hashes and this key agree
    return f"{content}-blender{version[0]}.{version[1]}-{script}"


def _short(name: str) -> str:
    return name.split("|")[-1]  # FBX: `Armature|Armature|idle`; a `clip` Decision may name either


def inspect_file(project: Project, asset: Asset, name: str, *, progress: Callable[[int, int, str], None],
                 check_cancel: Callable[[], None]) -> dict[str, Any]:
    get_kind(asset.kind)  # the Kind's module may swap Blender for a test one: load the Kinds before any call
    role, path = resolve(asset, name)
    cached = project.state_dir / CACHE_DIR / f"{_key(path)}.json"
    found: dict[str, Any] | None = None
    if cached.is_file():
        try:
            found = json.loads(cached.read_text(encoding="utf-8"))
        except ValueError:
            found = None  # a damaged cache is read again
    from_cache = found is not None
    if found is None:
        executable = project.settings.character.blender
        try:
            read = launch_for("read_actions", {"input": str(path), "root": [], "travel": False, "optional": True},
                              executable=executable, progress=progress, check_cancel=check_cancel)
        except StageFailure as failure:
            shown = f"kiripix probe inspect {asset.id} {name}"
            if failure.owner_action is not None:
                raise fail(failure.code or "inspect.failed", str(failure), owner_action=failure.owner_action,
                           exit_code=ExitCode.NEEDS_OWNER) from None
            raise fail(failure.code or "inspect.failed", str(failure), fix=failure.fix or shown) from None
        found = {
            "armature": read["armature"],
            "bones": list(read["bones"]),
            "fps": read["fps"],
            "actions": [{"name": a["name"], "short": _short(a["name"]), "start": a["start"], "end": a["end"]}
                        for a in read["actions"]],
        }
        atomic.write_json(cached, found)
    return {"file": name, "role": role, "path": project.relative(path), "cached": from_cache, **found}
