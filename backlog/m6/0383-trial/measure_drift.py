"""Trial 0383: how far a repainted view's silhouette is from the render it was painted from (ChatGPT doesn't keep alignment).

    uv run python measure_drift.py --mask <render mask png> --painted <painted png> [--bg r,g,b] [--tol 12] [--no-fit]
                                   [--overlay out.png] [--write-aligned aligned.png] [--json report.json]

The render's silhouette is the mask (any 8-bit PNG, > 127 inside); its size is the canvas, the "1024 px scale" is that canvas's px
(the figure 1024 px tall). The painted image may be another size or aspect: it is first brought to the canvas by a uniform scale that
matches the heights (centre-cropped or padded in width), which the report names. Its silhouette is what the background does not
reach: the background colour is the median of the image's border (or `--bg`), the background is flooded in from the border through
pixels within `--tol` (largest channel difference) of it, and the rest, holes closed and specks under 2% dropped, is the figure.

Contour drift: the distance from each contour pixel of one silhouette to the nearest contour pixel of the other, in both directions;
`worst` is the largest of all (the Hausdorff distance), `mean` the mean of the two directions' means, in canvas px. Contour pixels are
whole pixels, so a distance is good to about +-0.7 px.

The fit is a uniform scale and a translation (no rotation, no stretch) found by iterated closest points on the contour, trimmed to the
best 80% of the pairs each round. It maps painted to render px: x_render = scale * x_painted + tx (and y alike). `--write-aligned`
resamples the (normalised) painted image by it onto the canvas, filled with the background colour, for project_views.py.
"""
import argparse
import json
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image


def erode4(mask: np.ndarray) -> np.ndarray:
    p = np.pad(mask, 1, constant_values=False)
    return mask & p[:-2, 1:-1] & p[2:, 1:-1] & p[1:-1, :-2] & p[1:-1, 2:]


def dilate8(mask: np.ndarray) -> np.ndarray:
    p = np.pad(mask, 1, constant_values=False)
    out = mask.copy()
    for dy in (0, 1, 2):
        for dx in (0, 1, 2):
            out |= p[dy:dy + mask.shape[0], dx:dx + mask.shape[1]]
    return out


def contour(mask: np.ndarray) -> np.ndarray:
    """Contour pixel centres (n, 2) as (x, y)."""
    ys, xs = np.nonzero(mask & ~erode4(mask))
    return np.stack([xs + 0.5, ys + 0.5], 1)


def components(mask: np.ndarray) -> list:
    """Connected components (8-neighbour) as lists of flat indices."""
    h, w = mask.shape
    flat = mask.ravel().copy()
    seen = np.zeros(flat.shape, bool)
    out = []
    for start in np.flatnonzero(flat):
        if seen[start]:
            continue
        seen[start] = True
        queue = deque([start])
        members = [start]
        while queue:
            i = queue.popleft()
            y, x = divmod(i, w)
            for dy in (-1, 0, 1):
                yy = y + dy
                if yy < 0 or yy >= h:
                    continue
                for dx in (-1, 0, 1):
                    xx = x + dx
                    if 0 <= xx < w:
                        j = yy * w + xx
                        if flat[j] and not seen[j]:
                            seen[j] = True
                            queue.append(j)
                            members.append(j)
        out.append(members)
    return out


def keep_figure(mask: np.ndarray, min_share: float = 0.02) -> np.ndarray:
    parts = components(mask)
    if not parts:
        return mask
    biggest = max(len(p) for p in parts)
    out = np.zeros(mask.size, bool)
    for p in parts:
        if len(p) >= min_share * biggest:
            out[p] = True
    return out.reshape(mask.shape)


def fill_holes(mask: np.ndarray) -> np.ndarray:
    return ~flood_from_border(~mask)


def _sweep(reach: np.ndarray, allowed: np.ndarray) -> np.ndarray:
    """One pass along the rows: every run of `allowed` pixels that holds a reached pixel is reached whole."""
    h, w = allowed.shape
    prev = np.zeros_like(allowed)
    prev[:, 1:] = allowed[:, :-1]
    start = (allowed & ~prev).ravel()
    ident = np.cumsum(start)
    hit = np.bincount(ident[(reach & allowed).ravel()], minlength=int(ident[-1]) + 1) > 0
    return (allowed.ravel() & hit[ident]).reshape(h, w)


def flood_from_border(allowed: np.ndarray) -> np.ndarray:
    """The pixels of `allowed` connected (8-neighbour) to the image border through `allowed`."""
    reach = np.zeros_like(allowed)
    reach[0, :], reach[-1, :], reach[:, 0], reach[:, -1] = True, True, True, True
    reach &= allowed
    for _ in range(2000):
        grown = _sweep(reach, allowed)  # along rows
        grown = _sweep(grown.T, allowed.T).T  # along columns
        grown = dilate8(grown) & allowed  # and one step in every direction, for the diagonals
        if (grown == reach).all():
            break
        reach = grown
    return reach


