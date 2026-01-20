# src/ots_containers/commands/instance/app.py
"""Instance management app and commands for OTS containers."""

import subprocess
from typing import Annotated

import cyclopts

from ots_containers import assets, db, quadlet, systemd
from ots_containers.config import Config

from ..common import DryRun, Follow, JsonOutput, Lines, Quiet, Yes
from ._helpers import (
    for_each,
    for_each_worker,
    format_command,
    resolve_ports,
    resolve_worker_ids,
)
from .annotations import Delay, InstanceType, OptionalPorts, Port, Ports

app = cyclopts.App(
    name=["instance", "instances"],
    help="Manage OTS container instances (quadlet, systemd)",
)


@app.default
def list_instances(
    ports: OptionalPorts = (),
    json_output: JsonOutput = False,
):
    """List instances with status, image, and deployment info.

    Auto-discovers running instances if no ports specified.

    Examples:
        ots instance list
        ots instance list -p 7043 7044
        ots instance list --json
    """
    ports = resolve_ports(ports)
    if not ports:
        return

    cfg = Config()

    if json_output:
        import json

        instances = []
        for port in ports:
            service = f"onetime@{port}.service"
            result = subprocess.run(
                ["systemctl", "is-active", service],
                capture_output=True,
                text=True,
            )
            status = result.stdout.strip()

            deployments = db.get_deployments(cfg.db_path, limit=1, port=port)
            if deployments:
                dep = deployments[0]
                instances.append(
                    {
                        "port": port,
                        "service": service,
                        "container": f"onetime@{port}",
                        "status": status,
                        "image": dep.image,
                        "tag": dep.tag,
                        "deployed": dep.timestamp,
                        "action": dep.action,
                    }
                )
            else:
                instances.append(
                    {
                        "port": port,
                        "service": service,
                        "container": f"onetime@{port}",
                        "status": status,
                        "image": None,
                        "tag": None,
                        "deployed": None,
                        "action": None,
                    }
                )
        print(json.dumps(instances, indent=2))
        return

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
def run(
    port: Port,
    detach: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--detach", "-d"],
            help="Run container in background",
        ),
    ] = False,
    rm: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--rm"],
            help="Remove container when it exits",
        ),
    ] = True,
    production: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--production", "-P"],
            help="Include env file, secrets, and volumes (like deploy)",
        ),
    ] = False,
    name: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--name", "-n"],
            help="Container name (default: onetimesecret-{port})",
        ),
    ] = None,
    quiet: Quiet = False,
    tag: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--tag", "-t"],
            help="Image tag to run (default: from TAG env or 'current' alias)",
        ),
    ] = None,
    remote: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--remote", "-r"],
            help="Pull from registry instead of using local image",
        ),
    ] = False,
):
    """Run a container directly with podman (no systemd).

    By default uses local images (from 'ots image build').
    If .env exists in current directory, it will be used.
    Use --remote to pull from registry instead.
    Use --production to include system env file, secrets, and volumes.

    Examples:
        ots instance run -p 7143 --tag plop-2   # local build (default)
        ots instance run -p 7143 -d             # detached
        ots instance run -p 7143 --remote --tag v0.19.0  # from registry
        ots instance run -p 7143 --production   # full production config
    """
    cfg = Config()

    # Resolve image/tag
    # Default: local images (from 'ots image build')
    # --remote: pull from registry (ghcr.io or OTS_REGISTRY)
    if remote:
        if tag:
            image = cfg.image
            resolved_tag = tag
        else:
            image, resolved_tag = cfg.resolve_image_tag()
    else:
        # Local is the default
        image = "onetimesecret"  # localhost/onetimesecret
        resolved_tag = tag or cfg.tag
    full_image = f"{image}:{resolved_tag}"

    # Container name
    container_name = name or f"onetimesecret-{port}"

    # Build podman run command
    cmd = ["podman", "run"]

    if detach:
        cmd.append("-d")
    if rm:
        cmd.append("--rm")

    cmd.extend(["--name", container_name])
    cmd.extend(["-p", f"{port}:{port}"])
    cmd.extend(["-e", f"PORT={port}"])

    # Check for local .env file in current directory
    from pathlib import Path

    local_env = Path.cwd() / ".env"
    if local_env.exists():
        cmd.extend(["--env-file", str(local_env)])

    # Production mode: add env file, secrets, and volumes
    if production:
        from ots_containers.environment_file import get_secrets_from_env_file

        env_file = quadlet.DEFAULT_ENV_FILE

        # Environment file
        if env_file.exists():
            cmd.extend(["--env-file", str(env_file)])

            # Secrets
            secret_specs = get_secrets_from_env_file(env_file)
            for spec in secret_specs:
                cmd.extend(["--secret", f"{spec.secret_name},type=env,target={spec.env_var_name}"])

        # Volumes
        cmd.extend(["-v", f"{cfg.config_dir}:/app/etc:ro"])
        cmd.extend(["-v", "static_assets:/app/public:ro"])

        # Auth file for private registry
        if cfg.registry:
            cmd.extend(["--authfile", str(cfg.registry_auth_file)])

    # Image
    cmd.append(full_image)

    if not quiet:
        print(format_command(cmd))
        print()

    # Run it
    try:
        if detach:
            result = subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"Container started: {result.stdout.strip()[:12]}")
        else:
            # Foreground - let it take over the terminal
            subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to run container: {e}")
        if e.stderr:
            print(e.stderr)
        raise SystemExit(1)
    except KeyboardInterrupt:
        print("\nStopped")


