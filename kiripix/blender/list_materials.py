"""Run inside Blender: list the materials a held thing's mesh uses (ticket 0301), for `import --role thing` of a `.blend`.

    blender -b -P list_materials.py -- <args.json> <result.json>

args:   {"input": <a .blend or .glb>}
result: {"materials": [<names of the materials the file's meshes use, sorted>]}

The names are the ones `render_frames.py` numbers a mesh's materials by: the materials of the meshes' slots, sorted by name.
"""

import json
import sys
from pathlib import Path

import bpy


def read(path: Path) -> list:
    if path.suffix.lower() == ".blend":
        bpy.ops.wm.open_mainfile(filepath=str(path))
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(path))
    used = {slot.material.name for obj in bpy.data.objects if obj.type == "MESH" for slot in obj.material_slots
            if slot.material is not None}
    return sorted(used)


def main() -> None:
    separator = sys.argv.index("--")
    args = json.loads(Path(sys.argv[separator + 1]).read_text(encoding="utf-8"))
    result_path = Path(sys.argv[separator + 2])
    try:
        result: dict = {"materials": read(Path(args["input"]))}
    except Exception as error:  # reported to Kiripix as the import's failure
        result = {"error": f"{type(error).__name__}: {error}"}
    result_path.write_text(json.dumps(result), encoding="utf-8")


main()
