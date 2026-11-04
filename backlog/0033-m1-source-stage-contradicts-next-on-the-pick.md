---
status: done
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
---

# M1: `describe` and `next` disagree about who makes the Pick

Found by the agent acceptance test ([0028](0028-m1-agent-acceptance-test.md)), real run of 2026-11-04:
[docs/acceptance/2026-11-04-m1.md](../docs/acceptance/2026-11-04-m1.md). The agent stopped at `source` after 10,417 fresh
tokens, without running `pick`.

## The bug

With one Variant, the tool tells an agent two opposite things:

- `kiripix describe room` says of the `source` Stage: "the Owner picks one as the Source"
  ([room.py:820](../kiripix/recipes/room.py#L820)), and the glossary calls the Pick a Decision.
- `kiripix next room.alley` and the `stage.needs_input` finding offer `kiripix pick room.alley <hash>` as a `fix`, so a
  Command for an agent ([room.py:120-121](../kiripix/recipes/room.py#L120-L121)). With several Variants, the same
  Stage gives an `owner_action` instead.

The agent's closing message, from the session log, as the first report didn't record it yet: "Picking the Source is the
owner's call (the `describe` output says 'the Owner picks one as the Source'), so I did not run `kiripix pick`." That is
a sound reading of what the tool said. It also stopped there in the second run; in the third it ran `pick` and passed.
The first run's last call was also denied by the harness's permission rule (`echo "exit=$?"`), which the agent mentions
too, so the Pick wasn't the only reason it stopped there.

## Decision

The Owner decided on 2026-11-04: **an agent may pick a lone Variant**, because it needs no judgement. The Owner chooses
between several. The `source` Stage's description, spec §6.1 and the glossary now say so; `next` already did.

## Acceptance criteria

- [x] `describe`, `next` and the `stage.needs_input` finding say the same thing about who makes the Pick with one
      Variant.
- [x] A CLI test covers it, and the acceptance run no longer records "the agent asked the owner, though `next` names
      `kiripix pick`". The run after this change ([2026-11-04-m1-4.md](../docs/acceptance/2026-11-04-m1-4.md)) picked
      without asking. It's one run of an intermittent behaviour, and it failed later on, for
      [0034](0034-m1-export-stage-done-reads-as-exported.md).
