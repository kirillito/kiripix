"""The join Commands (ticket 0201): one finding code per cause, and a cancel that stops `op seam-join` and leaves no output."""

import threading
import time
from pathlib import Path

import numpy as np
from conftest import Kiripix
from PIL import Image
from test_serve import Reply, Server, server  # noqa: F401 - the `server` fixture


def save(project: Kiripix, name: str, rgb: np.ndarray) -> None:
    Image.fromarray(rgb, "RGB").save(project.cwd / name)


def blocky(seed: int, height: int, width: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.kron(rng.integers(0, 256, (height // 4, width // 4, 3), dtype=np.uint8), np.ones((4, 4, 1), dtype=np.uint8))


def codes_of(result: dict) -> list[str]:  # type: ignore[type-arg]
    return [f["code"] for f in result["findings"]]


def test_a_piece_that_misses_the_base_is_join_no_overlap(project: Kiripix) -> None:
    save(project, "base.png", blocky(1, 80, 200))
    save(project, "piece.png", blocky(2, 80, 200))
    result = project.json("op", "register-piece", "base.png", "piece.png", "--overlap", "east:100:400", expect=1)
    [finding] = result["findings"]
    assert finding["code"] == "join.no_overlap" and "--help" in finding["fix"]


def test_a_flat_overlap_is_join_too_few_patches_and_needs_the_owner(project: Kiripix) -> None:
    for name in ("base.png", "piece.png"):
        Image.new("RGB", (200, 80), (90, 120, 150)).save(project.cwd / name)
    result = project.json("op", "register-piece", "base.png", "piece.png", "--overlap", "east:100", expect=1)
    [finding] = result["findings"]
    assert finding["code"] == "join.too_few_patches" and finding["owner_action"] and not finding.get("fix")


def test_an_overlap_wider_than_the_images_is_join_overlap_width(project: Kiripix) -> None:
    save(project, "base.png", blocky(1, 80, 200))
    save(project, "piece.png", blocky(2, 80, 200))
    result = project.json("op", "seam-join", "base.png", "piece.png", "out.png", "--overlap", "east:300", expect=1)
    assert codes_of(result) == ["join.overlap_width"] and result["findings"][0]["fix"]
    assert not (project.cwd / "out.png").exists()


def test_an_overlap_too_narrow_for_a_seam_is_join_overlap_too_narrow(project: Kiripix) -> None:
    save(project, "base.png", blocky(1, 80, 200))
    save(project, "piece.png", blocky(2, 80, 200))
    result = project.json("op", "seam-join", "base.png", "piece.png", "out.png", "--overlap", "east:1", "--blend", "6", expect=1)
    assert codes_of(result) == ["join.overlap_too_narrow"] and result["findings"][0]["fix"]


def test_images_that_share_no_pixel_are_join_no_shared_pixels(project: Kiripix) -> None:
    save(project, "base.png", blocky(1, 80, 200))
    clear = np.zeros((80, 200, 4), dtype=np.uint8)
    Image.fromarray(clear, "RGBA").save(project.cwd / "piece.png")
    result = project.json("op", "match-tone", "base.png", "piece.png", "out.png", "--overlap", "east:100", expect=1)
    assert codes_of(result) == ["join.no_shared_pixels"]
    assert result["findings"][0]["fix"].startswith("kiripix op register-piece base.png piece.png --overlap east:100 --output")


def test_a_cancel_during_seam_join_stops_within_a_second_and_writes_nothing(project: Kiripix, server: Server) -> None:  # noqa: F811
    save(project, "base.png", blocky(1, 16000, 800))
    save(project, "piece.png", blocky(2, 16000, 800))
    body = {"base": "base.png", "piece": "piece.png", "output": "out.png", "overlap": "east:600"}
    replies: list[Reply] = []
    caller = threading.Thread(target=lambda: replies.append(server.call("/api/op/seam-join", body, headers={"X-Kiripix-Job": "s"})))
    caller.start()
    time.sleep(0.4)
    asked = time.monotonic()
    cancel = server.call("/api/jobs/s/cancel")
    caller.join(timeout=30)
    stopped_after = time.monotonic() - asked

    assert cancel.json["data"] == {"job": "s", "cancelled": True}
    assert stopped_after < 1.5
    [reply] = replies
    assert reply.codes == ["run.cancelled"]
    assert not Path(project.cwd / "out.png").exists()
