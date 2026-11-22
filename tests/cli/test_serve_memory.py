"""Ticket 0373: `serve` works each Asset out once, and the list answers before any status (spec §10.6, §11, ADR 0005).

The cheap list (`assets`), `status` and `queue` by Asset ID, and `serve`'s memory of each Asset's derived state: kept until a
change Kiripix recorded drops it, and a Reload (`refresh`) drops all of it. What `serve` works out is seen through the test
Kinds' hook (`kiripix_test_recipes.py`): while `.kiripix/log-states` exists, each Asset's work is a line in
`.kiripix/states-calls.txt`."""

import shutil
import threading
import time
from collections import Counter
from typing import Any

from conftest import Kiripix, make_demo
from test_serve import Server, serving

LOG = ".kiripix/states-calls.txt"
BODY = "character.zed"
HAIR = "demo_wearable.hair"
OTHER = "demo_wearable.cap"


def start_log(project: Kiripix, delay: str = "") -> None:
    (project.cwd / ".kiripix").mkdir(exist_ok=True)
    (project.cwd / ".kiripix" / "log-states").write_text(delay, encoding="utf-8")
    (project.cwd / LOG).unlink(missing_ok=True)


def worked(project: Kiripix) -> Counter[str]:
    """How often each Asset was worked out since the log was last cleared."""
    path = project.cwd / LOG
    return Counter(path.read_text(encoding="utf-8").split()) if path.exists() else Counter()


def clear(project: Kiripix) -> None:
    (project.cwd / LOG).unlink(missing_ok=True)


def demos(project: Kiripix, names: list[str]) -> None:
    for name in names:
        make_demo(project, name)


def statuses(reply: Any) -> dict[str, list[str]]:
    assert reply.status == 200, reply.body
    return {a["asset"]: [s["status"] for s in a["stages"]] for a in reply.json["data"]["assets"]}


def worn(project: Kiripix) -> None:
    """A body, and two Wearables on it."""
    project.json("new", "character", "zed")
    project.json("new", "demo_wearable", "hair", "--body", BODY)
    project.json("new", "demo_wearable", "cap", "--body", BODY)


# the cheap list


def test_the_list_gives_each_asset_from_its_asset_toml_alone(project: Kiripix) -> None:
    demos(project, ["a"])
    worn(project)
    project.json("new", "character", "twin", "--base", BODY)
    project.json("new", "prop", "bench")
    project.json("style-add", "prop.bench", owner=True)

    data = project.json("assets")["data"]

    rows = {row["asset"]: row for row in data["assets"]}
    assert list(rows) == sorted(rows) and set(rows) == {"demo.a", BODY, "character.twin", HAIR, OTHER, "prop.bench"}
    assert rows["character.twin"] == {"asset": "character.twin", "kind": "character", "name": "twin", "base": BODY,
                                      "body": None, "reference": False}
    assert rows[HAIR]["body"] == BODY and rows[HAIR]["base"] is None and rows[HAIR]["kind"] == "demo_wearable"
    assert rows["prop.bench"]["reference"] is True and rows[BODY]["reference"] is False
    assert data["project"]
    assert [r["asset"] for r in project.json("assets", "--kind", "demo_wearable")["data"]["assets"]] == [OTHER, HAIR]
    assert [r["asset"] for r in project.json("assets", "--match", "character.*")["data"]["assets"]] == ["character.twin", BODY]
    assert "demo.a" in project("assets").stdout


def test_the_list_holds_no_stage_status_and_works_nothing_out(project: Kiripix) -> None:
    demos(project, ["a", "b"])
    start_log(project)

    data = project.json("assets")["data"]

    assert all(set(row) == {"asset", "kind", "name", "base", "body", "reference"} for row in data["assets"])
    assert not worked(project)


def test_a_broken_asset_toml_is_a_finding_and_hides_no_other_asset(project: Kiripix) -> None:
    demos(project, ["a"])
    (project.cwd / "assets" / "demo" / "broken").mkdir()
    (project.cwd / "assets" / "demo" / "broken" / "asset.toml").write_text("kind = \n", encoding="utf-8")

    result = project.json("assets", expect=1)

    assert [r["asset"] for r in result["data"]["assets"]] == ["demo.a"]
    assert result["findings"]


# status and queue by Asset ID


def test_status_and_queue_take_asset_ids(project: Kiripix) -> None:
    demos(project, ["a", "b", "c"])

    status = project.json("status", "--asset", "demo.c", "--asset", "demo.a")["data"]["assets"]
    queue = project.json("queue", "--asset", "demo.b")["data"]

    assert [a["asset"] for a in status] == ["demo.a", "demo.c"]
    assert [a["asset"] for a in project.json("status")["data"]["assets"]] == ["demo.a", "demo.b", "demo.c"]
    assert queue["counts"]["assets_clear"] in (["demo.b"], [])  # only the Asset asked for is looked at
    assert all(s["asset"] == "demo.b" for s in queue["stops"])


