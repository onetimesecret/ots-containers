# src/ots_containers/commands/instance.py
"""Instance management commands for OTS containers."""

import subprocess
from typing import Annotated

import cyclopts

from .. import assets, quadlet, systemd
from ..config import Config

app = cyclopts.App(name="instance", help="Manage container instances")

# Type aliases (defined here to avoid circular imports)
Delay = Annotated[
    int,
    cyclopts.Parameter(
        name=["--delay", "-d"], help="Seconds between operations"
    ),
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
def list_instances(ports: OptionalPorts = ()):
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
    """Deploy new instance(s) on PORT(s).

    Creates .env-{port} from template, writes quadlet config, starts systemd service.
    """
    cfg = Config()
    cfg.validate()
    assets.update(cfg, create_volume=True)
    quadlet.write_template(cfg)

    def do_deploy(port: int) -> None:
        _write_env_file(cfg, port)
        systemd.start(f"onetime@{port}")
        systemd.status(f"onetime@{port}")

    _for_each(ports, delay, do_deploy, "Deploying")


@app.command
def redeploy(
    ports: OptionalPorts = (),
    delay: Delay = 5,
    force: Annotated[
        bool,
        cyclopts.Parameter(
            help="Teardown and recreate (deletes .env, stops, then deploys fresh)"
        ),
    ] = False,
):
    """Redeploy instance(s) with config refresh.

    Rewrites .env-{port} from template, updates quadlet config, restarts service.
    Use --force to fully teardown and recreate.
    """
    ports = _resolve_ports(ports)
    if not ports:
        return
    cfg = Config()
    cfg.validate()
    assets.update(cfg, create_volume=force)
    quadlet.write_template(cfg)

    def do_redeploy(port: int) -> None:
        if force:
            # Teardown first
            systemd.stop(f"onetime@{port}")
            env_file = cfg.env_file(port)
            if env_file.exists():
                env_file.unlink()
        # Deploy
        _write_env_file(cfg, port)
        if force:
            systemd.start(f"onetime@{port}")
        else:
            systemd.restart(f"onetime@{port}")
        systemd.status(f"onetime@{port}")

    verb = "Force redeploying" if force else "Redeploying"
    _for_each(ports, delay, do_redeploy, verb)


@app.command
def undeploy(ports: OptionalPorts = (), delay: Delay = 5):
    """Remove instance(s) completely.

    Stops systemd service and deletes .env-{port} config file.
    """
    ports = _resolve_ports(ports)
    if not ports:
        return
    cfg = Config()

    def do_undeploy(port: int) -> None:
        systemd.stop(f"onetime@{port}")
        env_file = cfg.env_file(port)
        if env_file.exists():
            env_file.unlink()
        print(f"Removed onetime@{port}")

    _for_each(ports, delay, do_undeploy, "Undeploying")


@app.command
def start(ports: OptionalPorts = ()):
    """Start systemd unit(s) for instance(s).

    Does NOT refresh .env or quadlet config. Use 'redeploy' to pick up config changes.
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

    Does NOT refresh .env or quadlet config. Use 'redeploy' to pick up config changes.
    """
    ports = _resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        systemd.restart(f"onetime@{port}")
        print(f"Restarted onetime@{port}")


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
    follow: Annotated[
        bool, cyclopts.Parameter(name=["--follow", "-f"])
    ] = False,
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
