# src/ots_containers/systemd.py

import re
import subprocess


def discover_instances(running_only: bool = False) -> list[int]:
    """Find onetime@* units and return their ports.

    Args:
        running_only: If True, only return units that are active and running.
                      If False (default), return all loaded units regardless of state.
    """
    result = subprocess.run(
        ["systemctl", "list-units", "onetime@*", "--plain", "--no-legend", "--all"],
        capture_output=True,
        text=True,
    )
    ports = []
    for line in result.stdout.strip().splitlines():
        # Format: onetime@7043.service loaded active running Description...
        # Columns: UNIT LOAD ACTIVE SUB DESCRIPTION
        parts = line.split()
        if len(parts) < 4:
            continue
        unit, load, active, sub = parts[:4]
        # Skip units that aren't loaded
        if load != "loaded":
            continue
        # If running_only, filter to active+running
        if running_only and (active != "active" or sub != "running"):
            continue
        match = re.match(r"onetime@(\d+)\.service", unit)
        if match:
            ports.append(int(match.group(1)))
    return sorted(ports)


def daemon_reload() -> None:
    subprocess.run(["sudo", "systemctl", "daemon-reload"], check=True)


def start(unit: str) -> None:
    subprocess.run(["sudo", "systemctl", "start", unit], check=True)


def stop(unit: str) -> None:
    subprocess.run(["sudo", "systemctl", "stop", unit], check=True)


def restart(unit: str) -> None:
    subprocess.run(["sudo", "systemctl", "restart", unit], check=True)


def status(unit: str, lines: int = 25) -> None:
    subprocess.run(
        ["sudo", "systemctl", "--no-pager", f"-n{lines}", "status", unit],
        check=False,  # status returns non-zero if not running
    )


def unit_exists(unit: str) -> bool:
    """Check if a systemd unit exists (loaded or not)."""
    result = subprocess.run(
        ["systemctl", "list-unit-files", unit, "--plain", "--no-legend"],
        capture_output=True,
        text=True,
    )
    return bool(result.stdout.strip())
