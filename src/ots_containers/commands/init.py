# src/ots_containers/commands/init.py
"""Init command for idempotent setup of ots-containers.

Creates required directories and initializes the deployment database.
Safe to run on new installs and existing systems.
"""

import os
import shutil
from pathlib import Path
from typing import Annotated

import cyclopts

from ots_containers import db
from ots_containers.config import Config

app = cyclopts.App(
    name="init",
    help="Initialize ots-containers directories and database.",
)


def _get_owner_group() -> tuple[int, int]:
    """Get appropriate owner UID and GID for files.

    Returns root:root if running as root, otherwise current user.
    """
    if os.geteuid() == 0:
        return (0, 0)  # root:root
    return (os.getuid(), os.getgid())


def _create_directory(path: Path, mode: int = 0o755, quiet: bool = False) -> bool | None:
    """Create directory with mode.

    Returns:
        True if created, False if existed, None if permission denied.
    """
    if path.exists():
        if not quiet:
            print(f"  [ok] {path}")
        return False

    try:
        path.mkdir(parents=True, mode=mode)
        uid, gid = _get_owner_group()
        os.chown(path, uid, gid)
    except PermissionError:
        print(f"  [denied] {path} - permission denied (run with sudo?)")
        return None

    if not quiet:
        print(f"  [created] {path}")
    return True


def _copy_template(src: Path, dest: Path, quiet: bool = False) -> bool | None:
    """Copy template file if destination doesn't exist.

    Returns:
        True if copied, False if existed or source missing, None if permission denied.
    """
    if dest.exists():
        if not quiet:
            print(f"  [ok] {dest}")
        return False

    if not src.exists():
        if not quiet:
            print(f"  [skip] {dest} (source {src} not found)")
        return False

    try:
        shutil.copy2(src, dest)
        uid, gid = _get_owner_group()
        os.chown(dest, uid, gid)
    except PermissionError:
        print(f"  [denied] {dest} - permission denied (run with sudo?)")
        return None

    if not quiet:
        print(f"  [copied] {src} -> {dest}")
    return True


@app.default
def init(
    source_dir: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--source", "-s"],
            help="Source directory containing config.yaml and .env templates to copy",
        ),
    ] = None,
    quiet: Annotated[
        bool,
        cyclopts.Parameter(name=["--quiet", "-q"], help="Suppress output"),
    ] = False,
    check: Annotated[
        bool,
        cyclopts.Parameter(help="Check status only, don't create anything"),
    ] = False,
):
    """Initialize ots-containers directories and database.

    Creates FHS-compliant directory structure:
      /etc/onetimesecret/          - System configuration
      /var/opt/onetimesecret/      - Variable runtime data

    Initializes the SQLite deployment database for tracking.

    This command is idempotent - safe to run multiple times.
    """
    cfg = Config()
    all_ok = True

    if check:
        print("Checking ots-containers setup...")
    else:
        if not quiet:
            print("Initializing ots-containers...")

    # 1. Create config directory and check/copy config files
    if not quiet or check:
        print("\nConfiguration directory:")
    if check:
        if cfg.config_dir.exists():
            print(f"  [ok] {cfg.config_dir}")
            # Check config files within directory
            if cfg.env_template.exists():
                print(f"  [ok] {cfg.env_template}")
            else:
                print(f"  [missing] {cfg.env_template}")
                all_ok = False
            if cfg.config_yaml.exists():
                print(f"  [ok] {cfg.config_yaml}")
            else:
                print(f"  [missing] {cfg.config_yaml}")
                all_ok = False
        else:
            print(f"  [missing] {cfg.config_dir}")
            all_ok = False
    else:
        result = _create_directory(cfg.config_dir, mode=0o755, quiet=quiet)
        if result is None:
            all_ok = False
        else:
            # Directory exists or was created - now handle config files
            if source_dir:
                src = Path(source_dir)
                if _copy_template(src / ".env", cfg.env_template, quiet=quiet) is None:
                    all_ok = False
                if _copy_template(src / "config.yaml", cfg.config_yaml, quiet=quiet) is None:
                    all_ok = False
            elif not quiet:
                # Report status of config files
                if cfg.env_template.exists():
                    print(f"  [ok] {cfg.env_template}")
                else:
                    print(f"  [missing] {cfg.env_template}")
                if cfg.config_yaml.exists():
                    print(f"  [ok] {cfg.config_yaml}")
                else:
                    print(f"  [missing] {cfg.config_yaml}")

    # 2. Create var directory
    if not quiet or check:
        print("\nVariable data directory:")
    if check:
        if cfg.var_dir.exists():
            print(f"  [ok] {cfg.var_dir}")
        else:
            print(f"  [missing] {cfg.var_dir}")
            all_ok = False
    else:
        if _create_directory(cfg.var_dir, mode=0o755, quiet=quiet) is None:
            all_ok = False

    # 3. Create quadlet parent directory
    if not quiet or check:
        print("\nQuadlet directory:")
    quadlet_dir = cfg.template_path.parent
    if check:
        if quadlet_dir.exists():
            print(f"  [ok] {quadlet_dir}")
        else:
            print(f"  [missing] {quadlet_dir}")
            all_ok = False
    else:
        if _create_directory(quadlet_dir, mode=0o755, quiet=quiet) is None:
            all_ok = False

    # 4. Initialize database
    if not quiet or check:
        print("\nDeployment database:")
    if check:
        if cfg.db_path.exists():
            print(f"  [ok] {cfg.db_path}")
        else:
            print(f"  [missing] {cfg.db_path}")
            all_ok = False
    else:
        if cfg.db_path.exists():
            if not quiet:
                print(f"  [ok] {cfg.db_path}")
        else:
            try:
                db.init_db(cfg.db_path)
                uid, gid = _get_owner_group()
                os.chown(cfg.db_path, uid, gid)
                if not quiet:
                    print(f"  [created] {cfg.db_path}")
            except PermissionError:
                print(f"  [denied] {cfg.db_path} - permission denied (run with sudo?)")
                all_ok = False

    # Summary
    if check:
        print()
        if all_ok:
            print("Status: All components present")
        else:
            print("Status: Missing components (run 'ots init' to create)")
        return 0 if all_ok else 1

    if not quiet:
        if all_ok:
            print("\nInitialization complete.")
        else:
            print("\nInitialization incomplete - some operations failed.")
            print("Try running with elevated privileges: sudo ots init")
        print("\nNext steps:")
        if not cfg.config_yaml.exists():
            print(f"  1. Create {cfg.config_yaml}")
        if not cfg.env_template.exists():
            print(f"  2. Create {cfg.env_template}")
        print("  3. Run 'ots image pull --tag <version>' to pull an image")
        print("  4. Run 'ots instance deploy <port>' to start an instance")

    return 0 if all_ok else 1
