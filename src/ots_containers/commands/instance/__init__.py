# src/ots_containers/commands/instance/__init__.py

"""Instance management commands for OTS containers."""

from .annotations import (
    Delay,
    Identifiers,
    InstanceType,
    SchedulerFlag,
    TypeSelector,
    WebFlag,
    WorkerFlag,
    resolve_instance_type,
)
from .app import (
    app,
    deploy,
    disable,
    enable,
    exec_shell,
    list_instances,
    logs,
    redeploy,
    restart,
    run,
    show_env,
    start,
    status,
    stop,
    undeploy,
)

__all__ = [
    "Delay",
    "Identifiers",
    "InstanceType",
    "SchedulerFlag",
    "TypeSelector",
    "WebFlag",
    "WorkerFlag",
    "app",
    "deploy",
    "disable",
    "enable",
    "exec_shell",
    "list_instances",
    "logs",
    "redeploy",
    "resolve_instance_type",
    "restart",
    "run",
    "show_env",
    "start",
    "status",
    "stop",
    "undeploy",
]
