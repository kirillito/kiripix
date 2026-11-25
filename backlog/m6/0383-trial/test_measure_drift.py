"""Trial 0383: measure_drift.py on synthetic shifts and scales with known answers.

    uv run python test_measure_drift.py [<render mask png>]    (with a mask, also the real silhouette; writes test_measure_drift.json)

The "painted" image is the silhouette's own picture moved by a known similarity (scale about the canvas centre, then shift), on a
background of another colour, with noise, sometimes at another size. The fit must give back the inverse.
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
import measure_drift as md  # noqa: E402

W, H = 1024, 1536
BG = (160, 160, 160)


def stick_figure() -> np.ndarray:
    im = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(im)
    d.ellipse((440, 260, 590, 430), fill=255)  # head
    d.rectangle((470, 420, 560, 480), fill=255)  # neck
    d.polygon([(400, 480), (630, 480), (600, 760), (430, 760)], fill=255)  # torso
    d.rectangle((70, 495, 960, 545), fill=255)  # arms
    d.rectangle((430, 760, 505, 1270), fill=255)  # legs
    d.rectangle((525, 760, 600, 1270), fill=255)
    d.ellipse((410, 1230, 510, 1285), fill=255)  # feet
    d.ellipse((520, 1230, 620, 1285), fill=255)
    return np.array(im) > 127


def painted_from(mask: np.ndarray, scale: float, shift: tuple, bg=BG, noise=0.0, size=None, seed=1) -> Image.Image:
    """The mask's figure, filled with three flat colours, moved: x' = scale * (x - centre) + centre + shift."""
    rng = np.random.default_rng(seed)
    h, w = mask.shape
    fig = np.zeros((h, w, 3), np.uint8)
    fig[...] = (236, 236, 236)  # white-ish clothes
    fig[: h * 5 // 16] = (90, 60, 45)
    fig[h * 5 // 16: h * 4 // 8, :] = (235, 190, 155)
    img = np.where(mask[..., None], fig, np.array(bg, np.uint8))
    im = Image.fromarray(img.astype(np.uint8))
    cx, cy = w / 2, h / 2
    # output (x', y') comes from input ((x' - shift - c) / scale + c)
    inv = 1 / scale
    moved = im.transform((w, h), Image.AFFINE, (inv, 0, cx - inv * (cx + shift[0]), 0, inv, cy - inv * (cy + shift[1])), Image.BILINEAR, fillcolor=bg)
    if noise:
        arr = np.array(moved).astype(np.float64) + rng.normal(0, noise, (h, w, 3))
        moved = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if size and size != (w, h):
        if abs(size[0] / size[1] - w / h) < 0.002:
            moved = moved.resize(size, Image.LANCZOS)
        else:  # another aspect: the figure kept at the height, padded in width
            scaled = moved.resize((round(w * size[1] / h), size[1]), Image.LANCZOS)
            canvas = Image.new("RGB", size, bg)
            canvas.paste(scaled, ((size[0] - scaled.width) // 2, 0))
            moved = canvas
    return moved


def check(name: str, mask: np.ndarray, scale, shift, tol_scale=0.004, tol_px=1.0, **kw) -> dict:
    painted = painted_from(mask, scale, shift, **kw)
    result = md.analyse(mask, painted, None, 12.0, True)
    r = result["report"]
    s, tx, ty = r["fit"]["scale"], r["fit"]["tx_px"], r["fit"]["ty_px"]
    # the true map render -> painted: x_p = scale * (x_r - c) + c + shift; so painted -> render: x_r = (x_p - c - shift) / scale + c
    true_s = 1 / scale
    true_tx = (-W / 2 - shift[0]) / scale + W / 2
    true_ty = (-H / 2 - shift[1]) / scale + H / 2
    # when the painting is at another size the report's coordinates are the canvas's (normalised), same as above
    if kw.get("size") and tuple(kw["size"]) != (W, H):
        tol_px = max(tol_px, 2.5)  # a painting resampled to another size has blurred edges: its contour is good to about 2 px
    ok = abs(s - true_s) <= tol_scale and abs(tx - true_tx) <= tol_px and abs(ty - true_ty) <= tol_px and r["after"]["mean_px"] <= 1.2
    row = {"case": name, "known": {"scale": scale, "shift_px": list(shift), "painted_to_render_scale": round(true_s, 5),
                                   "tx": round(true_tx, 2), "ty": round(true_ty, 2)},
           "measured_fit": r["fit"], "before": r["before"], "after": r["after"], "iou_before": r["iou_before"], "iou_after": r["iou_after"],
           "normalised": r["normalised"], "ok": bool(ok)}
    print(f"{'ok  ' if ok else 'FAIL'} {name}: known s={true_s:.4f} t=({true_tx:.1f}, {true_ty:.1f}); measured s={s:.4f} t=({tx:.1f}, {ty:.1f}); "
          f"drift before worst {r['before']['worst_px']} mean {r['before']['mean_px']}, after worst {r['after']['worst_px']} mean {r['after']['mean_px']}")
    return row


def main() -> None:
    masks = {"stick figure": stick_figure()}
    if len(sys.argv) > 1:
        masks["real front mask"] = np.array(Image.open(sys.argv[1]).convert("L")) > 127
    rows = []
    for label, mask in masks.items():
        rows += [
            check(f"{label}: identity", mask, 1.0, (0, 0)),
            check(f"{label}: shift (12, -7)", mask, 1.0, (12, -7)),
            check(f"{label}: shift (-30, 25)", mask, 1.0, (-30, 25)),
            check(f"{label}: scale 0.92", mask, 0.92, (0, 0)),
            check(f"{label}: scale 1.06, shift (10, 14)", mask, 1.06, (10, 14)),
            check(f"{label}: scale 0.9, shift (-15, 20), white background, noise 3", mask, 0.9, (-15, 20), bg=(255, 255, 255), noise=3.0),
            check(f"{label}: shift (8, 8) painted at 768x1152", mask, 1.0, (8, 8), size=(768, 1152)),
            check(f"{label}: scale 0.95, shift (5, -9) painted on 1536x1536", mask, 0.95, (5, -9), size=(1536, 1536)),
        ]
    if len(sys.argv) > 1:
        Path(__file__).with_name("test_measure_drift.json").write_text(json.dumps(rows, indent=1))
    bad = [r["case"] for r in rows if not r["ok"]]
    print("all ok" if not bad else f"FAILED: {bad}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
