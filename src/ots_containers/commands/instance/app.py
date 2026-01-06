# src/ots_containers/commands/instance/app.py
"""Instance management app and commands for OTS containers."""

import subprocess
from typing import Annotated

import cyclopts

from ots_containers import assets, db, quadlet, systemd
from ots_containers.config import Config

from ._helpers import for_each, for_each_worker, resolve_ports
from .annotations import Delay, InstanceType, OptionalPorts

app = cyclopts.App(
    name=["instance", "instances"],
    help="Manage OTS container instances (quadlet, systemd)",
)


@app.default
def list_instances(ports: OptionalPorts = (), alias: str = "instances"):
    """List instances with status, image, and deployment info (auto-discovers if no ports given)."""
    ports = resolve_ports(ports)
    if not ports:
        return

    cfg = Config()

    # Header
    header = (
        f"{'PORT':<6} {'SERVICE':<22} {'CONTAINER':<16} "
        f"{'STATUS':<12} {'IMAGE:TAG':<38} {'DEPLOYED':<20} {'ACTION':<10}"
    )
    print(header)
    print("-" * 130)

    for port in ports:
        service = f"onetime@{port}.service"
        container = f"onetime@{port}"

        # Get systemd status
        result = subprocess.run(
            ["systemctl", "is-active", service],
            capture_output=True,
            text=True,
        )
        status = result.stdout.strip()

        # Get last deployment from database
        deployments = db.get_deployments(cfg.db_path, limit=1, port=port)
        if deployments:
            dep = deployments[0]
            image_tag = f"{dep.image}:{dep.tag}"
            # Format timestamp - strip microseconds and 'T'
            deployed = dep.timestamp.split(".")[0].replace("T", " ")
            action = dep.action
        else:
            image_tag = "unknown"
            deployed = "n/a"
            action = "n/a"

        row = (
            f"{port:<6} {service:<22} {container:<16} "
            f"{status:<12} {image_tag:<38} {deployed:<20} {action:<10}"
        )
        print(row)


@app.command
def deploy(
    ids: Annotated[
        tuple[str, ...],
        cyclopts.Parameter(help="Instance IDs (ports for web, names/numbers for workers)"),
    ],
    delay: Delay = 5,
    instance_type: Annotated[
        InstanceType,
        cyclopts.Parameter(
            name=["--type", "-t"],
            help="Container type: 'web' (default) or 'worker'",
        ),
    ] = InstanceType.WEB,
):
    """Deploy new instance(s) using quadlet and Podman secrets.

    Writes quadlet config and starts systemd service.
    Requires /etc/default/onetimesecret and Podman secrets to be configured.
    Records deployment to timeline for audit and rollback support.

    Examples:
        ots instance deploy 7043 7044       # Deploy web containers on ports
        ots instance deploy --type worker 1 2  # Deploy worker containers 1, 2
        ots instance deploy -t worker billing  # Deploy 'billing' queue worker
    """
    cfg = Config()
    cfg.validate()

    # Resolve image/tag (handles CURRENT/ROLLBACK aliases)
    image, tag = cfg.resolve_image_tag()
    print(f"Image: {image}:{tag}")

    print(f"Reading config from {cfg.config_yaml}")

    if instance_type == InstanceType.WORKER:
        _deploy_workers(cfg, ids, delay, image, tag)
    else:
        # Convert string IDs to int ports for web containers
        ports = tuple(int(p) for p in ids)
        _deploy_web(cfg, ports, delay, image, tag)


def _deploy_web(
    cfg: Config,
    ports: tuple[int, ...],
    delay: int,
    image: str,
    tag: str,
) -> None:
    """Deploy web container instances."""
    assets.update(cfg, create_volume=True)
    print(f"Writing quadlet files to {cfg.template_path.parent}")
    quadlet.write_template(cfg)

    def do_deploy(port: int) -> None:
        print(f"Starting onetime@{port}")
        try:
            systemd.start(f"onetime@{port}")
            # Record successful deployment
            db.record_deployment(
                cfg.db_path,
                image=image,
                tag=tag,
                action="deploy",
                port=port,
                success=True,
            )
        except Exception as e:
            # Record failed deployment
            db.record_deployment(
                cfg.db_path,
                image=image,
                tag=tag,
                action="deploy",
                port=port,
                success=False,
                notes=str(e),
            )
            raise

    for_each(ports, delay, do_deploy, "Deploying")


def _deploy_workers(
    cfg: Config,
    worker_ids: tuple[str, ...],
    delay: int,
    image: str,
    tag: str,
) -> None:
    """Deploy worker container instances."""
    print(f"Writing worker quadlet files to {cfg.worker_template_path.parent}")
    quadlet.write_worker_template(cfg)

    def do_deploy(worker_id: str) -> None:
        unit = f"onetime-worker@{worker_id}"
        print(f"Starting {unit}")
        try:
            systemd.start(unit)
            # Record successful deployment (use worker_id as port field for tracking)
            db.record_deployment(
                cfg.db_path,
                image=image,
                tag=tag,
                action="deploy-worker",
                port=0,  # Workers don't have ports
                success=True,
                notes=f"worker_id={worker_id}",
            )
        except Exception as e:
            # Record failed deployment
            db.record_deployment(
                cfg.db_path,
                image=image,
                tag=tag,
                action="deploy-worker",
                port=0,
                success=False,
                notes=f"worker_id={worker_id}: {e}",
            )
            raise

    for_each_worker(worker_ids, delay, do_deploy, "Deploying")


