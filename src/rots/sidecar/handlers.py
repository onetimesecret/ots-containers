# src/rots/sidecar/handlers.py

"""Command handlers for sidecar operations.

Each handler receives a payload dict and returns a response dict.
Handlers use existing rots modules (systemd, podman) for implementation.
"""

from __future__ import annotations

import logging
from typing import Any

from rots import systemd

logger = logging.getLogger(__name__)

# Type alias for handler functions
HandlerResult = dict[str, Any]


def _unit_name(instance_type: str, identifier: str) -> str:
    """Build systemd unit name with .service suffix."""
    return f"{systemd.unit_name(instance_type, identifier)}.service"


def _lifecycle_operation(
    action: str,
    instance_type: str,
    payload: dict[str, Any],
) -> HandlerResult:
    """Generic lifecycle operation (start/stop/restart).

    Args:
        action: One of "start", "stop", "restart"
        instance_type: One of "web", "worker", "scheduler"
        payload: Must contain "identifier" (port or instance ID)

    Returns:
        {"status": "ok"} or {"status": "error", "error": "..."}
    """
    identifier = payload.get("identifier")
    if not identifier:
        return {"status": "error", "error": "Missing 'identifier' in payload"}

    unit = _unit_name(instance_type, str(identifier))
    logger.info("Executing %s on %s", action, unit)

    try:
        if action == "start":
            systemd.start(unit)
        elif action == "stop":
            systemd.stop(unit)
        elif action == "restart":
            systemd.restart(unit)
        else:
            return {"status": "error", "error": f"Unknown action: {action}"}

        return {"status": "ok", "unit": unit, "action": action}
    except systemd.SystemctlError as e:
        logger.error("systemctl %s %s failed: %s", action, unit, e.journal)
        return {
            "status": "error",
            "error": f"{action} failed for {unit}",
            "journal": e.journal,
        }
    except Exception as e:
        logger.exception("Unexpected error in %s %s", action, unit)
        return {"status": "error", "error": str(e)}


# --- Web instance handlers ---


def handle_restart_web(payload: dict[str, Any]) -> HandlerResult:
    """Restart a web instance.

    Payload:
        identifier: Port number (e.g., 7043)
    """
    return _lifecycle_operation("restart", "web", payload)


def handle_stop_web(payload: dict[str, Any]) -> HandlerResult:
    """Stop a web instance.

    Payload:
        identifier: Port number (e.g., 7043)
    """
    return _lifecycle_operation("stop", "web", payload)


def handle_start_web(payload: dict[str, Any]) -> HandlerResult:
    """Start a web instance.

    Payload:
        identifier: Port number (e.g., 7043)
    """
    return _lifecycle_operation("start", "web", payload)


# --- Worker instance handlers ---


def handle_restart_worker(payload: dict[str, Any]) -> HandlerResult:
    """Restart a worker instance.

    Payload:
        identifier: Worker ID (e.g., "billing", "email")
    """
    return _lifecycle_operation("restart", "worker", payload)


def handle_stop_worker(payload: dict[str, Any]) -> HandlerResult:
    """Stop a worker instance.

    Payload:
        identifier: Worker ID
    """
    return _lifecycle_operation("stop", "worker", payload)


def handle_start_worker(payload: dict[str, Any]) -> HandlerResult:
    """Start a worker instance.

    Payload:
        identifier: Worker ID
    """
    return _lifecycle_operation("start", "worker", payload)


# --- Scheduler instance handlers ---


def handle_restart_scheduler(payload: dict[str, Any]) -> HandlerResult:
    """Restart the scheduler instance.

    Payload:
        identifier: Scheduler ID (usually "default")
    """
    return _lifecycle_operation("restart", "scheduler", payload)


def handle_stop_scheduler(payload: dict[str, Any]) -> HandlerResult:
    """Stop the scheduler instance.

    Payload:
        identifier: Scheduler ID
    """
    return _lifecycle_operation("stop", "scheduler", payload)


