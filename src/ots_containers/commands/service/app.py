# src/ots_containers/commands/service/app.py
"""Service management commands for systemd template services.

Manages systemd template services like valkey-server@ and redis-server@
on Debian 13 systems. Uses package-provided templates rather than custom
unit files.
"""

import subprocess
from typing import Annotated

import cyclopts

from ._helpers import (
    add_secrets_include,
    copy_default_config,
    create_secrets_file,
    ensure_data_dir,
    is_service_active,
    is_service_enabled,
    systemctl,
    update_config_value,
)
from .packages import get_package, list_packages

app = cyclopts.App(
    name="service",
    help="Manage systemd template services (valkey, redis)",
)

# Type aliases for cyclopts annotations
Package = Annotated[str, cyclopts.Parameter(help="Package name (valkey, redis)")]
Instance = Annotated[str, cyclopts.Parameter(help="Instance identifier (usually port)")]
OptInstance = Annotated[str | None, cyclopts.Parameter(help="Instance identifier (optional)")]


@app.default
def _default():
    """Show available packages and help."""
    print("Service management for systemd template services")
    print()
    print("Available packages:")
    for name in list_packages():
        pkg = get_package(name)
        print(f"  {name:10} - {pkg.template}.service")
    print()
    print("Use 'ots service --help' for commands")


@app.command
def init(
    package: Package,
    instance: Instance,
    *,
    port: Annotated[int | None, cyclopts.Parameter(help="Port number")] = None,
    bind: Annotated[str, cyclopts.Parameter(help="Bind address")] = "127.0.0.1",
    no_secrets: Annotated[bool, cyclopts.Parameter(help="Skip secrets file creation")] = False,
    start: Annotated[bool, cyclopts.Parameter(help="Start service after init")] = True,
    enable: Annotated[bool, cyclopts.Parameter(help="Enable service at boot")] = True,
):
    """Initialize a new service instance.

    Creates config files, sets up directories, optionally starts service.
    Config is copy-on-write from package default to /etc/<pkg>/instances/.

    Example:
        ots service init valkey 6379
        ots service init redis 6380 --port 6380 --bind 0.0.0.0
    """
    pkg = get_package(package)
    port_num = port or int(instance)

    print(f"Initializing {pkg.name} instance '{instance}'")
    print(f"  Template: {pkg.template_unit}")
    print(f"  Port: {port_num}")
    print(f"  Bind: {bind}")
    print()

    # Step 1: Copy default config
    print(f"Creating config from {pkg.default_config}...")
    try:
        config_path = copy_default_config(pkg, instance)
        print(f"  Created: {config_path}")
    except FileExistsError:
        print(f"  Config already exists: {pkg.config_file(instance)}")
        config_path = pkg.config_file(instance)
    except FileNotFoundError as e:
        print(f"  ERROR: {e}")
        return

    # Step 2: Update port and bind in config
    print("Updating config values...")
    update_config_value(config_path, pkg.port_config_key, str(port_num), pkg)
    update_config_value(config_path, pkg.bind_config_key, bind, pkg)

    # Step 3: Set data directory
    data_dir = ensure_data_dir(pkg, instance)
    print(f"  Data dir: {data_dir}")
    # Update config to point to instance-specific data dir
    update_config_value(config_path, "dir", str(data_dir), pkg)

    # Step 4: Create secrets file (if applicable)
    if not no_secrets and pkg.secrets:
        print("Creating secrets file...")
        secrets_path = create_secrets_file(pkg, instance)
        if secrets_path:
            print(f"  Created: {secrets_path}")
            add_secrets_include(config_path, secrets_path, pkg)
            print("  Added include directive to config")
    else:
        print("Skipping secrets file (--no-secrets or package has no secrets config)")

    # Step 5: Enable service
    unit = pkg.instance_unit(instance)
    if enable:
        print(f"Enabling {unit}...")
        try:
            systemctl("enable", unit)
            print("  Enabled")
        except subprocess.CalledProcessError as e:
            print(f"  WARNING: Could not enable: {e.stderr}")

    # Step 6: Start service
    if start:
        print(f"Starting {unit}...")
        try:
            systemctl("start", unit)
            print("  Started")
        except subprocess.CalledProcessError as e:
            print(f"  ERROR: Could not start: {e.stderr}")
            return

    print()
    print(f"Instance '{instance}' initialized successfully!")
    print(f"  Config: {config_path}")
    print(f"  Data:   {data_dir}")
    print(f"  Status: ots service status {package} {instance}")


