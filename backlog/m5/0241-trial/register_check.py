"""Does registration recover a known shift and scale? Perturbs the angry edit and registers it back, both ways."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from portrait_set import *  # noqa: E402

folder = Path(__file__).parent / "input"
neutral = cutout(load(folder / "neutral.jpeg"))[0]
angry = cutout(load(folder / "angry.jpeg"))[0]
for sx, dx, dy in ((1.00, 6.0, -4.0), (1.03, 9.0, 5.0), (0.97, -12.0, 14.0)):
    moved = warp_nearest(angry, Alignment(sx, sx, dx, dy))
    cuts = {"neutral": neutral, "edit": moved}
    for label, box in (("whole", None), ("outside box", FACE_BOX)):
        a = register_set(cuts, "neutral", box)["edit"]
        # moved(p) = angry(s*p + d), so the expected alignment is the inverse: scale 1/s, shift -d/s
        fixed = warp_nearest(moved, a)
        keep = box_mask(neutral.shape[:2], FACE_BOX)
        both = (neutral[..., 3] == 255) & (fixed[..., 3] == 255) & ~keep
        diff = int((np.abs(neutral[..., :3].astype(int) - fixed[..., :3].astype(int)).sum(-1) > 60)[both].sum())
        print(f"perturb scale {sx} shift ({dx:+}, {dy:+}) | {label:11s} -> scale {a.scale_x:.4f}/{a.scale_y:.4f} "
              f"shift ({a.shift_x:+.2f}, {a.shift_y:+.2f}) [want {1/sx:.4f}, ({-dx/sx:+.2f}, {-dy/sx:+.2f})] resid {a.residual:.2f} tiles {a.tiles} | "
              f"px outside the box still differing {diff}")
