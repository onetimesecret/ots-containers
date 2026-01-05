# src/ots_containers/commands/image/app.py
"""Image management commands for OTS containers.

Supports pulling from multiple registries:
  - ghcr.io/onetimesecret/onetimesecret (default)
  - docker.io/onetimesecret/onetimesecret
  - registry.digitalocean.com/<registry>/onetimesecret
  - Any OCI-compliant registry

Maintains CURRENT and ROLLBACK aliases in SQLite database for:
  - Deterministic deployments
  - Consecutive rollback support (history-based, not env-var based)
  - Full audit trail
"""

from typing import Annotated

import cyclopts

from ots_containers import db
from ots_containers.config import DEFAULT_IMAGE, Config
from ots_containers.podman import podman

app = cyclopts.App(
    name=["image", "images"],
    help="Manage container images (pull, aliases, rollback).",
)


@app.command
def pull(
    tag: Annotated[
        str,
        cyclopts.Parameter(
            name=["--tag", "-t"],
            help="Image tag to pull (e.g., v0.23.0, latest)",
        ),
    ],
    image: Annotated[
        str,
        cyclopts.Parameter(
            name=["--image", "-i"],
            help="Full image path (default: ghcr.io/onetimesecret/onetimesecret)",
        ),
    ] = DEFAULT_IMAGE,
    set_as_current: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--current", "-c"],
            help="Set as CURRENT alias after pulling",
        ),
    ] = False,
    private: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--private", "-P"],
            help="Pull from private registry (uses configured OTS_REGISTRY)",
        ),
    ] = False,
    quiet: Annotated[
        bool,
        cyclopts.Parameter(name=["--quiet", "-q"], help="Suppress progress output"),
    ] = False,
):
    """Pull a container image from registry.

    Examples:
        ots image pull --tag v0.23.0
        ots image pull --tag latest --current
        ots image pull --tag v0.23.0 --image docker.io/onetimesecret/onetimesecret
        ots image pull --tag v0.23.0 --private  # Pull from private registry
    """
    cfg = Config()

    # Use private registry if requested
    if private:
        if not cfg.private_image:
            print("Error: --private requires OTS_REGISTRY env var to be set")
            raise SystemExit(1)
        image = cfg.private_image

    full_image = f"{image}:{tag}"

    if not quiet:
        print(f"Pulling {full_image}...")

    try:
        # Use auth file for authenticated registries
        podman.pull(
            full_image,
            authfile=str(cfg.registry_auth_file),
            check=True,
            capture_output=True,
            text=True,
        )
        if not quiet:
            print(f"Successfully pulled {full_image}")
    except Exception as e:
        print(f"Failed to pull {full_image}: {e}")
        db.record_deployment(
            cfg.db_path,
            image=image,
            tag=tag,
            action="pull",
            success=False,
            notes=str(e),
        )
        raise SystemExit(1)

    # Record successful pull
    db.record_deployment(
        cfg.db_path,
        image=image,
        tag=tag,
        action="pull",
        success=True,
    )

    # Set as current if requested
    if set_as_current:
        previous = db.set_current(cfg.db_path, image, tag)
        if not quiet:
            if previous:
                print(f"Set CURRENT to {tag} (previous: {previous})")
            else:
                print(f"Set CURRENT to {tag}")


@app.command(name="list")
def ls(
    all_tags: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--all", "-a"],
            help="Show all images, not just onetimesecret",
        ),
    ] = False,
):
    """List local container images.

    Shows images available locally (already pulled).
    """
    cfg = Config()

    if all_tags:
        result = podman.images(
            format="table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.Created}}",
            capture_output=True,
            text=True,
        )
    else:
        result = podman.images(
            filter="reference=*onetimesecret*",
            format="table {{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.Created}}",
            capture_output=True,
            text=True,
        )

    print("Local images:")
    print(result.stdout)

    # Show current aliases
    aliases = db.get_all_aliases(cfg.db_path)
    if aliases:
        print("\nAliases:")
        for alias in aliases:
            print(f"  {alias.alias}: {alias.image}:{alias.tag} (set {alias.set_at})")


@app.command(name="set-current")
def set_current(
    tag: Annotated[
        str,
        cyclopts.Parameter(help="Tag to set as CURRENT"),
    ],
    image: Annotated[
        str,
        cyclopts.Parameter(
            name=["--image", "-i"],
            help="Full image path",
        ),
    ] = DEFAULT_IMAGE,
):
    """Set the CURRENT image alias.

    The previous CURRENT becomes ROLLBACK automatically.

    Examples:
        ots image set-current v0.23.0
        ots image set-current latest --image docker.io/onetimesecret/onetimesecret
    """
    cfg = Config()

    previous = db.set_current(cfg.db_path, image, tag)

    print(f"CURRENT set to {image}:{tag}")
    if previous:
        print(f"ROLLBACK set to previous: {previous}")
    else:
        print("(No previous CURRENT to roll back to)")


