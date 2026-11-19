"""0307 trial: a scratch Project (in the scratchpad) of the four mc03 bodies, copied from the art repo (read only).
The Owner's art repo is mid-remodel (its last Model pick and its rigged file are newer than the built work/), so the scratch copy
pins each Asset's Model pick to the variant its built work/model was made from, and puts the rigged file back in src/rigged."""
import json, shutil, sys
from pathlib import Path
from common import SC, ART, BODIES

proj = SC / "proj"
shutil.rmtree(proj, ignore_errors=True)
(proj / "assets/character").mkdir(parents=True)
shutil.copy(ART / "kiripix.toml", proj / "kiripix.toml")
shutil.copytree(ART / "style", proj / "style")
for a in BODIES:
    src, dst = ART / "assets/character" / a, proj / "assets/character" / a
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("out", "history.jsonl", "time.jsonl", "_retired_rigged", "work"))
    rig = json.loads((src / "work/rig/rig.json").read_text())
    (dst / "src/rigged").mkdir(exist_ok=True)
    shutil.copy(src / "_retired_rigged" / rig["file"], dst / "src/rigged" / rig["file"])
    variant = json.loads((src / "work/model/model.json").read_text())["source"].split(".")[0]
    (dst / "decisions/model.jsonl").write_text(json.dumps({"id": "01M7BQRVWQME70KTG9DTBX5QXR", "parent": None, "decision": "pick", "data": {"variant": variant}}, separators=(",", ":")) + "\n")
    print(a, rig["file"], variant)
