"""Trial 0153 (not Kiripix code): run generate.py of the art repo unchanged, with its output folder moved, then split
each built character's mesh by material into objects. Run: blender -b --factory-startup -P gen.py -- <outdir> <a.toml> ...
The art repo is only read."""
import os, sys
ART = "C:/Homespace/urban-mystery-club-art/chargen"
args = sys.argv[sys.argv.index("--") + 1:]
OUTDIR = args[0]
src = open(ART + "/generate.py", encoding="utf-8").read()
marker = 'for arg in sys.argv[sys.argv.index("--") + 1:]:\n    build(arg)'
assert marker in src
src = src.replace(marker, "").replace('OUT = os.path.join(HERE, "out")', f"OUT = {OUTDIR!r}")
ns = {"__name__": "generate_trial", "__file__": ART + "/generate.py"}
exec(compile(src, ART + "/generate.py", "exec"), ns)
import bpy
for toml in args[1:]:
    ns["build"](toml)
