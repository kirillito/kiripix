"""Shared loading for trial 0286: rooms of the art Project, read-only."""
from pathlib import Path

import numpy as np
from PIL import Image

ART = Path("C:/Workspace/urban-mystery-club-art")
ROOMS = ["ch01_002_laneway", "ch01_dungeon_r01", "ch01_dungeon_r02", "ch01_dungeon_r03"]
OUT = Path(__file__).parent / "out"


def load(room: str):
    d = ART / "assets/room" / room
    fit = np.asarray(Image.open(d / "work/fit/fit.png").convert("RGBA"))
    solid = np.asarray(Image.open(d / "work/masks/solid.png").convert("L")) > 0
    pit_file = d / "work/masks/pit.png"
    pit = np.asarray(Image.open(pit_file).convert("L")) > 0 if pit_file.exists() else np.zeros_like(solid)
    key = {}
    for f in sorted((d / "out/export").glob("layer.*.png")):
        key[f.name[6:-4]] = np.asarray(Image.open(f).convert("RGBA"))[..., 3] > 0
    return fit, solid, pit, key


def iou(a, b):
    u = (a | b).sum()
    return float((a & b).sum() / u) if u else 0.0
