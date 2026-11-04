# One Command registry, three generated adapters

Every operation is defined once in core as a Command with typed input and output, and the CLI, the REST API and the
MCP server are generated from that registry, with the same names, JSON, errors and version. Kiripix must be easy for
AI coding agents to drive and easy to build UIs on; with three hand-written surfaces they would drift apart, and a UI
could end up needing something an agent can't do. With one registry, the built-in UI, any other UI and an agent all
use exactly the same surface.

## Consequences

- The registry carries more than JSON types: file inputs (an import PNG), image outputs and progress events, which each
  adapter maps in its own way; CLI metadata (positional arguments, short aliases); and an MCP flag per Command
  (exposed, hidden or owner-only), because about 60 tools would cost an agent too much context.
- Every UI action maps to exactly one Command; continuous gestures (dragging a Marker, a brush stroke) become one
  Command when the mouse is released.
- One API version covers the whole tool, not one per Command.
- Probe Commands (read-only, never recorded) exist on every surface, but are only fast through the long-running server.
- Amended by [0007](0007-adapter-transport-is-not-a-command.md): an adapter's transport (moving files, the event
  stream, cancel, launching) is not a Command.
- Amended by the Owner on 2026-11-04: on the masks screen, with its rebuild option on, an edit (`decide`, `undo`, `redo`
  or `mask-import`) is followed by a `run` of the Stage, because a Decision changes the Masks only once the Stage has run.
  The gesture still records one Decision. The `run` can be cancelled and its findings show with the edit's. It re-runs a
  Runner only for a `click`, which asks for a new result (ADR 0002). Every other UI action stays one Command.