@app.command
def rollback():
    """Roll back to the previous deployment.

    Uses the deployment timeline to find the previous successful deployment,
    NOT environment variables. This ensures consecutive rollbacks work
    correctly by walking back through history.

    The current CURRENT becomes ROLLBACK, and the previous deployment
    becomes the new CURRENT.
    """
    cfg = Config()

    # Show current state
    current = db.get_current_image(cfg.db_path)
    if current:
        print(f"Current: {current[0]}:{current[1]}")
    else:
        print("No CURRENT alias set")
        raise SystemExit(1)

    # Get previous tags from timeline for context
    previous = db.get_previous_tags(cfg.db_path, limit=5)
    if len(previous) < 2:
        print("No previous deployment to roll back to")
        raise SystemExit(1)

    print(f"\nRolling back to: {previous[1][0]}:{previous[1][1]}")
    print(f"  (last deployed: {previous[1][2]})")

    result = db.rollback(cfg.db_path)
    if result:
        image, tag = result
        print("\nRollback complete!")
        print(f"  CURRENT: {image}:{tag}")
        print(f"  ROLLBACK: {current[0]}:{current[1]}")
        print("\nTo apply: ots instance redeploy")
    else:
        print("Rollback failed - no previous deployment found")
        raise SystemExit(1)


@app.command
def history(
    limit: Annotated[
        int,
        cyclopts.Parameter(
            name=["--limit", "-n"],
            help="Number of entries to show",
        ),
    ] = 20,
    port: Annotated[
        int | None,
        cyclopts.Parameter(
            name=["--port", "-p"],
            help="Filter by port",
        ),
    ] = None,
):
    """Show deployment timeline.

    The timeline is an append-only audit trail of all deployment actions.
    """
    cfg = Config()

    deployments = db.get_deployments(cfg.db_path, limit=limit, port=port)

    if not deployments:
        print("No deployments recorded yet.")
        return

    # Show aliases first
    aliases = db.get_all_aliases(cfg.db_path)
    if aliases:
        print("Current aliases:")
        for alias in aliases:
            print(f"  {alias.alias}: {alias.image}:{alias.tag}")
        print()

    # Show deployment history
    if port:
        print(f"Deployment history (port {port}):")
    else:
        print("Deployment history:")
    print("-" * 80)
    print(f"{'ID':>4}  {'Timestamp':<20}  {'Port':>5}  {'Action':<12}  {'Tag':<15}  {'Status'}")
    print("-" * 80)

    for d in deployments:
        port_str = str(d.port) if d.port else "-"
        status = "OK" if d.success else "FAIL"
        # Truncate tag if too long
        tag_display = d.tag[:15] if len(d.tag) <= 15 else d.tag[:12] + "..."
        line = f"{d.id:>4}  {d.timestamp:<20}  {port_str:>5}  {d.action:<12}  {tag_display:<15}"
        print(f"{line}  {status}")

    print("-" * 80)
    print(f"Showing {len(deployments)} of {limit} max entries")


@app.command
def aliases():
    """Show current image aliases (CURRENT, ROLLBACK)."""
    cfg = Config()

    aliases = db.get_all_aliases(cfg.db_path)

    if not aliases:
        print("No aliases configured.")
        print("\nSet an alias with: ots image set-current <tag>")
        return

    print("Image aliases:")
    print("-" * 60)
    for alias in aliases:
        print(f"  {alias.alias}:")
        print(f"    Image: {alias.image}:{alias.tag}")
        print(f"    Set:   {alias.set_at}")
    print("-" * 60)

    # Show what commands would resolve to
    print("\nResolution:")
    current = db.get_current_image(cfg.db_path)
    if current:
        print(f"  TAG=current  -> {current[0]}:{current[1]}")

    rollback_img = db.get_rollback_image(cfg.db_path)
    if rollback_img:
        print(f"  TAG=rollback -> {rollback_img[0]}:{rollback_img[1]}")


# --- Private Registry Commands ---


