"""Variants and the Pick: `import` copies an outside image into `src/` as a Variant, `pick` chooses the Source.

A Variant is `src/<hash>.png`, named by the start of its content hash, so importing the same image twice is a no-op
and a Variant never changes once picked. The caller holds the Asset lock.
"""

from pathlib import Path

from kiripix.checks import Position
from kiripix.core import atomic, editing, journal
from kiripix.core.assets import Asset
from kiripix.core.errors import fail
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache, hash_bytes
from kiripix.core.images import read_png
from kiripix.core.project import Project
from kiripix.recipes.base import PICK, StageSpec

VARIANT_NAME_LENGTH = 16  # hex digits of the SHA-256: 64 bits, plenty for one Asset's Variants


def variants(asset: Asset) -> dict[str, Path]:
    """The Asset's Variants by name, sorted."""
    return {path.stem: path for path in sorted((asset.dir / "src").glob("*.png")) if path.is_file()}


def import_variant(asset: Asset, file: Path, shown: str) -> tuple[str, Path, bool]:
    """Copy a PNG into `src/` as a Variant. Returns its name, its path, and whether it is new."""
    data, _ = read_png(file, shown)
    name = hash_bytes(data)[:VARIANT_NAME_LENGTH]
    path = asset.dir / "src" / f"{name}.png"
    if path.exists():
        return name, path, False
    atomic.write_bytes(path, data)
    return name, path, True


def _pick_stage(graph: AssetGraph) -> StageSpec:
    spec = next((s for s in graph.kind.stages if any(d.name == PICK.name for d in s.decisions)), None)
    if spec is None:
        raise fail("pick.no_stage", f"a {graph.kind.name} has no Stage that takes a Pick",
                   fix=f"kiripix describe {graph.kind.name}")
    return spec


def pick(project: Project, asset: Asset, variant: str) -> tuple[StageSpec, journal.JournalEntry]:
    """Record the Pick Decision on the Stage that takes it, the same entry `decide` would write."""
    spec = _pick_stage(AssetGraph(project, asset, HashCache(project.state_dir)))
    known = variants(asset)
    if variant not in known:
        position = Position(asset=asset.id, stage=spec.name)
        if not known:
            raise fail("pick.unknown_variant", f"{asset.id} has no Variants yet", position=position,
                       fix=f"kiripix import {asset.id} <file>")
        raise fail("pick.unknown_variant", f"{asset.id} has no Variant '{variant}'; its Variants are "
                   f"{', '.join(known)}", position=position,
                   owner_action=f"Pick one of them: kiripix pick {asset.id} <variant>")
    document = editing.DecisionDocument(decision=PICK.name, data={"variant": variant})
    entry, _ = editing.record_decision(project, asset, spec.name, document)
    return spec, entry
