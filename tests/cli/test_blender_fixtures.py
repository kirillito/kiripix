"""The character test fixtures open in Blender (ticket 0100). Skipped without Blender 5.2.x."""

import json
import os
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent.parent / "fixtures"
CHARACTERS = FIXTURES / "characters"


def probe(file: Path) -> dict:
    done = subprocess.run(
        [os.environ["KIRIPIX_BLENDER"], "--background", "--factory-startup", "--python",
         str(FIXTURES / "blender_probe.py"), "--", str(file)],
        capture_output=True, text=True, timeout=120)
    lines = [line for line in done.stdout.splitlines() if line.startswith("PROBE ")]
    assert lines, f"Blender printed no probe line:\n{done.stdout}\n{done.stderr}"
    return json.loads(lines[-1][len("PROBE "):])


@pytest.mark.blender
@pytest.mark.parametrize("suffix", [".glb", ".fbx"])
def test_rigged_fixture_opens_with_a_rig_two_actions_and_two_materials(suffix: str) -> None:
    info = probe(CHARACTERS / f"rigged{suffix}")
    assert info["meshes"] >= 1 and 0 < info["triangles"] <= 500
    assert "root" in info["bones"] and "mixamorig:Hips" in info["bones"]
    assert len(info["actions"]) >= 2
    assert {"skin", "cloth"} <= set(info["materials"])


@pytest.mark.blender
@pytest.mark.parametrize("suffix", [".glb", ".fbx"])
def test_no_rig_fixture_opens_with_a_mesh_and_no_bones(suffix: str) -> None:
    info = probe(CHARACTERS / f"no_rig{suffix}")
    assert info["meshes"] >= 1
    assert info["bones"] == []
