"""Trial 0134: the same SAM 2 click on the whole room and on a one-screen crop. Runs `kiripix probe segment-preview` on each
crop room, shifts its Mask into the whole room's coordinates, and compares pixels, boxes and IoU."""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

whole_dir = Path(sys.argv[1])
CROPS = {"a": (480, 0), "b": (480, 272), "c": (0, 0), "d": (0, 272)}
OBJECTS = {  # name: (x, y) in the whole room, crop
    "hydrant": (925, 412, "b"), "bikerack": (912, 525, "b"), "chairs": (590, 425, "b"), "hedge": (820, 500, "b"),
    "sign": (940, 121, "a"), "lamp": (1025, 100, "a"), "van": (1077, 120, "a"), "car": (395, 90, "c"),
    "drain": (355, 235, "c"), "puddle": (440, 230, "c"), "shed": (45, 400, "d"), "tomatoes": (50, 560, "d"),
}


def mask(result: dict, dx: int = 0, dy: int = 0) -> np.ndarray:
    m = np.zeros((624, 1120), bool)
    for y, x, n in result["runs"]:
        m[y + dy, x + dx : x + dx + n] = True
    return m


def box(m: np.ndarray) -> tuple[int, int, int, int]:
    ys, xs = np.nonzero(m)
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


rows = []
for name, (x, y, crop) in OBJECTS.items():
    ox, oy = CROPS[crop]
    out = subprocess.run(["uv", "run", "--project", "C:/Workspace/kiripix", "kiripix", "probe", "segment-preview",
                          f"room.zz_trial0134_crop_{crop}", f"{x - ox},{y - oy}", "--json"],
                         capture_output=True, text=True, check=True).stdout
    cropped = json.loads(out)["data"]["result"]
    whole = json.loads((whole_dir / f"{name}.json").read_text())["data"]["result"]
    a, b = mask(whole), mask(cropped, ox, oy)
    iou = (a & b).sum() / max((a | b).sum(), 1)
    rows.append((name, crop, int(a.sum()), int(b.sum()), box(a), box(b), round(float(iou), 3)))
    print(*rows[-1], flush=True)
