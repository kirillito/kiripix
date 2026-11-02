---
status: review
milestone: M0
agent: core-engineer
type: ticket
parent: 0001-m0-skeleton.md
depends_on: []
---

# M0: repo, environment and CI

The Python package, the locked environment and the checks every later ticket relies on. User stories 52–57 of
[0001](0001-m0-skeleton.md).

## What to build

- `pyproject.toml` for the `kiripix` package (Python 3.12, uv), with a committed `uv.lock`. Console scripts `kiripix`
  and `kpx`.
- The package layout of spec §13: `core`, `commands`, `ops`, `checks`, `recipes`, `cli` (empty `runners`,
  `providers`, `export` and `server` packages may exist).
- The import rule enforced by import-linter contracts, as stated in 0001.
- A type check (mypy) and pytest wired up; `tests/` with `cli/` and `golden/`.
- `.gitattributes` in the repo: golden images (`tests/golden/**/*.png`) through git LFS.
- CI (GitHub Actions) on every push: `uv sync --locked`, pytest, import-linter, type check. CI never commits or pushes.
- CLAUDE.md expanded: coding conventions (Pydantic classes named after what they describe, never `*Model`; `model`
  means only the 3D Model), how to run the tests, the import rule, and that `KIRIPIX_TEST_RECIPES` and
  `KIRIPIX_TEST_OWNER` are test-only.

## Acceptance criteria

- [ ] `uv sync --locked && uv run pytest` passes on a clean clone.
- [ ] `uv run lint-imports` passes, and fails if `ops` imports `core`.
- [ ] The type check passes.
- [ ] `uv run kiripix --help` works.
