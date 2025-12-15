# src/ots_containers/commands/instance/app.py
"""Instance management app and commands for OTS containers."""

import subprocess
from typing import Annotated

import cyclopts

from ots_containers import assets, quadlet, systemd
from ots_containers.config import Config

from ._helpers import for_each, resolve_ports, write_env_file
from .annotations import Delay, OptionalPorts, Ports

app = cyclopts.App(
    name=["instance", "instances"],
    help="Manage instances (.env-{port}, quadlet, systemd)",
)


@app.default
def list_instances(ports: OptionalPorts = (), alias: str = "instances"):
    """List running instances (auto-discovers if no ports given)."""
    ports = resolve_ports(ports)
    if not ports:
        return
    print("Instances:")
    print("-" * 40)
    for port in ports:
        print(f"  onetime@{port}")


@app.command
def deploy(ports: Ports, delay: Delay = 5):
    """Deploy new instance(s) from config.yaml and .env template.

    Creates .env-{port}, writes quadlet config, starts systemd service.
    """
    cfg = Config()
    cfg.validate()
    print(f"Reading config from {cfg.config_yaml}")
    print(f"Reading env template from {cfg.env_template}")
    assets.update(cfg, create_volume=True)
    print(f"Writing quadlet files to {cfg.template_path.parent}")
    quadlet.write_template(cfg)

    def do_deploy(port: int) -> None:
        env_file = cfg.env_file(port)
        print(f"Writing {env_file}")
        write_env_file(cfg, port)
        print(f"Starting onetime@{port}")
        systemd.start(f"onetime@{port}")

    for_each(ports, delay, do_deploy, "Deploying")


@app.command
def redeploy(
    ports: OptionalPorts = (),
    delay: Delay = 5,
    force: Annotated[
        bool,
        cyclopts.Parameter(help="Teardown and recreate (deletes .env, stops, redeploys)"),
    ] = False,
):
    """Regenerate .env-{port} and quadlet from config.yaml/.env, restart.

    Use after editing config.yaml or .env template.
    Use --force to fully teardown and recreate.
    """
    ports = resolve_ports(ports)
    if not ports:
        return
    cfg = Config()
    cfg.validate()
    print(f"Reading config from {cfg.config_yaml}")
    print(f"Reading env template from {cfg.env_template}")
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
        write_env_file(cfg, port)
        unit = f"onetime@{port}"
        if force or not systemd.unit_exists(unit):
            print(f"Starting {unit}")
            systemd.start(unit)
        else:
            print(f"Restarting {unit}")
            systemd.restart(unit)

    verb = "Force redeploying" if force else "Redeploying"
    for_each(ports, delay, do_redeploy, verb)


@app.command
def undeploy(ports: OptionalPorts = (), delay: Delay = 5):
    """Stop systemd service and delete .env-{port} config file.

    Stops systemd service and deletes .env-{port} config file.
    """
    ports = resolve_ports(ports)
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

    for_each(ports, delay, do_undeploy, "Undeploying")


@app.command
def start(ports: OptionalPorts = ()):
    """Start systemd unit(s) for instance(s).

    Picks up manual edits to .env-{port}. Does NOT regenerate from
    config.yaml or .env template - use 'redeploy' for that.
    """
    ports = resolve_ports(ports)
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
    ports = resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        systemd.stop(f"onetime@{port}")
        print(f"Stopped onetime@{port}")


@app.command
def restart(ports: OptionalPorts = ()):
    """Restart systemd unit(s) for instance(s).

    Picks up manual edits to .env-{port}. Does NOT regenerate from
    config.yaml or .env template - use 'redeploy' for that.
    """
    ports = resolve_ports(ports)
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
    ports = resolve_ports(ports)
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
    ports = resolve_ports(ports)
    if not ports:
        return
    units = [f"onetime@{port}" for port in ports]
    cmd = ["sudo", "journalctl", "--no-pager", f"-n{lines}"]
    if follow:
        cmd.append("-f")
    for unit in units:
        cmd.extend(["-u", unit])
    subprocess.run(cmd)


@app.command
def env(ports: OptionalPorts = ()):
    """Show sorted environment variables for instance(s).

    Reads and displays the .env-{port} file contents, sorted alphabetically.
    """
    ports = resolve_ports(ports)
    if not ports:
        return
    cfg = Config()
    for port in ports:
        env_file = cfg.env_file(port)
        print(f"=== {env_file} ===")
        if env_file.exists():
            lines = env_file.read_text().splitlines()
            # Sort non-empty, non-comment lines
            env_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
            for line in sorted(env_lines):
                print(line)
        else:
            print("  (file not found)")
        print()


@app.command(name="exec")
def exec_shell(
    ports: OptionalPorts = (),
    command: Annotated[
        str,
        cyclopts.Parameter(name=["--command", "-c"], help="Command to run (default: $SHELL)"),
    ] = "",
):
    """Run interactive shell in container(s).

    When no ports specified, iterates through all discovered instances sequentially.
    Uses $SHELL environment variable or /bin/sh as fallback.
    """
    import os

    ports = resolve_ports(ports)
    if not ports:
        return

    shell = command or os.environ.get("SHELL", "/bin/sh")

    for port in ports:
        container = f"systemd-onetime@{port}"
        print(f"=== Entering {container} ===")
        # Interactive exec requires subprocess.run with no capture
        subprocess.run(["podman", "exec", "-it", container, shell])
        print()
