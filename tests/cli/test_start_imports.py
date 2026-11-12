"""What `kiripix.launch` imports at start: the heavy libraries wait until a Command needs them (ticket 0163).

The check reads `sys.modules` in a fresh interpreter, so it doesn't depend on machine speed."""

import subprocess
import sys

HEAVY = ("numpy", "PIL", "onnxruntime", "jsonschema")


def test_launch_imports_no_heavy_library() -> None:
    code = (
        "import sys, kiripix.launch\n"
        f"print(','.join(m for m in {HEAVY!r} if m in sys.modules))"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert done.stdout.strip() == "", f"imported at start: {done.stdout.strip()}"
