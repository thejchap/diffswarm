# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DiffSwarm is a Python web application built with FastAPI that provides real-time collaborative diff editing. The project uses modern Python tooling with uv as the package manager and follows a minimal structure.

Technology stack:
- **Backend**: [FastAPI](https://fastapi.tiangolo.com/) with SQLAlchemy and SQLite
- **Real-time**: Y-CRDT (Yjs) for conflict-free collaborative editing via WebSockets  
- **Frontend**: Vue.js SPA with TailwindCSS
- **Tooling**: [uv](https://github.com/uv) package manager, Ruff linting, Pyright type checking

## Architecture

DiffSwarm follows a layered architecture with real-time collaborative editing capabilities:

### Core Components

- **FastAPI App**: `src/diffswarm/app/app.py` - Main application with database lifecycle management and WebSocket support
- **Models**: `src/diffswarm/app/models.py` - Pydantic models with sophisticated unified diff parser (`DiffBase`, `Hunk`, `Line` types)
- **Database**: `src/diffswarm/app/database.py` - SQLAlchemy setup with SQLite backend and `DBDiff` table model
- **HTTP Router**: `src/diffswarm/app/routers/pages.py` - REST API endpoints for diff creation and retrieval  
- **WebSocket Server**: `src/diffswarm/app/y.py` - Real-time collaborative editing using Y-CRDT protocol with room-based document synchronization
- **Frontend**: `templates/diff.html` - Vue.js SPA with Y.js WebSocket integration for real-time collaboration
- **CLI Tool**: `src/diffswarm/tools/invoke.py` - Dynamic API endpoint testing with metadata-driven example extraction
- **Settings**: `src/diffswarm/app/settings.py` - Configuration management via pydantic-settings

### Real-time Collaboration Architecture

- **YWebSocketServer**: Manages multiple diff rooms with per-diff document synchronization
- **YRoom**: Handles client connections, document updates, and broadcasting within a single diff session
- **Y-CRDT Integration**: Conflict-free replicated data types ensure automatic merge of concurrent edits
- **Room Management**: Automatic client cleanup and empty room deletion

### Entry Points

- **Direct execution**: `uv run fastapi dev` (development mode)
- **Invoke tool**: `uv run invoke <route_name>` - CLI tool for testing API endpoints with example data

### Data Flow

1. **Diff Creation**: POST requests parse unified diff strings via `UnifiedDiffParser` into `DiffBase` models with validation
2. **Database Storage**: Validated diffs stored in SQLite with ULID identifiers via SQLAlchemy ORM
3. **Real-time Collaboration**: WebSocket connections per diff-id create Y-CRDT document rooms for concurrent editing
4. **Frontend Integration**: Vue.js client connects via Y.js WebSocket provider for live synchronization

## Development Commands

### Environment Setup

```bash
uv sync  # Install dependencies and create virtual environment
```

### Running the Application

```bash
uv run fastapi dev src/diffswarm        # Development server with hot reload
uv run invoke <route_name>               # Test API endpoint with example data (e.g., "create_diff")
uv run invoke --list                     # List all available endpoints for testing
```

### Development Tools

```bash
uv run ruff check       # Lint code
uv run ruff format      # Format code
uv run pytest           # Run tests
uv run basedpyright     # Run basedpyright (type checker)
```

### Package Management

```bash
uv add <package>        # Add runtime dependency
uv add --dev <package>  # Add development dependency
uv remove <package>     # Remove dependency
uv lock                 # Update lockfile
```

## Type Checking & Code Quality

- **Type Checker**: Pyright with strict mode enabled (`.venv` virtual environment)
- **Linter**: Ruff with comprehensive rule set ("ALL" selected with specific ignores)
- **Formatter**: Ruff (88 character line length)
- **Testing**: pytest with doctest integration enabled

## Key Features

- **Diff Parsing**: Sophisticated unified diff parser with validation of line counts and hunk structure
- **Real-time Collaboration**: Y-CRDT-based collaborative editing with automatic conflict resolution
- **Strong Typing**: Comprehensive type safety with Pydantic models and strict Pyright checking
- **Database**: SQLite storage via SQLAlchemy ORM with ULID identifiers and automatic table creation
- **Dynamic Testing**: Built-in `invoke` tool with metadata-driven example extraction for API testing
- **WebSocket Protocol**: Y.js binary protocol implementation for efficient real-time synchronization

# Development Notes

- After all changes, run the following to ensure correct functionality and code quality:
  - `uv run basedpyright`
  - `uv run ruff check --fix`
  - `uv run ruff format`
  - `uv run pytest`
- All log messages should be lowercased
- WebSocket error handling uses specific exception types: `WebSocketDisconnect`, `ConnectionResetError`
- Y-CRDT documents use strongly typed `DiffDoc = Doc[Array[int]]` for collaborative arrays
- Database uses ULID format for primary keys (26 characters, sortable)

## API Endpoints

- **GET /**: Simple health check returning "diffswarm"
- **POST /**: Create diff from unified diff string, returns URL to view diff
- **GET /diffs/{diff_id}**: Retrieve and display diff with interactive collaborative UI
- **WebSocket /ws/{diff_id}**: Real-time collaboration endpoint for Y.js protocol
