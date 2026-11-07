---
status: done
milestone: M1
agent: qa-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0022-m1-export-ownership-and-id-freeze.md]
---

# M1: the agent acceptance test harness

Spec §14 (the agent acceptance test). User story 33 of [0010](0010-m1-room-end-to-end.md).

## What to build

- A harness, outside CI, that starts an agent on a cheap model with a fixed token budget, in a fresh Project with an
  imported room image and an empty temporary Godot project, with the task "take this room from `import` to `export`".
  The agent sees only the tool (`--help`, `describe`, `next`, `check` and the rest of the CLI), never the source, the
  spec or CLAUDE.md.
- The stand-in owner: a fixture file of the owner's Decisions (the Pick, the Mask strokes, the Markers), fed in through
  `decide` and `accept` with `KIRIPIX_TEST_OWNER=1`, set by the harness only, whenever the agent reports an owner
  action.
- The result: pass or fail (the room is exported and `check --all` is clean), the tokens used, and every Command the
  agent ran. Recorded in a dated file under `docs/`, so each milestone's token count can be compared.
- Every failure is treated as a tool bug: the harness's report names the step where the agent got lost.

## Notes

- **Five real runs on 2026-11-04, all on `claude-haiku-5-5`.** Each has its own report in
  [docs/acceptance/](../../docs/acceptance/README.md). The fifth is the M1 token figure, the first on the tool with 0033 and
  0034 fixed: **7,629 fresh tokens** (119,248 counting cache reads), 13 Commands, one owner step. It is one pass, and an
  agent's path varies from run to run.
  - `2026-11-04-m1.md`, FAIL: the agent stopped at the Pick, because `describe` and `next` disagree about who makes it. A
    tool bug, filed as [0033](0033-m1-source-stage-contradicts-next-on-the-pick.md).
  - `2026-11-04-m1-2.md`, FAIL: a harness bug, not the tool's. `echo "exit=$?"` got the agent's `run` denied, and it
    concluded Bash was off. The task prompt now says one plain command per call. It stopped at the Pick here too.
  - `2026-11-04-m1-3.md`, PASS: the agent ran `pick` this time, so **a pass doesn't clear 0033**: it stopped there in two
    runs of three.
  - `2026-11-04-m1-4.md`, FAIL, after 0033 was fixed: it picked without asking, then took a `done` `export` Stage to mean
    exported and never ran `kiripix export`. A tool bug, filed as [0034](0034-m1-export-stage-done-reads-as-exported.md).
  - `2026-11-04-m1-5.md`, PASS, after 0034 was fixed.
- **The three runs aren't quite comparable.** The third's task prompt has the extra line on one plain command per call.
  It describes the permission rule, not Kiripix, so later milestones should keep it.
- **Three things differ from the ticket's words.** The Pick goes through `pick`, not `decide`. The owner also acts whenever
  `next` waits on them, whether or not the agent said so, so an agent that stops silently at an owner Stage is rescued. And
  "outside CI" holds for real runs only: the dry run is in `uv run pytest`, and the test that reads `claude --help` skips
  where there's no `claude`.
- **The agent is `claude -p`**, because this machine has no API key. Run the harness from a normal shell if you can; from
  inside a Claude session it also works, because the agent's environment drops every `CLAUDE*` and `MCP_*` variable.
- **Isolation has one soft edge.** Claude Code allows what it counts as read-only inside the agent's temporary folder
  (`cd`, `echo`, `head`), even in `dontAsk` mode. Reading the repo's `CLAUDE.md` and source was tried and denied.
  Claude Code still adds the account's email address to the agent's context; `--safe-mode` doesn't remove it.
- **The budget counts fresh tokens** (input, output, cache written), not cache reads, which repeat the system prompt every
  turn. The spec says only "a fixed token budget". The report gives both.
- **The stand-in owner answers two things:** what `next` says waits on the owner, and what the agent itself asks the owner
  for, if the fixture has an entry for that Stage. The second kind is marked in the report, because it means the tool told
  the agent two things.
- **Each real run leaves a session log** under `~/.claude/projects/`, because `--resume` needs one. The reports name the
  session.

## Acceptance criteria

- [x] A dry run with a scripted "agent" that follows `next` exactly passes, so the harness itself is known to work.
- [x] One real run on the cheap model, with its tokens recorded, and any failures filed as tickets in `backlog/`.