def test_an_id_that_is_no_asset_is_a_finding_and_the_others_still_answer(project: Kiripix) -> None:
    demos(project, ["a"])

    status = project.json("status", "--asset", "demo.a", "--asset", "demo.gone", expect=1)
    queue = project.json("queue", "--asset", "demo.a", "--asset", "demo.gone")

    assert [a["asset"] for a in status["data"]["assets"]] == ["demo.a"]
    assert [f["code"] for f in status["findings"]] == ["asset.not_found"]
    assert status["findings"][0]["fix"] and "owner_action" not in {k for k, v in status["findings"][0].items() if v}
    assert "asset.not_found" in [f["code"] for f in queue["findings"]]


def test_an_empty_list_of_ids_asks_for_no_asset(project: Kiripix) -> None:
    demos(project, ["a"])
    with serving(project.cwd, "--web", str(project.cwd / "no_web_app")) as server:
        status = server.call("/api/status", {"assets": []})
        queue = server.call("/api/queue", {"assets": []})
        everything = server.call("/api/status", {})

    assert status.json["data"]["assets"] == [] and queue.json["data"]["counts"]["total"] == 0
    assert [a["asset"] for a in everything.json["data"]["assets"]] == ["demo.a"]


# serve's memory


def serve(project: Kiripix) -> Any:
    return serving(project.cwd, "--web", str(project.cwd / "no_web_app"))


def test_a_second_status_works_nothing_out_again(project: Kiripix) -> None:
    demos(project, ["a", "b", "c"])
    start_log(project)
    with serve(project) as server:
        first = server.call("/api/status", {})
        assert worked(project) == Counter({"demo.a": 1, "demo.b": 1, "demo.c": 1})
        second = server.call("/api/status", {})
        queue = server.call("/api/queue", {})
        third = server.call("/api/queue", {})

    assert statuses(first) == statuses(second) and queue.json == third.json
    assert worked(project) == Counter({"demo.a": 1, "demo.b": 1, "demo.c": 1})  # the queue read the states `status` made


def test_what_the_cli_changes_drops_only_the_asset_it_touches(project: Kiripix) -> None:
    demos(project, ["a", "b", "c"])
    start_log(project)
    with serve(project) as server:
        statuses(server.call("/api/status", {}))
        clear(project)

        project.json("run", "demo.a", "copy")  # another process: its change file is what serve reads
        after = statuses(server.call("/api/status", {}))

        assert worked(project) == Counter({"demo.a": 1})
        assert after["demo.a"][0] == "done" and after["demo.b"][0] == "todo"
        clear(project)
        statuses(server.call("/api/status", {}))
        assert not worked(project)


def test_a_write_serve_made_itself_shows_in_the_very_next_status(project: Kiripix) -> None:
    demos(project, ["a", "b"])
    with serve(project) as server:
        assert server.call("/api/run", {"asset": "demo.a", "force": True, "from_stage": "copy"}).status in (200, 400, 422)
        before = statuses(server.call("/api/status", {}))
        assert before["demo.a"][:2] == ["done", "done"]

        assert server.call("/api/set", {"asset": "demo.a", "stage": "concat", "assignments": ["sep=-"]}).status == 200
        after = statuses(server.call("/api/status", {}))

    assert after["demo.a"][:2] == ["done", "stale"] and after["demo.b"][:2] == ["todo", "todo"]


def test_a_change_to_the_projects_own_files_works_every_asset_out_again(project: Kiripix) -> None:
    demos(project, ["a", "b", "c"])
    project.json("new", "prop", "bench")
    start_log(project)
    with serve(project) as server:
        statuses(server.call("/api/status", {}))
        clear(project)

        project.json("style-add", "prop.bench", owner=True)  # writes kiripix.toml
        statuses(server.call("/api/status", {}))

    assert worked(project) == Counter({"demo.a": 1, "demo.b": 1, "demo.c": 1, "prop.bench": 1})


