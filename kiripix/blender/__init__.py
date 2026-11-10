"""bpy scripts, run inside Blender only (spec §12): `blender -b -P kiripix/blender/<script>.py -- <args.json> <result.json>`.

Nothing in Kiripix imports this package; `kiripix.recipes.blender_launcher` runs the scripts as files. The scripts share
no module: Blender runs each as `__main__`, so each carries the few helpers it needs.
"""