@app.command
def deploy(
    ports: Ports,
    delay: Delay = 5,
    instance_type: Annotated[
        InstanceType,
        cyclopts.Parameter(
            name=["--type", "-t"],
            help="Container type: 'web' (default) or 'worker'",
        ),
    ] = InstanceType.WEB,
    dry_run: DryRun = False,
    quiet: Quiet = False,
):
    """Deploy new instance(s) using quadlet and Podman secrets.

    Writes quadlet config and starts systemd service.
    Requires /etc/default/onetimesecret and Podman secrets to be configured.
    Records deployment to timeline for audit and rollback support.

    Examples:
        ots instance deploy -p 7043 7044       # Deploy web containers on ports
        ots instance deploy --type worker -w 1 2  # Deploy worker containers 1, 2
        ots instance deploy -t worker -w billing  # Deploy 'billing' queue worker
    """
    cfg = Config()
    cfg.validate()

    # Resolve image/tag (handles CURRENT/ROLLBACK aliases)
    image, tag = cfg.resolve_image_tag()
    if not quiet:
        print(f"Image: {image}:{tag}")

    if not quiet:
        print(f"Reading config from {cfg.config_yaml}")

    if dry_run:
        print("[dry-run] Would deploy to ports:", ports)
        return

    if instance_type == InstanceType.WORKER:
        # Convert ports to strings for worker IDs
        worker_ids = tuple(str(p) for p in ports)
        _deploy_workers(cfg, worker_ids, delay, image, tag)
    else:
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
        cyclopts.Parameter(
            name=["--force", "-f"],
            help="Teardown and recreate (stops, redeploys)",
        ),
    ] = False,
    dry_run: DryRun = False,
    quiet: Quiet = False,
):
    """Regenerate quadlet and restart containers.

    Use after editing config.yaml or /etc/default/onetimesecret.
    Use --force to fully teardown and recreate.
    Records deployment to timeline for audit and rollback support.

    Note: Always recreates containers (stop+start) to ensure quadlet changes
    (volume mounts, image, etc.) are applied.

    Examples:
        ots instance redeploy
        ots instance redeploy -p 7043 7044
        ots instance redeploy --force
    """
    ports = resolve_ports(ports)
    if not ports:
        return
    cfg = Config()
    cfg.validate()

    # Resolve image/tag (handles CURRENT/ROLLBACK aliases)
    image, tag = cfg.resolve_image_tag()
    if not quiet:
        print(f"Image: {image}:{tag}")

    if not quiet:
        print(f"Reading config from {cfg.config_yaml}")

    if dry_run:
        verb = "force redeploy" if force else "redeploy"
        print(f"[dry-run] Would {verb} ports:", ports)
        return

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
def undeploy(
    ports: OptionalPorts = (),
    delay: Delay = 5,
    dry_run: DryRun = False,
    yes: Yes = False,
):
    """Stop systemd service for instance(s).

    Stops systemd service. Records action to timeline for audit.

    Examples:
        ots instance undeploy
        ots instance undeploy -p 7043 7044
        ots instance undeploy -y  # Skip confirmation
    """
    ports = resolve_ports(ports)
    if not ports:
        return

    if not yes and not dry_run:
        print(f"This will stop instances: {', '.join(str(p) for p in ports)}")
        response = input("Continue? [y/N] ")
        if response.lower() not in ("y", "yes"):
            print("Aborted")
            return

    if dry_run:
        print("[dry-run] Would undeploy ports:", ports)
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

    Examples:
        ots instance start
        ots instance start -p 7043 7044
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
    Only stops running instances; already-stopped instances are skipped.

    When no ports specified, stops all running web AND worker instances.

    Examples:
        ots instance stop                    # Stop all running instances
        ots instance stop -p 7043 7044       # Stop specific web instances
    """
    # Track if user explicitly specified ports
    explicit_ports = bool(ports)

    ports = resolve_ports(ports, running_only=True)
    for port in ports:
        systemd.stop(f"onetime@{port}")
        print(f"Stopped onetime@{port}")

    # Also stop workers when no specific ports given
    if not explicit_ports:
        worker_ids = resolve_worker_ids((), running_only=True)
        for worker_id in worker_ids:
            unit = f"onetime-worker@{worker_id}"
            systemd.stop(unit)
            print(f"Stopped {unit}")


@app.command
def restart(ports: OptionalPorts = ()):
    """Restart systemd unit(s) for instance(s).

    Does NOT regenerate quadlet - use 'redeploy' for that.
    Only restarts running instances; stopped instances are skipped.

    When no ports specified, restarts all running web AND worker instances.

    Examples:
        ots instance restart                 # Restart all running instances
        ots instance restart -p 7043 7044    # Restart specific web instances
    """
    # Track if user explicitly specified ports
    explicit_ports = bool(ports)

    ports = resolve_ports(ports, running_only=True)
    for port in ports:
        unit = f"onetime@{port}"
        systemd.restart(unit)
        print(f"Restarted {unit}")

    # Also restart workers when no specific ports given
    if not explicit_ports:
        worker_ids = resolve_worker_ids((), running_only=True)
        for worker_id in worker_ids:
            unit = f"onetime-worker@{worker_id}"
            systemd.restart(unit)
            print(f"Restarted {unit}")


@app.command
def enable(ports: OptionalPorts = ()):
    """Enable instance(s) to start at boot.

    Does not start the instance - use 'start' for that.

    Examples:
        ots instance enable
        ots instance enable -p 7043 7044
    """
    ports = resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        unit = f"onetime@{port}"
        try:
            subprocess.run(
                ["systemctl", "enable", unit],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"Enabled {unit}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to enable {unit}: {e.stderr}")


@app.command
def disable(
    ports: OptionalPorts = (),
    yes: Yes = False,
):
    """Disable instance(s) from starting at boot.

    Does not stop the instance - use 'stop' for that.

    Examples:
        ots instance disable
        ots instance disable -p 7043 7044 -y
    """
    ports = resolve_ports(ports)
    if not ports:
        return

    if not yes:
        print(f"This will disable boot startup for: {', '.join(str(p) for p in ports)}")
        response = input("Continue? [y/N] ")
        if response.lower() not in ("y", "yes"):
            print("Aborted")
            return

    for port in ports:
        unit = f"onetime@{port}"
        try:
            subprocess.run(
                ["systemctl", "disable", unit],
                check=True,
                capture_output=True,
                text=True,
            )
            print(f"Disabled {unit}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to disable {unit}: {e.stderr}")


@app.command
def status(ports: OptionalPorts = ()):
    """Show systemd status for instance(s).

    Examples:
        ots instance status
        ots instance status -p 7043 7044
    """
    ports = resolve_ports(ports)
    if not ports:
        return
    for port in ports:
        systemd.status(f"onetime@{port}")
        print()


@app.command
def logs(
    ports: OptionalPorts = (),
    lines: Lines = 50,
    follow: Follow = False,
):
    """Show logs for instance(s).

    Examples:
        ots instance logs
        ots instance logs -p 7043 -f
        ots instance logs -n 100
    """
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


@app.command(name="show-env")
def show_env():
    """Show infrastructure environment variables.

    Displays the contents of /etc/default/onetimesecret (shared by all instances).
    Only shows valid KEY=VALUE pairs, sorted alphabetically.

    Examples:
        ots instance show-env
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

    Examples:
        ots instance exec
        ots instance exec -p 7043
        ots instance exec -c "/bin/bash"
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