@app.command
def login(
    registry: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--registry", "-r"],
            help="Registry URL (or set OTS_REGISTRY env var)",
        ),
    ] = None,
    username: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--username", "-u"],
            help="Registry username (or set OTS_REGISTRY_USER env var)",
        ),
    ] = None,
    password: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--password", "-p"],
            help="Registry password (env: OTS_REGISTRY_PASSWORD, or --password-stdin)",
        ),
    ] = None,
    password_stdin: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--password-stdin"],
            help="Read password from stdin",
        ),
    ] = False,
):
    """Authenticate with a container registry.

    Uses HTTP basic auth. Credentials can be provided via:
      - Command line arguments
      - Environment variables: OTS_REGISTRY_USER, OTS_REGISTRY_PASSWORD
      - Interactive prompt (if not provided)

    Examples:
        ots image login --registry registry.example.com
        ots image login --registry registry.example.com --username admin --password-stdin
        OTS_REGISTRY=registry.example.com ots image login
    """
    import getpass
    import os
    import sys

    cfg = Config()

    # Resolve registry from arg or config
    reg = registry or cfg.registry
    if not reg:
        print("Error: Registry URL required. Use --registry or set OTS_REGISTRY env var")
        raise SystemExit(1)

    # Resolve credentials from args, env vars, or prompt
    user = username or os.environ.get("OTS_REGISTRY_USER")
    pw = password or os.environ.get("OTS_REGISTRY_PASSWORD")

    if not user:
        user = input(f"Username for {reg}: ")

    if password_stdin:
        pw = sys.stdin.read().strip()
    elif not pw:
        pw = getpass.getpass(f"Password for {user}@{reg}: ")

    if not user or not pw:
        print("Error: Username and password are required")
        raise SystemExit(1)

    print(f"Logging in to {reg}...")

    try:
        podman.login(
            reg,
            username=user,
            password=pw,
            authfile=str(cfg.registry_auth_file),
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"Login successful: {reg}")
    except Exception as e:
        print(f"Login failed: {e}")
        raise SystemExit(1)


@app.command
def push(
    tag: Annotated[
        str,
        cyclopts.Parameter(
            name=["--tag", "-t"],
            help="Image tag to push",
        ),
    ],
    source_image: Annotated[
        str,
        cyclopts.Parameter(
            name=["--source", "-s"],
            help="Source image to push (default: ghcr.io/onetimesecret/onetimesecret)",
        ),
    ] = DEFAULT_IMAGE,
    registry: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--registry", "-r"],
            help="Target registry URL (or set OTS_REGISTRY env var)",
        ),
    ] = None,
    quiet: Annotated[
        bool,
        cyclopts.Parameter(name=["--quiet", "-q"], help="Suppress progress output"),
    ] = False,
):
    """Push an image to a private registry.

    Tags the source image for the target registry and pushes it.
    Requires prior authentication via 'ots image login'.

    Examples:
        ots image push --tag v0.23.0 --registry registry.example.com
        ots image push --tag latest --source docker.io/onetimesecret/onetimesecret
        OTS_REGISTRY=registry.example.com ots image push --tag v0.23.0
    """
    cfg = Config()

    # Resolve registry from arg or config
    reg = registry or cfg.registry
    if not reg:
        print("Error: Registry URL required. Use --registry or set OTS_REGISTRY env var")
        raise SystemExit(1)

    source_full = f"{source_image}:{tag}"
    target_full = f"{reg}/onetimesecret:{tag}"

    if not quiet:
        print(f"Tagging {source_full} -> {target_full}")

    # Tag the image for the target registry
    try:
        podman.tag(source_full, target_full, check=True, capture_output=True, text=True)
    except Exception as e:
        print(f"Failed to tag image: {e}")
        raise SystemExit(1)

    if not quiet:
        print(f"Pushing {target_full}...")

    # Push to registry
    try:
        podman.push(
            target_full,
            authfile=str(cfg.registry_auth_file),
            check=True,
            capture_output=True,
            text=True,
        )
        if not quiet:
            print(f"Successfully pushed {target_full}")
    except Exception as e:
        print(f"Failed to push {target_full}: {e}")
        raise SystemExit(1)

    # Record the push action
    db.record_deployment(
        cfg.db_path,
        image=f"{reg}/onetimesecret",
        tag=tag,
        action="push",
        success=True,
    )


@app.command
def logout(
    registry: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--registry", "-r"],
            help="Registry URL (or set OTS_REGISTRY env var)",
        ),
    ] = None,
):
    """Remove authentication for a container registry.

    Examples:
        ots image logout --registry registry.example.com
        OTS_REGISTRY=registry.example.com ots image logout
    """
    cfg = Config()

    # Resolve registry from arg or config
    reg = registry or cfg.registry
    if not reg:
        print("Error: Registry URL required. Use --registry or set OTS_REGISTRY env var")
        raise SystemExit(1)

    print(f"Logging out from {reg}...")

    try:
        podman.logout(
            reg,
            authfile=str(cfg.registry_auth_file),
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"Logged out from {reg}")
    except Exception as e:
        print(f"Logout failed: {e}")
