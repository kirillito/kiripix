"""`kiripix inbox` (ticket 0350): file the images the Owner made elsewhere, by their file names.

Every PNG and JPEG in the inbox folder is matched to an Asset by name (the names `to-paint` told the Owner to use, in
`kiripix.core.paint`): `<room>.png` or `<room>-<anything>.png` is imported as a Variant, `<room>.<side>.png` is joined onto
the room's image as `extend add` does. The Asset is named with or without its Kind prefix. A file that matches no Asset, or
several, stays where it is. After each import the file moves to `<folder>/imported/<date>/`, so a second run never imports
it twice. Importing never picks. All the importing is `kiripix.core.sources` and `kiripix.core.extend`.

`file_one` files one image into one named Asset the same way, whatever the file is called: what the UI's drop on a waiting
room runs (ticket 0351), with the sides `to-paint` gave the room. That file isn't moved.
"""

import datetime
import os
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from kiripix.checks import Finding, Position
from kiripix.core import atomic, cancel, changes, extend, sources
from kiripix.core.assets import Asset, list_assets, load_asset
from kiripix.core.errors import ExitCode, KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.paint import SIDES
from kiripix.core.project import Project

IMPORTED_FOLDER = "imported"
SUFFIXES = (".png", ".jpg", ".jpeg")


def folder(project: Project, override: str | None, cwd: Path) -> Path:
    """The inbox folder: `--folder` (relative to the working directory), else `[inbox] folder` (relative to the Project)."""
    if override is not None:
        path = Path(override)
        return path if path.is_absolute() else cwd / path
    path = Path(project.settings.inbox.folder)
    return path if path.is_absolute() else project.root / path


def files(inbox: Path) -> list[Path]:
    """The PNG and JPEG files directly in the folder, by name; the `imported/` folder is left alone."""
    if not inbox.is_dir():
        return []
    return sorted((p for p in inbox.iterdir() if p.is_file() and p.suffix.lower() in SUFFIXES and not p.name.startswith(".")),
                  key=lambda p: p.name.lower())


def parse(name: str) -> tuple[str, list[str]]:
    """A file name as the name of an Asset (a Kind prefix or none, anything after a `-` dropped) and the sides of a piece:
    `alley-2.jpg` as ("alley", []), `room.alley.east+south.png` as ("room.alley", ["east", "south"])."""
    stem = name[: name.rfind(".")].lower()
    base, dot, last = stem.rpartition(".")
    sides = last.split("+") if dot else []
    if not dot or not base or not all(side in SIDES for side in sides):
        base, sides = stem, []
    return base.split("-", 1)[0], sides


def candidates(assets: list[Asset], key: str) -> list[Asset]:
    """The Assets that take an image Variant whose name, or whose ID, is `key`."""
    found = [a for a in assets if key in (a.name, a.id) and not sources.takes_models(a) and not sources.takes_sheets(a)]
    return found


FiledOutcome = Literal["imported", "would_import", "unmatched", "ambiguous", "failed"]
FiledAction = Literal["import", "extend"]


@dataclass
class Filed:
    """What became of one file."""

    file: str
    outcome: FiledOutcome
    asset: str | None = None
    action: FiledAction | None = None
    sides: list[str] = field(default_factory=list)
    variant: str | None = None
    piece: str | None = None
    created: bool | None = None
    moved_to: str | None = None
    candidates: list[str] = field(default_factory=list)
    code: str | None = None


@dataclass
class Result:
    files: list[Filed] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    lone: list[tuple[str, str]] = field(default_factory=list)  # (asset, its one Variant), not picked
    exit_code: ExitCode = ExitCode.OK


def _move(project: Project, inbox: Path, file: Path, day: str) -> Path:
    """Move the imported file to `imported/<day>/`, atomically; a name already there gets a number."""
    target = inbox / IMPORTED_FOLDER / day / file.name
    number = 1
    while target.exists():
        number += 1
        target = target.with_name(f"{file.stem}.{number}{file.suffix}")
    target.parent.mkdir(parents=True, exist_ok=True)
    os.replace(file, target)
    changes.record(file, target)
    return target


