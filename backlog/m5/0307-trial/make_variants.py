"""0307 trial: for each body, a scratch Asset `<body>_f<N>` whose clips are decided at min(current fps, N) (transitions follow their `from` clip's
fps, as decided), then run by the real Stages (CPU). Usage: make_variants.py <caps...>  (default 8 6 4). The base Asset is the 12-fps cap's own."""
import json, shutil, sys, time
from common import *

caps = [int(c) for c in sys.argv[1:]] or [8, 6, 4]
for a in BODIES:
    for cap in caps:
        name = f"{a}_f{cap}"
        dst = PROJ / "assets/character" / name
        if (dst / "work/sheet/sheet.json").exists():
            continue
        shutil.rmtree(dst, ignore_errors=True)
        shutil.copytree(PROJ / "assets/character" / a, dst, ignore=shutil.ignore_patterns("work", "out", "history.jsonl"))
        for sub in ("model", "rig"):
            shutil.copytree(PROJ / "assets/character" / a / "work" / sub, dst / "work" / sub)
        lines = [json.loads(l) for l in (dst / "decisions/clips.jsonl").read_text().splitlines() if l.strip()]
        for l in lines:
            if l["decision"] == "clip":
                l["data"]["fps"] = min(int(l["data"]["fps"]), cap)
            elif l["decision"] == "transition" and "fps" in l["data"]:
                l["data"]["fps"] = min(int(l["data"]["fps"]), cap)
        (dst / "decisions/clips.jsonl").write_text("".join(json.dumps(l, separators=(",", ":")) + "\n" for l in lines))
        t = time.time()
        d = kpx("run", f"character.{name}", "--cpu")
        print(name, round(time.time() - t), d.get("ok"), [(r["stage"], r["outcome"], r.get("duration_s")) for r in (d.get("data") or {}).get("results", [])],
              [(f["code"], f["message"][:200]) for f in d.get("findings", [])], flush=True)
