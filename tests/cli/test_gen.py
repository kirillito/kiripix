"""`kiripix gen`, `approve`, `reject` and `cost` (tickets 0379, 0378, 0381, 0380, 0143), with the fake Providers of the test
recipes: fixed images, $0.04 an image, no network. No test here, or anywhere, uses the OpenAI Provider."""

import json
import re
from pathlib import Path
from typing import Any

import numpy as np
from conftest import Kiripix, save_image
from PIL import Image

PROP = "prop.bench"
PRICE = 0.04


def providers(project: Kiripix, **values: object) -> None:
    """Set keys of kiripix.toml's [providers] (the template has each once)."""
    path = project.cwd / "kiripix.toml"
    text = path.read_text(encoding="utf-8")
    for key, value in values.items():
        shown = json.dumps(value) if isinstance(value, str) else str(value)
        text, found = re.subn(rf"(?m)^{key} = [^#\n]*?(\s*#|$)", lambda m: f"{key} = {shown}{m.group(1)}", text, count=1)
        assert found == 1, key
    path.write_text(text, encoding="utf-8")


def sending(project: Kiripix, **values: object) -> None:
    """The fake Provider, sending at once."""
    providers(project, **{"default": "fake", "approve": "none", **values})


def files(project: Kiripix) -> dict[str, bytes]:
    """Every file outside `.kiripix/` (the caches), by path."""
    return {p.relative_to(project.cwd).as_posix(): p.read_bytes() for p in sorted(project.cwd.rglob("*"))
            if p.is_file() and ".kiripix" not in p.relative_to(project.cwd).parts}


