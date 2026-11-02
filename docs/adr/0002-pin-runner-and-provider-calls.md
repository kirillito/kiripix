# Pin every Runner and Provider call

"Repeatable" means reproducible from committed files, not re-derivable from scratch. Runners (SAM 2, LaMa, BiRefNet…)
are not bit-exact across CUDA and CPU, and Providers are not deterministic at all, so deleting a cache and rebuilding
could silently change an exported asset. Each Runner or Provider call is therefore pinned: its result is committed
(git LFS), keyed on all of its inputs: the input image or crop hash, the click Decisions, the parameters, and the
Runner's ID with a hash of its weights. The device that produced it is not part of the key. Only deterministic Ops
rebuild implicitly, and their bit-exactness relies on locked dependency versions (`uv.lock`).

## Consequences

- Pinning is per call, not per Stage output, so a deterministic parameter in the same Stage can change without
  re-running the Runner.
- `kiripix run` never re-runs a stale pinned call; the Stage goes to needs-input. `run --rerun` re-runs Runners at any
  scope, and its results land in needs-review. Providers are called only through `gen`, because they cost money.
- Committed: `src/`, `decisions/`, pinned calls, `out/`. `work/` holds only deterministic cache.
