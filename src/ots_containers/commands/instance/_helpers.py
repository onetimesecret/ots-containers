# src/ots_containers/commands/instance/_helpers.py
"""Internal helper functions for instance commands."""

import shlex
from collections.abc import Callable, Sequence

from ots_containers import systemd


def format_command(cmd: Sequence[str]) -> str:
    """Format command list as a copy-pasteable shell string.

    Arguments containing spaces, special characters, or that are empty
    will be properly quoted using shlex.quote.
    """
    return " ".join(shlex.quote(arg) for arg in cmd)


def resolve_ports(
    ports: tuple[int, ...],
    running_only: bool = False,
) -> tuple[int, ...]:
    """Return provided ports, or discover instances if none given.

    Args:
        ports: Explicitly provided ports. If non-empty, returned as-is.
        running_only: If True, only discover running instances.
                      If False (default), discover all loaded units.
    """
    if ports:
        return ports
    discovered = systemd.discover_instances(running_only=running_only)
    if not discovered:
        msg = "No running instances found" if running_only else "No configured instances found"
        print(msg)
        return ()
    return tuple(discovered)


def resolve_worker_ids(
    worker_ids: tuple[str, ...],
    running_only: bool = False,
) -> tuple[str, ...]:
    """Return provided worker IDs, or discover worker instances if none given.

    Args:
        worker_ids: Explicitly provided worker IDs. If non-empty, returned as-is.
        running_only: If True, only discover running instances.
                      If False (default), discover all loaded units.
    """
    if worker_ids:
        return worker_ids
    discovered = systemd.discover_worker_instances(running_only=running_only)
    if not discovered:
        if running_only:
            print("No running worker instances found")
        else:
            print("No configured worker instances found")
        return ()
    return tuple(discovered)


def for_each(
    ports: tuple[int, ...],
    delay: int,
    action: Callable[[int], None],
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


def for_each_worker(
    worker_ids: tuple[str, ...],
    delay: int,
    action: Callable[[str], None],
    verb: str,
) -> None:
    """Run action for each worker ID with delay between."""
    import time

    total = len(worker_ids)
    for i, worker_id in enumerate(worker_ids, 1):
        print(f"[{i}/{total}] {verb} worker {worker_id}...")
        action(worker_id)
        if i < total and delay > 0:
            print(f"Waiting {delay}s...")
            time.sleep(delay)
    print(f"Processed {total} worker(s)")
