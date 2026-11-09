"""Run inside Blender: import one file and print one JSON line (`PROBE {...}`) about it.

    blender --background --factory-startup --python tests/fixtures/blender_probe.py -- <file>
"""

import json
import sys
from pathlib import Path

import bpy

path = Path(sys.argv[sys.argv.index("--") + 1])
bpy.ops.wm.read_factory_settings(use_empty=True)
if path.suffix == ".glb":
    bpy.ops.import_scene.gltf(filepath=str(path))
else:
    bpy.ops.import_scene.fbx(filepath=str(path))
meshes = [o for o in bpy.data.objects if o.type == "MESH"]
bones = [b.name for a in bpy.data.armatures for b in a.bones]
print("PROBE " + json.dumps({
    "meshes": len(meshes),
    "triangles": sum(len(p.vertices) - 2 for o in meshes for p in o.data.polygons),
    "bones": bones,
    "actions": sorted(a.name.split("|")[-1].split("Armature")[0] for a in bpy.data.actions),
    "materials": sorted(m.name.split(".")[0] for m in bpy.data.materials),
}))
