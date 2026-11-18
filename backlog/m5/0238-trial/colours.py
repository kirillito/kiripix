"""Trial 0238 step 4: what colours the held things take under the two options, from the built Assets of the scratch Project:
held_base (no things), held_a1 (the things outside every part: 'fixed') and held_a1rows (phone and stick each a part with a ramp row)."""
import json, sys
import numpy as np
from PIL import Image
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
proj = SC / "proj/assets/character"
out = {}
for name in ("held_base", "held_a1", "held_a1rows"):
    pal = json.loads((proj / name / "work/palette/palette.json").read_text())
    rj = json.loads((proj / name / "work/render/render.json").read_text())
    mats = {m["name"]: m["index"] for m in rj["materials"]}
    ramps = {p["name"]: [c["index"] if isinstance(c, dict) else c for c in p.get("colors", p.get("indexes", []))] for p in pal.get("parts", [])}
    fin = proj / name / "work/finish/color"
    mat = proj / name / "work/render/material"
    thing = {"phone": ["phone", "phone_screen"], "stick": ["stick"]}
    seen = {k: set() for k in thing}
    body = set()
    for clip in (c["name"] for c in rj["clips"]):
        for d in EIGHT:
            for f in sorted((fin / clip / d).glob("*.png")):
                col = np.array(Image.open(f).convert("RGBA"))
                m = np.array(Image.open(mat / clip / d / f.name))
                for k, names in thing.items():
                    sel = np.isin(m, [mats[n] for n in names if n in mats])
                    if sel.any():
                        seen[k] |= {tuple(c[:3]) for c in col[sel]}
    out[name] = {"palette_colors": len(pal["colors"]), "fixed_count": pal.get("fixed", None), "parts": {p["name"]: p for p in pal.get("parts", [])}.keys() and [ (p["name"], len(p.get("colors", p.get("indexes", [])))) for p in pal.get("parts", [])],
                 "thing_colours": {k: sorted(v) for k, v in seen.items()}}
    print(name, "palette colours", len(pal["colors"]), "keys", [k for k in pal if k not in ("colors",)])
    print("   parts", out[name]["parts"])
    print("   thing colours", {k: len(v) for k, v in seen.items()}, {k: sorted(v) for k, v in seen.items()})
json.dump(out, open(HERE / "colours.json", "w"), indent=1, default=str)
