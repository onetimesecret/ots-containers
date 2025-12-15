# src/ots_containers/commands/instance/annotations.py
"""Type annotations for instance commands."""

from typing import Annotated

import cyclopts

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