def run(
    project: Project, inbox: Path, dry_run: bool, hold: Callable[[Asset], AbstractContextManager[None]],
) -> Result:
    """File every image in `inbox`. `hold` takes an Asset's lock for the length of its import."""
    result = Result()
    every, result.findings = list_assets(project)
    day = datetime.date.today().isoformat()
    cache = HashCache(project.state_dir)
    touched: dict[str, Asset] = {}
    for file in files(inbox):
        cancel.check()
        shown = project.relative(file)
        key, sides = parse(file.name)
        found = candidates(every, key)
        if not found:
            result.files.append(Filed(shown, "unmatched", sides=sides, code="inbox.unmatched"))
            result.findings.append(Finding(
                code="inbox.unmatched", severity="warning", position=Position(file=shown),
                message=f"{file.name} matches no Asset",
                owner_action=f"Name it <asset>.png (an Asset's name, with or without its Kind prefix) or "
                             f"<asset>.<side>.png, or import it with `kiripix import <asset> {shown}`."))
            continue
        if len(found) > 1:
            ids = [a.id for a in found]
            result.files.append(Filed(shown, "ambiguous", sides=sides, candidates=ids, code="inbox.ambiguous"))
            result.findings.append(Finding(
                code="inbox.ambiguous", severity="warning", position=Position(file=shown),
                message=f"{file.name} matches {len(found)} Assets: {', '.join(ids)}",
                owner_action=f"Name it with its Kind prefix (such as {ids[0]}.png), or import it with "
                             f"`kiripix import <asset> {shown}`."))
            continue
        asset = found[0]
        action: FiledAction = "extend" if sides else "import"
        if dry_run:
            result.files.append(Filed(shown, "would_import", asset=asset.id, action=action, sides=sides))
            continue
        try:
            with hold(asset):
                entry, extra = _file(project, asset, file, shown, sides)
                entry.moved_to = project.relative(_move(project, inbox, file, day))
        except KiripixError as error:
            result.files.append(Filed(shown, "failed", asset=asset.id, action=action, sides=sides,
                                      code=error.findings[0].code if error.findings else None))
            result.findings.extend(error.findings)
            result.exit_code = max(result.exit_code, error.exit_code)
            continue
        result.files.append(entry)
        result.findings.extend(extra)
        touched[asset.id] = asset
    _lone(project, result, touched.values(), cache)
    return result


def file_one(
    project: Project, asset_id: str, file: Path, shown: str, sides: list[str],
    hold: Callable[[Asset], AbstractContextManager[None]],
) -> Result:
    """File one image into one Asset: a Variant with no `sides`, else a piece joined on those sides. The file stays."""
    result = Result()
    asset = load_asset(project, asset_id)
    action: FiledAction = "extend" if sides else "import"
    if not candidates([asset], asset.id) or any(side not in SIDES for side in sides):
        raise KiripixError([Finding(
            code="input.invalid", position=Position(asset=asset.id),
            message=f"{asset.id} takes no image Variant" if not candidates([asset], asset.id)
            else f"the sides are {', '.join(SIDES)}, not {', '.join(sides)}",
            fix=f"kiripix to-paint --match {asset.id}")])
    try:
        with hold(asset):
            entry, extra = _file(project, asset, file, shown, sides)
    except KiripixError as error:
        result.files.append(Filed(shown, "failed", asset=asset.id, action=action, sides=sides,
                                  code=error.findings[0].code if error.findings else None))
        result.findings.extend(error.findings)
        result.exit_code = error.exit_code
        return result
    result.files.append(entry)
    result.findings.extend(extra)
    _lone(project, result, [asset], HashCache(project.state_dir))
    return result


def _lone(project: Project, result: Result, touched: Iterable[Asset], cache: HashCache) -> None:
    """Note each Asset imported into that now has exactly one Variant, not picked."""
    for asset in touched:
        if any(f.asset == asset.id and f.action == "import" and f.outcome == "imported" for f in result.files):
            known = list(sources.variants(asset))
            if len(known) == 1 and sources.picked(AssetGraph(project, asset, cache)) != known[0]:
                result.lone.append((asset.id, known[0]))
    cache.save()


def _file(project: Project, asset: Asset, file: Path, shown: str, sides: list[str]) -> tuple[Filed, list[Finding]]:
    if not sides:
        name, _, created = sources.import_file(asset, file, shown, "variant")
        return Filed(shown, "imported", asset=asset.id, action="import", variant=name, created=created), []
    example = f"kiripix extend {asset.id} add {shown} --side {','.join(sides)}"
    extend.ensure_canvas(project, asset, sides, example)
    joined, findings = extend.add_piece(project, asset, file, shown, sides, example)
    return Filed(shown, "imported", asset=asset.id, action="extend", sides=joined.sides, piece=joined.piece), findings
