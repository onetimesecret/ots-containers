# src/ots_containers/commands/instance.py
"""Instance management commands for OTS containers."""

import subprocess
from collections.abc import Callable
from typing import Annotated

import cyclopts

from .. import assets, quadlet, systemd
from ..config import Config

app = cyclopts.App(
    name=["instance", "instances"],
    help="Manage instances (.env-{port}, quadlet, systemd)",
)

# Type aliases (defined here to avoid circular imports)
Delay = Annotated[
    int,
    cyclopts.Parameter(name=["--delay", "-d"], help="Seconds between operations"),
]
Ports = Annotated[tuple[int, ...], cyclopts.Parameter(help="Container ports to operate on")]
OptionalPorts = Annotated[
    tuple[int, ...],
    cyclopts.Parameter(help="Container ports (discovers running instances if omitted)"),
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
    ports: tuple[int, ...],
    delay: int,
    action: "Callable[[int], None]",
    verb: str,
) -> None:
    """Run action for each port with delay between."""
    import time

    total = len(ports)
    for i, port in enumerate(ports, 1):
        print(f"[{i}/{total}] {verb} container on port {port}...")
        action(port)
        if i < total and delay > 0:
            print(f"Waiting {delay}s...")
            time.sleep(delay)
    print(f"Processed {total} container(s)")


def _write_env_file(cfg: Config, port: int) -> None:
    """Write .env-{port} from template with port substitution."""
    template = (cfg.base_dir / "config" / ".env").read_text()
    content = template.replace("${PORT}", str(port)).replace("$PORT", str(port))
    cfg.env_file(port).write_text(content)


@app.default
def list_instances(ports: OptionalPorts = (), alias: str = "instances"):
    """List running instances (auto-discovers if no ports given)."""
    ports = _resolve_ports(ports)
    if not ports:
        return
    print("Instances:")
    print("-" * 40)
    for port in ports:
        print(f"  onetime@{port}")


@app.command
def deploy(ports: Ports, delay: Delay = 5):
    """Deploy new instance(s) from config.yaml and config/.env template.

    Creates .env-{port}, writes quadlet config, starts systemd service.
    """
    cfg = Config()
    cfg.validate()
    print(f"Reading config from {cfg.base_dir / 'config' / 'config.yaml'}")
    print(f"Updating assets from {cfg.base_dir / 'config'}")
    assets.update(cfg, create_volume=True)
    print(f"Writing quadlet files to {cfg.template_path.parent}")
    quadlet.write_template(cfg)

    def do_deploy(port: int) -> None:
        env_file = cfg.env_file(port)
        print(f"Writing {env_file}")
        _write_env_file(cfg, port)
        print(f"Starting onetime@{port}")
        systemd.start(f"onetime@{port}")

    _for_each(ports, delay, do_deploy, "Deploying")


@app.command
def redeploy(
    ports: OptionalPorts = (),
    delay: Delay = 5,
    force: Annotated[
        bool,
        cyclopts.Parameter(help="Teardown and recreate (deletes .env, stops, redeploys)"),
    ] = False,
):
    """Regenerate .env-{port} and quadlet from config.yaml/config/.env, restart.

    Use after editing config.yaml or config/.env template.
    Use --force to fully teardown and recreate.
    """
    ports = _resolve_ports(ports)
    if not ports:
        return
    cfg = Config()
    cfg.validate()
    print(f"Reading config from {cfg.base_dir / 'config' / 'config.yaml'}")
    print(f"Updating assets from {cfg.base_dir / 'config'}")
    assets.update(cfg, create_volume=force)
    print(f"Writing quadlet files to {cfg.template_path.parent}")
    quadlet.write_template(cfg)

    def do_redeploy(port: int) -> None:
        env_file = cfg.env_file(port)
        if force:
            # Teardown first
            print(f"Stopping onetime@{port}")
            systemd.stop(f"onetime@{port}")
            if env_file.exists():
                print(f"Removing {env_file}")
                env_file.unlink()
        # Deploy
        print(f"Writing {env_file}")
        _write_env_file(cfg, port)
        unit = f"onetime@{port}"
        if force or not systemd.unit_exists(unit):
            print(f"Starting {unit}")
            systemd.start(unit)
        else:
            print(f"Restarting {unit}")
            systemd.restart(unit)

    verb = "Force redeploying" if force else "Redeploying"
    _for_each(ports, delay, do_redeploy, verb)


@app.command
def undeploy(ports: OptionalPorts = (), delay: Delay = 5):
    """Stop systemd service and delete .env-{port} config file.

    Stops systemd service and deletes .env-{port} config file.
    """
    ports = _resolve_ports(ports)
    if not ports:
        return
    cfg = Config()

    def do_undeploy(port: int) -> None:
        print(f"Stopping onetime@{port}")
        systemd.stop(f"onetime@{port}")
        env_file = cfg.env_file(port)
        if env_file.exists():
            print(f"Removing {env_file}")
            env_file.unlink()

    _for_each(ports, delay, do_undeploy, "Undeploying")


@app.command
def start(ports: OptionalPorts = ()):
    """Start systemd unit(s) for instance(s).

    Picks up manual edits to .env-{port}. Does NOT regenerate from
    config.yaml or config/.env - use 'redeploy' for that.
    """
    ports = _resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        systemd.start(f"onetime@{port}")
        print(f"Started onetime@{port}")


@app.command
def stop(ports: OptionalPorts = ()):
    """Stop systemd unit(s) for instance(s).

    Does NOT affect .env or quadlet config.
    """
    ports = _resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        systemd.stop(f"onetime@{port}")
        print(f"Stopped onetime@{port}")


@app.command
def restart(ports: OptionalPorts = ()):
    """Restart systemd unit(s) for instance(s).

    Picks up manual edits to .env-{port}. Does NOT regenerate from
    config.yaml or config/.env - use 'redeploy' for that.
    """
    ports = _resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        unit = f"onetime@{port}"
        if systemd.unit_exists(unit):
            systemd.restart(unit)
            print(f"Restarted {unit}")
        else:
            systemd.start(unit)
            print(f"Started {unit} (unit was not loaded)")


@app.command
def status(ports: OptionalPorts = ()):
    """Show systemd status for instance(s)."""
    ports = _resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        systemd.status(f"onetime@{port}")
        print()


@app.command
def logs(
    ports: OptionalPorts = (),
    lines: Annotated[int, cyclopts.Parameter(name=["--lines", "-n"])] = 50,
    follow: Annotated[bool, cyclopts.Parameter(name=["--follow", "-f"])] = False,
):
    """Show logs for instance(s)."""
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
