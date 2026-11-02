# Kiripix

A local pixel asset studio for Godot games. Read [GLOSSARY.md](GLOSSARY.md) and the ADRs in [docs/adr/](docs/adr/)
before changing anything; the full design is in [docs/KIRIPIX_SPEC.md](docs/KIRIPIX_SPEC.md). (M0 expands this file.)

## Rules

- **Never commit, stage for a commit, or push.** The owner reviews every change and commits it. Finish by listing the
  changed files.
- **Tickets live in [backlog/](backlog/)** as Markdown files with YAML frontmatter (`status`, `milestone`, `agent`).
  There is no issue tracker.
- Never set `KIRIPIX_TEST_OWNER` or `KIRIPIX_TEST_RECIPES` outside the test harness.

## Subagents: cost rules

The agents in `.claude/agents/` are expensive. Each one starts with no context and re-reads the project.
- **Delegate only when the ticket's `agent:` field names an agent, or the owner names one.** Otherwise do the work in
  the main session, whatever the task looks like.
- **One agent per ticket.** Don't fan a ticket out to several agents. If a ticket needs two areas, say so to the owner;
  it should probably be split.
- **Don't call `reviewer` after every change.** The owner asks for a review, or a ticket names it.
- **Small changes stay in the main session:** typo fixes, renames, doc edits, one-file changes, running tests,
  answering questions.
- Agents never call other agents.

| Agent | Area |
|---|---|
| `reviewer` | Read-only pre-review against the spec, ADRs and glossary; ADR drafts; splitting specs into tickets |
| `core-engineer` | core, commands, cli, server |
| `imaging-engineer` | ops, checks, room and prop image stages |
| `ml-engineer` | runners, providers, pinning, VRAM, licences, cost |
| `qa-engineer` | tests at the CLI and golden-image seams; the acceptance-test harness |
| `godot-export` | export, the Manifest |
| `ui-engineer` | web/ |
| `character-pipeline` | the character recipe, blender/ |
