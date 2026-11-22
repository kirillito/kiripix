"""What `status`, `queue` and `assets` share: the Project's Assets, from `serve`'s memory when there is one (ticket 0373).

In the CLI (one process, one call) `context.memory` is None and each Command reads the Project as it always did. In `serve`
a call first brings the memory up to date with what Kiripix recorded (`Memory.sync`) and honours its `refresh` token."""

from kiripix.checks import Finding
from kiripix.commands.contract import Context
from kiripix.core.assets import Asset, list_assets
from kiripix.core.project import Project

REFRESH_HELP = ("A token for one full refresh: with `serve`, the first call that carries one `serve` hasn't seen forgets "
                "everything it remembers of the Project, and the others with the same token keep what they work out. Meant "
                "for a refresh that must see a file changed outside Kiripix. No effect on the CLI.")


FORGET_HELP = ("With `serve`: forget these Assets (by ID) and what reads them before answering, so a file of theirs changed "
               "outside Kiripix is seen, and keep everything else it remembers (the UI's refresh when its window gets the focus "
               "back). No effect on the CLI.")


def project_assets(project: Project, context: Context, refresh: str | None,
                   forget: list[str] | None = None) -> tuple[list[Asset], list[Finding]]:
    """Every Asset sorted by ID, and a finding for each that can't be read (`list_assets`), through `serve`'s memory."""
    memory = context.memory
    if memory is None:
        return list_assets(project)
    memory.refresh(refresh)
    memory.sync()
    if forget:
        memory.forget(forget)
    return memory.assets(project)


def named_assets(assets: list[Asset], findings: list[Finding], wanted: list[str] | None) -> tuple[list[Asset], list[Finding]]:
    """The Assets whose IDs are in `wanted`, in ID order; None is every Asset, and an empty list none. An ID that isn't an
    Asset is a finding, and the broken Assets' findings are left out unless they name a wanted one."""
    if wanted is None:
        return assets, findings
    asked = set(wanted)
    found = [a for a in assets if a.id in asked]
    missing = sorted(asked - {a.id for a in found})
    kept = [f for f in findings if f.position is not None and f.position.asset in asked]
    kept.extend(Finding(code="asset.not_found", message=f"no Asset '{asset_id}' in this Project", fix="kiripix assets")
                for asset_id in missing)
    return found, kept
