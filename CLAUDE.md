# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test Commands

```bash
# Install for development (editable)
pip install -e ".[dev,test]"

# Run all tests
pytest tests/

# Run single test file
pytest tests/test_quadlet.py

# Run single test by name
pytest tests/test_quadlet.py -k "test_template"

# Run tests with coverage (CI threshold: 70%)
pytest tests/ --cov=ots_containers --cov-report=term-missing --cov-fail-under=70

# Lint and format
ruff check src/
ruff format src/
ruff check src/ --fix  # auto-fix

# Type checking
pyright src/

# Pre-commit hooks (auto-installed)
pre-commit run --all-files
```

## Git Notes

When running git commands with long output, use `git --no-pager diff` etc.

## Architecture

This is a CLI tool for managing OneTimeSecret containers via Podman Quadlets (systemd integration).

### Core Modules (`src/ots_containers/`)

- **cli.py** - Entry point (`app`), registers subcommand groups
- **config.py** - `Config` dataclass: image, tag, paths. Reads from env vars (IMAGE, TAG, etc.)
- **quadlet.py** - Writes systemd Quadlet template to `/etc/containers/systemd/onetime@.container`
- **systemd.py** - Wrappers around `systemctl`: start/stop/restart/status, `discover_instances()` for auto-detection
- **podman.py** - `Podman` class: chainable interface to podman CLI (e.g., `podman.container.ls()`)
- **assets.py** - Extracts `/app/public` from container image to shared volume

### Commands (`src/ots_containers/commands/`)

- **instance.py** - Main operations: `deploy`, `redeploy`, `undeploy`, `start`, `stop`, `restart`, `status`, `logs`, `list`
- **assets.py** - `sync` command for static asset updates

### Key Patterns

- Uses **cyclopts** for CLI framework (decorators like `@app.command()`)
- Port-based instance identification: each instance runs on a specific port (e.g., 7043)
- Auto-discovery via `systemd.discover_instances()` - finds running `onetime@*` services
- Env file templating: `/opt/onetimesecret/config/.env` → `/opt/onetimesecret/.env-{port}`
