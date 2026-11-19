"""0307 trial: measures.json -> the Markdown tables of the ticket (summary.md, kept here). Disk = colour.png + normal.png as this trial's encoder
writes them (the real `sheet` Stage's files are in `real_sheet_bytes`); VRAM = RGBA8 colour + normal atlas, width x height x 4 each."""
import json
from common import *
m = json.loads((HERE / "measures.json").read_text())
KB, MB = 1024, 1024 * 1024
lines = []
for a in BODIES:
    base = m[a]["none"]
    rows = [("current (no lever)", m[a]["none"]), ("A fps cap 8", m.get(a + "_f8", {}).get("none")), ("A fps cap 6", m.get(a + "_f6", {}).get("none")),
            ("A fps cap 4", m.get(a + "_f4", {}).get("none")), ("B trimmed cells", m[a]["B_trim"]), ("C mirrored (5 directions)", m[a]["C_mirror"]),
            ("D duplicates shared", m[a]["D_dedupe"]), ("E indexed PNG", m[a]["E_indexed"]), ("B+C+D+E", m[a]["B+C+D+E"]),
            ("A cap 8 + B+C+D+E", m.get(a + "_f8", {}).get("B+C+D+E")), ("A cap 6 + B+C+D+E", m.get(a + "_f6", {}).get("B+C+D+E")),
            ("A cap 4 + B+C+D+E", m.get(a + "_f4", {}).get("B+C+D+E"))]
    real = m[a]["real_sheet_bytes"]
    lines.append(f"\n**{a}** (real sheet: {m[a]['real_atlas'][0]} x {m[a]['real_atlas'][1]}, colour.png {real['color'] // KB} KB, normal.png {real['normal'] // KB} KB)\n")
    lines.append("| Lever | Cells | Atlas px | Disk KB | Disk vs now | VRAM MB | VRAM vs now |\n|---|---|---|---|---|---|---|")
    for name, r in rows:
        if r is None:
            continue
        lines.append(f"| {name} | {r['cells']} | {r['atlas'][0]} x {r['atlas'][1]} | {r['disk'] // KB} | {100 * (r['disk'] / base['disk'] - 1):+.0f} % | {r['vram'] / MB:.1f} | {100 * (r['vram'] / base['vram'] - 1):+.0f} % |")
(HERE / "summary.md").write_text("\n".join(lines))
print("\n".join(lines))
