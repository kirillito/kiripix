# An adapter's transport is not a Command

Amends [0006](0006-one-command-registry.md). The registry holds the operations on a Project. What one adapter needs
only to carry those operations over its own channel is part of that adapter, not a Command. The REST adapter has to
move files both ways, stream progress, cancel a running Command and be started. The CLI gets the same things from a
file path, stdout, Ctrl+C and the shell. Making them Commands would give the CLI, MCP and the contract test operations
that mean nothing there, like an `upload` that copies a file onto itself. So they stay out of the registry.

## Consequences

- REST transport routes: the file route (`GET /files/...`), the event stream (`GET /api/events`, progress and
  "changed" events) and cancel (`POST /api/jobs/<id>/cancel`). `serve` and `ui` are Launchers, started from the CLI but
  not registered as Commands.
- Transport changes nothing in a Project. A file a Command needs comes in as a multipart part of that Command's own
  request, so every write is still a Command. There is no separate upload route.
- Transport holds no logic either. Job tracking, the owner check and input validation stay in `kiripix.commands`, and
  the adapter only maps them to HTTP.
- `schema` lists the transport routes in a `transport` section, with their HTTP statuses, so an agent or a UI can
  find them as it finds Commands.
- A transport feature that later means something on every surface becomes a real Command. The likely one is a
  `cancel` that one agent sends from another terminal, which needs a job list shared between processes.
