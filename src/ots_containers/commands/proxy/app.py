# src/ots_containers/commands/proxy/app.py
"""Proxy management commands for OTS containers.

These commands manage the reverse proxy (Caddy) configuration using HOST
environment variables via envsubst. This is intentionally separate from
container .env files to avoid mixing host and container configurations.
"""

from pathlib import Path
from typing import Annotated

import cyclopts

from ots_containers.config import Config

from ._helpers import ProxyError, reload_caddy, render_template, validate_caddy_config

app = cyclopts.App(
    name="proxy",
    help="Manage reverse proxy (Caddy) configuration",
)

Template = Annotated[
    Path | None,
    cyclopts.Parameter(
        name=["--template", "-t"],
        help="Template file path (default: /etc/onetimesecret/Caddyfile.template)",
    ),
]

Output = Annotated[
    Path | None,
    cyclopts.Parameter(
        name=["--output", "-o"],
        help="Output file path (default: /etc/caddy/Caddyfile)",
    ),
]

DryRun = Annotated[
    bool,
    cyclopts.Parameter(
        name=["--dry-run", "-n"],
        negative=[],  # Disable --no-dry-run generation
        help="Print rendered config without writing or reloading",
    ),
]


@app.command
def render(
    template: Template = None,
    output: Output = None,
    dry_run: DryRun = False,
) -> None:
    """Render proxy config from template using HOST environment.

    Uses envsubst to substitute environment variables in the template.
    Validates the result with 'caddy validate' before writing.

    Note: Uses HOST environment variables, not container .env files.
    """
    cfg = Config()
    tpl = template or cfg.proxy_template
    out = output or cfg.proxy_config

    try:
        rendered = render_template(tpl)

        if dry_run:
            print(rendered)
            return

        # Validate before writing
        validate_caddy_config(rendered)

        # Write to output path (may need sudo)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered)
        print(f"[ok] Rendered {tpl} -> {out}")

    except ProxyError as e:
        raise SystemExit(f"[error] {e}") from e


@app.command
def reload() -> None:
    """Reload the Caddy service.

    Runs 'systemctl reload caddy' to apply configuration changes.
    """
    try:
        reload_caddy()
        print("[ok] Caddy reloaded")
    except ProxyError as e:
        raise SystemExit(f"[error] {e}") from e