def ledger(project: Kiripix) -> list[dict[str, Any]]:
    path = project.cwd / ".kiripix" / "cost.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def history(project: Kiripix, folder: str) -> list[dict[str, Any]]:
    text = (project.cwd / "assets" / folder / "history.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def pending(project: Kiripix) -> list[Path]:
    return sorted((project.cwd / ".kiripix" / "calls").glob("*.json"))


# gen, the ledger and cost (0379)


def test_gen_n_2_adds_two_variants_logs_them_writes_the_ledger_and_changes_nothing_else(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project)
    before = files(project)

    data = project.json("gen", PROP, "-n", "2", "--prompt", "a park bench")["data"]

    assert data["sent"] is True and len(data["variants"]) == 2 and data["usd"] == 2 * PRICE
    after = files(project)
    added = sorted(set(after) - set(before))
    assert added == sorted([*(f"assets/prop/bench/src/{v}.png" for v in data["variants"]),
                            "assets/prop/bench/imported.jsonl"])  # the names they were stored under, as `import` records
    changed = sorted(k for k in before if before[k] != after.get(k))
    assert changed == ["assets/prop/bench/history.jsonl"]
    [logged] = [h for h in history(project, "prop/bench") if h.get("call") == data["call"]]
    assert logged["outcome"] == "done" and logged["variants"] == data["variants"] and logged["provider"] == "fake"
    [line] = ledger(project)  # one line per call sent, its `count` the images asked for
    assert line["count"] == 2 and line["images"] == 2 and line["usd"] == 2 * PRICE and line["asset"] == PROP
    assert line["estimated"] is False and line["prices_date"] == "2026-11-23" and line["provider"] == "fake"
    assert line["usage"] == {"input_tokens": 100, "output_tokens": 2000}  # the tokens the Provider reported
    assert data["usage"] == line["usage"] and data["month_spent_usd"] == 2 * PRICE
    assert logged["usage"] == line["usage"] and logged["prompt"] == "a park bench" and logged["provider_model"] == "fake-model"


def test_cost_month_sums_the_ledger_by_provider(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project)
    project.json("gen", PROP, "-n", "2", "--prompt", "a bench")
    project.json("gen", PROP, "--prompt", "another bench")

    data = project.json("cost", "--month")["data"]

    [month] = data["months"]
    assert month["usd"] == round(3 * PRICE, 6) and month["calls"] == 2 and month["images"] == 3
    assert month["providers"] == {"fake": round(3 * PRICE, 6)}
    assert data["spent_usd"] == round(3 * PRICE, 6) and data["budget_usd_month"] == 20
    assert data["remaining_usd"] == round(20 - 3 * PRICE, 6)


def test_each_call_states_what_it_cost_after_it_returns_and_cost_since_sums_a_session(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project, budget_usd_month=10)
    started = project.json("cost")["data"]  # nothing spent yet
    assert started["since"] is None and started["spent_usd"] == 0
    project.json("gen", PROP, "--prompt", "an earlier bench")
    session = ledger(project)[-1]["time"]

    result = project("gen", PROP, "-n", "2", "--prompt", "a bench", "--json")

    call = result.json["data"]["call"]
    assert (f"gen: prop.bench, call {call} cost $0.0800 (from the reported usage; tokens 100 input, 2,000 output); "
            "$0.12 of $10.00 spent this month") in result.stderr
    window = project.json("cost", "--since", session)["data"]["since"]
    assert window["calls"] == 2 and window["usd"] == round(3 * PRICE, 6) and window["images"] == 3
    assert window["tokens"] == {"input_tokens": 200, "output_tokens": 3000}
    assert project("cost", "--since", "yesterday", "--json").codes == ["input.invalid"]


def test_a_missing_key_is_an_owner_action_and_a_key_is_written_nowhere(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project, default="fake_keyed")

    result = project("gen", PROP, "--prompt", "a bench", "--json")

    assert result.code == 3 and result.codes == ["provider.key_missing"]
    finding = result.json["findings"][0]
    assert "FAKE_PROVIDER_KEY" in finding["owner_action"] and ".env" in finding["owner_action"] and not finding["fix"]
    assert ledger(project) == []
    secret = "sk-test-0123456789abcdef"
    (project.cwd / ".env").write_text(f"FAKE_PROVIDER_KEY={secret}\n", encoding="utf-8")

    project.json("gen", PROP, "--prompt", "a bench")

    for path in project.cwd.rglob("*"):
        if path.is_file() and path.name != ".env":
            assert secret.encode() not in path.read_bytes(), path


def test_the_import_provider_paints_nothing(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    providers(project, approve="none")

    result = project("gen", PROP, "--prompt", "a bench", "--json")

    assert result.code == 3 and result.codes == ["provider.not_generating"]


def test_a_prop_needs_words_and_a_room_needs_its_brief_prompt(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    project.json("new", "room", "alley", "--view", "top")
    sending(project)

    assert project("gen", PROP, "--json").codes == ["gen.prompt_needed"]
    assert project("gen", "room.alley", "--json").codes == ["gen.no_prompt"]
    (project.cwd / "style" / "prompts" / "room.j2").write_text("A room {{ width }}x{{ height }}.\n", encoding="utf-8")
    project.json("run", "room.alley", "brief")

    data = project.json("gen", "room.alley")["data"]

    assert data["size"] == "1376x768" and len(data["variants"]) == 1  # the brief's canvas
    assert ledger(project)[-1]["size"] == "1376x768"


def test_a_failed_call_is_recorded_only_when_billed(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project)

    failed = project("gen", PROP, "--prompt", "FAIL", "--json")
    assert failed.code == 3 and failed.codes == ["provider.call_failed"]
    assert ledger(project) == []
    billed = project("gen", PROP, "--prompt", "FAIL-BILLED", "--json")

    assert billed.code == 3 and billed.codes == ["provider.call_failed"]
    [line] = ledger(project)
    assert line["outcome"] == "failed" and line["usd"] == 0.01 and line["images"] == 0
    assert [h["outcome"] for h in history(project, "prop/bench") if "call" in h] == ["failed", "failed"]


# the estimate and the cap (0378)


def test_the_estimate_and_the_remaining_budget_come_before_the_call(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project, budget_usd_month=10)

    result = project("gen", PROP, "-n", "2", "--prompt", "a bench", "--json")

    assert result.code == 0
    data = result.json["data"]
    assert data["estimated_usd"] == 0.08 and data["remaining_usd"] == 10 and data["budget_usd_month"] == 10
    assert "gen: prop.bench, 2 images, est. $0.08; $10.00 of $10.00 left this month" in result.stderr


def test_a_call_past_the_cap_is_refused_before_it_is_sent_and_one_that_fits_exactly_is_sent(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project, budget_usd_month=0.12)
    project.json("gen", PROP, "-n", "2", "--prompt", "a bench")  # $0.08 spent
    before = files(project)

    refused = project("gen", PROP, "-n", "2", "--prompt", "two more", "--json")

    assert refused.code == 3 and refused.codes == ["cost.budget_exceeded"]
    finding = refused.json["findings"][0]
    assert "$0.0800" in finding["message"] and "$0.0400" in finding["message"]
    assert "budget_usd_month" in finding["owner_action"] and not finding["fix"]
    assert len(ledger(project)) == 1 and files(project) == before  # nothing sent, nothing recorded, -n not cut down
    exact = project.json("gen", PROP, "--prompt", "one more")["data"]
    assert exact["sent"] is True and exact["remaining_usd"] == 0.04
    assert len(ledger(project)) == 2


def test_a_budget_of_zero_refuses_every_paid_call(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project, budget_usd_month=0)

    assert project("gen", PROP, "--prompt", "a bench", "--json").codes == ["cost.budget_exceeded"]
    assert ledger(project) == []


# the Owner approves each call (0381)


def test_gen_only_writes_a_pending_call_and_approve_sends_it_once(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    providers(project, default="fake")
    before = files(project)

    result = project("gen", PROP, "--prompt", "a bench", "--json")

    assert result.code == 3 and result.codes == ["provider.approval_needed"]
    data = result.json["data"]
    call = data["call"]
    assert data["sent"] is False and data["pending"]["prompt"] == "a bench" and data["pending"]["estimated_usd"] == PRICE
    assert f"kiripix approve {call}" in result.json["findings"][0]["owner_action"]
    assert [p.stem for p in pending(project)] == [call]
    assert files(project) == before and ledger(project) == []
    assert project("approve", call, "--json").codes == ["owner.required"]
    listed = project.json("approve", "--list", owner=True)["data"]["pending"]
    assert [c["id"] for c in listed] == [call]

    sent = project.json("approve", call, owner=True)["data"]["sent"]

    assert sent["sent"] is True and len(sent["variants"]) == 1 and len(ledger(project)) == 1 and pending(project) == []
    again = project("approve", call, "--json", owner=True)
    assert again.code == 1 and again.codes == ["provider.call_unknown"] and len(ledger(project)) == 1


def test_reject_deletes_a_pending_call_and_sends_nothing(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    providers(project, default="fake")
    call = project.json("gen", PROP, "--prompt", "a bench", expect=3)["data"]["call"]

    assert project.json("reject", call)["data"]["rejected"] == call

    assert pending(project) == [] and ledger(project) == []


def test_a_changed_input_makes_the_pending_call_stale(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    providers(project, default="fake")
    save_image(project.cwd / "ref.png", (8, 8))
    call = project.json("gen", PROP, "--prompt", "a bench", "--reference", "ref.png", expect=3)["data"]["call"]
    save_image(project.cwd / "ref.png", (8, 8), (0, 0, 0, 255))

    result = project("approve", call, "--json", owner=True)

    assert result.code == 1 and result.codes == ["provider.call_stale"] and "kiripix gen" in result.json["findings"][0]["fix"]
    assert ledger(project) == [] and len(pending(project)) == 1


def test_the_limits_besides_the_budget_are_refused_before_a_pending_call_is_written(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    providers(project, default="fake", max_calls_per_day=1)

    too_many = project("gen", PROP, "-n", "5", "--prompt", "a bench", "--json")
    assert too_many.codes == ["provider.too_many_images"] and "-n 4" in too_many.json["findings"][0]["fix"]
    assert pending(project) == []
    providers(project, approve="none")
    project.json("gen", PROP, "--prompt", "a bench")

    second = project("gen", PROP, "--prompt", "a bench", "--json")

    assert second.code == 3 and second.codes == ["provider.daily_limit"] and len(ledger(project)) == 1


# a Look's edit (0143), a Prop's state


def room_with_source(project: Kiripix) -> None:
    project.json("new", "room", "alley", "--view", "top")
    rng = np.random.default_rng(3)
    Image.fromarray(rng.integers(0, 256, (48, 64, 3), dtype=np.uint8), "RGB").save(project.cwd / "first.png")
    variant = project.json("import", "room.alley", "first.png")["data"]["variant"]
    project.json("pick", "room.alley", variant)


def test_gen_look_adds_n_edit_variants_of_the_look_and_touches_nothing_else(project: Kiripix) -> None:
    room_with_source(project)
    sending(project)
    before = files(project)

    data = project.json("gen", "room.alley", "--look", "night", "-n", "2", "--prompt", "make it night")["data"]

    assert data["target"] == "look" and len(data["variants"]) == 2 and data["size"] == "64x48"
    added = sorted(set(files(project)) - set(before))
    assert added == sorted(f"assets/room/alley/src/looks/night/{v}.png" for v in data["variants"])
    [logged] = [h for h in history(project, "room/alley") if h.get("call") == data["call"]]
    assert logged["stage"] == "looks" and logged["look"] == "night"
    shown = project.json("import", "room.alley", project.cwd / data["files"][0], "--look", "night")["data"]
    assert shown["created"] is False  # stored exactly as `import --look` stores it


def test_the_edit_prompt_is_the_default_wording_or_the_kinds_template(project: Kiripix) -> None:
    room_with_source(project)
    providers(project, default="fake")

    first = project.json("gen", "room.alley", "--look", "night", "--prompt", "make it night", expect=3)["data"]
    assert first["pending"]["prompt"] == "Edit this image. Keep everything exactly the same except: make it night"
    (project.cwd / "style" / "prompts" / "room-edit.j2").write_text("For {{ look }}: {{ edit }}", encoding="utf-8")
    second = project.json("gen", "room.alley", "--look", "night", "--prompt", "make it night", expect=3)["data"]

    assert second["pending"]["prompt"] == "For night: make it night"
    assert project("gen", "room.alley", "--look", "night", "--json").codes == ["gen.prompt_needed"]


def test_an_undeclared_state_is_refused_before_the_call(project: Kiripix) -> None:
    project.json("new", "prop", "bench")
    sending(project)
    save_image(project.cwd / "bench.png", (16, 16))
    project.json("pick", PROP, project.json("import", PROP, "bench.png")["data"]["variant"])

    result = project("gen", PROP, "--state", "toppled", "--prompt", "knocked over", "--json")

    assert result.codes == ["prop.state_unknown"] and ledger(project) == []


# gen drives extend (0380)


def test_the_extend_prompt_says_what_the_canvas_is(project: Kiripix) -> None:
    from test_extend import ROOM, room

    room(project)
    (project.cwd / "style" / "prompts" / "room.j2").write_text("A laneway.\n", encoding="utf-8")
    project.json("run", ROOM, "brief")
    providers(project, default="fake")

    call = project.json("gen", ROOM, "--side", "east", "--prompt", "a brick wall", expect=3)["data"]["pending"]

    assert "strip at its left edge" in call["prompt"] and "continue the painting east" in call["prompt"]
    assert "A laneway." in call["prompt"] and call["prompt"].rstrip().endswith("The new area holds: a brick wall")
    assert [i["role"] for i in call["inputs"]] == ["canvas"]


def test_gen_side_keeps_candidate_pieces_and_extend_add_joins_one_under_the_raised_limit(project: Kiripix) -> None:
    from test_extend import ROOM, room

    room(project)
    (project.cwd / "style" / "prompts" / "room.j2").write_text("A laneway.\n", encoding="utf-8")
    project.json("run", ROOM, "brief")
    sending(project)

    data = project.json("gen", ROOM, "--side", "east", "-n", "2")["data"]

    assert data["target"] == "extend" and data["variants"] == [] and len(data["candidates"]) == 2
    assert data["size"] == "240x160"  # the [extend] canvas
    journal = project.cwd / "assets" / "room" / "alley" / "extend" / "journal.jsonl"
    assert not journal.exists()  # no join recorded
    candidate = data["candidates"][0]
    assert candidate["add"] == f"kiripix extend {ROOM} add {candidate['file']}"

    joined = project.json("extend", ROOM, "add", candidate["file"])

    assert joined["data"]["pieces"] == 1 and joined["data"]["residual"] <= 1.0
    assert journal.exists()
