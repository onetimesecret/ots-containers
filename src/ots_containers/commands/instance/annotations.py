# src/ots_containers/commands/instance/annotations.py
"""Type annotations for instance commands."""

from enum import Enum
from typing import Annotated

import cyclopts


class InstanceType(str, Enum):
    """Type of container instance to deploy."""

    WEB = "web"
    WORKER = "worker"


Delay = Annotated[
    int,
    cyclopts.Parameter(name=["--delay", "-d"], help="Seconds between operations"),
]

Ports = Annotated[
    tuple[int, ...],
    cyclopts.Parameter(help="Container ports to operate on"),
]

OptionalPorts = Annotated[
    tuple[int, ...],
    cyclopts.Parameter(help="Container ports (discovers running instances if omitted)"),
]

# Worker instance IDs can be numeric (1, 2, 3) or named (billing, emails)
WorkerIds = Annotated[
    tuple[str, ...],
    cyclopts.Parameter(help="Worker instance IDs (numeric or queue names like 'billing')"),
]
