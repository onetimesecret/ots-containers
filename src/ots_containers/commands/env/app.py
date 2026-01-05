# src/ots_containers/commands/env/app.py
"""Environment file management commands.

Process environment files to extract secrets and prepare for container deployment.
"""

from pathlib import Path
from typing import Annotated

import cyclopts

from ots_containers.environment_file import (
    EnvFile,
    extract_secrets,
    process_env_file,
    secret_exists,
)
from ots_containers.quadlet import DEFAULT_ENV_FILE

app = cyclopts.App(
    name="env",
    help="Manage environment files and secrets.",
)


@app.command
def process(
    env_file: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--file", "-f"],
            help="Path to environment file",
        ),
    ] = None,
    dry_run: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--dry-run", "-n"],
            help="Show what would be done without making changes",
        ),
    ] = False,
    skip_secrets: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--skip-secrets"],
            help="Skip creating podman secrets (only transform env file)",
        ),
    ] = False,
):
    """Process environment file: extract secrets and create podman secrets.

    Reads SECRET_VARIABLE_NAMES from the environment file to identify
    which variables should be stored as podman secrets.

    For each secret variable found with a value:
    1. Creates a podman secret (ots_<varname_lowercase>)
    2. Transforms the env file entry: VARNAME=value -> _VARNAME=ots_varname

    This command is idempotent - safe to run multiple times.

    Example:
        # Process default env file
        ots env process

        # Process specific file with dry-run
        ots env process -f /path/to/envfile -n
    """
    path = env_file or DEFAULT_ENV_FILE

    if not path.exists():
        print(f"Error: Environment file not found: {path}")
        return 1

    print(f"Processing environment file: {path}")
    if dry_run:
        print("(dry-run mode - no changes will be made)")
    print()

    parsed = EnvFile.parse(path)

    if not parsed.secret_variable_names:
        print("Error: No SECRET_VARIABLE_NAMES defined in environment file.")
        print("Add a line like: SECRET_VARIABLE_NAMES=VAR1,VAR2,VAR3")
        return 1

    print(f"Secret variables defined: {', '.join(parsed.secret_variable_names)}")
    print()

    secrets, messages = process_env_file(
        parsed,
        create_secrets=not skip_secrets,
        dry_run=dry_run,
    )

    for msg in messages:
        print(f"  {msg}")

    print()
    if dry_run:
        print("Dry-run complete. Run without --dry-run to apply changes.")
    else:
        print("Processing complete.")

    return 0


@app.command
def show(
    env_file: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--file", "-f"],
            help="Path to environment file",
        ),
    ] = None,
):
    """Show secrets configuration from environment file.

    Displays SECRET_VARIABLE_NAMES and the status of each secret
    (whether it exists in podman, is processed in env file, etc.).
    """
    path = env_file or DEFAULT_ENV_FILE

    if not path.exists():
        print(f"Error: Environment file not found: {path}")
        return 1

    parsed = EnvFile.parse(path)

    if not parsed.secret_variable_names:
        print(f"File: {path}")
        print("Warning: No SECRET_VARIABLE_NAMES defined.")
        print("Add a line like: SECRET_VARIABLE_NAMES=VAR1,VAR2,VAR3")
        return 0

    print(f"File: {path}")
    print(f"SECRET_VARIABLE_NAMES: {parsed.get('SECRET_VARIABLE_NAMES')}")
    print()
    print("Secret Status:")
    print("-" * 60)

    secrets, messages = extract_secrets(parsed)

    for spec in secrets:
        podman_status = "exists" if secret_exists(spec.secret_name) else "missing"

        # Check env file status
        if parsed.has(f"_{spec.env_var_name}"):
            env_status = "processed"
        elif parsed.has(spec.env_var_name):
            value = parsed.get(spec.env_var_name)
            env_status = "has value" if value else "empty"
        else:
            env_status = "not in file"

        print(f"  {spec.env_var_name}:")
        print(f"    podman secret: {spec.secret_name} ({podman_status})")
        print(f"    env file: {env_status}")

    # Show any warnings from extraction
    if messages:
        print()
        for msg in messages:
            print(msg)

    return 0


@app.command
def quadlet_lines(
    env_file: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--file", "-f"],
            help="Path to environment file",
        ),
    ] = None,
):
    """Generate Secret= lines for quadlet template.

    Outputs the Secret= directives that should be included in the
    quadlet container template based on SECRET_VARIABLE_NAMES.
    """
    path = env_file or DEFAULT_ENV_FILE

    if not path.exists():
        print(f"# Error: Environment file not found: {path}")
        return 1

    parsed = EnvFile.parse(path)

    if not parsed.secret_variable_names:
        print("Error: No SECRET_VARIABLE_NAMES defined in environment file.")
        print("Add a line like: SECRET_VARIABLE_NAMES=VAR1,VAR2,VAR3")
        return 1

    secrets, _ = extract_secrets(parsed)

    print("# Secrets via Podman secret store (not on disk)")
    print("# These are injected as environment variables at container start")
    for spec in secrets:
        print(spec.quadlet_line)

    return 0


@app.command
def verify(
    env_file: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--file", "-f"],
            help="Path to environment file",
        ),
    ] = None,
):
    """Verify all required podman secrets exist.

    Checks that each secret defined in SECRET_VARIABLE_NAMES has
    a corresponding podman secret created. Useful before deployment.
    """
    path = env_file or DEFAULT_ENV_FILE

    if not path.exists():
        print(f"Error: Environment file not found: {path}")
        return 1

    parsed = EnvFile.parse(path)

    if not parsed.secret_variable_names:
        print("No SECRET_VARIABLE_NAMES defined - nothing to verify.")
        return 0

    print(f"Verifying secrets for: {path}")
    print()

    secrets, _ = extract_secrets(parsed)
    all_ok = True

    for spec in secrets:
        exists = secret_exists(spec.secret_name)
        status = "OK" if exists else "MISSING"
        symbol = "+" if exists else "-"
        print(f"  [{symbol}] {spec.secret_name} -> {spec.env_var_name}: {status}")
        if not exists:
            all_ok = False

    print()
    if all_ok:
        print("All secrets verified.")
        return 0
    else:
        print("Missing secrets detected. Run 'ots env process' to create them.")
        return 1