def painted_silhouette(rgb: np.ndarray, bg: np.ndarray | None, tol: float) -> tuple[np.ndarray, np.ndarray]:
    h, w = rgb.shape[:2]
    if bg is None:
        border = np.concatenate([rgb[:8].reshape(-1, 3), rgb[-8:].reshape(-1, 3), rgb[:, :8].reshape(-1, 3), rgb[:, -8:].reshape(-1, 3)])
        bg = np.median(border, 0)
    like = np.abs(rgb.astype(np.float64) - bg).max(-1) <= tol
    outside = flood_from_border(like)
    mask = fill_holes(~outside)
    mask = keep_figure(mask)
    return mask, bg


def normalise(painted: Image.Image, size: tuple[int, int], bg) -> tuple[Image.Image, dict]:
    """The painted image on the canvas: same size as it is; the same aspect resized; another aspect scaled to the canvas height,
    then centre-cropped or padded in width."""
    W, H = size
    if painted.size == (W, H):
        return painted, {"how": "same size"}
    w, h = painted.size
    if abs(w / h - W / H) < 0.002:
        return painted.resize((W, H), Image.LANCZOS), {"how": f"resized {w}x{h} to {W}x{H}"}
    scale = H / h
    scaled = painted.resize((max(1, round(w * scale)), H), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), tuple(int(v) for v in bg))
    canvas.paste(scaled, ((W - scaled.width) // 2, 0))
    return canvas, {"how": f"scaled {w}x{h} by {scale:.4f} to the canvas height, centred in width (cropped or padded)"}


def nearest(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For each point of a, the distance to and the index of the nearest point of b."""
    dist = np.empty(len(a))
    index = np.empty(len(a), np.int64)
    bb = (b * b).sum(1)
    for i in range(0, len(a), 1024):
        chunk = a[i:i + 1024]
        d2 = (chunk * chunk).sum(1)[:, None] + bb[None, :] - 2 * chunk @ b.T
        j = d2.argmin(1)
        index[i:i + 1024] = j
        dist[i:i + 1024] = np.sqrt(np.maximum(d2[np.arange(len(chunk)), j], 0))
    return dist, index


def drift(a_points: np.ndarray, b_points: np.ndarray) -> dict:
    d_ab, _ = nearest(a_points, b_points)
    d_ba, _ = nearest(b_points, a_points)
    both = np.concatenate([d_ab, d_ba])
    return {"worst_px": round(float(both.max()), 2), "mean_px": round(float((d_ab.mean() + d_ba.mean()) / 2), 2),
            "p95_px": round(float(np.percentile(both, 95)), 2),
            "painted_to_render_mean_px": round(float(d_ab.mean()), 2), "render_to_painted_mean_px": round(float(d_ba.mean()), 2)}


def fit_similarity(painted: np.ndarray, render: np.ndarray, rounds: int = 40, keep: float = 0.8) -> tuple[float, float, float]:
    """Uniform scale and translation taking the painted contour onto the render's (iterated closest points, trimmed)."""
    ph = painted[:, 1].max() - painted[:, 1].min()
    rh = render[:, 1].max() - render[:, 1].min()
    s = rh / ph
    centre_p = (painted.min(0) + painted.max(0)) / 2
    centre_r = (render.min(0) + render.max(0)) / 2
    t = centre_r - s * centre_p
    for _ in range(rounds):
        q = painted * s + t
        dist, index = nearest(q, render)
        order = np.argsort(dist)[: max(10, int(len(dist) * keep))]
        p, r = painted[order], render[index[order]]
        pm, rm = p.mean(0), r.mean(0)
        pc = p - pm
        new_s = float((pc * (r - rm)).sum() / (pc * pc).sum())
        new_t = rm - new_s * pm
        if abs(new_s - s) < 1e-6 and np.abs(new_t - t).max() < 1e-4:
            s, t = new_s, new_t
            break
        s, t = new_s, new_t
    return float(s), float(t[0]), float(t[1])


def analyse(render_mask: np.ndarray, painted_img: Image.Image, bg=None, tol: float = 12.0, fit: bool = True) -> dict:
    H, W = render_mask.shape
    bg_guess = bg
    if bg_guess is None:
        arr = np.array(painted_img.convert("RGB"))
        border = np.concatenate([arr[:8].reshape(-1, 3), arr[-8:].reshape(-1, 3), arr[:, :8].reshape(-1, 3), arr[:, -8:].reshape(-1, 3)])
        bg_guess = np.median(border, 0)
    image, how = normalise(painted_img.convert("RGB"), (W, H), bg_guess)
    rgb = np.array(image)
    mask, bg_used = painted_silhouette(rgb, None if bg is None else np.array(bg, float), tol)
    cr, cp = contour(render_mask), contour(mask)
    inter = (render_mask & mask).sum()
    union = (render_mask | mask).sum()
    report = {"canvas": [W, H], "painted_size": list(painted_img.size), "normalised": how, "background": [round(float(v)) for v in bg_used],
              "tolerance": tol, "render_silhouette_px": int(render_mask.sum()), "painted_silhouette_px": int(mask.sum()),
              "painted_height_over_render_height": round(float((np.nonzero(mask.any(1))[0][[0, -1]] @ [-1, 1] + 1) /
                                                               (np.nonzero(render_mask.any(1))[0][[0, -1]] @ [-1, 1] + 1)), 4),
              "iou_before": round(float(inter / max(union, 1)), 4), "before": drift(cp, cr)}
    result = {"report": report, "image": image, "mask": mask, "bg": bg_used, "contours": (cr, cp)}
    if fit:
        s, tx, ty = fit_similarity(cp, cr)
        report["fit"] = {"scale": round(s, 5), "tx_px": round(tx, 2), "ty_px": round(ty, 2),
                         "meaning": "x_render = scale * x_painted + tx, y_render = scale * y_painted + ty (canvas px, after normalising)"}
        report["after"] = drift(cp * s + np.array([tx, ty]), cr)
        # the fitted painted mask, for the IoU
        m = Image.fromarray(mask.astype(np.uint8) * 255).transform((W, H), Image.AFFINE, (1 / s, 0, -tx / s, 0, 1 / s, -ty / s), Image.NEAREST)
        fm = np.array(m) > 127
        report["iou_after"] = round(float((render_mask & fm).sum() / max((render_mask | fm).sum(), 1)), 4)
        result["fit"] = (s, tx, ty)
    return result


def aligned(image: Image.Image, fit: tuple, bg) -> Image.Image:
    s, tx, ty = fit
    return image.transform(image.size, Image.AFFINE, (1 / s, 0, -tx / s, 0, 1 / s, -ty / s), Image.BICUBIC, fillcolor=tuple(int(v) for v in bg))


def overlay(result: dict, render_mask: np.ndarray) -> Image.Image:
    """Before | after, the painted image dimmed, the render's contour green, the painted contour red (before) and blue (after)."""
    H, W = render_mask.shape
    cr, cp = result["contours"]
    base = (np.array(result["image"]).astype(np.float64) * 0.55 + 255 * 0.45 * 0.5).astype(np.uint8)

    def draw(points, colour, canvas):
        ys = np.clip(np.floor(points[:, 1]).astype(int), 0, H - 1)
        xs = np.clip(np.floor(points[:, 0]).astype(int), 0, W - 1)
        layer = np.zeros((H, W), bool)
        layer[ys, xs] = True
        layer = dilate8(layer)
        canvas[layer] = colour
        return canvas

    left = draw(cp, (230, 30, 30), draw(cr, (20, 200, 40), base.copy()))
    panels = [Image.fromarray(left)]
    if "fit" in result:
        s, tx, ty = result["fit"]
        fitted = aligned(result["image"], result["fit"], result["bg"])
        right_base = (np.array(fitted).astype(np.float64) * 0.55 + 255 * 0.45 * 0.5).astype(np.uint8)
        right = draw(cp * s + np.array([tx, ty]), (40, 60, 240), draw(cr, (20, 200, 40), right_base))
        panels.append(Image.fromarray(right))
    sheet = Image.new("RGB", (W * len(panels), H))
    for i, p in enumerate(panels):
        sheet.paste(p, (i * W, 0))
    ys, xs = np.nonzero(render_mask)
    return sheet.resize((sheet.width // 2, sheet.height // 2), Image.LANCZOS)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--mask", required=True)
    p.add_argument("--painted", required=True)
    p.add_argument("--bg")
    p.add_argument("--tol", type=float, default=12.0)
    p.add_argument("--no-fit", action="store_true")
    p.add_argument("--overlay")
    p.add_argument("--write-aligned")
    p.add_argument("--json")
    a = p.parse_args()
    render_mask = np.array(Image.open(a.mask).convert("L")) > 127
    bg = [float(v) for v in a.bg.split(",")] if a.bg else None
    result = analyse(render_mask, Image.open(a.painted), bg, a.tol, not a.no_fit)
    text = json.dumps(result["report"], indent=1)
    print(text)
    if a.json:
        Path(a.json).write_text(text)
    if a.overlay:
        overlay(result, render_mask).save(a.overlay)
    if a.write_aligned:
        image = aligned(result["image"], result["fit"], result["bg"]) if "fit" in result else result["image"]
        image.save(a.write_aligned)


if __name__ == "__main__":
    main()
