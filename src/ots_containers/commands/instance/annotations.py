# src/ots_containers/commands/instance/annotations.py
"""Type annotations for instance commands.

Port argument patterns:
- Ports (--ports/-p variadic): Multi-target commands (list, start, stop, etc.)
- Port (--port/-p singular): Single-target commands (run)
- OptionalPorts (--ports/-p variadic): Commands that auto-discover if omitted
"""

from enum import Enum
from typing import Annotated

import cyclopts


class InstanceType(str, Enum):
    """Type of container instance to deploy."""

    WEB = "web"
    WORKER = "worker"


Delay = Annotated[
    int,
    cyclopts.Parameter(
        name=["--delay", "-d"],
        help="Seconds between operations",
    ),
]

# Single port for commands that operate on one instance (e.g., run)
Port = Annotated[
    int,
    cyclopts.Parameter(
        name=["--port", "-p"],
        help="Container port to operate on",
    ),
]

# Multiple ports for commands that operate on multiple instances
Ports = Annotated[
    tuple[int, ...],
    cyclopts.Parameter(
        name=["--ports", "-p"],
        help="Container ports to operate on",
    ),
]

# Optional multiple ports - auto-discovers running instances if omitted
OptionalPorts = Annotated[
    tuple[int, ...],
    cyclopts.Parameter(
        name=["--ports", "-p"],
        help="Container ports (discovers running instances if omitted)",
    ),
]

# Worker instance IDs can be numeric (1, 2, 3) or named (billing, emails)
WorkerIds = Annotated[
    tuple[str, ...],
    cyclopts.Parameter(
        name=["--workers", "-w"],
        help="Worker instance IDs (numeric or queue names like 'billing')",
    ),
]
