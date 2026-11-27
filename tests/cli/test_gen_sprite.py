"""`gen` for a sprite through PixelLab (ticket 0388), over the fake transport of the test recipes (`pixellab-requests/`): a
character from text or from the sprite's frames, a state, motion by PixelLab's rig, one pending call for an operation's jobs, a
sheet per call, the ledger's generations. No test reaches PixelLab."""

import datetime
import json
import tomllib
import zipfile
from pathlib import Path
from typing import Any

from conftest import Kiripix
from test_gen import ledger, providers, sending
from test_pixellab import requests
from test_sprite import FOUR, SPRITE, decide, new_sprite, png_sheet, sheet_of

FOUR_WORDS = {"south", "west", "north", "east"}


def sprite(project: Kiripix, approve: str = "none") -> Path:
    """A sprite, PixelLab the default Provider with a fake key, sending at once unless `approve` says otherwise."""
    folder = new_sprite(project)
    sending(project, default="pixellab", approve=approve)
    (project.cwd / ".env").write_text("PIXELLAB_API_KEY=pl-fake-for-the-fake-transport\n", encoding="utf-8")
    return folder


def posts(project: Kiripix) -> list[dict[str, Any]]:
    return [r for r in requests(project) if r["method"] == "POST"]


def sheet_entries(folder: Path, name: str) -> list[str]:
    [path] = (folder / "src" / "sheets").glob(f"{name}*.zip")
    with zipfile.ZipFile(path) as archive:
        return sorted(archive.namelist())


