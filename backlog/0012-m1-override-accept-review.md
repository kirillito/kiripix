---
status: todo
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0011-m1-decision-journal.md]
---

# M1: `override`, `accept`, and replay into needs-review

Spec §5 (Replaying Decisions, Overrides) and §10.3. User stories 5–8 of [0010](0010-m1-room-end-to-end.md).

## What to build

- `kiripix override <id> <stage> <png>`: stores the painted image under `decisions/` by its hash and appends a journal
  entry referencing it, with the hash of the Stage output it was painted on. The Override counts as a Decision of the
  next Stage, and core applies it on top of the Stage's output when that Stage runs.
- Replay: with an unchanged input the Stage replays exactly and is `done`. If any current click or Override was made on
  an image whose hash differs from the current one, the Stage runs and lands in `needs-review` (derived, never stored,
  ADR 0005). Stages below a `needs-review` Stage don't build. A Pick of a deleted Variant means `needs-input`.
- `kiripix accept <id> <stage>`, owner-only: appends re-recorded clicks against the new input hash and a rebased
  Override (the same image recorded against the new hash), so the next replay is exact. It also resolves "divergent
  Decisions" from [0011](0011-m1-decision-journal.md) by recording the current replay as accepted.
- The owner-only guard in the registry: from the CLI, refuse unless stdin is a TTY, with exit code 3 and an
  `owner_action`; bypassed by `KIRIPIX_TEST_OWNER=1` for the test harness only. REST's session-token half comes in
  [0023](0023-m1-serve.md).
- `accept` is marked never exposed over MCP in the registry.

## Acceptance criteria

- [ ] An Override whose size doesn't match the Stage output fails with a finding.
- [ ] Changing an upstream input under a Stage with a click Decision gives `needs-review`; `accept` (with
      `KIRIPIX_TEST_OWNER=1`) gives `done`, and the next `run` stays `done`.
- [ ] `accept` from a non-TTY without the test variable exits 3 with an `owner_action`, and the journal is unchanged.
