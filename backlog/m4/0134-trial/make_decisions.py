"""Trial 0134: the first pass of masks, layers and place Decisions for room.ch01_002_laneway, written as JSON arrays."""
import json
import sys
from pathlib import Path

out = Path(sys.argv[1])


def rect(mask, x0, y0, x1, y1, erase=False):
    return {"decision": "polygon", "data": {"mask": mask, "erase": erase,
                                             "points": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}}


def click(mask, x, y, positive=True):
    return {"decision": "click", "data": {"x": x, "y": y, "mask": mask, "positive": positive}}


def box(mask, x0, y0, x1, y1, positive=True):
    return {"decision": "box", "data": {"x0": x0, "y0": y0, "x1": x1, "y1": y1, "mask": mask, "positive": positive}}


masks = [
    {"decision": "border", "data": {"mask": "solid", "sides": ["top", "right", "bottom", "left"]}},
    # north: tree, fence, white garage; behind the car; the utility pole; green garage and brick house
    rect("solid", 0, 0, 312, 142), rect("solid", 352, 0, 448, 30), rect("solid", 448, 0, 465, 165),
    rect("solid", 465, 0, 925, 145),
    # bases of the posts and the tree
    rect("solid", 1016, 168, 1032, 182), rect("solid", 936, 172, 944, 182), rect("solid", 934, 312, 942, 320),
    rect("solid", 1000, 100, 1012, 112),
    box("solid", 1046, 60, 1106, 182), box("solid", 358, 32, 434, 144),  # van, car
    # the south fence, with the opening at the slab (x 362-520)
    rect("solid", 0, 292, 362, 340), rect("solid", 520, 292, 658, 340),
    # the back yards
    click("solid", 45, 400),  # shed
    rect("solid", 0, 358, 136, 402), rect("solid", 126, 358, 138, 624), rect("solid", 0, 498, 104, 624),
    rect("solid", 190, 540, 202, 624), rect("solid", 318, 486, 452, 578),
    rect("solid", 355, 357, 702, 408), rect("solid", 700, 362, 838, 406), rect("solid", 526, 380, 540, 624),
    click("solid", 820, 500), rect("solid", 836, 400, 848, 624),  # hedge and its fence
    click("solid", 925, 412), click("solid", 912, 525), box("solid", 560, 402, 632, 452),  # hydrant, rack, chairs
    box("pit", 372, 205, 525, 258),  # the puddle
]

layers = [
    {"decision": "box", "data": {"x0": 358, "y0": 32, "x1": 434, "y1": 144, "layer": "car", "positive": True}},
    {"decision": "box", "data": {"x0": 1046, "y0": 60, "x1": 1106, "y1": 182, "layer": "van", "positive": True}},
    {"decision": "click", "data": {"x": 1025, "y": 100, "layer": "lamp", "positive": True}},
    {"decision": "click", "data": {"x": 925, "y": 412, "layer": "hydrant", "positive": True}},
    {"decision": "click", "data": {"x": 45, "y": 400, "layer": "shed", "positive": True}},
]


def marker(**data):
    return {"decision": "marker", "data": data}


place = [
    marker(id="player", type="spawn", x=60, y=230),
    marker(id="west", type="exit", x=8, y=225, target_room="room.ch01_001_tbd", target_exit="laneway"),
    marker(id="alley", type="exit", x=332, y=150, target_room="room.ch01_003_tbd", target_exit="laneway"),
    marker(id="major_st_north", type="exit", x=966, y=8, target_room="room.ch01_004_tbd", target_exit="laneway"),
    marker(id="major_st_south", type="exit", x=966, y=616, target_room="room.ch01_005_tbd", target_exit="laneway"),
    marker(id="back_gate", type="interactable", x=222, y=284),
    marker(id="battle.tutorial", type="area", x=160, y=150, x2=800, y2=288, cell=16, walkable=True),
    marker(id="car", type="ysort", layer="car", x=359, y=143, x2=439, y2=143),
    marker(id="van", type="ysort", layer="van", x=1051, y=180, x2=1106, y2=180),
    marker(id="lamp", type="ysort", layer="lamp", x=1016, y=180, x2=1032, y2=180),
    marker(id="hydrant", type="ysort", layer="hydrant", x=911, y=434, x2=939, y2=434),
    marker(id="shed", type="ysort", layer="shed", x=7, y=463, x2=80, y2=463),
]

for name, entries in (("masks", masks), ("layers", layers), ("place", place)):
    (out / f"{name}.json").write_text(json.dumps(entries, indent=1))
    print(name, len(entries))
