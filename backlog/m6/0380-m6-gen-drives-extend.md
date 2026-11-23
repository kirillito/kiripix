---
status: todo
milestone: M6
agent: ml-engineer
type: ticket
depends_on: [0379-m6-openai-provider-and-gen.md, 0377-m6-extend-joins-a-re-rendered-strip.md]
---

# M6: `gen` drives `extend`: canvas, OpenAI, `add`

Spec §14 (the Owner's aim for `extend`, 2026-11-16), §16 decision 5. The Provider is OpenAI's GPT Image
([0379](0379-m6-openai-provider-and-gen.md)).

## What to build

- `kiripix gen <id> --side <side> [-n N]` writes the next canvas (`extend <id> canvas`), sends it with the room's prompt to
  the Provider as an edit, and keeps the N results as candidate pieces for the Owner, without joining any.
- The Owner (or the UI) joins the chosen one with `extend add`. GPT Image re-renders the kept strip, so a piece from it joins
  under `--max-residual 1` ([0377](0377-m6-extend-joins-a-re-rendered-strip.md)) with `extend.strip_repainted`; decide
  whether `gen` records which Provider made a piece so `add` raises the limit itself, and say why in the Result.
- Within the budget and its estimate ([0378](0378-m6-gen-states-the-cost-and-refuses-past-the-cap.md)).

## Acceptance criteria

- [ ] CLI seam with a fake Provider that returns a re-rendered strip (0377's synthetic piece): `gen --side east -n 2` keeps
      2 pieces, records no join, and `extend add` on one joins it.
- [ ] One real 2-screen room on the art Project's copy, with the cost and the Owner's minutes in the Result, beside
      [0134](../m4/0134-m4-trial-room-extended-both-ways.md)'s 25 minutes of hand work for four pieces.
