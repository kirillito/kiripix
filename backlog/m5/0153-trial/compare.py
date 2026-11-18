"""Trial 0153 (plain Python): stack the layers in every order, count differing pixels against the full render.
uv run --project <kiripix> python compare.py"""
from stacklib import *
import json, itertools
results = {"orders": {}, "frames": {}, "outline": {}}
perms = list(itertools.permutations(range(4)))
for sname, order in STACKS.items():
    full = "full_" + sname
    rows = []
    for clip, d, i in frames():
        base = rgba("body", clip, d, i)
        parts = {l: rgba("layer_" + l, clip, d, i) for l in order}
        ref = rgba(full, clip, d, i)
        counts = []
        for p in perms:
            counts.append(int(differ(stack(base, [parts[order[k]] for k in p]), ref).sum()))
        natural = counts[perms.index((0, 1, 2, 3))]
        zdepth = [(base, load("body", "depth", clip, d, i))] + [(parts[l], load("layer_" + l, "depth", clip, d, i)) for l in order]
        z = int(differ(zmerge(zdepth), ref).sum())
        rows.append({"clip": clip, "dir": d, "i": i, "natural": natural, "per_perm": counts, "z": z,
                     "visible_px": int((ref[..., 3] > 0).sum()), "layer_px": {l: int((parts[l][..., 3] > 0).sum()) for l in order}})
    results["frames"][sname] = rows
    tot = lambda key: sum(r[key] for r in rows)
    perm_totals = [sum(r["per_perm"][k] for r in rows) for k in range(len(perms))]
    best = int(np.argmin(perm_totals))
    by_dir = {}
    for d in EIGHT:
        sub = [r for r in rows if r["dir"] == d]
        t = [sum(r["per_perm"][k] for r in sub) for k in range(len(perms))]
        by_dir[d] = {"natural": t[perms.index((0, 1, 2, 3))], "best_order": [order[k] for k in perms[int(np.argmin(t))]], "best": min(t)}
    per_frame_best = sum(min(r["per_perm"]) for r in rows)
    by_clip = {}
    for clip in CLIPS:
        sub = [r for r in rows if r["clip"] == clip]
        by_clip[clip] = {"frames": len(sub), "natural": sum(r["natural"] for r in sub), "z": sum(r["z"] for r in sub),
                         "frames_with_diff": sum(1 for r in sub if r["natural"]), "max_frame": max(r["natural"] for r in sub),
                         "visible_px_total": sum(r["visible_px"] for r in sub)}
    results["orders"][sname] = {"stack": ["body"] + order, "natural_total": tot("natural"), "z_total": tot("z"),
        "best_fixed": {"order": [order[k] for k in perms[best]], "total": perm_totals[best]}, "per_direction_best_total": sum(v["best"] for v in by_dir.values()),
        "per_frame_best_total": per_frame_best, "by_dir": by_dir, "by_clip": by_clip,
        "frames": len(rows), "visible_px_total": tot("visible_px"),
        "perm_totals": {"".join(order[k][0] for k in p): perm_totals[n] for n, p in enumerate(perms)}}
json.dump(results, open(HERE / "diff_counts.json", "w"), indent=1)
print(json.dumps({k: {kk: v for kk, v in s.items() if kk in ("natural_total", "z_total", "best_fixed", "per_direction_best_total", "per_frame_best_total", "frames", "visible_px_total", "by_clip")} for k, s in results["orders"].items()}, indent=1))
print(json.dumps({s: v["by_dir"] for s, v in results["orders"].items()}, indent=0))
