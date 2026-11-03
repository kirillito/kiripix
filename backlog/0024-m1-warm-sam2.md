---
status: todo
milestone: M1
agent: ml-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0020-m1-pinned-runner-calls-sam2.md, 0023-m1-serve.md, 0031-m1-cooperative-cancel.md]
---

# M1: warm SAM 2 and the embedding cache

Spec §10.4 (the GPU lock) and §10.6. User story 29 of [0010](0010-m1-room-end-to-end.md).

## What to build

- The `segment-preview` Probe: given a room and click points, returns the Mask SAM 2 would produce, without recording
  or pinning anything.
- In `serve` only: SAM 2 stays loaded after use until an idle timeout, and its image embedding is cached by image
  hash, so a hover runs only the decoder.
- `serve` holds the GPU lock while warm and unloads when another process asks for it; that process waits with
  progress events, or runs on the CPU with `--cpu`.
- Cancel ([0031](0031-m1-cooperative-cancel.md)): the warm session's encoder and decoder runs take the cancel token
  through `RunOptions.terminate`, as in [0020](0020-m1-pinned-runner-calls-sam2.md). A cancelled encoder run leaves
  no entry in the embedding cache, and the warm session stays usable for the next Probe.

## Acceptance criteria

- [ ] With the fake Runner: a second `segment-preview` on the same image doesn't recompute the embedding.
- [ ] A CLI `run --rerun` on another Asset while `serve` is warm gets the GPU lock after `serve` unloads.
- [ ] A manual (not CI) timing of hover previews with the real SAM 2 on the owner's GPU, recorded in this ticket.
