# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## Project Overview

### Backend

- FastAPI backend
- SQLAlchemy
- Jinja Templates

### Frontend

- No-build frontend
- Preact with Tailwind
- Specific mini-apps per-resource, not SPA
- Types for development workflow, but not compiled

### Tools

```sh
uv run basedpyright # python type checking
uv run ruff check # linter
uv run ruff format # formatter
bun run tsc # frontend types
bun run prettier . --check # frontend style
uvx tryke test # tests (uses --reporter llm)
```

### Rules

- be sure the tests, type checkers, linters and formatters all pass to validate code changes