def frames_json(folder: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads((folder / "work" / "frames" / "frames.json").read_text(encoding="utf-8"))
    return value


def settings(folder: Path) -> dict[str, Any]:
    return tomllib.loads((folder / "asset.toml").read_text(encoding="utf-8"))


def a_character(project: Kiripix, folder: Path) -> dict[str, Any]:
    """A character from text, its sheet's frames built."""
    data: dict[str, Any] = project.json("gen", SPRITE, "--prompt", "a raccoon")["data"]
    project.json("run", SPRITE, "frames")
    return data


def test_a_prompt_makes_a_character_and_stores_its_rotations_as_the_idle_clip(project: Kiripix) -> None:
    folder = sprite(project)

    data = project.json("gen", SPRITE, "--prompt", "a raccoon")["data"]

    assert data["sent"] is True and data["operation"] == "character" and data["target"] == "character"
    assert data["clips"] == ["idle"] and data["next"] == f"kiripix run {SPRITE} frames" and data["jobs"] == 1
    assert data["character_id"].startswith("char-") and data["replaced_character_id"] is None
    assert data["terms"].startswith("output is the Project's")
    [post] = posts(project)
    assert post["path"] == "/create-character-v3" and post["body"]["description"] == "a raccoon"
    assert post["body"]["image_size"] == {"width": 32, "height": 32} and post["body"]["n_directions"] == 4
    pixellab = settings(folder)["sprite"]["pixellab"]
    assert pixellab == {"character_id": data["character_id"], "canvas": "32x32", "made_from": "text", "view": "high top-down"}
    assert sheet_entries(folder, data["sheet"]) == sorted(f"Idle/rotations/{word}.png" for word in FOUR_WORDS)
    [line] = ledger(project)
    assert line["schema_version"] == 2 and line["operation"] == "create-character-v3" and line["generations"] is None
    assert line["call"] == data["call"] and line["outcome"] == "done" and line["usd"] == 0.03
    names = [json.loads(n) for n in (folder / "imported.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [(n["provider"], n["call"]) for n in names] == [("pixellab", data["call"])]
    kept = project.cwd / ".kiripix" / "calls" / "sent" / data["call"]
    assert (kept / "00-create-character-v3.zip").is_file() and (kept / "00-create-character-v3.json").is_file()
    history = [json.loads(line) for line in (folder / "history.jsonl").read_text(encoding="utf-8").splitlines()]
    [logged] = [h for h in history if h.get("call") == data["call"]]
    assert logged["operation"] == "character" and logged["outcome"] == "done" and logged["character_id"] == data["character_id"]

    project.json("run", SPRITE, "frames")  # the naming rule reads the sheet: no Decision

    assert [c["name"] for c in frames_json(folder)["clips"]] == ["idle"]


def test_a_second_character_call_replaces_the_first_and_says_so(project: Kiripix) -> None:
    folder = sprite(project)
    first = project.json("gen", SPRITE, "--prompt", "a raccoon")["data"]

    second = project.json("gen", SPRITE, "--prompt", "a squirrel")["data"]

    assert second["replaced_character_id"] == first["character_id"]
    assert settings(folder)["sprite"]["pixellab"]["character_id"] == second["character_id"]


def test_from_frames_sends_the_first_frames_stores_no_sheet_and_keeps_the_id(project: Kiripix) -> None:
    folder = sprite(project)
    png_sheet(project, sheet_of(FOUR, 1), 1)
    project.json("run", SPRITE, "frames")
    sheets_before = sorted((folder / "src" / "sheets").glob("*"))

    data = project.json("gen", SPRITE, "--from-frames")["data"]

    assert data["sent"] is True and data["sheet"] is None and data["clips"] == [] and data["character_id"]
    assert sorted((folder / "src" / "sheets").glob("*")) == sheets_before
    [post] = posts(project)
    body = post["body"]
    assert {*body["direction_images"]} == FOUR_WORDS - {"south"} and body["reference_image"]["type"] == "base64"  # south is the reference
    assert body["n_directions"] == 4 and "image_size" not in body
    assert settings(folder)["sprite"]["pixellab"] == {"character_id": data["character_id"], "canvas": "16x20",
                                                      "made_from": "frames", "view": "high top-down"}
    [line] = ledger(project)
    assert line["generations"] == 0.25 and line["operation"] == "create-character-v3"


def test_from_frames_before_frames_have_run_is_frames_needed(project: Kiripix) -> None:
    sprite(project)

    result = project("gen", SPRITE, "--from-frames", "--json")

    assert result.codes == ["gen.frames_needed"] and not (project.cwd / "pixellab-requests").exists()


def test_a_state_stores_only_its_own_rotations_and_a_retry_is_a_new_name(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)

    first = project.json("gen", SPRITE, "--state", "hop", "--prompt", "hopping")["data"]
    second = project.json("gen", SPRITE, "--state", "hop", "--prompt", "hopping higher")["data"]

    assert first["clips"] == ["hop"] and second["clips"] == ["hop_2"] and first["operation"] == "state"
    assert {e.split("/")[0] for e in sheet_entries(folder, first["sheet"])} == {"hop"}  # the ZIP held idle, hop and swipe
    assert {e.split("/")[0] for e in sheet_entries(folder, second["sheet"])} == {"hop_2"}
    sent = [p["body"] for p in posts(project) if p["path"] == "/create-character-state"]
    assert [b["state_name"] for b in sent] == ["hop", "hop_2"]
    assert all(b["character_id"] == settings(folder)["sprite"]["pixellab"]["character_id"] for b in sent)
    assert settings(folder)["sprite"]["pixellab"]["made_from"] == "text"  # a state doesn't replace the character
    assert first["character_id"] == settings(folder)["sprite"]["pixellab"]["character_id"]

    project.json("run", SPRITE, "frames")
    assert sorted(c["name"] for c in frames_json(folder)["clips"]) == ["hop", "hop_2", "idle"]
    decide(project, "frames", "sheet", {"file": second["sheet"], "leave_out": ["hop_2"]})  # 0385: keep one
    project.json("run", SPRITE, "frames")
    assert sorted(c["name"] for c in frames_json(folder)["clips"]) == ["hop", "idle"]


def test_a_state_takes_a_canvas(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)

    project.json("gen", SPRITE, "--state", "swipe", "--prompt", "a swipe", "--canvas", "64")

    [post] = [p for p in posts(project) if p["path"] == "/create-character-state"]
    assert post["body"]["override_frame_size"] == {"width": 64, "height": 64}


def test_a_clip_by_rig_is_one_pending_call_of_four_jobs_and_approve_sends_them_all(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)
    providers(project, approve="each")

    waiting = project.json("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--directions", "s,e", "--prompt", "walks",
                           "--frames", "6", expect=3)

    pending = waiting["data"]["pending"]
    assert waiting["data"]["sent"] is False and waiting["data"]["operation"] == "motion" and waiting["data"]["jobs"] == 4
    assert [j["operation"] for j in pending["jobs"]] == ["estimate_rig", "animate_skeleton"] * 2
    assert [j["direction"] for j in pending["jobs"]] == ["s", "s", "e", "e"]
    assert pending["jobs"][1]["needs"] == 0 and pending["jobs"][3]["needs"] == 2
    assert [j["endpoint"] for j in pending["jobs"][:2]] == ["estimate-custom-skeleton", "animate-with-skeleton-v3"]
    assert pending["estimated_usd"] == round(sum(j["estimate_usd"] for j in pending["jobs"]), 6) == 0.044
    assert [i["role"] for i in pending["inputs"]] == ["frame", "frame"] and pending["params"]["directions"] == ["s", "e"]
    before = ledger(project)  # the character's own call (a_character, sent at once)
    assert [line["operation"] for line in before] == ["create-character-v3"]
    assert not [p for p in posts(project) if "skeleton" in p["path"]]
    assert waiting["findings"][0]["code"] == "provider.approval_needed"

    sent = project.json("approve", waiting["data"]["call"], owner=True)["data"]["sent"]

    # the charge, not the estimate: the fake bills the rig estimate $0.005 against the table's $0.006
    assert sent["sent"] is True and sent["clips"] == ["walk"] and sent["usd"] == 0.042 and sent["jobs"] == 4
    lines = ledger(project)[len(before):]
    assert [line["operation"] for line in lines] == ["estimate-custom-skeleton", "animate-with-skeleton-v3"] * 2
    assert {line["call"] for line in lines} == {waiting["data"]["call"]} and all(line["outcome"] == "done" for line in lines)
    sent_posts = [p for p in posts(project) if "skeleton" in p["path"]]
    assert [p["path"] for p in sent_posts] == ["/estimate-custom-skeleton", "/animate-with-skeleton-v3"] * 2
    animate = sent_posts[1]["body"]
    assert animate["rig"] == {"joints": ["head", "tail"]} and animate["first_frame_keypoints"]  # fed by the rig estimate
    assert animate["write_motion_frames"] == 6 and animate["direction"] == "south" and animate["action"] == "walks"
    assert sent_posts[2]["body"]["direction"] == "east"
    entries = sheet_entries(folder, sent["sheet"])
    assert entries == sorted(f"animations/walk/{d}/frame_{n:03d}.png" for d in ("east", "south") for n in range(6))
    assert not list((project.cwd / ".kiripix" / "calls").glob("*.json"))  # approved: no longer pending
    month = project.json("cost", "--month")["data"]["months"][0]
    assert month["calls"] == 2  # the character call and this one: an operation's four jobs count once

    waiting_frames = project.json("run", SPRITE, "frames", expect=2)  # w and n have no walk: never mirrored (0179)
    assert {f["code"] for f in waiting_frames["findings"] if f["severity"] == "error"} == {"frames.direction_missing"}
    walk = next(c for c in frames_json(folder)["clips"] if c["name"] == "walk")
    assert sorted(walk["directions"]) == ["e", "s"] and len(walk["directions"]["s"]) == 6


def test_a_job_that_fails_stops_the_rest_and_the_charge_is_recorded(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)
    spent = len(ledger(project))

    result = project("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--prompt", "walks STOPBILLED-animate", "--json")

    assert result.code == 3 and result.codes == ["provider.call_failed"]
    lines = ledger(project)[spent:]
    assert [(line["operation"], line["outcome"]) for line in lines] == [
        ("estimate-custom-skeleton", "done"), ("animate-with-skeleton-v3", "failed")]
    assert lines[1]["usd"] == 0.01
    assert len([p for p in posts(project) if p["path"] == "/estimate-custom-skeleton"]) == 1  # the other directions never ran
    assert len(list((folder / "src" / "sheets").glob("*"))) == 1  # only the character's: nothing past the failed job


def test_the_directions_that_came_back_are_stored_when_a_later_one_fails(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)
    spent = len(ledger(project))

    result = project("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--directions", "s,e", "--prompt",
                     "walks STOP-east", "--json")

    assert result.code == 3 and "were stored as sheet" in result.json["findings"][0]["message"]
    assert len(ledger(project)[spent:]) == 2  # the south pair; the east estimate failed with no charge
    [walk] = [p for p in (folder / "src" / "sheets").glob("*.zip") if "animations/walk/south/frame_000.png" in
              zipfile.ZipFile(p).namelist()]
    assert not any("east" in n for n in zipfile.ZipFile(walk).namelist())


def test_a_state_or_a_clip_without_a_character_is_character_needed(project: Kiripix) -> None:
    folder = sprite(project)

    state = project("gen", SPRITE, "--state", "hop", "--prompt", "hopping", "--json")
    png_sheet(project, sheet_of(FOUR, 1), 1)
    clip = project("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--prompt", "walks", "--json")

    assert state.codes == ["gen.character_needed"] and state.json["findings"][0]["fix"] == f'kiripix gen {SPRITE} --prompt "<who>"'
    assert clip.codes == ["gen.character_needed"] and clip.json["findings"][0]["fix"] == f"kiripix gen {SPRITE} --from-frames"
    assert "sprite" not in settings(folder) and not (project.cwd / "pixellab-requests").exists()


def test_flags_that_dont_fit_are_refused_before_planning(project: Kiripix) -> None:
    sprite(project)
    project.json("new", "prop", "bench")

    skeleton = project("gen", SPRITE, "--clip", "walk", "--motion", "skeleton", "--prompt", "walks", "--json")  # no --render
    look = project("gen", SPRITE, "--look", "dusk", "--prompt", "x", "--json")
    side = project("gen", SPRITE, "--side", "east", "--json")
    both = project("gen", SPRITE, "--state", "hop", "--clip", "walk", "--prompt", "x", "--json")
    motion = project("gen", SPRITE, "--motion", "rig", "--prompt", "x", "--json")
    frames = project("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--frames", "16", "--prompt", "x", "--json")
    other = project("gen", SPRITE, "--prompt", "x", "--provider", "fake", "--json")
    plain = project("gen", "prop.bench", "--prompt", "x", "--clip", "walk", "--json")

    assert skeleton.codes == ["gen.render_needed"] and look.codes == ["gen.flag_unsupported"]
    assert side.codes == ["gen.flag_unsupported"] and both.codes == ["gen.one_target"]
    assert motion.codes == ["gen.clip_needed"] and frames.codes == ["gen.frames_range"]
    assert other.codes == ["gen.provider_unsupported"] and "pixellab" in other.json["findings"][0]["message"]
    assert plain.codes == ["gen.sprite_flag"]
    assert not (project.cwd / "pixellab-requests").exists() and ledger(project) == []


def test_a_refused_job_of_a_clip_is_call_failed_and_records_nothing(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)
    spent = len(ledger(project))

    result = project("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--prompt", "a 402 walk", "--json")

    assert result.codes == ["provider.call_failed"] and len(ledger(project)) == spent


def test_a_version_1_ledger_reads_and_cost_shows_generations(project: Kiripix) -> None:
    sprite(project)
    now = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    old = {"schema_version": 1, "time": now, "call": "OLD", "asset": "prop.bench", "provider": "openai", "model": "m",
           "size": "8x8", "quality": "low", "count": 1, "images": 1, "usd": 0.05, "estimated": False,
           "prices_date": "2026-11-01", "mask": None, "input_fidelity": None, "usage": {}, "outcome": "done"}
    path = project.cwd / ".kiripix" / "cost.jsonl"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(old) + "\n", encoding="utf-8")

    project.json("gen", SPRITE, "--prompt", "a GENERATIONS raccoon")
    data = project.json("cost", "--month")["data"]

    [month] = data["months"]
    assert month["providers"]["openai"] == 0.05 and month["generations"] == {"pixellab": 1.0}
    assert month["calls"] == 2 and data["terms"]["pixellab"].startswith("output is the Project's")
    text = project("cost", "--month").stdout
    assert "1 generations" in text and "terms (pixellab)" in text
    lines = ledger(project)
    assert lines[0]["schema_version"] == 1 and lines[1]["schema_version"] == 2 and lines[1]["generations"] == 1.0


def test_a_version_1_pending_call_still_approves(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project, default="pixellab", approve="each")
    (project.cwd / ".env").write_text("PIXELLAB_API_KEY=pl-fake-for-the-fake-transport\n", encoding="utf-8")
    call = project.json("gen", "prop.bench", "--prompt", "a bench", expect=3)["data"]["call"]
    path = project.cwd / ".kiripix" / "calls" / f"{call}.json"
    document = json.loads(path.read_text(encoding="utf-8"))
    for key in ("operation", "params", "jobs"):
        del document[key]
    document["schema_version"] = 1
    path.write_text(json.dumps(document), encoding="utf-8")

    sent = project.json("approve", call, owner=True)["data"]["sent"]

    assert sent["sent"] is True and len(sent["variants"]) == 1 and sent["operation"] is None


def test_the_daily_limit_counts_an_operation_once(project: Kiripix) -> None:
    folder = sprite(project)
    providers(project, max_calls_per_day=2)
    a_character(project, folder)  # one call

    project.json("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--directions", "s,e", "--prompt", "walks")  # 4 lines, one call
    refused = project("gen", SPRITE, "--state", "hop", "--prompt", "hopping", "--json")

    assert len(ledger(project)) == 5 and refused.codes == ["provider.daily_limit"]


def test_gen_names_the_sprite_targets(project: Kiripix) -> None:
    schema = project.json("schema", "gen")["data"]["commands"]["gen"]["input"]["properties"]
    help_text = project("gen", "--help").stdout

    assert {"from_frames", "from_clip", "clip", "motion", "frames", "directions", "canvas"} <= set(schema)
    assert "--from-frames" in help_text and "PixelLab" in help_text and "--from" in help_text


def test_a_character_whose_zip_never_comes_is_kept_with_its_charge(project: Kiripix) -> None:
    folder = sprite(project)
    (project.cwd / "pixellab-zip-fails").write_text("", encoding="utf-8")

    result = project("gen", SPRITE, "--prompt", "a raccoon", "--json")

    assert result.codes == ["gen.archive_missing"] and result.code == 3
    finding = result.json["findings"][0]
    kept = settings(folder)["sprite"]["pixellab"]["character_id"]  # made and charged: kept, so --state can use it
    assert kept.startswith("char-") and kept in finding["owner_action"] and "--role sheet" in finding["owner_action"]
    [line] = ledger(project)
    assert line["outcome"] == "done" and line["usd"] == 0.03 and line["estimated"] is False  # the real charge
    assert not (folder / "src" / "sheets").exists() or not list((folder / "src" / "sheets").iterdir())

    (project.cwd / "pixellab-zip-fails").unlink()
    state = project.json("gen", SPRITE, "--state", "hop", "--prompt", "hopping")["data"]
    assert state["character_id"] == kept


def test_motion_for_a_clip_already_held_is_a_new_name(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)
    walk = ("--clip", "walk", "--motion", "rig", "--directions", "s", "--prompt", "walks")

    first = project.json("gen", SPRITE, *walk)["data"]
    project.json("run", SPRITE, "frames", expect=2)  # w, n and e have no walk: frames.direction_missing
    second = project.json("gen", SPRITE, *walk)["data"]

    assert first["clips"] == ["walk"] and second["clips"] == ["walk_2"]
    assert sheet_entries(folder, second["sheet"]) == [f"animations/walk_2/south/frame_{n:03d}.png" for n in range(8)]  # 8 frames by default


def test_a_state_never_joins_a_clip_a_sheet_decision_named(project: Kiripix) -> None:
    folder = sprite(project)
    made = a_character(project, folder)
    decide(project, "frames", "sheet", {"file": made["sheet"], "clips": {"Idle": "rest"}})

    data = project.json("gen", SPRITE, "--state", "rest", "--prompt", "resting")["data"]

    assert data["clips"] == ["rest_2"]  # `rest` is the renamed idle: a new state with that name would join it


def test_a_fix_replaces_only_the_faulty_flag(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)

    motion = project("gen", SPRITE, "--clip", "walk", "--motion", "jump", "--prompt", "walks", "--json")
    directions = project("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--directions", "q", "--prompt", "walks",
                         "--json")

    assert motion.json["findings"][0]["fix"] == f'kiripix gen {SPRITE} --clip walk --prompt "walks" --motion rig'
    assert directions.json["findings"][0]["fix"] == (f'kiripix gen {SPRITE} --clip walk --motion rig --prompt "walks" '
                                                     "--directions s,w,n,e")


# ticket 0390: a sprite from one image: a picked image, its other facings, the camera's view


def south_only(project: Kiripix, directions: str = "4") -> Path:
    """A sprite with only its south frame, `directions` it asks for; `frames` built (it warns of the missing ones)."""
    folder = sprite(project)
    project.json("set", SPRITE, "frames", f"directions={directions}")
    png_sheet(project, sheet_of(["s"], 1), 1, directions=["s"])
    project.json("run", SPRITE, "frames", expect=2)
    return folder


def a_style_sprite(project: Kiripix) -> None:
    project.json("new", "sprite", "raccoon")
    png_sheet(project, sheet_of(FOUR, 1), 1, asset="sprite.raccoon")
    project.json("run", "sprite.raccoon", "frames")


def test_an_image_with_a_style_sprite_sends_its_south_frame_and_a_pick_stores_a_one_direction_sheet(project: Kiripix) -> None:
    folder = sprite(project)
    a_style_sprite(project)
    providers(project, approve="each")

    waiting = project.json("gen", SPRITE, "--image", "--style", "sprite.raccoon", "--prompt", "a boss raccoon", "-n", "2",
                           expect=3)
    pending = waiting["data"]["pending"]
    assert pending["operation"] is None and pending["count"] == 2 and pending["size"] == "64x64"
    [style] = pending["inputs"]
    assert style["role"] == "reference" and style["path"].startswith("assets/sprite/raccoon/work/frames/")
    sent = project.json("approve", waiting["data"]["call"], owner=True)["data"]["sent"]

    [post] = posts(project)
    assert post["path"] == "/generate-image-v2" and post["body"]["style_image"]["size"] == {"width": 16, "height": 20}
    assert len(sent["variants"]) == 2 and sent["sheet"] is None
    assert not (folder / "src" / "sheets").exists()
    names = project.json("show", SPRITE)["data"]
    assert sorted(v["name"] for v in names["variants"]) == sorted(sent["variants"])

    picked = project.json("pick", SPRITE, sent["variants"][0])["data"]

    assert picked["clip"] == "idle" and picked["stage"] == "frames"
    assert sheet_entries(folder, picked["sheet"]) == ["idle/rotations/south.png"]
    record = [json.loads(n) for n in (folder / "imported.jsonl").read_text(encoding="utf-8").splitlines()][-1]
    assert (record["provider"], record["call"]) == ("pixellab", waiting["data"]["call"])
    result = project("run", SPRITE, "frames", "--json")
    assert [c["name"] for c in frames_json(folder)["clips"]] == ["idle"]  # the frames Stage reads it unchanged
    assert result.code in (0, 2)  # the other directions are missing until the facings are made


def test_an_image_from_a_png_or_none_and_the_refusals(project: Kiripix) -> None:
    sprite(project)
    from test_sprite import save

    save(project.cwd / "look.png", sheet_of(["s"], 1))

    png = project.json("gen", SPRITE, "--image", "--style", "look.png", "--prompt", "a worker", "--canvas", "48")["data"]
    plain = project.json("gen", SPRITE, "--image", "--prompt", "a worker")["data"]
    again_png = project("gen", SPRITE, "--image", "--prompt", "x", "--style", "nope.png", "--json")
    no_prompt = project("gen", SPRITE, "--image", "--json")
    view = project("gen", SPRITE, "--image", "--prompt", "x", "--view", "side", "--json")
    stray = project("gen", SPRITE, "--prompt", "x", "--style", "look.png", "--json")
    both = project("gen", SPRITE, "--image", "--state", "hop", "--prompt", "x", "--json")

    assert png["size"] == "48x48" and plain["size"] == "64x64"
    first, second = [p for p in posts(project)]
    assert "style_image" in first["body"] and "style_image" not in second["body"]
    assert again_png.codes == ["gen.style_unknown"] and no_prompt.codes == ["gen.prompt_needed"]
    assert view.codes == ["gen.flag_unsupported"] and stray.codes == ["gen.flag_unsupported"] and both.codes == ["gen.one_target"]


def test_image_flags_are_refused_for_another_asset(project: Kiripix) -> None:
    sprite(project)
    project.json("new", "prop", "bench")

    result = project("gen", "prop.bench", "--prompt", "x", "--image", "--view", "side", "--json")

    assert result.codes == ["gen.sprite_flag"] and "--image" in result.json["findings"][0]["message"]


def test_from_frames_on_a_south_only_sprite_makes_the_other_facings_and_stores_them_as_a_new_clip(project: Kiripix) -> None:
    folder = south_only(project, "8")
    providers(project, approve="each")

    waiting = project.json("gen", SPRITE, "--from-frames", expect=3)
    pending = waiting["data"]["pending"]
    assert pending["operation"] == "character" and len(pending["inputs"]) == 1
    assert [j["endpoint"] for j in pending["jobs"]] == ["generate-8-rotations-v3", "create-character-v3"]
    assert pending["estimated_usd"] == round(0.0203 + 0.0043, 4)
    assert pending["params"]["made"] == ["sw", "w", "nw", "n", "ne", "e", "se"] and pending["params"]["clip"] == "idle_2"
    assert not (project.cwd / "pixellab-requests").exists()
    data = project.json("approve", waiting["data"]["call"], owner=True)["data"]["sent"]

    rotations, character = posts(project)
    body = character["body"]
    assert rotations["path"] == "/generate-8-rotations-v3" and character["path"] == "/create-character-v3"
    assert body["reference_image"]["type"] == "base64" and body["n_directions"] == 8
    assert {*body["direction_images"]} == {"south-west", "west", "north-west", "north", "north-east", "east", "south-east"}
    assert data["clips"] == ["idle_2"] and data["character_id"] and data["sheet"]
    entries = sheet_entries(folder, data["sheet"])
    assert entries == sorted(f"idle_2/rotations/{w}.png" for w in
                             ("south", "south-west", "west", "north-west", "north", "north-east", "east", "south-east"))
    pixellab = settings(folder)["sprite"]["pixellab"]
    assert pixellab["character_id"] == data["character_id"] and pixellab["made_from"] == "frames"
    first, second = ledger(project)
    assert first["operation"] == "generate-8-rotations-v3" and second["generations"] == 0.25  # all frames are ours: imported


def test_the_sent_south_frame_stays_as_drawn_in_the_stored_sheet(project: Kiripix) -> None:
    folder = south_only(project, "4")
    [frame] = [p for p in (folder / "work" / "frames").rglob("*.png") if p.stem.endswith("000") or "south" in p.name or "_s" in p.name][:1]

    data = project.json("gen", SPRITE, "--from-frames")["data"]

    with zipfile.ZipFile(next((folder / "src" / "sheets").glob(f"{data['sheet']}*.zip"))) as archive:
        assert archive.read("idle_2/rotations/south.png") == frame.read_bytes()
        assert archive.read("idle_2/rotations/west.png") != frame.read_bytes()


def test_a_four_direction_sprite_makes_three_facings(project: Kiripix) -> None:
    folder = south_only(project, "4")

    data = project.json("gen", SPRITE, "--from-frames")["data"]

    assert sheet_entries(folder, data["sheet"]) == sorted(f"idle_2/rotations/{w}.png" for w in FOUR_WORDS)
    assert posts(project)[1]["body"]["n_directions"] == 4
    project.json("run", SPRITE, "frames", expect=2)  # idle (south only) and idle_2 (all four)
    assert sorted(c["name"] for c in frames_json(folder)["clips"]) == ["idle", "idle_2"]
    decide(project, "frames", "sheet", {"file": data["sheet"], "leave_out": ["idle_2"]})  # the Owner leaves it out
    project.json("run", SPRITE, "frames", expect=2)
    assert [c["name"] for c in frames_json(folder)["clips"]] == ["idle"]


def test_from_frames_on_a_sprite_that_has_every_facing_stores_no_sheet(project: Kiripix) -> None:
    folder = sprite(project)
    png_sheet(project, sheet_of(FOUR, 1), 1)
    project.json("run", SPRITE, "frames")

    pending = project.json("gen", SPRITE, "--from-frames")["data"]

    assert pending["sheet"] is None and pending["clips"] == []


def test_from_frames_without_south_is_direction_missing(project: Kiripix) -> None:
    sprite(project)
    png_sheet(project, sheet_of(["w", "n", "e"], 1), 1, directions=["w", "n", "e"])
    project.json("run", SPRITE, "frames", expect=2)

    result = project("gen", SPRITE, "--from-frames", "--json")

    assert result.codes == ["gen.direction_missing"]


def test_the_rotations_are_two_jobs_and_the_character_takes_the_made_frames(project: Kiripix) -> None:
    folder = south_only(project, "4")
    providers(project, approve="each")

    waiting = project.json("gen", SPRITE, "--from-frames", expect=3)
    jobs = waiting["data"]["pending"]["jobs"]
    assert [j["endpoint"] for j in jobs] == ["generate-8-rotations-v3", "create-character-v3"] and jobs[1]["needs"] == 0
    assert waiting["data"]["pending"]["estimated_usd"] == round(0.0203 + 0.0043, 4)
    data = project.json("approve", waiting["data"]["call"], owner=True)["data"]["sent"]

    first, second = posts(project)[:2]
    assert first["path"] == "/generate-8-rotations-v3" and second["path"] == "/create-character-v3"
    assert "view" not in first["body"] and second["body"]["view"] == "high top-down"  # a lone frame is rotated as drawn
    assert {*second["body"]["direction_images"]} == {"west", "north", "east"} and "south" not in second["body"]["direction_images"]
    assert first["body"]["first_frame"] == second["body"]["reference_image"]
    assert data["jobs"] == 2 and data["clips"] == ["idle_2"]
    assert [line["operation"] for line in ledger(project)] == ["generate-8-rotations-v3", "create-character-v3"]
    assert sheet_entries(folder, data["sheet"]) == sorted(f"idle_2/rotations/{w}.png" for w in FOUR_WORDS)


def test_a_failed_character_after_the_rotations_stores_nothing_and_records_both_charges(project: Kiripix) -> None:
    folder = south_only(project, "4")
    before = sorted((folder / "src" / "sheets").glob("*"))
    (project.cwd / "pixellab-zip-fails").write_text("", encoding="utf-8")

    result = project("gen", SPRITE, "--from-frames", "--json")

    assert result.codes == ["gen.archive_missing"]  # made and charged, its ZIP never came
    assert sorted((folder / "src" / "sheets").glob("*")) == before
    assert [line["operation"] for line in ledger(project)] == ["generate-8-rotations-v3", "create-character-v3"]


def test_view_is_sent_by_the_character_and_by_every_later_state_and_motion(project: Kiripix) -> None:
    folder = sprite(project)

    project.json("gen", SPRITE, "--prompt", "a raccoon", "--view", "low top-down")
    project.json("run", SPRITE, "frames")
    project.json("gen", SPRITE, "--state", "hop", "--prompt", "hopping")
    project.json("run", SPRITE, "frames")
    project.json("gen", SPRITE, "--clip", "walk", "--motion", "rig", "--directions", "s", "--prompt", "walks")

    assert settings(folder)["sprite"]["pixellab"]["view"] == "low top-down"
    sent = {p["path"]: p["body"] for p in posts(project)}
    assert sent["/create-character-v3"]["view"] == "low top-down"
    assert sent["/create-character-state"].get("view") is None  # PixelLab's state call has no view: the character carries it
    assert sent["/estimate-custom-skeleton"]["view"] == "low top-down" and sent["/animate-with-skeleton-v3"]["view"] == "low top-down"
    assert "view low top-down" in project("show", SPRITE).stdout
    assert project.json("show", SPRITE)["data"]["pixellab"]["view"] == "low top-down"


def test_the_view_defaults_to_high_top_down_and_a_bad_one_is_refused(project: Kiripix) -> None:
    sprite(project)

    bad = project("gen", SPRITE, "--prompt", "x", "--view", "isometric", "--json")
    project.json("gen", SPRITE, "--prompt", "a raccoon")
    state = project("gen", SPRITE, "--state", "hop", "--prompt", "x", "--view", "side", "--json")

    assert bad.codes == ["input.invalid"] and state.codes == ["gen.flag_unsupported"]
    assert posts(project)[0]["body"]["view"] == "high top-down"
    assert bad.json["findings"][0]["fix"] == f'kiripix gen {SPRITE} --prompt "x" --view "high top-down"'


# ticket 0391: an object's clip between two of its frames (`--motion keyframes`)


def a_bin(project: Kiripix, directions: str = "1") -> Path:
    """A faceless object: its `standing` and `toppled` clips (one frame each, south only), `frames` built, marked faceless."""
    folder = sprite(project)
    project.json("set", SPRITE, "frames", f"directions={directions}")
    png_sheet(project, sheet_of(["s"], 1), 1, clip="standing", directions=["s"], file="standing.png")
    png_sheet(project, sheet_of(["s"], 1, hops={0: 3}), 1, clip="toppled", directions=["s"], file="toppled.png")
    project.json("run", SPRITE, "frames")
    project.json("set", SPRITE, "pixellab", "faces=false")
    return folder


TOPPLE = ("--clip", "topple", "--motion", "keyframes", "--from", "standing", "--to", "toppled", "--prompt", "the bin topples over")


def test_a_faceless_object_plans_one_job_with_both_frames_and_approve_stores_the_clip(project: Kiripix) -> None:
    folder = a_bin(project)
    providers(project, approve="each")

    waiting = project.json("gen", SPRITE, *TOPPLE, "--frames", "8", expect=3)

    pending = waiting["data"]["pending"]
    assert waiting["data"]["operation"] == "motion" and waiting["data"]["jobs"] == 1
    [job] = pending["jobs"]
    assert job["operation"] == "animate_keyframes" and job["endpoint"] == "animate-with-text-v3" and job["direction"] == "s"
    assert job["images"] == {"first_frame": 0, "last_frame": 1} and job["needs"] is None
    assert [i["role"] for i in pending["inputs"]] == ["frame", "frame"] and pending["inputs"][0]["sha256"] != pending["inputs"][1]["sha256"]
    assert pending["params"]["motion"] == "keyframes" and pending["params"]["to_clip"] == "toppled"
    assert not (project.cwd / "pixellab-requests").exists()

    sent = project.json("approve", waiting["data"]["call"], owner=True)["data"]["sent"]

    [post] = posts(project)
    body = post["body"]
    assert post["path"] == "/animate-with-text-v3" and body["action"] == "the bin topples over" and body["frame_count"] == 8
    assert body["first_frame"]["type"] == "base64" and body["last_frame"]["type"] == "base64"
    assert body["first_frame"]["base64"] != body["last_frame"]["base64"] and body["no_background"] is True
    assert sent["clips"] == ["topple"] and sent["usd"] == 0.022
    assert sheet_entries(folder, sent["sheet"]) == [f"animations/topple/south/frame_{n:03d}.png" for n in range(8)]
    project.json("run", SPRITE, "frames")  # the Stage reads the stored clip unchanged
    topple = next(c for c in frames_json(folder)["clips"] if c["name"] == "topple")
    assert len(topple["directions"]["s"]) == 8
    assert sorted(c["name"] for c in frames_json(folder)["clips"]) == ["standing", "topple", "toppled"]


def test_without_faces_false_keyframes_is_keyframes_faces_and_plans_nothing(project: Kiripix) -> None:
    folder = a_bin(project)
    project.json("set", SPRITE, "pixellab", "faces=true")

    refused = project("gen", SPRITE, *TOPPLE, "--json")

    assert refused.codes == ["gen.keyframes_faces"]
    [finding] = refused.json["findings"]  # faceless is the Owner's choice: an owner_action, never a fix an agent runs
    assert finding.get("fix") is None and f"kiripix set {SPRITE} pixellab faces=false" in finding["owner_action"]
    assert refused.code == 3 and not (project.cwd / "pixellab-requests").exists() and ledger(project) == []
    assert settings(folder)["sprite"]["pixellab"].get("faces", True) is True

    project.json("new", "sprite", "crate")  # a sprite never marked: the same refusal
    unmarked = project("gen", "sprite.crate", *TOPPLE, "--json")
    assert unmarked.codes == ["gen.keyframes_faces"]


def test_keyframes_without_to_is_keyframes_need_end_and_plans_nothing(project: Kiripix) -> None:
    a_bin(project)

    result = project("gen", SPRITE, "--clip", "topple", "--motion", "keyframes", "--from", "standing", "--prompt", "topples", "--json")

    assert result.codes == ["gen.keyframes_need_end"] and result.json["findings"][0]["fix"].endswith("--to <clip>")
    assert not (project.cwd / "pixellab-requests").exists() and ledger(project) == []
    assert not list((project.cwd / ".kiripix" / "calls").glob("*.json"))


def test_set_pixellab_faces_needs_no_character_and_a_character_call_keeps_it(project: Kiripix) -> None:
    folder = a_bin(project)

    assert settings(folder)["sprite"]["pixellab"] == {"faces": False}  # no character: only the mark
    shown = project.json("show", SPRITE)["data"]["pixellab"]
    assert shown["faces"] is False and shown["character_id"] is None
    state = project("gen", SPRITE, "--state", "hop", "--prompt", "x", "--json")
    assert state.codes == ["gen.character_needed"]  # the mark is no character

    project.json("gen", SPRITE, "--from-frames", "--from", "standing")

    kept = settings(folder)["sprite"]["pixellab"]
    assert kept["faces"] is False and kept["made_from"] == "frames" and kept["character_id"]


def test_set_pixellab_refuses_an_unknown_key_a_bad_value_and_another_kind_with_a_matching_fix(project: Kiripix) -> None:
    folder = a_bin(project)
    project.json("new", "prop", "bench")

    unknown = project("set", SPRITE, "pixellab", "colour=red", "--json")
    view = project("set", SPRITE, "pixellab", "view=side", "--json")  # the view is set when the character is made
    value = project("set", SPRITE, "pixellab", "faces=maybe", "--json")
    plain = project("set", SPRITE, "pixellab", "faces", "--json")
    other = project("set", "prop.bench", "pixellab", "faces=false", "--json")

    assert unknown.codes == view.codes == ["set.unknown_parameter"] and value.codes == ["set.invalid_value"]
    assert plain.codes == ["set.invalid_assignment"] and other.codes == ["stage.unknown"]
    for refused in (unknown, view, value, plain):
        [finding] = refused.json["findings"]
        assert "faces=false" not in finding["fix"]  # a refusal never proposes the Owner's choice as the cure
        assert finding["fix"] == f"kiripix show {SPRITE}"
    assert "faces" in unknown.json["findings"][0]["message"] and settings(folder)["sprite"]["pixellab"] == {"faces": False}


def test_an_asset_toml_at_version_1_loads_and_is_written_back_at_version_2(project: Kiripix) -> None:
    folder = sprite(project)
    a_character(project, folder)
    old = (folder / "asset.toml").read_text(encoding="utf-8").replace("schema_version = 2", "schema_version = 1")
    assert "schema_version = 1" in old and "[sprite.pixellab]" in old
    (folder / "asset.toml").write_text(old, encoding="utf-8")

    shown = project.json("show", SPRITE)["data"]["pixellab"]
    project.json("set", SPRITE, "pixellab", "faces=false")

    assert shown["view"] == "high top-down" and shown["faces"] is True and shown["character_id"].startswith("char-")
    after = (folder / "asset.toml").read_text(encoding="utf-8")
    assert "schema_version = 2" in after and settings(folder)["sprite"]["pixellab"]["faces"] is False


def test_keyframes_frames_are_even_four_to_sixteen_and_the_pixel_budget_holds(project: Kiripix) -> None:
    a_bin(project)

    odd = project("gen", SPRITE, *TOPPLE, "--frames", "5", "--json")
    low = project("gen", SPRITE, *TOPPLE, "--frames", "2", "--json")
    high = project("gen", SPRITE, *TOPPLE, "--frames", "18", "--json")

    assert odd.codes == low.codes == high.codes == ["gen.frames_range"]
    assert odd.json["findings"][0]["fix"].endswith(" --frames 8") and "--frames 5" not in odd.json["findings"][0]["fix"]
    assert not (project.cwd / "pixellab-requests").exists()


def test_keyframes_default_to_eight_frames_and_flags_that_dont_fit_are_refused(project: Kiripix) -> None:
    folder = a_bin(project)

    unknown = project("gen", SPRITE, *TOPPLE[:-2], "--from", "nope", "--prompt", "x", "--json")
    stray = project("gen", SPRITE, "--clip", "topple", "--motion", "rig", "--to", "toppled", "--prompt", "x", "--json")
    noprompt = project("gen", SPRITE, *TOPPLE[:-2], "--json")
    data = project.json("gen", SPRITE, *TOPPLE)["data"]

    assert unknown.codes == ["gen.clip_unknown"] and stray.codes == ["gen.flag_unsupported"]
    assert noprompt.codes == ["gen.prompt_needed"]
    [post] = posts(project)
    assert post["body"]["frame_count"] == 8 and data["clips"] == ["topple"]
    assert len(sheet_entries(folder, data["sheet"])) == 8


def test_a_second_keyframes_clip_is_a_new_name_and_every_direction_is_a_job(project: Kiripix) -> None:
    folder = a_bin(project)
    two = project.json("gen", SPRITE, *TOPPLE)["data"]["clips"]
    project.json("run", SPRITE, "frames")

    again = project.json("gen", SPRITE, *TOPPLE, "--frames", "4")["data"]

    assert two == ["topple"] and again["clips"] == ["topple_2"]
    assert sheet_entries(folder, again["sheet"]) == [f"animations/topple_2/south/frame_{n:03d}.png" for n in range(4)]


def test_keyframes_of_a_four_direction_sprite_send_one_job_per_direction(project: Kiripix) -> None:
    sprite(project)
    png_sheet(project, sheet_of(FOUR, 1), 1, clip="standing", file="a.png")
    png_sheet(project, sheet_of(FOUR, 1, hops={0: 2}), 1, clip="toppled", file="b.png")
    project.json("run", SPRITE, "frames")
    project.json("set", SPRITE, "pixellab", "faces=false")

    data = project.json("gen", SPRITE, *TOPPLE, "--directions", "s,e")["data"]

    assert data["jobs"] == 2 and [p["body"]["first_frame"] for p in posts(project)][0] != [p["body"]["first_frame"] for p in posts(project)][1]
    assert sorted(e.split("/")[2] for e in sheet_entries(project.cwd / "assets" / "sprite" / "npc", data["sheet"])
                  if "topple" in e) == ["east"] * 8 + ["south"] * 8


def test_a_frame_over_256_px_is_canvas_range_not_a_frames_fix_that_fails_again(project: Kiripix) -> None:
    sprite(project)
    project.json("set", SPRITE, "frames", "directions=1")
    png_sheet(project, sheet_of(["s"], 1, scale=17), 1, clip="standing", directions=["s"], file="a.png")  # 272 x 340 px
    png_sheet(project, sheet_of(["s"], 1, scale=17, hops={0: 3}), 1, clip="toppled", directions=["s"], file="b.png")
    project.json("run", SPRITE, "frames")
    project.json("set", SPRITE, "pixellab", "faces=false")

    result = project("gen", SPRITE, *TOPPLE, "--frames", "4", "--json")

    assert result.codes == ["gen.canvas_range"] and "272x340" in result.json["findings"][0]["message"]
    assert "--frames" not in result.json["findings"][0]["fix"] and not (project.cwd / "pixellab-requests").exists()


def test_from_frames_with_a_view_stores_it_and_a_plain_character_shows_faces_and_view(project: Kiripix) -> None:
    folder = sprite(project)
    png_sheet(project, sheet_of(FOUR, 1), 1)
    project.json("run", SPRITE, "frames")

    project.json("gen", SPRITE, "--from-frames", "--view", "side")

    assert settings(folder)["sprite"]["pixellab"]["view"] == "side" and "faces" not in settings(folder)["sprite"]["pixellab"]
    assert posts(project)[0]["body"]["view"] == "side"
    shown = project.json("show", SPRITE)["data"]["pixellab"]
    assert shown["view"] == "side" and shown["faces"] is True  # only the TOML leaves a default out
