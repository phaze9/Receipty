# AGENTS.md — Receipty

Local-first receipt workspace: browser UI, REST API, and Streamable HTTP MCP
server over a SQLite database. See README.md for setup and usage.

## Documentation conventions

- `MEMORY.md` and `README.md` hold abstract, default-level information only:
  project layout, commands, conventions, and verification history.
- They must NOT contain workspace-specific details: absolute workspace paths,
  live receipt contents, identifiers, or inventories. Those live in the agent's
  own setup notes, not in this repo.
- Keep documentation general so it stays portable across machines and
  workspaces.

## Key conventions

- Receipts are arbitrary JSON fields; use `title` (required) and `date`
  (required; `"todo"` when unknown). `description` is optional and removed when
  identical to the title. Organize with `tags` (list of lowercase English
  strings), never a `category` field.
- REST and MCP field updates REPLACE the entire fields object — fetch first,
  merge, preserve unrelated fields.
- Tests: `PYTHONPATH=src pytest`.
