"""0347: put every route's frames in frames/<route>_<effect>/NNN.png and write enlarged (nearest) strips in previews/."""
import json, re, shutil
from pathlib import Path
import numpy as np
from PIL import Image
H = Path(__file__).parent
SRC = {
 "hit_spark": {"b": H/"b_kit/hit_spark", "d": H/"d_out/hit-spark.v1"},
 "telegraph": {"b": H/"b_kit/telegraph", "d": H/"d_out/telegraph.v2"},
 "sound_wave": {"c": H/"c_ops/sound_wave", "d": H/"d_out/sound-wave.v3"},
 "summon_puff": {"c": H/"c_ops/summon_puff", "d": H/"d_out/summon-puff.v2"},
 "buff_glow": {"c": H/"c_ops/buff_glow", "d": H/"d_out/buff-glow.v2"},
}
def frames_of(folder):
    if (folder/"strip.png").exists():
        return [np.array(Image.open(p).convert("RGBA")) for p in sorted(folder.glob("[0-9][0-9][0-9].png"))]
    fs = sorted((folder/"frames").glob("*.png"), key=lambda p: int(re.search(r"(\d+)$", p.stem).group(1)) if re.search(r"\d+$", p.stem) else 0)
    return [np.array(Image.open(p).convert("RGBA")) for p in fs]
def bg(h, w, k):
    y, x = np.mgrid[0:h, 0:w]
    c = np.where(((x // 4 + y // 4) % 2)[..., None] == 0, np.array([44, 57, 61]), np.array([37, 49, 54])).astype(np.uint8)
    return np.dstack([c, np.full((h, w), 255, np.uint8)])
def over(f, add=False):
    b = bg(*f.shape[:2], 1).astype(int)
    a = f[..., 3:4] > 0
    if add: out = np.where(a, np.minimum(255, b[..., :3] + f[..., :3]), b[..., :3])
    else:
        al = f[..., 3:4] / 255.0
        out = (f[..., :3] * al + b[..., :3] * (1 - al))
    return np.dstack([out.astype(np.uint8), np.full(f.shape[:2], 255, np.uint8)])
(H/"previews").mkdir(exist_ok=True)
for eff, routes in SRC.items():
    for r, folder in routes.items():
        fs = frames_of(folder)
        out = H/"frames"/f"{r}_{eff}"
        shutil.rmtree(out, ignore_errors=True); out.mkdir(parents=True)
        for i, f in enumerate(fs): Image.fromarray(f).save(out/f"{i:03d}.png")
        fs8 = [np.repeat(np.repeat(over(f), 4, 0), 4, 1) for f in fs]
        gap = np.full((fs8[0].shape[0], 4, 4), 255, np.uint8)
        strip = np.concatenate([x for f in fs8 for x in (f, gap)][:-1], axis=1)
        Image.fromarray(strip).save(H/"previews"/f"{eff}.{r}.strip.x4.png")
        print(eff, r, len(fs), fs[0].shape)
