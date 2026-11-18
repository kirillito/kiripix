"""Trial 0238 (not Kiripix code), inside Blender: the rest geometry of a hand, and where a closed fist is. Imported by the other
scripts through sys.path."""
from mathutils import Matrix, Vector

FINGERS = ("Index", "Middle", "Ring", "Pinky")


def head(arm, name):
    return arm.matrix_world @ arm.data.bones["mixamorig:" + name].head_local


def rest_frame(arm, side="Right"):
    """The hand's own frame in the rest pose, in world space, from the bones' heads (nothing guessed by eye):
    X across the hand (index to little finger), Y along the fingers, Z out of the back of the hand (the palm is -Z).
    Origin: the wrist. Also the knuckle line's centre."""
    wrist = head(arm, f"{side}Hand")
    knuckles = [head(arm, f"{side}Hand{f}1") for f in FINGERS]
    k = sum(knuckles, Vector()) / 4.0
    fingers = (k - wrist).normalized()
    across = (knuckles[3] - knuckles[0])
    across = (across - fingers * across.dot(fingers)).normalized()
    back = across.cross(fingers)  # right-handed X x Y = Z
    m = Matrix((across, fingers, back)).transposed().to_4x4()
    m.translation = wrist
    return m, k


def fist_centre(arm, side="Right"):
    """The hollow of the fist in the current pose, world space: the centroid of the finger joints 1 to 3 of the four fingers and
    the thumb's second joint (the knuckles, the middle and the tips' joints close round the held thing)."""
    pts = []
    for f in FINGERS:
        for j in (1, 2, 3):
            pts.append(arm.matrix_world @ arm.pose.bones[f"mixamorig:{side}Hand{f}{j}"].head)
    pts.append(arm.matrix_world @ arm.pose.bones[f"mixamorig:{side}HandThumb2"].head)
    return sum(pts, Vector()) / len(pts)


def fist_axis(arm, side="Right"):
    """The line across the closed fist in the current pose (index to little finger, joint 2), world space, unit length."""
    a = arm.matrix_world @ arm.pose.bones[f"mixamorig:{side}HandIndex2"].head
    b = arm.matrix_world @ arm.pose.bones[f"mixamorig:{side}HandPinky2"].head
    return (b - a).normalized()
