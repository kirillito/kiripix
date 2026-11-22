"""One key light for every character (ticket 0361, spec §6.3): the Project check `style.light_angle_differs`.

A figure's light is its render preset's `light_angle` (`[character.camera.*]`), so the check compares settings, not images. It
names each character whose resolved preset (its `render` Stage's `camera` parameter, the base's if it takes it from one) has
another angle than the Project's most common. A Wearable follows its body's render, so it is named in its body's finding
rather than reported twice. Nothing here writes; `project_checks` registers it for `check --all` and `export --all` calls it.
"""

from collections import Counter

from kiripix.checks import Finding, Position
from kiripix.core.assets import Asset
from kiripix.core.errors import KiripixError
from kiripix.core.graph import AssetGraph
from kiripix.core.hashing import HashCache
from kiripix.core.project import Project
from kiripix.recipes.base import BODY_PARAM

CHARACTER_KIND = "character"
WEARABLE_KIND = "wearable"
RENDER_STAGE = "render"
CAMERA_PARAM = "camera"


def _presets(project: Project, assets: list[Asset], cache: HashCache) -> dict[str, tuple[str, float]]:
    """Each character's camera preset name and its light angle. A character whose preset doesn't exist (`render.camera_unknown`
    says so) or that can't be read is left out."""
    presets = project.settings.character.camera
    found: dict[str, tuple[str, float]] = {}
    for asset in assets:
        if asset.kind != CHARACTER_KIND:
            continue
        try:
            graph = AssetGraph(project, asset, cache)
            name = str(graph.params(graph.spec(RENDER_STAGE))[CAMERA_PARAM])  # the declared default included
        except KiripixError:
            continue
        if name in presets:
            found[asset.id] = (name, presets[name].light_angle)
    return found


def light_angle_findings(project: Project, assets: list[Asset], cache: HashCache | None = None) -> list[Finding]:
    """`style.light_angle_differs` (warning) for each character whose light angle isn't the Project's most common."""
    cache = cache or HashCache(project.state_dir)
    used = _presets(project, assets, cache)
    counts = Counter(angle for _, angle in used.values())
    if len(counts) < 2:
        return []
    ranked = counts.most_common()
    majority = ranked[0][0] if ranked[0][1] > ranked[1][1] else None
    wearables: dict[str, list[str]] = {}
    for asset in assets:
        if asset.kind == WEARABLE_KIND and isinstance(asset.settings.params.get(BODY_PARAM), str):
            wearables.setdefault(str(asset.settings.params[BODY_PARAM]), []).append(asset.id)
    matching = Counter(name for name, angle in used.values() if angle == majority)
    found: list[Finding] = []
    for asset_id, (name, angle) in sorted(used.items()):
        if angle == majority:
            continue
        where = Position(asset=asset_id, stage=RENDER_STAGE, field=f"params.{CAMERA_PARAM}")
        message = f"{asset_id}'s camera preset '{name}' has light_angle {angle:g}"
        follow = sorted(wearables.get(asset_id, []))
        note = f" Its Wearables ({', '.join(follow)}) follow its render, so they differ with it." if follow else ""
        if majority is None:
            tied = ", ".join(f"{a:g}" for a, _ in ranked)
            found.append(Finding(
                code="style.light_angle_differs", severity="warning", position=where,
                message=f"{message}, and no light angle is the Project's most common (the characters use {tied} equally)."
                        + note,
                owner_action="Choose one light_angle for the Project: point every character's `camera` at one preset, or set "
                             "the presets' light_angle to one value, then run `kiripix run <character> render` again."))
            continue
        preset = matching.most_common(1)[0][0]
        found.append(Finding(
            code="style.light_angle_differs", severity="warning", position=where,
            message=f"{message}; the Project's most common is {majority:g} ('{preset}')." + note,
            fix=f"kiripix set {asset_id} {RENDER_STAGE} {CAMERA_PARAM}={preset}"))
    return found


def check_light_angle(project: Project, assets: list[Asset]) -> list[Finding]:
    return light_angle_findings(project, assets)
