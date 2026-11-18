import sys, json; sys.path.insert(0,"C:/Workspace/kiripix/backlog/m5/0238-trial")
from common import *
names=["idle","walk","run","attack","phone_in","phone","phone_out"]
args=base_args(SC/"model.blend",names)
r=blender("grip_metrics.py",args,SC/"grip.json")
print({k:len(v) for k,v in r["clips"].items()}, r["knuckle_centre_hand_local"])
