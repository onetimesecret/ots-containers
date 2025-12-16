# CLI Style Guide

## Command Structure

We follow a Heroku-style `topic:command` pattern:

```
ots-containers <topic> <command> [args] [flags]
```

## Topics

Each topic is a separate module in this directory with its own `cyclopts.App`:

| Topic | Purpose |
|-------|---------|
| `instance` | Container lifecycle and runtime control |
| `assets` | Static asset management |

To add a new topic, create a module and register it in `cli.py`.

## Two-Level Abstraction

Commands are categorized by their impact:

### High-level (affects config + state)
Commands that modify `.env-{port}` files, quadlet templates, or both:
- `deploy`, `redeploy`, `undeploy`

These commands should document their config impact in the docstring.

### Low-level (runtime control only)
Commands that only interact with systemd, no config changes:
- `start`, `stop`, `restart`, `status`, `logs`

These commands should explicitly state they do NOT refresh config.

## Naming Conventions

| Pattern | Example | Use for |
|---------|---------|---------|
| Verb | `deploy`, `sync` | Actions |
| `--flag` | `--force`, `--create-volume` | Boolean options |
| `--option VALUE` | `--delay 5`, `--lines 50` | Value options |

## Default Commands

Use `@app.default` for the "list" operation when invoking a topic without a subcommand:

```python
@app.default
def list_instances():
    """List running instances."""
    ...
```

This follows Heroku's pattern where `heroku apps` lists apps.

## Help Text

First line: Brief imperative description.
Blank line, then: Config impact and usage notes.

```python
@app.command
def redeploy(...):
    """Redeploy instance(s) with config refresh.

    Rewrites .env-{port} from template, updates quadlet config, restarts service.
    Use --force to fully teardown and recreate.
    """
```

## Adding Commands

1. Add to existing topic module, or create new topic
2. Use shared helpers from the topic module (`_resolve_ports`, `_for_each`, etc.)
3. Document config impact in docstring
4. Register new topics in `cli.py` via `app.command(topic.app)`
