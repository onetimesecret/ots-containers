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

from pathlib import Path
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


@app.command(name="list-remote")
def list_remote(
    registry: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--registry", "-r"],
            help="Registry URL (or set OTS_REGISTRY env var)",
        ),
    ] = None,
    image: Annotated[
        str,
        cyclopts.Parameter(
            name=["--image", "-i"],
            help="Image name to list tags for",
        ),
    ] = "onetimesecret",
    quiet: Annotated[
        bool,
        cyclopts.Parameter(name=["--quiet", "-q"], help="Suppress command output"),
    ] = False,
):
    """List image tags on a remote registry.

    Uses skopeo to query the registry API. Requires skopeo to be installed.

    Examples:
        ots image list-remote
        ots image list-remote --registry ghcr.io/onetimesecret
        OTS_REGISTRY=registry.example.com ots image list-remote
    """
    import json
    import shutil
    import subprocess

    cfg = Config()

    # Check for skopeo
    if not shutil.which("skopeo"):
        print("Error: skopeo not found. Install with: brew install skopeo (macOS)")
        raise SystemExit(1)

    # Resolve registry
    reg = registry or cfg.registry
    if not reg:
        print("Error: Registry URL required. Use --registry or set OTS_REGISTRY env var")
        raise SystemExit(1)

    # Build skopeo command
    image_ref = f"docker://{reg}/{image}"
    cmd = [
        "skopeo",
        "list-tags",
        "--authfile",
        str(cfg.registry_auth_file),
        image_ref,
    ]

    if not quiet:
        print(f"$ {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        tags = data.get("Tags", [])

        if not quiet:
            print(f"\nTags for {reg}/{image} ({len(tags)} total):")

        # Sort tags (newest-looking first)
        tags_sorted = sorted(tags, reverse=True)
        for tag in tags_sorted:
            print(f"  {tag}")

    except subprocess.CalledProcessError as e:
        print(f"Failed to list tags: {e.stderr}")
        raise SystemExit(1)
    except json.JSONDecodeError as e:
        print(f"Failed to parse response: {e}")
        raise SystemExit(1)


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
            help="Source image to push (default: onetimesecret for local builds)",
        ),
    ] = "onetimesecret",
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
        ots image push --tag v0.23.0
        ots image push --tag v0.23.0 --registry registry.example.com
        ots image push --tag latest --source ghcr.io/onetimesecret/onetimesecret
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


# --- Build Commands ---


def _is_dev_version(version: str) -> bool:
    """Check if version is a development placeholder.

    Returns True for versions that should include git hash:
    - Starts with 0.0.0
    - Ends with -rc0, -dev, -alpha, -beta
    """
    import re

    if re.match(r"^0\.0\.0", version):
        return True
    if re.search(r"-(rc0|dev|alpha|beta)$", version):
        return True
    return False


def _get_git_hash(project_dir: Path) -> str:
    """Get short git commit hash from project directory."""
    import subprocess

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=8", "HEAD"],
            cwd=project_dir,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"Failed to get git hash: {e.stderr}") from e


def _read_package_version(project_dir: Path) -> str:
    """Read version from package.json in project directory."""
    import json

    package_json = project_dir / "package.json"
    if not package_json.exists():
        raise SystemExit(f"package.json not found in {project_dir}")

    try:
        with package_json.open() as f:
            data = json.load(f)
        version = data.get("version")
        if not version:
            raise SystemExit("No 'version' field in package.json")
        return version
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid package.json: {e}") from e


def _determine_build_tag(project_dir: Path, override_tag: str | None) -> str:
    """Determine the build tag based on version and git state.

    Logic:
    1. If override_tag provided, use it as-is
    2. Read version from package.json
    3. If version is a dev placeholder (0.0.0*, -rc0, -dev, -alpha, -beta):
       - Append git hash: v{version}-{hash}
    4. Otherwise use version directly: v{version}
    """
    if override_tag:
        return override_tag

    version = _read_package_version(project_dir)

    if _is_dev_version(version):
        git_hash = _get_git_hash(project_dir)
        return f"v{version}-{git_hash}"
    else:
        return f"v{version}"


