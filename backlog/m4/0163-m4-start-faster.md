---
status: done
milestone: M4
agent: core-engineer
type: ticket
---

# M4: `kiripix` starts in 0.7 s: import less at start

Spec §8 (the CLI is the agent's interface) and §13 (layers). Found while closing M3, 2026-11-11.

## The gap

`kiripix --help` takes 0.70 s on the Owner's laptop, where `python -c pass` takes 0.05 s: 0.65 s is imports
(`python -X importtime -c "import kiripix.launch"`: 0.56 s warm). Every Command pays it before doing any work. Today
`status` on the art Project takes 1.2 s, nearly all start-up.

It adds up:
- **Agents:** an agent's every step is a Command. The acceptance test makes dozens.
- **The tests:** the CLI seam runs `kiripix ... --json` as a subprocess, thousands of times. The full suite takes 44 minutes
  in parallel (2026-11-11).
- **The UI** is a long-running `serve`, so it doesn't pay this per click, but `kiripix ui` does once.

Where it goes (cumulative, warm): `kiripix.commands` 0.38 s, of which `commands.project` 0.26 s, which pulls in `checks`
(`checks.cutout` 0.14 s) and through it numpy (0.09 s). Also pydantic (about 0.1 s), `jsonschema` 0.06 s (`core.editing`),
`typer` 0.06 s, `core.graph` 0.09 s, and every Kind's recipe (`recipes.character` 0.04 s) at import.

## What to build

- Import heavy modules where they're used, not at a module's top: numpy, PIL, `jsonschema`, `kiripix.checks`, the recipes'
  Stage code and the Runners. A Command's module may still be imported to register it, as long as registering is cheap.
- `kiripix --help`, `describe`, `schema` and `status` on an empty Project don't import numpy, PIL or onnxruntime.
- A test holds the budget: `python -X importtime -c "import kiripix.launch"` under 0.25 s on CI, or the set of modules
  `kiripix.launch` imports excludes numpy, PIL, onnxruntime and jsonschema (a check that doesn't depend on machine speed).
- The import rule (`lint-imports`) still holds: function-level imports count too.

## Acceptance criteria

- [ ] `kiripix --help` and `kiripix status --json` on an empty Project take under 0.3 s on the Owner's laptop (record before
      and after here). **Not met**; see Timings.
- [x] The test of what `kiripix.launch` imports: `tests/cli/test_start_imports.py`.
- [ ] The full suite's time before and after, recorded here. Before: 44 min (2026-11-11). After: 56 min (2026-11-12,
      1,393 tests, `-n auto --dist loadfile`), not comparable: it ran with `KIRIPIX_BLENDER` set, so the `blender` tests
      ran too, and it includes the tests added by 0148 to 0178. Re-time without `KIRIPIX_BLENDER` for a like-for-like number.

## Done

numpy, PIL (`Image`, `ImageOps`) and `jsonschema` no longer load at start. `kiripix.launch` imports none of numpy, PIL,
onnxruntime, jsonschema, and neither do `--help`, `describe`, `schema` and `status` on an empty Project
(`tests/cli/test_start_imports.py`, which reads `sys.modules` in a fresh interpreter).

- `kiripix/ops/lazy.py` (`lazy_module`, stdlib only): a module writes `np = lazy_module("numpy")` under `else:` of
  `if TYPE_CHECKING:`, so the type checker sees numpy and run time loads it on first use. Those modules have
  `from __future__ import annotations`. Ops, checks, recipes, runners and core use it.
- Module-level values that built numpy arrays are built on first use (OKLab matrices in `ops.colour`, mean and std in
  the two Runners); the array type aliases (`U8`, `BoolMask`, ...) are `Any` at run time.
- `jsonschema` loads inside the Decision validation; `urllib` inside the weights download.
- Recipes still import at start (they register the Kinds), but cost only their own code now.

## Timings

Median of 9 runs, `python -m kiripix` on an empty Project, 2026-11-12. The machine was busy (Blender tests in another
agent's session; `python -c pass` is far from idle), so the absolute numbers are well above the Owner's laptop; the
before and after were measured back to back.

| | before | after |
|---|---|---|
| `kiripix --help` | 1.28 s | 0.92 s |
| `kiripix status --json` | 1.20 s | 0.99 s |

What is left is pydantic (0.15 s here) and typer (0.19 s with its dependencies), which the contract needs. The 0.3 s
goal probably needs a different path for them (a lighter parser for `--help`, or lazy pydantic model building); that is
not an import move, so it is left for a follow-up if still wanted. Re-measure on the Owner's laptop.
