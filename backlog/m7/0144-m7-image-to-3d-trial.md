---
status: todo
milestone: M7
agent: ml-engineer
type: trial
---

# M7: trial: image-to-3D, a local Runner in 8 GB or a Provider?

Spec §16, open decision 4 ("Image-to-3D: which local Runner fits 8 GB well enough, or none (M3)"), §6.3 (model: "optional
image-to-3D") and §8.

**Deferred from M3** (Q3 of [0097](../m3/0097-m3-characters.md), 2026-11-07). The Owner's rule: in M3 only if the work is estimated
under 1M tokens. The estimate was 0.7 to 1.2M (this trial 300 to 500k, mostly Windows CUDA builds of each candidate's
dependencies; a Runner and the `model` Stage path after it 400 to 700k). Also, the models known to fit 8 GB in mid-2026 gave
blobby meshes with lighting baked into the texture, which rig badly, while the good ones needed 16 to 24 GB. In M6, with
Providers, the trial compares local Runners with a Provider (an API) on the same image. Recheck the candidates first: the list
above is from mid-2026.

**Rechecked on 2026-11-20** from the research briefings in `.research/` (second-hand: confirm each figure and licence upstream
before relying on it). The machine is an **RTX 2070** (8 GB, Turing: no BF16 and no FP8, so a model shipped in either runs in
FP16 or FP32, slower or not at all; a figure measured on an Ampere or later card doesn't carry over). **Budget $0**: a Provider
is tried only on its free tier (the Owner, 2026-11-20).

| Candidate | VRAM (reported) | Licence (reported) | What it makes | Note |
|---|---|---|---|---|
| [TripoSR](https://github.com/VAST-AI-Research/TripoSR) | ~6 GB | MIT code and weights | Mesh, vertex colours or a baked texture | The safe baseline; blobby on hidden sides |
| [TripoSG](https://github.com/VAST-AI-Research/TripoSG) | 8 GB minimum | MIT | Geometry only (GLB) | Tight on 8 GB; its background-removal helper has its own licence to check |
| [Stable Fast 3D](https://github.com/Stability-AI/stable-fast-3d) | ~7 GB | Stability AI Community (free under $1M revenue, registration) | UV-unwrapped mesh, albedo, optional normal map | Gated weights |
| SPAR3D | ~6–10.5 GB by path | Stability AI Community | Textured mesh, better back sides | Windows support experimental |
| TRELLIS.2 GGUF Q4 (Modly) | ~6 GB, geometry only | Weights repo has no clear licence | Geometry | Drop unless the weights' licence is found |
| Pixal3D | unclear on 8 GB | Repo and plugins disagree | Mesh with PBR | Drop unless settled |
| Hunyuan3D 2.1 | ~10 GB shape, ~29 GB with texture | Tencent Community (territory limits) | — | Drop: too big |
| UltraTex (texturing, not 3D) | 6–8 GB, community GGUF route | Runs FLUX.2 Klein Base 9B: non-commercial | Textures an untextured mesh | Only with the Owner's yes (runner-licences policy) |
| Meshy, Tripo (Providers) | — | Free-tier terms conflict or limit ownership | — | Their terms and prices come from [0353](../m6/0353-m6-provider-research.md)'s desk table; free tier only |

**Characters may be the wrong target.** Every source agrees these models suit props (benches, machines, signs), not characters
that rig cleanly. So the trial also runs one **prop** concept image through the same candidates and renders it at the rooms'
top-down 3/4 camera at the Prop's target size, to ask whether a Prop made from 3D could sit in a painted room. The style match
measures (0332) judge it beside a painted room, if they are ready; otherwise the Owner does.

## What to do

1. List the current open image-to-3D models that might run in 8 GB of VRAM, shared with nothing else during the test. For each,
   record its licence and the source of its weights. Drop any whose licence isn't confirmed for commercial use; ask the Owner
   about any that are unclear. Don't add one to the project. Add one or two image-to-3D Providers that M6 can call, with their
   terms for game assets.
2. On the two or three that remain, from one concept image of a game character the Owner provides: peak VRAM, time on the
   GPU and on the CPU, and whether the result has a clean mesh Mixamo can rig.
3. Take the best result through Mixamo by hand and render one frame at 52 px, beside the gate's bought or hand-made Model.
   Prototype code stays out of `kiripix/`.
4. From one prop concept image the Owner provides (a bench or a vending machine), the same candidates: render the best mesh in
   headless Blender at the rooms' camera and the Prop's target size, through `palette` and `finish` by hand, and put it beside a
   painted Prop in a painted room.

## What to record, in this ticket

- The table of candidates: licence, weights' source, VRAM, time on the RTX 2070, rig result, prop result.
- The 52 px frames and the prop renders side by side, their paths for the Owner.
- A recommendation: a Runner for the `model` Stage (and a follow-up ticket), or "none", which spec §8's table then says; and
  separately, whether a Prop from 3D is worth a path in the prop recipe.

## Acceptance criteria

- [x] The Owner's call on Q3 is recorded here first: deferred to M4, then moved to M5 on 2026-11-08 with the Providers, which became M6 on 2026-11-11.
- [ ] The table and frames above, and the Owner's choice, with the change to spec §8 and §16 decision 4 listed for the main
      session.