def handle_start_scheduler(payload: dict[str, Any]) -> HandlerResult:
    """Start the scheduler instance.

    Payload:
        identifier: Scheduler ID
    """
    return _lifecycle_operation("start", "scheduler", payload)


# --- Status and health handlers (task 7) ---


def handle_status(payload: dict[str, Any]) -> HandlerResult:
    """Get status of all or specific instances.

    Payload:
        instance_type: Optional, one of "web", "worker", "scheduler"
        identifier: Optional, specific instance to query

    Returns:
        List of instance statuses with health info.
    """
    instance_type = payload.get("instance_type")
    identifier = payload.get("identifier")

    try:
        instances: list[dict[str, Any]] = []

        # Get health map for all containers
        health_map = systemd.get_container_health_map()

        # Determine which types to query
        types_to_query = [instance_type] if instance_type else ["web", "worker", "scheduler"]

        for inst_type in types_to_query:
            # Get appropriate discover function
            if inst_type == "web":
                ids = systemd.discover_web_instances()
                ids = [str(i) for i in ids]  # Convert ports to strings
            elif inst_type == "worker":
                ids = systemd.discover_worker_instances()
            elif inst_type == "scheduler":
                ids = systemd.discover_scheduler_instances()
            else:
                continue

            # Filter by identifier if specified
            if identifier:
                ids = [i for i in ids if str(i) == str(identifier)]

            for inst_id in ids:
                unit = _unit_name(inst_type, str(inst_id))
                is_active = systemd.is_active(unit)
                health_info = health_map.get((inst_type, str(inst_id)), {})

                instances.append(
                    {
                        "type": inst_type,
                        "identifier": inst_id,
                        "unit": unit,
                        "active": is_active,
                        "health": health_info.get("health", "unknown"),
                        "uptime": health_info.get("uptime", ""),
                    }
                )

        return {"status": "ok", "instances": instances}
    except Exception as e:
        logger.exception("Error getting status")
        return {"status": "error", "error": str(e)}


def handle_health(payload: dict[str, Any]) -> HandlerResult:
    """Health check for the sidecar daemon itself.

    Returns basic health info about the sidecar service.
    """
    import os
    import time

    return {
        "status": "ok",
        "health": "healthy",
        "pid": os.getpid(),
        "timestamp": time.time(),
    }


# --- Phased restart handlers (task 6) ---


def handle_phased_restart_web(payload: dict[str, Any]) -> HandlerResult:
    """Phased restart of web instances.

    Restarts instances one at a time with delay between each.

    Payload:
        identifiers: List of port numbers to restart
        delay: Seconds between restarts (default: 5)
    """
    import time

    identifiers = payload.get("identifiers", [])
    delay = payload.get("delay", 5)

    if not identifiers:
        # Discover all web instances
        identifiers = systemd.discover_web_instances()

    if not identifiers:
        return {"status": "ok", "message": "No web instances to restart"}

    results: list[dict[str, Any]] = []

    for i, identifier in enumerate(identifiers):
        if i > 0 and delay > 0:
            time.sleep(delay)

        result = handle_restart_web({"identifier": identifier})
        results.append({"identifier": identifier, **result})

        if result["status"] != "ok":
            # Stop on first failure
            return {
                "status": "partial",
                "message": f"Failed at instance {identifier}",
                "results": results,
            }

    return {"status": "ok", "results": results}


def handle_phased_restart_worker(payload: dict[str, Any]) -> HandlerResult:
    """Phased restart of worker instances.

    Payload:
        identifiers: List of worker IDs to restart
        delay: Seconds between restarts (default: 5)
    """
    import time

    identifiers = payload.get("identifiers", [])
    delay = payload.get("delay", 5)

    if not identifiers:
        identifiers = systemd.discover_worker_instances()

    if not identifiers:
        return {"status": "ok", "message": "No worker instances to restart"}

    results: list[dict[str, Any]] = []

    for i, identifier in enumerate(identifiers):
        if i > 0 and delay > 0:
            time.sleep(delay)

        result = handle_restart_worker({"identifier": identifier})
        results.append({"identifier": identifier, **result})

        if result["status"] != "ok":
            return {
                "status": "partial",
                "message": f"Failed at instance {identifier}",
                "results": results,
            }

    return {"status": "ok", "results": results}


