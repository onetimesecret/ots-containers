# src/ots_containers/commands/common.py
"""Shared CLI annotations for consistency across commands.

All common flags use long+short forms for consistency:
  --quiet, -q
  --dry-run, -n
  --yes, -y
  --follow, -f
  --lines, -n
  --json, -j
"""

from typing import Annotated

import cyclopts

# Output control
Quiet = Annotated[
    bool,
    cyclopts.Parameter(
        name=["--quiet", "-q"],
        help="Suppress output",
    ),
]

DryRun = Annotated[
    bool,
    cyclopts.Parameter(
        name=["--dry-run", "-n"],
        help="Show what would be done without doing it",
        negative=[],  # Disable --no-dry-run generation
    ),
]


# Confirmation
Yes = Annotated[
    bool,
    cyclopts.Parameter(
        name=["--yes", "-y"],
        help="Skip confirmation prompts",
    ),
]


# Log viewing
Follow = Annotated[
    bool,
    cyclopts.Parameter(
        name=["--follow", "-f"],
        help="Follow log output",
    ),
]

Lines = Annotated[
    int,
    cyclopts.Parameter(
        name=["--lines", "-n"],
        help="Number of lines to show",
    ),
]


# JSON output
JsonOutput = Annotated[
    bool,
    cyclopts.Parameter(
        name=["--json", "-j"],
        help="Output as JSON",
    ),
]