def test_a_body_and_its_wearables_follow_each_other_and_no_other_asset(project: Kiripix) -> None:
    demos(project, ["a"])
    worn(project)
    start_log(project)
    with serve(project) as server:
        statuses(server.call("/api/status", {}))
        clear(project)

        project.json("note", HAIR, "render", "a note on a Wearable")  # its own folder: its body reads its Wearables
        statuses(server.call("/api/status", {}))
        assert set(worked(project)) == {HAIR, BODY}
        clear(project)

        project.json("new", "character", "twin", "--base", BODY)  # an Asset made from the body: only it is new work
        statuses(server.call("/api/status", {}))
        assert set(worked(project)) >= {"character.twin"} and not set(worked(project)) & {"demo.a", OTHER}
        clear(project)

        project.json("note", BODY, "model", "a note on the body")  # the body's folder: its Wearables and the twin follow
        statuses(server.call("/api/status", {}))

    assert set(worked(project)) == {BODY, HAIR, OTHER, "character.twin"}


def test_a_wearable_given_another_body_drops_both_bodies(project: Kiripix) -> None:
    demos(project, ["a"])
    worn(project)
    project.json("new", "character", "yan")
    start_log(project)
    with serve(project) as server:
        statuses(server.call("/api/status", {}))
        file = project.cwd / "assets" / "demo_wearable" / "hair" / "asset.toml"
        file.write_text(file.read_text(encoding="utf-8").replace(BODY, "character.yan"), encoding="utf-8")
        statuses(server.call("/api/status", {"refresh": "moved"}))  # a hand edit is only seen after a refresh
        clear(project)

        project.json("note", HAIR, "render", "moved")  # recorded: the Wearable and the body it is now worn on
        statuses(server.call("/api/status", {}))

    assert set(worked(project)) == {HAIR, "character.yan"}


def test_a_hand_edit_shows_after_a_refresh_and_not_before(project: Kiripix) -> None:
    demos(project, ["a", "b"])
    project.json("run", "demo.a", "copy")
    start_log(project)
    with serve(project) as server:
        assert statuses(server.call("/api/status", {}))["demo.a"][0] == "done"
        (project.cwd / "assets" / "demo" / "a" / "src" / "input.txt").write_text("changed by hand", encoding="utf-8")
        time.sleep(0.2)
        assert statuses(server.call("/api/status", {}))["demo.a"][0] == "done"  # nothing recorded it: serve can't know
        clear(project)

        refreshed = statuses(server.call("/api/status", {"refresh": "reload-1"}))
        assert refreshed["demo.a"][0] == "stale" and worked(project) == Counter({"demo.a": 1, "demo.b": 1})
        clear(project)

        statuses(server.call("/api/status", {"refresh": "reload-1"}))  # the same token again drops nothing
        assert not worked(project)
        (project.cwd / "assets" / "demo" / "b" / "src" / "input.txt").write_text("also by hand", encoding="utf-8")
        statuses(server.call("/api/status", {"refresh": "reload-2"}))
        assert worked(project) == Counter({"demo.a": 1, "demo.b": 1})


def test_forget_sees_a_hand_edit_in_the_named_assets_and_keeps_the_rest(project: Kiripix) -> None:
    """The UI's refresh when its window gets the focus back: the rows it shows are forgotten, every other is kept."""
    demos(project, ["a", "b", "c"])
    project.json("run", "demo.a", "copy")
    start_log(project)
    with serve(project) as server:
        statuses(server.call("/api/status", {}))
        (project.cwd / "assets" / "demo" / "a" / "src" / "input.txt").write_text("changed by hand", encoding="utf-8")
        clear(project)

        shown = statuses(server.call("/api/status", {"assets": ["demo.a", "demo.b"], "forget": ["demo.a", "demo.b"]}))

        assert shown["demo.a"][0] == "stale" and worked(project) == Counter({"demo.a": 1, "demo.b": 1})
        clear(project)
        statuses(server.call("/api/status", {}))
        assert not worked(project)  # demo.c was never forgotten, and the other two are remembered again


