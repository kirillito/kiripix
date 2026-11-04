# The UI is React with TypeScript and Vite

Status: draft, for the Owner's review. The Owner decided this on 2026-11-02.

The UI needs generated forms, lists, filters and panels that follow `describe` and refresh when an agent changes the
Project, and it needs canvas tools that respond on every mouse move. We use React with TypeScript and Vite for the
first. The canvas widgets are plain TypeScript classes that React components mount through a `ref`, so hover and brush
updates never go through React state. Svelte and plain TypeScript were considered: Svelte would serve as well but
gives us no more, and plain TypeScript would leave us writing and keeping our own rendering for all the panels.

## Consequences

- The UI is a build step, with its own dependencies locked in `web/package-lock.json`. `uv sync` and the Python tests
  don't need Node.
- `web/` is built only on the REST Commands and transport routes. Its types describe their results, and it has no
  logic of its own: what a Stage needs, how it is checked and what comes next all come from Commands.
- A canvas widget owns its pixels and its gesture state, and tells React only about finished gestures, each of which
  is one Command (spec §10.1).
- The wheel carries the built app as `kiripix/web`, so an installed Kiripix needs no Node.
