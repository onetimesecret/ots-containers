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
from .commands import cloudinit, image, init, instance, proxy, service
from .podman import podman

app = cyclopts.App(
    name="ots-containers",
    help="Service orchestration for OTS: Podman Quadlets and systemd services",
    version=__version__,
)

# Register topic sub-apps
app.command(init.app)
app.command(instance.app)
app.command(image.app)
app.command(assets_cmd.app)
app.command(proxy.app)
app.command(service.app)
app.command(cloudinit.app)


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


@app.command
def version():
    """Show version and build info."""
    import subprocess
    from pathlib import Path

    print(f"ots-containers {__version__}")

    # Try to get git info if available
    try:
        pkg_dir = Path(__file__).parent
        result = subprocess.run(
            ["git", "-C", str(pkg_dir), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            print(f"git commit: {commit}")
    except Exception:
        pass


if __name__ == "__main__":
    app()
