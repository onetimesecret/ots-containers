# src/ots_containers/systemd.py

import subprocess


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
