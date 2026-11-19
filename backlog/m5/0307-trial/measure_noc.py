"""0307 trial: the combinations without C (mirror): B+D+E and A cap 8/6/4 + B+D+E. Adds them to measures.json."""
import json
from common import *
from lib import *
import measure
m = json.loads((HERE / "measures.json").read_text())
for a in BODIES:
    for suf in ("", "_f8", "_f6", "_f4"):
        asset, cell, _ = load_asset(PROJ / "assets/character" / (a + suf))
        r = measure.build(asset, cell, trim=True, dedupe=True, index=True)
        m[a + suf]["B+D+E"] = r
        print(a + suf, r["cells"], r["atlas"], r["disk"] // 1024, r["vram"] / 1048576, flush=True)
(HERE / "measures.json").write_text(json.dumps(m, indent=1))
