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
    """
    cfg = Config()
    full_image = f"{image}:{tag}"

    if not quiet:
        print(f"Pulling {full_image}...")

    try:
        podman.pull(full_image, check=True, capture_output=True, text=True)
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
