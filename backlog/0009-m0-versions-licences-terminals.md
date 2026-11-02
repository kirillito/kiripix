---
status: done
milestone: M0
agent: none
type: research
parent: 0001-m0-skeleton.md
depends_on: [0002-m0-repo-and-tooling.md]
---

# M0: pinned versions, Runner licences and isatty

User stories 58–60 of [0001](0001-m0-skeleton.md). Needs the owner, because the terminals and the version choice are
theirs.

- Pin the Godot and Blender versions in the spec (§4 `version`, §12).
- Verify and record the licences of SAM 2 (each size), BiRefNet, Depth Anything V2 (each size) and LaMa in
  `docs/runner-licences.md`.
- Run `uv run python -c "import sys; print(sys.stdin.isatty())"` in Windows Terminal, the VS Code terminal and Git
  Bash (mintty), and record the results in `docs/terminals.md`.
