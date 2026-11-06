# The agent acceptance test

Spec §14, ticket 0028. An agent with no project knowledge takes a room from `import` to `export` using only the
`kiripix` tool. A real run costs money, so CI and a plain `uv run pytest` never start one. They do run the harness's own
tests, including the scripted dry run, which is free.

```
uv run python -m tests.acceptance.run                 # the real run: claude -p, claude-haiku-5-5, 200k fresh tokens
uv run python -m tests.acceptance.run --dry-run       # a scripted agent that follows `next`; free, writes no report
```

Flags: `--agent-version`, `--budget` (fresh tokens, that is in + out + cache written, across all resumes), `--max-usd`
(`--max-budget-usd` of each `claude` call), `--milestone`, `--report` (write a report for a dry run too), `--keep`.
A real run writes `docs/acceptance/<date>-<milestone>.md` (a second run that day gets `-2`). The harness itself is
tested without a model by `uv run pytest tests/acceptance` (the dry run, the isolation, the stream parser).

How the agent is held to the tool, how the stand-in owner works and what counts as a pass are in the docstrings of
`tests/acceptance/claude_agent.py` and `harness.py`. The owner's Decisions are `tests/acceptance/fixtures/owner.json`.

**M2 and later.** The room has a red crate for the stand-in owner to lift into a foreground Layer (`click` on `layers`,
then `accept`, then a y-sort line on `place`). The Runners are fakes (0037's D16): `tests/acceptance/fixtures/acceptance_recipes.py`
loads the fakes from `tests/fixtures` and removes the test Kinds, so `describe` shows only the real ones. The harness's own
calls get `KIRIPIX_TEST_RECIPES`; the agent gets it only through the `kiripix` and `kpx` shims first on its PATH. A pass also
needs the Layer in the export's Manifest. Use `--milestone m2` for that record.
