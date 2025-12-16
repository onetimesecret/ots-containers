# src/ots_containers/cli.py

"""
Manage OTS Podman containers via Quadlets.

Usage:

    ots-containers init
    ots-containers image pull --tag v0.23.0 --current
    ots-containers instance deploy 7043
    ots-containers instance redeploy 7044
    ots-containers image rollback
    ots-containers instance redeploy
    ots-containers assets sync

    # Or run directly without installing:
    $ cd src/
    $ pip install -e .
    $ python -m ots_containers.cli instance deploy 7043
"""

import cyclopts

from . import __version__
from .commands import assets as assets_cmd
from .commands import image, init, instance, proxy
from .podman import podman

app = cyclopts.App(
    name="ots-containers",
    help="Manage OTS Podman containers via Quadlets",
    version=__version__,
)

# Register topic sub-apps
app.command(init.app)
app.command(instance.app)
app.command(image.app)
app.command(assets_cmd.app)
app.command(proxy.app)


@app.default
def _default():
    """Show help when no command is specified."""
    app.help_print([])


# Root-level command for quick access
@app.command
def ps():
    """Show running OTS containers (podman view)."""
    podman.ps(
        filter="name=onetime",
        format="table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}",
    )


if __name__ == "__main__":
    app()
