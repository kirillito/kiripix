---
status: todo
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0012-m1-override-accept-review.md]
---

# M1: `serve`: REST, SSE progress, cancel, the session token and Probes

Spec §10.1, §10.3, §10.6 and ADR 0006. User story 28 of [0010](0010-m1-room-end-to-end.md).

## What to build

- `kiripix serve` (and `kiripix ui`, which also opens the browser): a FastAPI adapter generated from the registry, one
  route per Command, holding no logic. Responses are the same envelope as `--json`; the exit code maps to an HTTP
  status, documented in `schema`.
- Progress events over SSE (the same events as `--progress=jsonl`), and a cancel endpoint that stops a running
  Command as Ctrl+C does.
- The session token: generated at start, given to the browser when `serve` opens it, and required for owner-only
  Commands over REST.
- File inputs (an Override PNG, an import) as uploads; image outputs as file paths, plus a route that serves files
  from the Project.
- `kiripix probe <name> <id> <args...>` and the Probe kind in the registry (records nothing, takes no lock), with a
  trivial Probe to prove the path. The SAM 2 `segment-preview` Probe is [0024](0024-m1-warm-sam2.md).
- A folder watch that pushes a "changed" event over SSE when an agent changes the Project, so the UI can refresh.
- Static serving of the built `web/` app when it exists.

## Acceptance criteria

- [ ] For every Command in the contract test, the REST response for the same input equals the CLI's `--json`.
- [ ] `accept` over REST without the token is refused with the owner-only finding; with it, it succeeds.
- [ ] A `run` of the `demo` Kind's `hold` Stage streams progress over SSE and stops cleanly on cancel.
