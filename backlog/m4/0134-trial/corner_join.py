"""Trial 0134: join the corner piece against two edges with Kiripix's join Ops, cropping the base to the piece's
extent (the workaround for the corner off-by-one in core/extend.py). Usage: corner_join.py base.png piece out.png ox oy"""
import json
import sys

import numpy as np
from PIL import Image

from kiripix.core.extend import BLEND, _snap, _trim
from kiripix.ops import Overlap, match_tone, register_piece, resample_piece, seam_join

base_path, piece_path, out_path, ox, oy = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), int(sys.argv[5])
base = np.ascontiguousarray(np.asarray(Image.open(base_path).convert("RGBA")))
piece = np.ascontiguousarray(np.asarray(Image.open(piece_path).convert("RGBA")))
sides = ["east", "south"]

overlaps = [Overlap.placed(s, base.shape, piece.shape, (ox, oy)) for s in sides]
reg = register_piece(base, piece, overlaps)
print("registration", reg)
reg = _snap(reg)
resampled, (px, py) = _trim(*resample_piece(piece, reg))
ph, pw = resampled.shape[:2]
# the workaround: the base cropped to where the piece ends, so each Overlap measures to the piece's far edge
cropped = np.ascontiguousarray(base[: py + ph, : px + pw])
print("piece at", (px, py), "size", (pw, ph), "base", base.shape[1::-1], "cropped to", cropped.shape[1::-1])
placed = [Overlap.placed(s, cropped.shape, resampled.shape, (px, py)) for s in sides]
toned, gain = match_tone(cropped, resampled, placed[0])
joined, seam = seam_join(cropped, toned, placed[0], BLEND)
lengths, diffs = [seam.length], [seam.mean_difference]
second = Overlap.placed(sides[1], joined.shape, toned.shape, seam.piece_origin)
joined, seam = seam_join(joined, toned, second, BLEND)
lengths.append(seam.length)
diffs.append(seam.mean_difference)
holes = int((joined[..., 3] != 255).sum())
Image.fromarray(joined).save(out_path)
print(json.dumps({"residual": round(reg.residual, 3), "patches": reg.patches, "scale": [reg.scale_x, reg.scale_y],
                  "gain": [gain.low, gain.high], "seam_length": [round(v, 1) for v in lengths],
                  "seam_difference": [round(v, 3) for v in diffs], "size": joined.shape[1::-1], "holes": holes}))
