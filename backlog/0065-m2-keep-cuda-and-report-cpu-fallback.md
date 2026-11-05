---
status: in-progress
milestone: M2
agent: ml-engineer
type: ticket
parent: 0037-m2-layers-and-props.md
---

# M2: keep the CUDA libraries through `uv sync`, and say when a GPU goes unused

Spec §8. Proposal 2 of [0059](0059-m2-slow-click-to-segment.md), agreed by the Owner. All 26 of the Owner's Runner calls ran on
the CPU, and nothing told them: `uv sync` uninstalls the CUDA libraries the README had them add by hand. An encode takes about
1.85 s on the CPU and about 0.25 s on the GPU.

## What to do

- A default dependency group `cuda`, in `uv.lock`, so that plain `uv sync` keeps the libraries. CI opts out, to spare a 1.1 GB
  download per run: its tests use the fake Runner.
- A Runner says when it was asked for the GPU, the machine has one, and it fell back. A `run --rerun` that made such a call
  reports it as the warning `runner.gpu_unused`.

## Acceptance criteria

- [x] `uv sync` installs the CUDA libraries, and SAM 2 reports `device: cuda` on the Owner's machine.
- [x] `uv sync --locked` still passes, and CI doesn't download the libraries. Checked locally with CI's flags and `UV_NO_SYNC`;
      the workflow itself first runs on the next push.
- [x] A CLI test: a rerun whose Runner fell back has the finding, once, with a `fix`; one that didn't, or that asked for `--cpu`,
      doesn't.
- [x] Checked by hand with the real Runner, in an environment without the libraries.

## Results

With the real Runner on a copy of `room.harbor_front`, one `kiripix run --rerun` from the CLI, load included:

| Environment | Device | Duration | `runner.gpu_unused` |
|---|---|---:|---|
| Without the libraries | `cpu` | 2.44 s | reported, with `fix: uv sync` |
| After `uv sync` | `cuda` | 0.80 s | not reported |

Not covered: the warning appears on `run --rerun` only, so a hover alone doesn't show it. Its reply does carry `device`.
