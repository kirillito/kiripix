"""0307 trial: the atlas levers, measured on finished frames (the real `finish` Stage's work/finish/{color,normal}/<clip>/<dir>/NNN.png).
Plain numpy/PIL; nothing here is Kiripix code."""
import hashlib, io, json
from pathlib import Path
import numpy as np
from PIL import Image

EIGHT = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
FIVE = ["s", "sw", "w", "nw", "n"]
MIRROR = {"ne": "nw", "e": "w", "se": "sw"}  # the three drawn in the game by flip_h of a rendered one


def load_asset(adir: Path):
    """{clip: {"fps", "loop", "stationary", "frames": {dir: [(colour RGBA array, normal RGBA array)]}}} and the cell (w, h)."""
    sheet = json.loads((adir / "work/sheet/sheet.json").read_text())
    cell = (sheet["cell"]["width"], sheet["cell"]["height"])
    out = {}
    for c in sheet["clips"]:
        frames = {}
        for d in EIGHT:
            lst = []
            for i in range(len(c["directions"][d])):
                col = np.array(Image.open(adir / f"work/finish/color/{c['name']}/{d}/{i:03d}.png").convert("RGBA"))
                nor = np.array(Image.open(adir / f"work/finish/normal/{c['name']}/{d}/{i:03d}.png").convert("RGBA"))
                lst.append((col, nor))
            frames[d] = lst
        out[c["name"]] = {"fps": c["fps"], "loop": c["loop"], "stationary": c["stationary"], "frames": frames}
    return out, cell, sheet


def png_bytes(arr: np.ndarray, indexed_palette=None, optimize=True) -> int:
    """Size in bytes of the PNG of an RGBA array; with `indexed_palette` (an (n, 4) uint8 table) as an 8-bit indexed PNG with tRNS."""
    buf = io.BytesIO()
    if indexed_palette is None:
        Image.fromarray(arr, "RGBA").save(buf, "PNG", optimize=optimize, compress_level=9)
    else:
        buf.write(indexed_png(arr, indexed_palette, optimize))
    return buf.tell() if indexed_palette is None else len(buf.getvalue())


def indexed_png(arr: np.ndarray, table: np.ndarray, optimize=True) -> bytes:
    """`arr` as an indexed PNG whose palette is `table` (exact: every pixel must be in the table; alpha 0 pixels become table[0])."""
    h, w, _ = arr.shape
    flat = arr.reshape(-1, 4).astype(np.uint32)
    key = (flat[:, 0] << 24) | (flat[:, 1] << 16) | (flat[:, 2] << 8) | flat[:, 3]
    tkey = (table[:, 0].astype(np.uint32) << 24) | (table[:, 1].astype(np.uint32) << 16) | (table[:, 2].astype(np.uint32) << 8) | table[:, 3].astype(np.uint32)
    order = np.argsort(tkey)
    pos = np.searchsorted(tkey[order], key)
    pos = np.clip(pos, 0, len(tkey) - 1)
    idx = order[pos].astype(np.uint8)
    assert (tkey[idx] == key).all(), "a pixel is not in the palette table"
    im = Image.fromarray(idx.reshape(h, w), "P")
    pal = table[:, :3].reshape(-1).tolist()
    im.putpalette(pal + [0] * (768 - len(pal)))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=optimize, compress_level=9, transparency=bytes(table[:, 3].tolist()))
    return buf.getvalue()


def colour_table(arrays):
    """Every distinct RGBA of the arrays, transparent pixels folded to (0,0,0,0)."""
    seen = set()
    for a in arrays:
        f = a.reshape(-1, 4).copy()
        f[f[:, 3] == 0] = 0
        seen |= set(map(tuple, np.unique(f, axis=0).tolist()))
    t = np.array(sorted(seen), dtype=np.uint8)
    return t


def opaque_box(col: np.ndarray, nor: np.ndarray):
    """(left, top, right, bottom) exclusive, of the pixels with any alpha in either pass; None if empty."""
    m = (col[..., 3] > 0) | (nor[..., 3] > 0)
    if not m.any():
        return None
    ys, xs = np.where(m)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def maxrects(sizes, width, pad=1):
    """MaxRects (best short side fit) of rects (w, h) into a bin `width` wide, as tall as needed. Returns ([(x, y)], height)
    or None if one is wider than the bin. A `pad` px gap on the right and below every rect."""
    free = [(0, 0, width, 10 ** 6)]
    placed = [None] * len(sizes)
    order = sorted(range(len(sizes)), key=lambda i: (-max(sizes[i]), -min(sizes[i])))
    height = 0
    for i in order:
        w, h = sizes[i][0] + pad, sizes[i][1] + pad
        best = None
        for fx, fy, fw, fh in free:
            if w <= fw and h <= fh:
                score = (min(fw - w, fh - h), max(fw - w, fh - h), fy)
                if best is None or score < best[0]:
                    best = (score, fx, fy)
        if best is None:
            return None
        _, x, y = best
        placed[i] = (x, y)
        height = max(height, y + h)
        new_free = []
        for fx, fy, fw, fh in free:
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                new_free.append((fx, fy, fw, fh))
                continue
            if x > fx:
                new_free.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                new_free.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                new_free.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                new_free.append((fx, y + h, fw, fy + fh - y - h))
        # drop contained rects
        pruned = []
        for a in new_free:
            if not any(b is not a and b[0] <= a[0] and b[1] <= a[1] and b[0] + b[2] >= a[0] + a[2] and b[1] + b[3] >= a[1] + a[3] for b in new_free):
                pruned.append(a)
        free = pruned
    return placed, height


def pack(sizes, pad=1):
    """The narrowest-area packing over several bin widths. Returns (width, height, [(x, y)])."""
    total = sum((w + pad) * (h + pad) for w, h in sizes)
    widest = max(w for w, _ in sizes) + pad
    best = None
    root = int(total ** 0.5)
    for k in (0.8, 0.9, 1.0, 1.1, 1.2, 1.35, 1.5, 1.75, 2.0):
        width = max(widest, int(root * k))
        r = maxrects(sizes, width, pad)
        if r is None:
            continue
        placed, height = r
        # tight width actually used
        used_w = max(x + sizes[i][0] for i, (x, _) in enumerate(placed))
        area = used_w * height
        if best is None or area < best[0]:
            best = (area, used_w, height, placed)
    return best[1], best[2], best[3]


def grid_size(n, cell, columns=None):
    """The real sheet's layout: rows of `columns` cells (the longest clip's frames), 8 direction rows per clip."""
    return None


def frame_key(col, nor):
    return hashlib.sha1(col.tobytes() + nor.tobytes()).hexdigest()
