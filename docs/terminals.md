# isatty in the owner's terminals

Owner-only Commands (`accept`, from M1) refuse from the CLI unless stdin is an interactive terminal (spec §10.3).
Python under Git Bash's mintty can report that stdin isn't a TTY even while the owner is typing, so this records where
the check works. Where it fails, the UI is the accept path.

Run by the owner in each terminal, from the Kiripix repo:

```
uv run python -c "import sys; print(sys.stdin.isatty(), sys.stdout.isatty())"
```

| Terminal | stdin isatty | stdout isatty | Date |
|---|---|---|---|
| Windows Terminal (PowerShell) | True | True | 2026-11-02 |
| VS Code integrated terminal | True | True | 2026-11-02 |
| Git Bash (mintty) | True | True | 2026-11-02 |

Result: the terminal check works in all three, so owner-only Commands can be run from any of them. Check again if a
terminal or Git for Windows is upgraded and `accept` starts refusing.

Agents can't fill this in: an agent's shell is never interactive, which is the point of the check.
