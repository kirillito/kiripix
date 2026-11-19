"""Build the held-thing test mesh in Blender 5.2 (ticket 0302): `tests/fixtures/characters/render_thing.glb`.

Run it from the repository root; it overwrites the file:

    blender --background --factory-startup --python tests/fixtures/make_render_thing.py

A box 0.3 m long along +Y and 0.1 m square, its origin in the middle of one end (the grip), one material, `metal`. A thing's origin
and axes are its grip, so at a socket bone (whose Y runs along the bone) it points the way the bone does. No skin, no armature.
"""

import sys
from pathlib import Path

import bmesh
import bpy

bpy.ops.wm.read_factory_settings(use_empty=True)
mesh = bpy.data.meshes.new("thing")
shape = bmesh.new()
bmesh.ops.create_cube(shape, size=1.0)
for vertex in shape.verts:
    vertex.co = (vertex.co.x * 0.1, 0.15 + vertex.co.y * 0.3, vertex.co.z * 0.1)
shape.to_mesh(mesh)
shape.free()
material = bpy.data.materials.new("metal")
material.diffuse_color = (0.8, 0.8, 0.85, 1.0)
mesh.materials.append(material)
obj = bpy.data.objects.new("thing", mesh)
bpy.context.scene.collection.objects.link(obj)
target = Path(sys.argv[sys.argv.index("--") + 1]) if "--" in sys.argv else Path("tests/fixtures/characters/render_thing.glb")
bpy.ops.export_scene.gltf(filepath=str(target), export_format="GLB", use_selection=False)
