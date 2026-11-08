"""The room's `palette` Stage with Layers (spec §6.1, ADR 0004, ticket 0045).

`palette.png` is the whole composite (the Plate with the Layers over it) mapped once and cleaned of orphans, and it stays
the Stage's image, so an Override paints over the composite. After the Overrides, a hook cuts `layer.<id>.png` from that
image by each Layer's alpha, and writes `plate.png`: the image outside the hole, and inside it the inpainted Plate
mapped separately with the same parameters (the same Bayer phase), cleaned of orphans only within the hole. So Plate and
Layers recompose exactly to `palette.png`. With no Layers `plate.png` is a byte copy of `palette.png`.
"""

import shutil

import numpy as np

from kiripix.checks import Finding, Position, check_conformance
from kiripix.ops import conformance, cut_by_alpha, has_partial_alpha, recompose, remove_orphans
from kiripix.recipes.base import StageFailure, StageRun
from kiripix.recipes.common import (
    check_mapping,
    check_palette as check_palette_image,
    map_to_palette,
    palette_rgb,
    quantize_to_palette,
    read_rgba,
    write_rgba,
)
from kiripix.recipes.layers import LAYERS_FILE, hole_of, read_layers


def _lifted(run: StageRun) -> tuple[np.ndarray, list[np.ndarray]]:
    """The Plate and the Layers `layers` built, as its Overrides left them."""
    upstream = run.upstream["layers"]
    plate = read_rgba(upstream / "plate.png")
    return plate, [read_rgba(upstream / str(entry["file"])) for entry in read_layers(upstream, run.asset_id)]


def run_room_palette(run: StageRun) -> None:
    plate, layers = _lifted(run)
    hole = hole_of(layers, plate.shape)
    composite = recompose(plate, layers)
    run.check_cancel()
    mapped = map_to_palette(run, composite, "composite")
    write_rgba(run.output_dir / "palette.png", mapped)
    if hole.any():
        run.check_cancel()
        # The inpainted area is mapped as its own image (the whole Plate, so the Bayer phase is the same), so what was
        # behind a Layer doesn't take colours from it. Its orphans are judged among the pixels `plate.png` will have
        # around them, and only pixels inside the hole change: outside it the Plate is `palette.png`.
        filled = np.where(hole[..., None], quantize_to_palette(run, plate, "Plate"), mapped)
        run.check_cancel()
        cleaned = remove_orphans(filled, int(run.params["orphan_size"]))
        mapped = np.where(hole[..., None], cleaned, mapped)
    write_rgba(run.output_dir / "plate.png", mapped)  # outside the hole `palette.png` as the Overrides will paint it


def after_overrides(run: StageRun) -> None:
    """Cut the Layers and the Plate from `palette.png` as the Overrides left it."""
    out = run.output_dir
    upstream = run.upstream["layers"]
    listing = read_layers(upstream, run.asset_id)
    shutil.copyfile(upstream / LAYERS_FILE, out / LAYERS_FILE)
    image = read_rgba(out / "palette.png")
    alphas = []
    for entry in listing:
        alpha = read_rgba(upstream / str(entry["file"]))[..., 3] > 0
        alphas.append(alpha)
        write_rgba(out / str(entry["file"]), cut_by_alpha(image, alpha))
    if not alphas:
        shutil.copyfile(out / "palette.png", out / "plate.png")
        return
    hole = hole_of(alphas, image.shape)
    inpainted = read_rgba(out / "plate.png")
    write_rgba(out / "plate.png", np.where(hole[..., None], inpainted, image))


def check_room_palette(run: StageRun) -> list[Finding]:
    findings = check_palette_image(run)
    try:
        palette = palette_rgb(run)
    except StageFailure:
        return findings
    out = run.output_dir
    asset = run.asset_id
    fix = f"kiripix run {asset} palette --force"
    image = read_rgba(out / "palette.png")
    plate = read_rgba(out / "plate.png")
    files = ["plate.png"]
    layers = []
    for entry in read_layers(out, asset):
        files.append(str(entry["file"]))
        layers.append(read_rgba(out / str(entry["file"])))
    for name, content in zip(files, [plate, *layers], strict=True):
        for finding in check_conformance(conformance(content, palette), name, fix=fix):
            assert finding.position is not None
            finding.position.asset, finding.position.stage = asset, "palette"
            findings.append(finding)
    lifted_plate, lifted_layers = _lifted(run)
    composite = recompose(lifted_plate, lifted_layers)  # what `palette` mapped, before it did
    if composite.shape == image.shape and not has_partial_alpha(image):
        fit = run.upstream["layers"].parent / "fit" / "fit.png"  # only to name the image `palette-suggest` reads
        findings += check_mapping(run, composite, image, fit)
    differs = (recompose(plate, layers) != image).any(axis=2)
    if differs.any():
        ys, xs = np.nonzero(differs)
        findings.append(
            Finding(
                code="layers.recompose_mismatch",
                message=f"Plate and Layers differ from palette.png in {int(differs.sum())} px, so they no longer "
                        f"recompose to it",
                position=Position(asset=asset, stage="palette", x=int(xs.min()), y=int(ys.min()),
                                  width=int(xs.max() - xs.min() + 1), height=int(ys.max() - ys.min() + 1)),
                fix=fix,
            )
        )
    return findings
