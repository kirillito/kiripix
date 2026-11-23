---
status: todo
milestone: M6
agent: ml-engineer
type: ticket
depends_on: [0379-m6-openai-provider-and-gen.md, 0377-m6-extend-joins-a-re-rendered-strip.md, 0381-m6-the-owner-approves-each-provider-call.md]
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

## Result

The first acceptance item is built. The trial on a real room stays open, so `status` stays `todo`.

- `kiripix gen <room> --side <side> [-n N] [--prompt "<what the new area holds>"]` plans the next canvas at the default keep
  (`extend.plan_canvas`), sends it as an edit with the prompt, and keeps the N results as **candidate pieces** in
  `extend/candidates/<piece>.png`. Each has a `<piece>.json` beside it: the call, the Provider, the model, the sides, and
  whether the Provider re-renders the kept strip. `gen` joins nothing: `data.candidates` gives each file and its
  `kiripix extend <room> add <file>`.
- The canvas is written to `extend/canvas.png` only once the call has passed its limits. With `approve = "each"`, that is
  when the pending call is written, and `approve` refuses the call if the canvas changed since (`provider.call_stale`).
- The prompt is `style/prompts/room-extend.<ext>` if the Project has one (fields `prompt`, the room's built prompt, `sides`,
  `edit`, `bible`). Otherwise it is a head saying that the strip at the canvas's edge is the finished painting to continue
  toward the side, then the room's prompt, then "The new area holds: <words>". This keeps the room-brief skill's rule that
  every extension prompt restates the whole room prompt.
- **`gen` records which Provider made a piece, and `add` raises the limit itself.** Without `--max-residual`, `extend add` of
  a candidate whose record says its Provider re-renders the kept strip (GPT Image, and the fake Provider) joins under
  1.0 px (`RESIDUAL_CEILING`), with `extend.strip_repainted` when it registers above 0.5. Why: every GPT Image piece needs
  the raised limit (0377), and an Owner or a UI joining the chosen piece shouldn't have to know that. A piece from anywhere
  else (the inbox, a hand-made one) keeps `[extend] max_residual`, so a strip from another scene still fails. An explicit
  `--max-residual` always wins.
- Calls are held to the budget, its estimate and the approval, like every `gen` call.
- Tests: `test_gen_side_keeps_candidate_pieces_and_extend_add_joins_one_under_the_raised_limit`. The fake Provider returns
  the canvas re-rendered the way 0377's synthetic piece is (a sub-pixel wave, a per-channel gain, new noise): 2 candidates,
  no journal, and `extend add` on one joins without `--max-residual`. Also `test_the_extend_prompt_says_what_the_canvas_is`.

### Still open, needs the Owner

- One real 2-screen room on the art Project's copy, with the cost and the Owner's minutes, beside 0134's 25 minutes for four
  pieces. It needs the key in the art Project's `.env`, a room template ([0348](0348-m6-brief-renders-the-prompt.md)'s draft),
  and the Owner's approval of each call.