def _validate_project_dir(project_dir: Path) -> None:
    """Validate that project directory has required build files."""
    if not project_dir.is_dir():
        raise SystemExit(f"Project directory not found: {project_dir}")

    has_containerfile = (project_dir / "Containerfile").exists()
    has_dockerfile = (project_dir / "Dockerfile").exists()

    if not has_containerfile and not has_dockerfile:
        raise SystemExit(f"No Containerfile or Dockerfile found in {project_dir}")

    if not (project_dir / "package.json").exists():
        raise SystemExit(f"No package.json found in {project_dir}")


@app.command
def build(
    project_dir: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--project-dir", "-d"],
            help="Path to onetimesecret checkout (default: current directory)",
        ),
    ] = None,
    platform: Annotated[
        str,
        cyclopts.Parameter(
            name=["--platform"],
            help="Build platforms, comma-separated",
        ),
    ] = "linux/amd64,linux/arm64",
    push: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--push"],
            help="Push to registry after building",
        ),
    ] = False,
    registry: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--registry", "-r"],
            help="Override registry URL (or OTS_REGISTRY env var)",
        ),
    ] = None,
    tag: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--tag", "-t"],
            help="Override version tag (auto-detected from package.json)",
        ),
    ] = None,
    quiet: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--quiet", "-q"],
            help="Suppress progress output",
        ),
    ] = False,
):
    """Build container image from onetimesecret source.

    Automatically determines version tag from package.json. For development
    versions (0.0.0, -rc0, -dev, -alpha, -beta), appends git hash.

    Examples:
        ots image build --project-dir ~/src/onetimesecret
        ots image build -d . --platform linux/amd64
        ots image build -d . --push --registry registry.example.com
        ots image build -d . --tag v0.23.0-custom
    """
    cfg = Config()

    # Resolve project directory
    proj_dir = Path(project_dir) if project_dir else Path.cwd()
    proj_dir = proj_dir.resolve()

    # Validate project structure
    _validate_project_dir(proj_dir)

    # Determine build tag
    build_tag = _determine_build_tag(proj_dir, tag)

    # Local image name
    local_image = f"onetimesecret:{build_tag}"

    if not quiet:
        print(f"Building {local_image}")
        print(f"  Project: {proj_dir}")
        print(f"  Platform: {platform}")

    # Build the image
    try:
        # Use buildx for multi-platform builds
        podman.buildx.build(
            str(proj_dir),
            platform=platform,
            tag=local_image,
            check=True,
            capture_output=quiet,
            text=True,
        )
        if not quiet:
            print(f"Successfully built {local_image}")
    except Exception as e:
        print(f"Build failed: {e}")
        raise SystemExit(1)

    # Record the build action
    db.record_deployment(
        cfg.db_path,
        image="onetimesecret",
        tag=build_tag,
        action="build",
        success=True,
    )

    # Push if requested
    if push:
        # Resolve registry from arg or config
        reg = registry or cfg.registry
        if not reg:
            print("Error: --push requires --registry or OTS_REGISTRY env var")
            raise SystemExit(1)

        target_image = f"{reg}/onetimesecret:{build_tag}"

        if not quiet:
            print(f"Tagging {local_image} -> {target_image}")

        # Tag for registry
        try:
            podman.tag(
                local_image,
                target_image,
                check=True,
                capture_output=True,
                text=True,
            )
        except Exception as e:
            print(f"Failed to tag image: {e}")
            raise SystemExit(1)

        if not quiet:
            print(f"Pushing {target_image}...")

        # Push to registry
        try:
            podman.push(
                target_image,
                authfile=str(cfg.registry_auth_file),
                check=True,
                capture_output=quiet,
                text=True,
            )
            if not quiet:
                print(f"Successfully pushed {target_image}")
        except Exception as e:
            print(f"Failed to push {target_image}: {e}")
            raise SystemExit(1)

        # Record the push
        db.record_deployment(
            cfg.db_path,
            image=f"{reg}/onetimesecret",
            tag=build_tag,
            action="push",
            success=True,
        )

    # Print summary
    if not quiet:
        print()
        print("Build complete:")
        print(f"  Local:  {local_image}")
        if push:
            print(f"  Remote: {target_image}")
