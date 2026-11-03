---
status: todo
milestone: M1
agent: core-engineer
type: ticket
parent: 0010-m1-room-end-to-end.md
depends_on: [0023-m1-serve.md]
---

# M1: REST transport per ADR 0007: file inputs as multipart, and a `transport` section in `schema`

[ADR 0007](../docs/adr/0007-adapter-transport-is-not-a-command.md) amends ADR 0006. A follow-up to
[0023](0023-m1-serve.md).

## What to build

- Remove `POST /api/upload`. A Command input that is a file (a field the registry marks as a file input, such as
  `override`'s `png`, `import`'s `file`, and the mask import from [0030](0030-m1-import-painted-mask.md)) is accepted
  over REST as a multipart part of that Command's own request. The adapter stores it in a temporary folder outside the
  Project, passes its path to the Command, and deletes it afterwards. A JSON body with a path inside the Project still
  works.
- `schema` gains a `transport` section listing the REST-only routes (the file route, the event stream, cancel), each
  with its method, path, purpose and HTTP statuses.
- The REST-vs-CLI equality test covers the multipart form for every Command with a file input.

## Acceptance criteria

- [ ] `override` over REST with the PNG as a multipart part equals the CLI's `--json` for the same file. Afterwards
      nothing is left in the temporary folder or in `.kiripix/uploads/`.
- [ ] `POST /api/upload` is gone (404).
- [ ] `schema --json` lists the three transport routes with their statuses.