def test_one_refresh_asked_with_status_and_queue_together_works_each_asset_out_once(project: Kiripix) -> None:
    demos(project, ["a", "b"])
    start_log(project, "0.3")
    with serve(project) as server:
        statuses(server.call("/api/status", {}))
        clear(project)
        replies: dict[str, Any] = {}
        threads = [threading.Thread(target=lambda n=name: replies.update({n: server.call(f"/api/{n}", {"refresh": "go"})}))
                   for name in ("status", "queue")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert replies["status"].status == 200 and replies["queue"].status == 200
    assert worked(project) == Counter({"demo.a": 1, "demo.b": 1})


def test_concurrent_status_and_queue_work_an_asset_out_once(project: Kiripix) -> None:
    demos(project, ["a", "b"])
    start_log(project, "0.4")
    with serve(project) as server:
        replies: dict[str, Any] = {}

        def ask(label: str, path: str) -> None:
            replies[label] = server.call(path, {})

        threads = [threading.Thread(target=ask, args=args)
                   for args in (("s1", "/api/status"), ("q1", "/api/queue"), ("s2", "/api/status"), ("q2", "/api/queue"))]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

    assert all(r.status == 200 for r in replies.values())
    assert worked(project) == Counter({"demo.a": 1, "demo.b": 1})
    assert statuses(replies["s1"]) == statuses(replies["s2"]) and replies["q1"].json == replies["q2"].json


def test_a_change_while_an_asset_is_being_worked_out_is_not_kept_from_before_it(project: Kiripix) -> None:
    demos(project, ["a"])
    start_log(project, "0.8")
    with serve(project) as server:
        first: dict[str, Any] = {}
        thread = threading.Thread(target=lambda: first.update(reply=server.call("/api/status", {})))
        thread.start()
        time.sleep(0.3)  # demo.a is being worked out, from before the run below
        (project.cwd / ".kiripix" / "log-states").write_text("", encoding="utf-8")
        project.json("run", "demo.a", "copy")
        thread.join()

        after = statuses(server.call("/api/status", {}))

    assert after["demo.a"][0] == "done"


def test_the_list_is_kept_in_step_with_new_and_removed_assets(project: Kiripix) -> None:
    demos(project, ["a"])
    with serve(project) as server:
        assert [a["asset"] for a in server.call("/api/assets", {}).json["data"]["assets"]] == ["demo.a"]

        project.json("new", "demo", "b")
        listed = server.call("/api/assets", {}).json["data"]["assets"]
        assert [a["asset"] for a in listed] == ["demo.a", "demo.b"]
        assert sorted(statuses(server.call("/api/status", {}))) == ["demo.a", "demo.b"]

        shutil.rmtree(project.cwd / "assets" / "demo" / "b")  # by hand: only a refresh sees it
        assert len(server.call("/api/assets", {}).json["data"]["assets"]) == 2
        listed = server.call("/api/assets", {"refresh": "gone"}).json["data"]["assets"]
        assert [a["asset"] for a in listed] == ["demo.a"]


def test_the_game_changing_under_serve_changes_what_status_says_to_export(project: Kiripix) -> None:
    """The game's files aren't in the change record, so `serve` asks about them on every call (`export_stamp`)."""
    from test_export import exportable_room, set_target  # the helpers that build a room whose export is pending

    exportable_room(project)
    set_target(project)
    with serve(project) as server:
        before = server.call("/api/status", {}).json["data"]["assets"]
        pending = next(a for a in before if a["asset"].startswith("room.") and a["export_command"])
        project.json("export", pending["asset"], owner=True)  # another process writes the game and its Manifest
        after = server.call("/api/status", {}).json["data"]["assets"]

    assert next(a for a in after if a["asset"] == pending["asset"])["export_command"] is None


# the budget


ASSETS = 400


def _timed(server: Server, path: str, body: dict[str, Any]) -> tuple[float, Any]:
    start = time.perf_counter()
    reply = server.call(path, body)
    return time.perf_counter() - start, reply


def test_a_project_of_400_assets_lists_at_once_and_answers_status_from_memory(project: Kiripix) -> None:
    folder = make_demo(project, "a000")
    for number in range(1, ASSETS):
        shutil.copytree(folder, folder.parent / f"a{number:03d}")
    with serve(project) as server:
        server.call("/api/describe", {"target": "demo"})  # the first call loads the test Kinds, which no real Project pays
        first_list, reply = _timed(server, "/api/assets", {})
        assert len(reply.json["data"]["assets"]) == ASSETS
        # each new token makes the list read its 400 files again: the fastest of three, so a busy machine can't fail it
        cold_list = min(_timed(server, "/api/assets", {"refresh": f"cold-{n}"})[0] for n in range(3))
        warm_list, _ = _timed(server, "/api/assets", {})
        _timed(server, "/api/status", {})  # works every Asset out: the cold cost, which the memory pays once
        warm, reply = _timed(server, "/api/status", {})
        assert len(reply.json["data"]["assets"]) == ASSETS
        project.json("run", "demo.a017", "copy")  # one Asset changes, in another process
        changed, reply = _timed(server, "/api/status", {})
        assert statuses(reply)["demo.a017"][0] == "done"
        rows, _ = _timed(server, "/api/status", {"assets": ["demo.a001", "demo.a002"]})

    # The ticket's budget: the list under 0.3 s, a warm status under 0.3 s, the one after a change under 0.5 s. The cold
    # list reads 400 files (0.15 s measured); the margin covers a busy CI machine (a call is one HTTP round trip).
    assert cold_list < 0.3, cold_list
    assert first_list < 2.0, first_list
    assert warm_list < 0.3, warm_list
    assert warm < 0.3, warm
    assert changed < 0.5, changed
    assert rows < 0.2, rows
