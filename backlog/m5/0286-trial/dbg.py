import sys
from common import *
from kiripix.ops.layers import connected_regions
for r in ROOMS:
    fit, solid, pit, key = load(r)
    h,w=solid.shape
    print(r)
    for reg in connected_regions(solid, eight=True):
        if len(reg)<20: continue
        y0,x0=reg.min(0); y1,x1=reg.max(0)+1
        print("  ",len(reg),(x0,y0,x1,y1), "edge" if (x0==0 or y0==0 or x1==w or y1==h) else "")
