import sys, time
from common import *
for a in BODIES:
    t = time.time()
    d = kpx("run", f"character.{a}", "--cpu")
    print(a, round(time.time() - t), d.get("ok"), [(r["stage"], r["outcome"], r.get("duration_s")) for r in (d.get("data") or {}).get("results", [])], [(f["code"], f["message"][:200]) for f in d.get("findings", [])], flush=True)
