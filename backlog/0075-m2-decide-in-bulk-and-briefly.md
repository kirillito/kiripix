---
status: done
milestone: M2
agent: core-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: `decide` in bulk, and without repeating the whole journal

Spec §10. Found by [0062](0062-m2-claude-first-pass-trial.md). `decide`, `undo` and `redo` return every current Decision with
its data, so what an agent reads grows with the square of the Decisions. Over r01's journal that comes to about 444 KB, roughly
150k tokens by a rough conversion, which is about the trial's whole budget for that room. The trial only avoided it because
Claude filtered the output. Each `decide` is also its own process, about a second, so 30 Decisions take half a minute.

This is the largest token saving the trial found, and an MCP tool in M4 would inherit it.

## What to build

- `--brief` on `decide`, `undo` and `redo`: the result leaves out `current` and gives `id`, `decision` and a count of current
  Decisions. The default stays as it is, because the UI's screens may read `current`; check them before changing anything more.
- `decide --file` also takes a JSON array of Decisions for one Stage. All are validated first, and any invalid one means none
  is recorded. The result gives their IDs in order. They are ordinary journal entries, one line each, and undo one at a time.
- `describe <kind> --stage <name>` gives one Stage's description, parameters, Decisions and Checks, so an agent needn't read
  the whole Kind for `masks`.

## Acceptance criteria

- [x] CLI seam: `--brief` output doesn't grow with the journal, and the default output is unchanged.
- [x] An array of 30 Decisions records 30 journal lines in order, in one process, and replays the same as 30 single calls.
- [x] An array with one invalid Decision records nothing, and the finding names which one.
- [x] `undo` after an array undoes only its last Decision.
- [x] A write interrupted during an array leaves the journal readable, with whole lines only, under `kiripix.core.atomic`.
- [x] `describe room --stage masks` gives only that Stage. An unknown Stage is refused, and the finding lists the Stages.
- [x] The token count of the agent acceptance test ([0057](0057-m2-agent-acceptance-test.md)) is noted before and after, if it
      uses these Commands.

## Notes

- Built: `decide` takes a JSON array (via `--file` or `--decision`), validated whole and appended in one atomic rewrite of
  the journal (`atomic.append_jsonl_many`), so an interruption leaves the journal as it was. Findings of an array name the
  index (`[3] ...`). `--brief` on decide/undo/redo gives `current: null` and `count`; the default output keeps `current`
  and only gains `count` and `ids`. The UI never reads `current` from a decide result.
- An interrupted write is not simulated at the CLI seam; the CLI test checks whole LF lines and no leftover temporary files.
- Token count for 0057: the agent acceptance test doesn't use these Commands (its agent runs one plain command per call and
  only the stand-in owner calls `decide`, outside the agent's tokens), so there is no before and after to note.
