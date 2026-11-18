"""Trial 0238: a scratch Project in the scratchpad: the art repo's kiripix.toml and style (copied), and the asset
mc03_male_clothes01 copied as `held_base` with only the six clips of the trial. The art repo is read only."""
import json, shutil, sys
sys.path.insert(0, "C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
ART = Path("C:/Workspace/urban-mystery-club-art")
proj = SC / "proj"
shutil.rmtree(proj, ignore_errors=True)
proj.mkdir()
shutil.copy(ART / "kiripix.toml", proj / "kiripix.toml")
shutil.copytree(ART / "style", proj / "style")
dst = proj / "assets/character/held_base"
shutil.copytree(ASSET, dst, ignore=shutil.ignore_patterns("out", "_retired_rigged", "history.jsonl"))
for folder in ("clips", "render", "palette", "finish", "sheet"):
    shutil.rmtree(dst / "work" / folder, ignore_errors=True)
keep = {"idle", "walk", "attack", "phone_in", "phone", "phone_out"}
lines = [json.loads(l) for l in (ASSET / "decisions/clips.jsonl").read_text().splitlines() if l.strip()]
last = {}
for l in lines:
    if l["decision"] == "clip":
        last[l["data"]["name"]] = l  # the latest of each name is the current one
chain, parent = [], None
for name in ["idle", "walk", "attack", "phone_in", "phone", "phone_out"]:
    l = dict(last[name]); l["parent"] = parent; parent = l["id"]; chain.append(l)
(dst / "decisions/clips.jsonl").write_text("".join(json.dumps(l, separators=(",", ":")) + "\n" for l in chain), encoding="utf-8")
print("ok", len(chain))
