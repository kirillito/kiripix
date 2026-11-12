"""What `kiripix.launch` imports at start: the heavy libraries wait until a Command needs them (ticket 0163).

The check reads `sys.modules` in a fresh interpreter, so it doesn't depend on machine speed."""

import subprocess
import sys
from pathlib import Path

HEAVY = ("numpy", "PIL", "onnxruntime", "jsonschema")


def test_launch_imports_no_heavy_library() -> None:
    code = (
        "import sys, kiripix.launch\n"
        f"print(','.join(m for m in {HEAVY!r} if m in sys.modules))"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "", f"imported at start: {done.stdout.strip()}"


def test_light_commands_import_no_heavy_library(tmp_path: Path) -> None:
    """`--help`, `describe`, `schema` and `status` on an empty Project don't load numpy, PIL, onnxruntime or jsonschema."""
    subprocess.run([sys.executable, "-m", "kiripix", "init", str(tmp_path)], capture_output=True, check=True)
    code = (
        "import sys\n"
        "from kiripix.launch import main\n"
        "args = sys.argv[1:]\n"
        "sys.argv = ['kiripix', *args]\n"
        "try:\n"
        "    main()\n"
        "except SystemExit:\n"
        "    pass\n"
        f"print('LOADED:' + ','.join(m for m in {HEAVY!r} if m in sys.modules))"
    )
    for args in (["--help"], ["describe", "--json"], ["schema", "--json"], ["status", "--json"]):
        done = subprocess.run([sys.executable, "-c", code, *args], capture_output=True, text=True, cwd=tmp_path)
        loaded = done.stdout.strip().splitlines()[-1]
        assert loaded == "LOADED:", f"`kiripix {' '.join(args)}` imported: {loaded}\n{done.stderr}"
