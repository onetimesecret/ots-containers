# src/ots_containers/cli.py

"""

Usage:

    For setting up and managing podman services for ghcr.io/onetimesecret/onetimesecret
    The next generation of setup-podman-containers.sh.

    ots-containers setup 7043
    ots-containers update 7044
    TAG=v0.19.0 ots-containers update 7043
    ots-containers remove 7043
    ots-containers static

    # Or run directly without installing:
    $ cd src/
    $ pip install -e .
    $ python -m ots_containers.cli setup 7043
"""

# cli.py
import time
from typing import Annotated

import cyclopts

from . import __version__, assets, quadlet, systemd
from .config import Config

app = cyclopts.App(
    help="Manage OTS Podman containers via Quadlets",
    version=__version__,
)

Delay = Annotated[
    int, cyclopts.Parameter("--delay -d", help="Seconds between operations")
]
Ports = Annotated[
    tuple[int, ...], cyclopts.Parameter(help="Container ports to operate on")
]
OptionalPorts = Annotated[
    tuple[int, ...],
    cyclopts.Parameter(
        help="Container ports (discovers running instances if omitted)"
    ),
]


def _resolve_ports(ports: tuple[int, ...]) -> tuple[int, ...]:
    """Return provided ports, or discover running instances if none given."""
    if ports:
        return ports
    discovered = systemd.discover_instances()
    if not discovered:
        print("No running instances found")
        return ()
    return tuple(discovered)


def _for_each(
    ports: tuple[int, ...], delay: int, action: callable, verb: str
) -> None:
    """Run action for each port with delay between."""
    total = len(ports)
    for i, port in enumerate(ports, 1):
        print(f"[{i}/{total}] {verb} container on port {port}...")
        action(port)
        if i < total and delay > 0:
            print(f"Waiting {delay}s...")
            time.sleep(delay)
    print(f"Processed {total} container(s)")


def _write_env_file(cfg: Config, port: int) -> None:
    template = (cfg.base_dir / "config" / ".env").read_text()
    content = template.replace("${PORT}", str(port)).replace("$PORT", str(port))
    cfg.env_file(port).write_text(content)


@app.command
def static():
    """Update static assets without creating volume."""
    cfg = Config()
    cfg.validate()
    assets.update(cfg, create_volume=False)


@app.command
def setup(ports: Ports, delay: Delay = 5):
    """Set up new instance(s) on PORT(s)."""
    cfg = Config()
    cfg.validate()
    assets.update(cfg, create_volume=True)
    quadlet.write_template(cfg)

    def do_setup(port: int) -> None:
        _write_env_file(cfg, port)
        systemd.start(f"onetime@{port}")
        systemd.status(f"onetime@{port}")

    _for_each(ports, delay, do_setup, "Setting up")


@app.command
def update(ports: OptionalPorts = (), delay: Delay = 5):
    """Update running instance(s) (or specified ports)."""
    ports = _resolve_ports(ports)
    if not ports:
        return
    cfg = Config()
    cfg.validate()
    assets.update(cfg, create_volume=False)
    quadlet.write_template(cfg)

    def do_update(port: int) -> None:
        _write_env_file(cfg, port)
        systemd.restart(f"onetime@{port}")
        systemd.status(f"onetime@{port}")

    _for_each(ports, delay, do_update, "Updating")


@app.command
def remove(ports: Ports, delay: Delay = 5):
    """Remove instance(s) on PORT(s)."""
    cfg = Config()

    def do_remove(port: int) -> None:
        systemd.stop(f"onetime@{port}")
        env_file = cfg.env_file(port)
        if env_file.exists():
            env_file.unlink()
        print(f"Removed onetime@{port}")

    _for_each(ports, delay, do_remove, "Removing")


@app.command
def replace(ports: Ports, delay: Delay = 5):
    """Replace instance(s): remove then setup, one at a time."""
    cfg = Config()
    cfg.validate()
    assets.update(cfg, create_volume=True)
    quadlet.write_template(cfg)

    def do_replace(port: int) -> None:
        # Remove
        systemd.stop(f"onetime@{port}")
        env_file = cfg.env_file(port)
        if env_file.exists():
            env_file.unlink()
        # Setup
        _write_env_file(cfg, port)
        systemd.start(f"onetime@{port}")
        systemd.status(f"onetime@{port}")

    _for_each(ports, delay, do_replace, "Replacing")


@app.command
def list_(ports: OptionalPorts = ()):
    """List running containers (or specified ports)."""
    ports = _resolve_ports(ports)
    if not ports:
        return
    print("Containers:")
    print("-" * 40)
    for port in ports:
        print(f"  onetime@{port}")


@app.command
def ps():
    """Show running OTS containers (podman view)."""
    import subprocess

    subprocess.run(
        [
            "podman",
            "ps",
            "--filter",
            "name=systemd-onetime",
            "--format",
            "table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}",
        ]
    )


@app.command
def status(ports: OptionalPorts = ()):
    """Show systemd status for running containers (or specified ports)."""
    ports = _resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        systemd.status(f"onetime@{port}")
        print()


@app.command
def logs(
    ports: OptionalPorts = (),
    lines: Annotated[int, cyclopts.Parameter("--lines -n")] = 50,
    follow: Annotated[bool, cyclopts.Parameter("--follow -f")] = False,
):
    """Show logs for running containers (or specified ports)."""
    import subprocess

    ports = _resolve_ports(ports)
    if not ports:
        return
    units = [f"onetime@{port}" for port in ports]
    cmd = ["sudo", "journalctl", "--no-pager", f"-n{lines}"]
    if follow:
        cmd.append("-f")
    for unit in units:
        cmd.extend(["-u", unit])
    subprocess.run(cmd)


if __name__ == "__main__":
    app()
