# src/ots_containers/commands/assets.py
"""Asset management commands for OTS containers."""

from typing import Annotated

import cyclopts

from .. import assets as assets_module
from ..config import Config

app = cyclopts.App(name="assets", help="Manage static assets")


@app.command
def sync(
    create_volume: Annotated[
        bool,
        cyclopts.Parameter(
            help="Create volume if it doesn't exist (use on first deploy)"
        ),
    ] = False,
):
    """Sync static assets from container image to volume.

    Extracts /app/public from image to static_assets volume.
    Use --create-volume on initial setup.
    """
    cfg = Config()
    cfg.validate()
    assets_module.update(cfg, create_volume=create_volume)
