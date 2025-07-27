# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DiffSwarm is a Python web application built with FastAPI. The project uses modern Python tooling with uv as the package manager and follows a minimal structure.

It uses:
- [FastAPI](https://fastapi.tiangolo.com/)
- [uv](https://github.com/uv)

## Architecture

DiffSwarm is structured as a diff parsing and storage service with a FastAPI web interface.

### Core Components
- **FastAPI App**: `src/diffswarm/app/app.py` contains the main FastAPI application (`APP`) with database lifecycle management
- **Models**: `src/diffswarm/app/models.py` defines Pydantic models for diff parsing including `DiffBase`, `Hunk`, and `Line` types
- **Database**: `src/diffswarm/app/database.py` handles SQLAlchemy setup with SQLite backend and `DBDiff` table model
- **Router**: `src/diffswarm/app/routers/pages.py` contains API endpoints
- **Settings**: `src/diffswarm/app/settings.py` manages configuration via pydantic-settings

### Entry Points
- **Direct execution**: `uv run fastapi dev` (development mode)
- **Invoke tool**: `uv run invoke <route_name>` - CLI tool for testing API endpoints with example data

### Data Flow
The application parses unified diff format strings into structured models, validates line counts in hunks, and stores them in SQLite via SQLAlchemy ORM.

## Development Commands

### Environment Setup
```bash
uv sync  # Install dependencies and create virtual environment
```

### Running the Application
```bash
uv run fastapi dev src/diffswarm        # Development server with hot reload
uv run invoke <route_name>               # Test specific API endpoint (e.g., "create_diff")
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

- **Diff Parsing**: Parses unified diff format with validation of line counts in hunks
- **Data Models**: Strong typing with Pydantic models and enum-based line types
- **Database**: SQLite storage via SQLAlchemy ORM with automatic table creation
- **Testing Tool**: Built-in `invoke` command for endpoint testing with example data

# Development Notes
- After all changes, run the following to ensure correct functionality and code quality:
  - `uv run basedpyright`
  - `uv run ruff check --fix`
  - `uv run ruff format`
  - `uv run pytest`
