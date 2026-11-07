---
status: todo
milestone: M4
agent: ml-engineer
type: trial
---

# M4: trial: image-to-3D, a local Runner in 8 GB or a Provider?

Spec §16, open decision 4 ("Image-to-3D: which local Runner fits 8 GB well enough, or none (M3)"), §6.3 (model: "optional
image-to-3D") and §8.

**Deferred from M3** (Q3 of [0097](0097-m3-characters.md), 2026-11-07). The Owner's rule: in M3 only if the work is estimated
under 1M tokens. The estimate was 0.7 to 1.2M (this trial 300 to 500k, mostly Windows CUDA builds of each candidate's
dependencies; a Runner and the `model` Stage path after it 400 to 700k). Also, the models known to fit 8 GB in mid-2026 gave
blobby meshes with lighting baked into the texture, which rig badly, while the good ones needed 16 to 24 GB. In M4, with
Providers, the trial compares local Runners with a Provider (an API) on the same image. Recheck the candidates first: the list
above is from mid-2026.

## What to do

1. List the current open image-to-3D models that might run in 8 GB of VRAM, shared with nothing else during the test. For each,
   record its licence and the source of its weights. Drop any whose licence isn't confirmed for commercial use; ask the Owner
   about any that are unclear. Don't add one to the project. Add one or two image-to-3D Providers that M4 can call, with their
   terms for game assets.
2. On the two or three that remain, from one concept image of a game character the Owner provides: peak VRAM, time on the
   GPU and on the CPU, and whether the result has a clean mesh Mixamo can rig.
3. Take the best result through Mixamo by hand and render one frame at 52 px, beside the gate's bought or hand-made Model.
   Prototype code stays out of `kiripix/`.

## What to record, in this ticket

- The table of candidates: licence, weights' source, VRAM, time, rig result.
- The 52 px frames side by side, their paths for the Owner.
- A recommendation: a Runner for the `model` Stage (and a follow-up ticket), or "none", which spec §8's table then says.

## Acceptance criteria

- [x] The Owner's call on Q3 is recorded here first: deferred to M4.
- [ ] The table and frames above, and the Owner's choice, with the change to spec §8 and §16 decision 4 listed for the main
      session.
