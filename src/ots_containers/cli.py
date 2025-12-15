# src/ots_containers/cli.py

"""
Manage OTS Podman containers via Quadlets.

Usage:

    ots-containers instance deploy 7043
    ots-containers instance redeploy 7044
    TAG=v0.19.0 ots-containers instance redeploy 7043
    ots-containers instance undeploy 7043
    ots-containers assets sync

    # Or run directly without installing:
    $ cd src/
    $ pip install -e .
    $ python -m ots_containers.cli instance deploy 7043
"""

import cyclopts

from . import __version__
from .commands import assets as assets_cmd
from .commands import instance
from .podman import podman

app = cyclopts.App(
    name="ots-containers",
    help="Manage OTS Podman containers via Quadlets",
    version=__version__,
)

# Register topic sub-apps
app.command(instance.app)
app.command(assets_cmd.app)


@app.default
def _default():
    """Show help when no command is specified."""
    app.help_print([])


# Root-level command for quick access
@app.command
def ps():
    """Show running OTS containers (podman view)."""
    podman.ps(
        filter="name=systemd-onetime",
        format="table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}",
    )


if __name__ == "__main__":
    app()