# --- Rolling restart handler (task 8) ---


def handle_rolling_restart(payload: dict[str, Any]) -> HandlerResult:
    """Rolling restart of all instances.

    Restarts workers first, then web instances, with health checks.

    Payload:
        delay: Seconds between restarts (default: 5)
        health_check_timeout: Seconds to wait for health (default: 30)
    """
    import time

    delay = payload.get("delay", 5)
    health_timeout = payload.get("health_check_timeout", 30)

    all_results: dict[str, list[dict[str, Any]]] = {
        "workers": [],
        "schedulers": [],
        "web": [],
    }

    def wait_for_health(instance_type: str, identifier: str) -> bool:
        """Wait for instance to become healthy."""
        unit = _unit_name(instance_type, identifier)
        start = time.time()
        while time.time() - start < health_timeout:
            if systemd.is_active(unit):
                health_map = systemd.get_container_health_map()
                health_info = health_map.get((instance_type, identifier), {})
                if health_info.get("health") == "healthy":
                    return True
            time.sleep(2)
        return False

    # 1. Restart workers first (non-critical)
    worker_ids = systemd.discover_worker_instances()
    for i, wid in enumerate(worker_ids):
        if i > 0:
            time.sleep(delay)
        result = handle_restart_worker({"identifier": wid})
        all_results["workers"].append({"identifier": wid, **result})

    # 2. Restart scheduler
    sched_ids = systemd.discover_scheduler_instances()
    for i, sid in enumerate(sched_ids):
        if i > 0:
            time.sleep(delay)
        result = handle_restart_scheduler({"identifier": sid})
        all_results["schedulers"].append({"identifier": sid, **result})

    # 3. Rolling restart of web instances with health checks
    web_ports = systemd.discover_web_instances()
    for i, port in enumerate(web_ports):
        if i > 0:
            time.sleep(delay)

        result = handle_restart_web({"identifier": port})
        healthy = wait_for_health("web", str(port)) if result["status"] == "ok" else False

        all_results["web"].append(
            {
                "identifier": port,
                **result,
                "healthy_after_restart": healthy,
            }
        )

        if result["status"] != "ok":
            return {
                "status": "partial",
                "message": f"Failed at web instance {port}",
                "results": all_results,
            }

    return {"status": "ok", "results": all_results}


# --- Handler registry ---

HANDLERS: dict[str, Any] = {
    # Lifecycle commands
    "restart.web": handle_restart_web,
    "stop.web": handle_stop_web,
    "start.web": handle_start_web,
    "restart.worker": handle_restart_worker,
    "stop.worker": handle_stop_worker,
    "start.worker": handle_start_worker,
    "restart.scheduler": handle_restart_scheduler,
    "stop.scheduler": handle_stop_scheduler,
    "start.scheduler": handle_start_scheduler,
    # Phased restarts
    "phased_restart.web": handle_phased_restart_web,
    "phased_restart.worker": handle_phased_restart_worker,
    # Status and health
    "status": handle_status,
    "health": handle_health,
    # Rolling restart
    "rolling_restart": handle_rolling_restart,
}


def dispatch(command: str, payload: dict[str, Any]) -> HandlerResult:
    """Dispatch a command to its handler.

    Args:
        command: Command name (e.g., "restart.web")
        payload: Command parameters

    Returns:
        Handler result dict
    """
    handler = HANDLERS.get(command)
    if handler is None:
        return {
            "status": "error",
            "error": f"Unknown command: {command}",
            "available_commands": list(HANDLERS.keys()),
        }

    try:
        return handler(payload)
    except Exception as e:
        logger.exception("Handler %s raised exception", command)
        return {"status": "error", "error": str(e)}
