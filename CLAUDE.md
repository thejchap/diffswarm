# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

DiffSwarm is a Python web application built with FastAPI. The project uses modern Python tooling with uv as the package manager and follows a minimal structure.

It uses:
- [FastAPI](https://fastapi.tiangolo.com/)
- [uv](https://github.com/uv)

## Architecture

- **Entry Points**: The application can be run via `python -m diffswarm` or the `diffswarm` command (installed via project scripts)
- **Main Application**: `src/diffswarm/app.py` contains the FastAPI application instance (`APP`)
- **Runner**: `src/diffswarm/__init__.py` provides the `run()` function that starts the uvicorn server
- **Module Entry**: `src/diffswarm/__main__.py` enables `python -m diffswarm` execution

## Development Commands

### Environment Setup
```bash
uv sync  # Install dependencies and create virtual environment
```

### Running the Application
```bash
uv run fastapi dev src/diffswarm # Run via uv (development)
uv run diffswarm # Run via uv (production)
```

### Development Tools
```bash
uv run ruff check       # Lint code
uv run ruff format      # Format code
uv run pytest           # Run tests
```

### Package Management
```bash
uv add <package>        # Add runtime dependency
uv add --dev <package>  # Add development dependency
uv remove <package>     # Remove dependency
uv lock                 # Update lockfile
```

## Project Structure

- `src/diffswarm/` - Main package directory
- `__init__.py` - Contains `run()` function for starting the server
- `__main__.py` - Module entry point
- `app.py` - FastAPI application definition
- `pyproject.toml` - Project configuration and dependencies
- `uv.lock` - Dependency lockfile

## Type Checking

The project is configured to use Pyright with the virtual environment located at `./.venv`.

## Notes
- Look up answers in the FastAPI documentation where relevant for extra certainty
- Use doctests to verify code examples in documentation
