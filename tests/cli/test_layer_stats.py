"""The `layer-stats` Probe (ticket 0084, spec §10.1): a Layer's numbers and its y-sort line, from the `layers` output as
built, with nothing recorded."""

import json
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, stage_status
from PIL import Image
from test_layers_stage import ROOM, accept, alpha_of, built_room, click, lift, out, trim
from test_place import above, line

PROBE = ["probe", "layer-stats", ROOM]


def stats(project: Kiripix, expect: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = project.json(*PROBE, expect=expect)["data"]["result"]
    return result


def layer(project: Kiripix, name: str) -> dict[str, Any]:
    found: dict[str, Any] = next(entry for entry in stats(project)["layers"] if entry["id"] == name)
    return found


def pieces_of(alpha: np.ndarray) -> list[int]:
    """The sizes of the 8-connected pieces, worked out here in a different way from the Probe: by merging labels."""
    seen = np.zeros_like(alpha)
    sizes = []
    for y, x in np.argwhere(alpha):
        if seen[y, x]:
            continue
        stack, size = [(y, x)], 0
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            size += 1
            for ny in range(cy - 1, cy + 2):
                for nx in range(cx - 1, cx + 2):
                    if 0 <= ny < alpha.shape[0] and 0 <= nx < alpha.shape[1] and alpha[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        sizes.append(size)
    return sorted(sizes, reverse=True)


def damaged_lamp(project: Kiripix) -> Path:
    """The lamp lifted, then cut in two by a stripe and holed by a dot, and a crate lifted whole."""
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    click(project, "crate", 40, 24)
    lift(project)
    accept(project)
    alpha = alpha_of(folder, "lamp")
    rows, columns = np.nonzero(alpha)
    middle = (int(columns.min()) + int(columns.max())) // 2
    trim(project, "lamp", [[middle, int(y)] for y in range(int(rows.min()), int(rows.max()) + 1)])
    trim(project, "crate", [[40, 24]])  # a hole in the crate
    project.json("run", ROOM, "layers")
    return folder


def test_the_numbers_match_the_layer_png_for_a_layer_in_pieces_and_one_with_a_hole(project: Kiripix) -> None:
    folder = damaged_lamp(project)
    lamp, crate = alpha_of(folder, "lamp"), alpha_of(folder, "crate")

    result = stats(project)

    assert result["awaiting_review"] is False and [e["id"] for e in result["layers"]] == ["lamp", "crate"]
    one, two = result["layers"]
    rows, columns = np.nonzero(lamp)
    assert one["pixels"] == int(lamp.sum())
    assert one["box"] == {"x": int(columns.min()), "y": int(rows.min()), "width": int(columns.max() - columns.min() + 1),
                          "height": int(rows.max() - rows.min() + 1)}
    sizes = pieces_of(lamp)
    assert len(sizes) == 2 and one["pieces"]["count"] == 2 and one["pieces"]["largest"] == sizes
    assert one["holes"] == 0
    assert two["pieces"]["count"] == 1 and two["holes"] == 1 and two["pixels"] == int(crate.sum())
    assert two["partial"] == 0 and one["pieces"]["small"] == []


def test_a_speck_is_listed_with_its_pixels(project: Kiripix) -> None:
    folder = damaged_lamp(project)
    alpha = alpha_of(folder, "lamp")
    rows, columns = np.nonzero(alpha)
    middle = (int(columns.min()) + int(columns.max())) // 2
    # cut the right half down to one pixel at its top, and the stripe stays out: a speck of one pixel
    right = [[x, y] for y in range(int(rows.min()), int(rows.max()) + 1) for x in range(middle + 1, int(columns.max()) + 1)
             if alpha[y, x]]
    keep = right[0]
    trim(project, "lamp", right[1:])
    project.json("run", ROOM, "layers")

    pieces = layer(project, "lamp")["pieces"]

    assert pieces["count"] == 2 and pieces["small"] == [{"pixels": 1, "at": [keep]}]
    assert pieces["largest"][-1] == 1


def test_it_answers_while_layers_awaits_review_and_says_so(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    assert stage_status(project, ROOM)["layers"] == "needs-review"

    result = stats(project)

    assert result["awaiting_review"] is True and result["status"] == "needs-review"
    assert result["layers"][0]["pixels"] == int(alpha_of(folder, "lamp").sum())


def test_partial_counts_pixels_with_alpha_between_0_and_255(project: Kiripix) -> None:
    folder = built_room(project)
    click(project, "lamp", 8, 8)
    lift(project)
    path = out(folder) / "layer.lamp.png"
    image = np.array(Image.open(path).convert("RGBA"))
    y, x = np.argwhere(image[..., 3] > 0)[0]
    image[y, x, 3] = 100
    Image.fromarray(image, "RGBA").save(path)

    assert layer(project, "lamp")["partial"] == 1


def test_sort_shows_a_line_above_and_none_from_the_journal_and_follows_an_undo(project: Kiripix) -> None:
    damaged_lamp(project)
    assert layer(project, "lamp")["sort"] == {"state": "none"}

    line(project, "lamp", y=20)
    assert layer(project, "lamp")["sort"] == {"state": "line", "marker": "ysort.lamp", "y": 20, "slope": 0}
    above(project, "lamp")
    assert layer(project, "lamp")["sort"] == {"state": "above"}
    project.json("undo", ROOM, "place")
    assert layer(project, "lamp")["sort"]["state"] == "line"
    project.json("undo", ROOM, "place")
    assert layer(project, "lamp")["sort"] == {"state": "none"}
    assert layer(project, "crate")["sort"] == {"state": "none"}


def test_the_ysort_suggestion_is_accepted_by_decide_and_clears_layer_no_ysort(project: Kiripix) -> None:
    folder = damaged_lamp(project)
    alpha = alpha_of(folder, "lamp")
    rows, columns = np.nonzero(alpha)
    suggestion = layer(project, "lamp")["ysort"]
    assert suggestion == {"id": "ysort.lamp", "type": "ysort", "layer": "lamp", "x": int(columns.min()),
                          "y": int(rows.max()), "x2": int(columns.max()), "y2": int(rows.max())}

    for name in ("lamp", "crate"):
        data = layer(project, name)["ysort"]
        project.json("decide", ROOM, "place", "--decision", json.dumps({"decision": "marker", "data": data}))
    project.json("run", ROOM, expect=3)

    codes = [f["code"] for f in project.json("check", ROOM)["findings"]]
    assert "layer.no_ysort" not in codes
    assert layer(project, "lamp")["sort"]["y"] == int(rows.max())


def test_with_no_layers_the_answer_is_an_empty_list(project: Kiripix) -> None:
    built_room(project)

    result = stats(project)

    assert result["layers"] == [] and result["awaiting_review"] is False


def test_nothing_is_written_and_no_status_changes(project: Kiripix) -> None:
    folder = damaged_lamp(project)
    status = stage_status(project, ROOM)
    before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file() and ".kiripix" not in p.parts}
    locks = project.cwd / ".kiripix" / "locks"

    stats(project)

    assert stage_status(project, ROOM) == status
    assert {p: p.read_bytes() for p in folder.rglob("*") if p.is_file() and ".kiripix" not in p.parts} == before
    assert not locks.exists() or not any(locks.iterdir())


def test_other_assets_and_arguments_are_refused(project: Kiripix) -> None:
    built_room(project)

    assert project.json(*PROBE, "x", expect=1)["findings"][0]["code"] == "input.invalid"
    project.json("new", "prop", "bench")
    assert project.json("probe", "layer-stats", "prop.bench", expect=1)["findings"][0]["code"] == "probe.not_supported"
