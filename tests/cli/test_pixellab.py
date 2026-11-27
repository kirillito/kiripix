"""The PixelLab Provider through `gen` (ticket 0387), over the fake transport of the test recipes: every request kept as JSON
in `pixellab-requests/`, jobs that queue then complete, fail or are cancelled. Only the plain image call is reachable from a
Command here; the operations (a character, a state, motion) are 0388's, which tests them through `gen` for a sprite."""

import json
import threading
from typing import Any

from conftest import Kiripix, save_image
from test_gen import PROP, history, ledger, pending, sending
from test_locks import wait_for
from test_serve import Server, server  # noqa: F401 - the `server` fixture


def pixellab(project: Kiripix) -> None:
    """The PixelLab Provider, sending at once, a fake key in .env."""
    project.json("new", "prop", "bench")
    sending(project, default="pixellab")
    (project.cwd / ".env").write_text("PIXELLAB_API_KEY=pl-fake-for-the-fake-transport\n", encoding="utf-8")


def requests(project: Kiripix) -> list[dict[str, Any]]:
    folder = project.cwd / "pixellab-requests"
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(folder.glob("*.json"))]


def test_gen_through_pixellab_stores_its_candidates_and_the_charged_usd(project: Kiripix) -> None:
    pixellab(project)

    data = project.json("gen", PROP, "-n", "2", "--prompt", "a park bench")["data"]

    assert data["sent"] is True and data["provider"] == "pixellab" and len(data["variants"]) == 2  # 4 candidates, 2 kept
    [line] = ledger(project)
    assert line["provider"] == "pixellab" and line["usd"] == 0.082 and line["estimated"] is False
    assert line["images"] == 2 and line["prices_date"] == "2026-11-27" and line["outcome"] == "done"
    [logged] = [h for h in history(project, "prop/bench") if h.get("call") == data["call"]]
    assert logged["outcome"] == "done" and logged["variants"] == data["variants"]
    posts = [r for r in requests(project) if r["method"] == "POST"]
    [post] = posts  # one call, however many candidates
    assert post["path"] == "/generate-image-v2" and post["bearer"] is True
    assert post["body"]["description"] == "a park bench" and max(post["body"]["image_size"].values()) <= 256
    polls = [r for r in requests(project) if r["method"] == "GET"]
    assert len(polls) >= 3 and all(r["path"].startswith("/background-jobs/") for r in polls)  # queued, processing, completed
    assert "pl-fake-for-the-fake-transport" not in json.dumps(requests(project))
    assert "pl-fake-for-the-fake-transport" not in (project.cwd / ".kiripix" / "cost.jsonl").read_text(encoding="utf-8")


def test_a_style_image_is_sent_as_the_style_image(project: Kiripix) -> None:
    pixellab(project)
    save_image(project.cwd / "style.png", (24, 16))

    project.json("gen", PROP, "--prompt", "a bench", "--reference", "style.png")

    [post] = [r for r in requests(project) if r["method"] == "POST"]
    style = post["body"]["style_image"]
    assert style["size"] == {"width": 24, "height": 16} and style["image"]["type"] == "base64"


def test_a_refused_call_is_call_failed_and_records_no_charge(project: Kiripix) -> None:
    pixellab(project)

    result = project("gen", PROP, "--prompt", "a 402 bench", "--json")

    assert result.codes == ["provider.call_failed"] and "HTTP 402" in result.json["findings"][0]["message"]
    assert ledger(project) == [] and pending(project) == []
    assert not list((project.cwd / "assets" / "prop" / "bench" / "src").glob("*.png"))


def test_a_failed_job_is_call_failed_with_its_charge_recorded_when_it_has_one(project: Kiripix) -> None:
    pixellab(project)

    free = project("gen", PROP, "--prompt", "a FAIL bench", "--json")
    billed = project("gen", PROP, "--prompt", "a FAIL-BILLED bench", "--json")

    assert free.codes == ["provider.call_failed"] and billed.codes == ["provider.call_failed"]
    [line] = ledger(project)  # only the call that was charged
    assert line["outcome"] == "failed" and line["usd"] == 0.01 and line["provider"] == "pixellab"
    assert not list((project.cwd / "assets" / "prop" / "bench" / "src").glob("*.png"))


def test_a_charge_in_generations_is_priced_at_the_dated_rate(project: Kiripix) -> None:
    pixellab(project)

    data = project.json("gen", PROP, "--prompt", "a GENERATIONS bench")["data"]
    cost = project.json("cost")["data"]

    [line] = ledger(project)
    assert line["usd"] == round(1.0 * 0.0173, 6) and line["estimated"] is False
    assert line["generations"] == 1.0 and data["generations"] == 1.0  # kept beside the USD on the plain image call too
    assert cost["months"][-1]["generations"] == {"pixellab": 1.0}


def test_pixellab_cant_edit_so_an_edit_or_extend_is_refused_before_anything_is_sent(project: Kiripix) -> None:
    pixellab(project)

    look = project("gen", PROP, "--look", "night", "--prompt", "at night", "--json")
    side = project("gen", PROP, "--side", "east", "--json")

    assert look.codes == ["gen.provider_cannot_edit"] and side.codes == ["gen.provider_cannot_edit"]
    fix = look.json["findings"][0]["fix"]
    assert "--provider pixellab" not in fix and "--provider " in fix and '--prompt "at night"' in fix
    assert not (project.cwd / "pixellab-requests").exists() and ledger(project) == [] and pending(project) == []


def test_a_missing_key_is_an_owner_action(project: Kiripix) -> None:
    pixellab(project)
    (project.cwd / ".env").write_text("", encoding="utf-8")

    result = project("gen", PROP, "--prompt", "a bench", "--json")

    assert result.codes == ["provider.key_missing"] and not (project.cwd / "pixellab-requests").exists()


def test_a_cancel_during_a_queued_job_deletes_it_and_leaves_no_variant(project: Kiripix, server: Server) -> None:  # noqa: F811
    pixellab(project)
    hold = project.cwd / "pixellab-hold"
    hold.write_text("", encoding="utf-8")
    replies: list[Any] = []
    body = {"asset": PROP, "prompt": "a HOLD bench", "provider": "pixellab"}
    caller = threading.Thread(target=lambda: replies.append(server.call("/api/gen", body, headers={"X-Kiripix-Job": "g"})))
    try:
        caller.start()
        wait_for(project.cwd / "pixellab-holding")
        server.call("/api/jobs/g/cancel")
        caller.join(timeout=30)
    finally:
        hold.unlink(missing_ok=True)

    [reply] = replies
    assert reply.codes == ["run.cancelled"]
    deletes = [r for r in requests(project) if r["method"] == "DELETE"]
    assert [d["path"] for d in deletes] == [f"/background-jobs/{deletes[0]['path'].rsplit('/', 1)[-1]}"] and len(deletes) == 1
    assert not list((project.cwd / "assets" / "prop" / "bench" / "src").glob("*.png"))
    [line] = ledger(project)  # recorded at its estimate, as for OpenAI
    assert line["outcome"] == "cancelled" and line["estimated"] is True and line["provider"] == "pixellab"