@app.command
def enable(package: Package, instance: Instance):
    """Enable a service instance to start at boot.

    Example:
        ots service enable valkey 6379
    """
    pkg = get_package(package)
    unit = pkg.instance_unit(instance)

    print(f"Enabling {unit}...")
    try:
        systemctl("enable", unit)
        print("Enabled")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {e.stderr}")


@app.command
def disable(package: Package, instance: Instance):
    """Disable a service instance and stop it.

    Example:
        ots service disable valkey 6379
    """
    pkg = get_package(package)
    unit = pkg.instance_unit(instance)

    print(f"Stopping {unit}...")
    try:
        systemctl("stop", unit, check=False)
    except subprocess.CalledProcessError:
        pass

    print(f"Disabling {unit}...")
    try:
        systemctl("disable", unit)
        print("Disabled")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {e.stderr}")


@app.command
def status(package: Package, instance: OptInstance = None):
    """Show status of service instance(s).

    Example:
        ots service status valkey 6379
        ots service status valkey  # Shows all valkey instances
    """
    pkg = get_package(package)

    if instance:
        unit = pkg.instance_unit(instance)
        result = systemctl("status", unit, check=False)
        print(result.stdout)
        if result.stderr:
            print(result.stderr)
    else:
        # Show all instances of this template
        pattern = f"{pkg.template}*"
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", pattern, "--no-pager"],
            capture_output=True,
            text=True,
        )
        print(result.stdout)


@app.command
def start(package: Package, instance: Instance):
    """Start a service instance.

    Example:
        ots service start valkey 6379
    """
    pkg = get_package(package)
    unit = pkg.instance_unit(instance)

    print(f"Starting {unit}...")
    try:
        systemctl("start", unit)
        print("Started")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {e.stderr}")


@app.command
def stop(package: Package, instance: Instance):
    """Stop a service instance.

    Example:
        ots service stop valkey 6379
    """
    pkg = get_package(package)
    unit = pkg.instance_unit(instance)

    print(f"Stopping {unit}...")
    try:
        systemctl("stop", unit)
        print("Stopped")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {e.stderr}")


@app.command
def restart(package: Package, instance: Instance):
    """Restart a service instance.

    Example:
        ots service restart valkey 6379
    """
    pkg = get_package(package)
    unit = pkg.instance_unit(instance)

    print(f"Restarting {unit}...")
    try:
        systemctl("restart", unit)
        print("Restarted")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: {e.stderr}")


@app.command
def logs(
    package: Package,
    instance: Instance,
    *,
    follow: Annotated[bool, cyclopts.Parameter("-f", help="Follow log output")] = False,
    lines: Annotated[int, cyclopts.Parameter("-n", help="Number of lines")] = 50,
):
    """Show logs for a service instance.

    Example:
        ots service logs valkey 6379
        ots service logs valkey 6379 -f
        ots service logs valkey 6379 -n 100
    """
    pkg = get_package(package)
    unit = pkg.instance_unit(instance)

    cmd = ["journalctl", "-u", unit, "-n", str(lines), "--no-pager"]
    if follow:
        cmd.append("-f")

    subprocess.run(cmd)


@app.command(name="list")
def list_instances(package: Package):
    """List all instances of a service package.

    Auto-discovers running and enabled instances via systemctl.

    Example:
        ots service list valkey
    """
    pkg = get_package(package)

    print(f"Instances of {pkg.name} ({pkg.template}):")
    print("-" * 50)

    # Find running/enabled units matching the template
    pattern = f"{pkg.template}*"
    result = subprocess.run(
        ["systemctl", "list-units", "--type=service", "--all", pattern, "--no-pager", "--plain"],
        capture_output=True,
        text=True,
    )

    if result.stdout.strip():
        # Parse output to extract instance names
        for line in result.stdout.splitlines():
            if pkg.template in line:
                parts = line.split()
                if parts:
                    unit_name = parts[0]
                    # Extract instance from unit name
                    # e.g., valkey-server@6379.service -> 6379
                    if "@" in unit_name and ".service" in unit_name:
                        instance = unit_name.split("@")[1].replace(".service", "")
                        active = "active" if is_service_active(unit_name) else "inactive"
                        enabled = "enabled" if is_service_enabled(unit_name) else "disabled"
                        config_exists = pkg.config_file(instance).exists()
                        config_status = "config ok" if config_exists else "no config"
                        print(f"  {instance:10} {active:10} {enabled:10} {config_status}")

    # Also check for config files that might not have running services
    if pkg.instances_dir.exists():
        print()
        print("Config files in instances directory:")
        for conf in pkg.instances_dir.glob("*.conf"):
            instance = conf.stem
            unit = pkg.instance_unit(instance)
            active = "active" if is_service_active(unit) else "inactive"
            print(f"  {conf.name:30} -> {active}")