@app.command
def redeploy(
    ports: OptionalPorts = (),
    delay: Delay = 5,
    force: Annotated[
        bool,
        cyclopts.Parameter(help="Teardown and recreate (stops, redeploys)"),
    ] = False,
):
    """Regenerate quadlet and restart containers.

    Use after editing config.yaml or /etc/default/onetimesecret.
    Use --force to fully teardown and recreate.
    Records deployment to timeline for audit and rollback support.

    Note: Always recreates containers (stop+start) to ensure quadlet changes
    (volume mounts, image, etc.) are applied.
    """
    ports = resolve_ports(ports)
    if not ports:
        return
    cfg = Config()
    cfg.validate()

    # Resolve image/tag (handles CURRENT/ROLLBACK aliases)
    image, tag = cfg.resolve_image_tag()
    print(f"Image: {image}:{tag}")

    print(f"Reading config from {cfg.config_yaml}")
    assets.update(cfg, create_volume=force)
    print(f"Writing quadlet files to {cfg.template_path.parent}")
    quadlet.write_template(cfg)

    def do_redeploy(port: int) -> None:
        unit = f"onetime@{port}"

        if force:
            # Teardown: stop container
            print(f"Stopping {unit}")
            systemd.stop(unit)

        try:
            if force or not systemd.container_exists(unit):
                # Fresh deployment (no existing container)
                print(f"Starting {unit}")
                systemd.start(unit)
            else:
                # Recreate existing container (stop+start to apply quadlet changes)
                print(f"Recreating {unit}")
                systemd.recreate(unit)

            # Record successful redeploy
            db.record_deployment(
                cfg.db_path,
                image=image,
                tag=tag,
                action="redeploy",
                port=port,
                success=True,
                notes="force" if force else None,
            )
        except Exception as e:
            # Record failed redeploy
            db.record_deployment(
                cfg.db_path,
                image=image,
                tag=tag,
                action="redeploy",
                port=port,
                success=False,
                notes=str(e),
            )
            raise

    verb = "Force redeploying" if force else "Redeploying"
    for_each(ports, delay, do_redeploy, verb)


@app.command
def undeploy(ports: OptionalPorts = (), delay: Delay = 5):
    """Stop systemd service for instance(s).

    Stops systemd service. Records action to timeline for audit.
    """
    ports = resolve_ports(ports)
    if not ports:
        return
    cfg = Config()

    # Get current image/tag for recording
    image, tag = cfg.resolve_image_tag()

    def do_undeploy(port: int) -> None:
        print(f"Stopping onetime@{port}")
        try:
            systemd.stop(f"onetime@{port}")
            # Record successful undeploy
            db.record_deployment(
                cfg.db_path,
                image=image,
                tag=tag,
                action="undeploy",
                port=port,
                success=True,
            )
        except Exception as e:
            db.record_deployment(
                cfg.db_path,
                image=image,
                tag=tag,
                action="undeploy",
                port=port,
                success=False,
                notes=str(e),
            )
            raise

    for_each(ports, delay, do_undeploy, "Undeploying")


@app.command
def start(ports: OptionalPorts = ()):
    """Start systemd unit(s) for instance(s).

    Does NOT regenerate quadlet - use 'redeploy' for that.
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

    Does NOT affect quadlet config.
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

    Does NOT regenerate quadlet - use 'redeploy' for that.
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
def env():
    """Show infrastructure environment variables.

    Displays the contents of /etc/default/onetimesecret (shared by all instances).
    Only shows valid KEY=VALUE pairs, sorted alphabetically.
    """
    from pathlib import Path

    env_file = Path("/etc/default/onetimesecret")
    print(f"=== {env_file} ===")
    if env_file.exists():
        lines = env_file.read_text().splitlines()
        # Parse only valid KEY=VALUE lines (key must be valid shell identifier)
        env_vars = {}
        for line in lines:
            line = line.strip()
            # Skip empty lines, comments, and shell commands
            if not line or line.startswith("#"):
                continue
            # Must contain = and start with a valid identifier char
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                # Valid env var: letter/underscore start, alnum/underscore chars
                if key and (key[0].isalpha() or key.startswith("_")):
                    if all(c.isalnum() or c == "_" for c in key):
                        env_vars[key] = value
        for key in sorted(env_vars.keys()):
            print(f"{key}={env_vars[key]}")
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

    When no ports specified, iterates through all running instances sequentially.
    Uses $SHELL environment variable or /bin/sh as fallback.
    """
    import os

    ports = resolve_ports(ports, running_only=True)
    if not ports:
        return

    shell = command or os.environ.get("SHELL", "/bin/sh")

    for port in ports:
        container = f"onetime@{port}"
        print(f"=== Entering {container} ===")
        # Interactive exec requires subprocess.run with no capture
        subprocess.run(["podman", "exec", "-it", container, shell])
        print()
