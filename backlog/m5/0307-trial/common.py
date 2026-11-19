"""0307 trial helpers (plain Python, not Kiripix code)."""
import json, os, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
SC = Path("C:/Users/KIRILL~1.BRE/AppData/Local/Temp/claude/2a77692328d6afa9/7db54635-7122-4e36-9e8a-c7e8c080ddb1/scratchpad")
ART = Path("C:/Homespace/urban-mystery-club-art")  # read only
PY = "C:/Homespace/kiripix/.venv/Scripts/python.exe"
SNAP = SC / "snap"  # `git archive HEAD` of kiripix/: the committed code only
PROJ = SC / "proj"
BODIES = ["mc03_male", "mc03_female", "mc03_male_clothes01", "mc03_female_clothes01"]
EIGHT = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]


def kpx(*args, cwd=PROJ):
    env = dict(os.environ, PYTHONPATH=str(SNAP))
    r = subprocess.run([PY, "-m", "kiripix", *args, "--json"], cwd=cwd, env=env, capture_output=True, text=True)
    out = r.stdout
    return json.loads(out[out.index("{"):]) if "{" in out else {"raw": out + r.stderr}
