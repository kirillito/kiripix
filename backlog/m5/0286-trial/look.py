import numpy as np, sys
from PIL import Image
from common import *
OUT.mkdir(exist_ok=True)
for r in ROOMS:
    fit, solid, pit, key = load(r)
    im = fit.copy()[..., :3].astype(float)
    im[solid] = im[solid]*0.5 + np.array([0,0,255])*0.5
    for k,m in key.items():
        im[m] = im[m]*0.5 + np.array([255,0,0])*0.5
    Image.fromarray(im.astype(np.uint8)).save(OUT/f"look_{r}.png")
    print(r, fit.shape, solid.sum(), {k:(int(m.sum())) for k,m in key.items()})
