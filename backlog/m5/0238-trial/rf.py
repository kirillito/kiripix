"""Trial 0238 (not Kiripix code): loads kiripix/blender/render_frames.py unchanged as a namespace (its source minus the final
`main()` call), so a trial script can call its functions and override some. Used inside Blender only."""
from pathlib import Path

RENDER_FRAMES = Path(__file__).resolve().parents[3] / "kiripix" / "blender" / "render_frames.py"


def load() -> dict:
    code = RENDER_FRAMES.read_text(encoding="utf-8").rstrip()
    assert code.endswith("main()")
    ns: dict = {"__name__": "render_frames_trial", "__file__": str(RENDER_FRAMES)}
    exec(compile(code[: -len("main()")], str(RENDER_FRAMES), "exec"), ns)
    return ns
