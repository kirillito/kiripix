import sys, json; sys.path.insert(0,"C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
cfg = json.loads((HERE / "grip_config.json").read_text())
args = {"model": str(SC / "model.blend"), "out": str(SC / "things"), **cfg}
blender("build_things.py", args, SC / "build_result.json")
print("built")
