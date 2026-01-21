# src/ots_containers/commands/instance/_helpers.py
"""Internal helper functions for instance commands."""

import shlex
import time
from collections.abc import Callable, Sequence

from ots_containers import systemd

from .annotations import InstanceType


def format_command(cmd: Sequence[str]) -> str:
    """Format command list as a copy-pasteable shell string.

    Arguments containing spaces, special characters, or that are empty
    will be properly quoted using shlex.quote.
    """
    return " ".join(shlex.quote(arg) for arg in cmd)


def resolve_identifiers(
    identifiers: tuple[str, ...],
    instance_type: InstanceType | None,
    running_only: bool = False,
) -> dict[InstanceType, list[str]]:
    """Resolve instance identifiers from explicit args or auto-discovery.

    Args:
        identifiers: Explicitly provided identifiers. If non-empty, requires instance_type.
        instance_type: Required when identifiers provided. If None with no identifiers,
                      discovers all types.
        running_only: If True, only discover running instances.

    Returns:
        Dict mapping InstanceType to list of identifiers (as strings).

    Raises:
        SystemExit: If identifiers provided without instance_type.
    """
    # If identifiers provided, type is required
    if identifiers:
        if instance_type is None:
            raise SystemExit(
                "Instance type required when identifiers are specified. "
                "Use --web, --worker, or --scheduler."
            )
        return {instance_type: list(identifiers)}

    # No identifiers: discover based on type filter
    result: dict[InstanceType, list[str]] = {}

    # If type specified, only discover that type
    if instance_type is not None:
        if instance_type == InstanceType.WEB:
            ports = systemd.discover_web_instances(running_only=running_only)
            if ports:
                result[InstanceType.WEB] = [str(p) for p in ports]
        elif instance_type == InstanceType.WORKER:
            workers = systemd.discover_worker_instances(running_only=running_only)
            if workers:
                result[InstanceType.WORKER] = workers
        elif instance_type == InstanceType.SCHEDULER:
            schedulers = systemd.discover_scheduler_instances(running_only=running_only)
            if schedulers:
                result[InstanceType.SCHEDULER] = schedulers
        return result

    # No type: discover ALL types
    ports = systemd.discover_web_instances(running_only=running_only)
    if ports:
        result[InstanceType.WEB] = [str(p) for p in ports]

    workers = systemd.discover_worker_instances(running_only=running_only)
    if workers:
        result[InstanceType.WORKER] = workers

    schedulers = systemd.discover_scheduler_instances(running_only=running_only)
    if schedulers:
        result[InstanceType.SCHEDULER] = schedulers

    return result


def for_each_instance(
    instances: dict[InstanceType, list[str]],
    delay: int,
    action: Callable[[InstanceType, str], None],
    verb: str,
) -> int:
    """Run action for each instance with delay between.

    Args:
        instances: Dict mapping InstanceType to list of identifiers
        delay: Seconds to wait between operations
        action: Callable taking (instance_type, identifier)
        verb: Present participle for logging (e.g., "Restarting")

    Returns:
        Total number of instances processed.
    """
    # Flatten to list of (type, id) tuples
    items: list[tuple[InstanceType, str]] = []
    for itype, ids in instances.items():
        for id_ in ids:
            items.append((itype, id_))

    total = len(items)
    if total == 0:
        print("No instances found to operate on.")
        return 0

    for i, (itype, id_) in enumerate(items, 1):
        unit = systemd.unit_name(itype.value, id_)
        print(f"[{i}/{total}] {verb} {unit}...")
        action(itype, id_)
        if i < total and delay > 0:
            print(f"Waiting {delay}s...")
            time.sleep(delay)

    print(f"Processed {total} instance(s)")
    return total
