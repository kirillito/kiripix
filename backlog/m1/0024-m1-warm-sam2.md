---
status: done
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

- [x] With the fake Runner: a second `segment-preview` on the same image doesn't recompute the embedding.
- [x] A CLI `run --rerun` on another Asset while `serve` is warm gets the GPU lock after `serve` unloads.
- [x] A manual (not CI) timing of hover previews with the real SAM 2 on the owner's GPU, recorded in this ticket.

## Manual timing (2026-11-04)

Through a real `kiripix serve` over HTTP, on the owner's RTX 2070 Super (8 GB), with `onnxruntime-gpu[cuda,cudnn]` as a `uv
run --with` overlay. The room is synthetic, not a real one: a 1376 x 768 Source of noisy colour blocks, downscaled to 640 x
368. 30 hovers at random points on one image.

- **A hover, embedding cached:** median 0.061 s, fastest 0.038 s, slowest 0.072 s, on `cuda`. Each included the HTTP call.
- **The first hover, Runner cold:** 13.3 s, once, with ONNX Runtime's own start-up. After an unload, in the same server,
  1.66 s to load and encode again.
- **Memory:** 3.4 GB in use while warm, and 1.2 GB after it unloaded (1.1 GB idle), so another process gets the GPU back.
- **On the CPU, for comparison:** a hover took a median of 0.073 s, and the first one 11.6 s.

## Notes

- **The protocol:** the warm `gpu.lock` says `warm: true`. A process that wants it writes `gpu.request` and waits, up to a
  minute, whatever its `--wait`, reporting a `gpu_wait` progress event. `serve` looks every 0.1 s, unloads once no preview
  is running, and releases the lock. A new preview won't take the lock from a live process that has asked, and a warm one
  gives way to it first; it answers `lock.busy`. A request from a dead process is removed. A hover never waits for the GPU
  lock, and its `lock.busy` offers `--cpu`, since a Probe has no `--wait`.
- **Probes and locks:** a Probe still takes no Asset lock, but one that loads a Runner takes the GPU lock, because the
  spec's GPU lock covers any loaded Runner. So `segment-preview` is `lock.busy` during a real run, unless it is `--cpu`.
- **Runner interface:** `EmbeddingRunner` splits `call` into `embed` and `decode`. Only SAM 2's file knows what the
  embedding is. `core/warm.py` keeps the last 4 by image hash.
- **`--warm-idle`** on `serve` and `ui` sets the idle timeout: 300 s by default.
- **In one process,** a warm Runner shares its object with `run --rerun`, so a `--cpu` run through `serve` unloads it too.
  A `--cpu` run in another process leaves it warm.
