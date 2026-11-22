"""`--match <glob>`: a district is the Assets whose IDs a glob matches (ticket 0327). Nothing is stored.

One place for the matching, so `status`, `check`, `run`, `export`, `stats` and later `queue` and `district` agree on it.
"""

from collections.abc import Iterable
from fnmatch import fnmatchcase

from kiripix.checks import Finding
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError, fail


def matches(asset_id: str, glob: str) -> bool:
    """Whether the Asset ID matches the glob (`fnmatch` rules, case-sensitive)."""
    return fnmatchcase(asset_id, glob)


def no_match(glob: str) -> KiripixError:
    return fail("match.none", f"no Asset ID matches '{glob}'", fix="kiripix status")


def select(assets: Iterable[Asset], glob: str) -> list[Asset]:
    """The Assets whose IDs match `glob`, in the order given. A glob that matches nothing is `match.none`, so a typo isn't
    an empty success."""
    found = [asset for asset in assets if matches(asset.id, glob)]
    if not found:
        raise no_match(glob)
    return found


def only_named(findings: list[Finding], ids: set[str]) -> list[Finding]:
    """The findings that name one of the Assets `ids`: what a district's Project checks report."""
    return [f for f in findings if f.position is not None and f.position.asset in ids]


__all__ = ["matches", "no_match", "only_named", "select"]
