# src/ots_containers/db.py
"""SQLite database for deployment timeline and image alias tracking.

The deployment timeline is an append-only audit trail that records all
deployment actions. It does NOT rely on environment variables for determining
previous tags - instead it queries the timeline history.

This ensures:
- Consecutive rollbacks work correctly (history moves forward, not toggling)
- Full audit trail of all deployments
- CURRENT and ROLLBACK aliases are tracked in the database
"""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Deployment:
    """A deployment record from the timeline."""

    id: int
    timestamp: str
    port: int | None
    image: str
    tag: str
    action: str  # deploy, redeploy, undeploy, rollback, set-current
    success: bool
    notes: str | None = None


@dataclass
class ImageAlias:
    """An image alias (CURRENT, ROLLBACK, etc.)."""

    alias: str
    image: str
    tag: str
    set_at: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    port INTEGER,
    image TEXT NOT NULL,
    tag TEXT NOT NULL,
    action TEXT NOT NULL,
    success INTEGER NOT NULL DEFAULT 1,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS image_aliases (
    alias TEXT PRIMARY KEY,
    image TEXT NOT NULL,
    tag TEXT NOT NULL,
    set_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_deployments_timestamp ON deployments(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_deployments_port ON deployments(port);
CREATE INDEX IF NOT EXISTS idx_deployments_tag ON deployments(tag);

-- Service instances (systemd template services like valkey-server@)
CREATE TABLE IF NOT EXISTS service_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    package TEXT NOT NULL,          -- e.g., "valkey", "redis"
    instance TEXT NOT NULL,         -- e.g., "6379" (port-based)
    config_file TEXT NOT NULL,      -- /etc/valkey/instances/6379.conf
    data_dir TEXT NOT NULL,         -- /var/lib/valkey/6379
    port INTEGER,                   -- Actual port number
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    notes TEXT,
    UNIQUE(package, instance)
);

-- Service action audit trail
CREATE TABLE IF NOT EXISTS service_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    package TEXT NOT NULL,
    instance TEXT NOT NULL,
    action TEXT NOT NULL,           -- init, enable, disable, start, stop, restart, secret-set, etc.
    success INTEGER NOT NULL DEFAULT 1,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_service_instances_package ON service_instances(package);
CREATE INDEX IF NOT EXISTS idx_service_actions_timestamp ON service_actions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_service_actions_pkg_inst
    ON service_actions(package, instance);
"""


def init_db(db_path: Path) -> None:
    """Initialize the database with schema. Idempotent."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    """Get a database connection, initializing if needed."""
    if not db_path.exists():
        init_db(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def record_deployment(
    db_path: Path,
    image: str,
    tag: str,
    action: str,
    port: int | None = None,
    success: bool = True,
    notes: str | None = None,
) -> int:
    """Record a deployment action to the timeline. Returns the deployment ID."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO deployments (port, image, tag, action, success, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (port, image, tag, action, 1 if success else 0, notes),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_deployments(
    db_path: Path,
    limit: int = 50,
    port: int | None = None,
) -> list[Deployment]:
    """Get deployment history, optionally filtered by port."""
    with get_connection(db_path) as conn:
        if port is not None:
            rows = conn.execute(
                """
                SELECT id, timestamp, port, image, tag, action, success, notes
                FROM deployments
                WHERE port = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (port, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, timestamp, port, image, tag, action, success, notes
                FROM deployments
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            Deployment(
                id=row["id"],
                timestamp=row["timestamp"],
                port=row["port"],
                image=row["image"],
                tag=row["tag"],
                action=row["action"],
                success=bool(row["success"]),
                notes=row["notes"],
            )
            for row in rows
        ]


def set_alias(db_path: Path, alias: str, image: str, tag: str) -> None:
    """Set an image alias (e.g., CURRENT, ROLLBACK)."""
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO image_aliases (alias, image, tag, set_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(alias) DO UPDATE SET
                image = excluded.image,
                tag = excluded.tag,
                set_at = datetime('now')
            """,
            (alias.upper(), image, tag),
        )
        conn.commit()


def get_alias(db_path: Path, alias: str) -> ImageAlias | None:
    """Get an image alias."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT alias, image, tag, set_at FROM image_aliases WHERE alias = ?",
            (alias.upper(),),
        ).fetchone()
        if row:
            return ImageAlias(
                alias=row["alias"],
                image=row["image"],
                tag=row["tag"],
                set_at=row["set_at"],
            )
        return None


def get_all_aliases(db_path: Path) -> list[ImageAlias]:
    """Get all image aliases."""
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT alias, image, tag, set_at FROM image_aliases ORDER BY alias"
        ).fetchall()
        return [
            ImageAlias(
                alias=row["alias"],
                image=row["image"],
                tag=row["tag"],
                set_at=row["set_at"],
            )
            for row in rows
        ]


def get_current_image(db_path: Path) -> tuple[str, str] | None:
    """Get the current image and tag. Returns (image, tag) or None."""
    alias = get_alias(db_path, "CURRENT")
    if alias:
        return (alias.image, alias.tag)
    return None


def get_rollback_image(db_path: Path) -> tuple[str, str] | None:
    """Get the rollback image and tag. Returns (image, tag) or None."""
    alias = get_alias(db_path, "ROLLBACK")
    if alias:
        return (alias.image, alias.tag)
    return None


def set_current(db_path: Path, image: str, tag: str) -> str | None:
    """Set CURRENT alias, moving previous CURRENT to ROLLBACK.

    Returns the previous CURRENT tag (now ROLLBACK), or None if no previous.
    """
    # Get current before updating
    previous = get_current_image(db_path)
    previous_tag = None

    if previous:
        prev_image, prev_tag = previous
        # Move current to rollback
        set_alias(db_path, "ROLLBACK", prev_image, prev_tag)
        previous_tag = prev_tag

    # Set new current
    set_alias(db_path, "CURRENT", image, tag)

    # Record the action
    record_deployment(
        db_path,
        image=image,
        tag=tag,
        action="set-current",
        notes=f"Previous: {previous_tag}" if previous_tag else "Initial current",
    )

    return previous_tag


def rollback(db_path: Path) -> tuple[str, str] | None:
    """Promote ROLLBACK to CURRENT.

    This queries the deployment timeline to find the previous successful
    deployment, NOT the ROLLBACK alias. This ensures consecutive rollbacks
    work correctly by walking back through history.

    Returns (image, tag) of the new CURRENT, or None if no rollback available.
    """
    # Get the last two distinct successful deployments from timeline
    with get_connection(db_path) as conn:
        # Find distinct image/tag pairs ordered by their most recent deployment
        # Using GROUP BY to get distinct pairs, MAX(id) for ordering (more reliable
        # than timestamp since datetime('now') only has second precision)
        rows = conn.execute(
            """
            SELECT image, tag, MAX(id) as last_id
            FROM deployments
            WHERE success = 1
              AND action IN ('deploy', 'redeploy', 'set-current')
            GROUP BY image, tag
            ORDER BY last_id DESC
            LIMIT 2
            """,
        ).fetchall()

    if len(rows) < 2:
        return None

    # rows[0] is current (most recent), rows[1] is what we want to roll back to
    rollback_image = rows[1]["image"]
    rollback_tag = rows[1]["tag"]

    # Get what we're rolling back from
    current = get_current_image(db_path)
    current_tag = current[1] if current else "unknown"

    # Update aliases - CURRENT becomes ROLLBACK, then new tag becomes CURRENT
    if current:
        set_alias(db_path, "ROLLBACK", current[0], current[1])

    set_alias(db_path, "CURRENT", rollback_image, rollback_tag)

    # Record the rollback action
    record_deployment(
        db_path,
        image=rollback_image,
        tag=rollback_tag,
        action="rollback",
        notes=f"Rolled back from {current_tag}",
    )

    return (rollback_image, rollback_tag)


def get_previous_tags(db_path: Path, limit: int = 10) -> list[tuple[str, str, str]]:
    """Get previous distinct (image, tag, timestamp) from deployment history.

    Used for displaying rollback options. Returns list of (image, tag, timestamp).
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT image, tag, MAX(timestamp) as last_used
            FROM deployments
            WHERE success = 1
              AND action IN ('deploy', 'redeploy', 'set-current')
            GROUP BY image, tag
            ORDER BY last_used DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [(row["image"], row["tag"], row["last_used"]) for row in rows]


# =============================================================================
# Service Instance Management
# =============================================================================


@dataclass
class ServiceInstance:
    """A managed service instance record."""

    id: int
    package: str
    instance: str
    config_file: str
    data_dir: str
    port: int | None
    created_at: str
    updated_at: str
    notes: str | None = None


@dataclass
class ServiceAction:
    """A service action audit record."""

    id: int
    timestamp: str
    package: str
    instance: str
    action: str
    success: bool
    notes: str | None = None


def record_service_instance(
    db_path: Path,
    package: str,
    instance: str,
    config_file: str,
    data_dir: str,
    port: int | None = None,
    notes: str | None = None,
) -> int:
    """Record a new service instance. Returns the instance ID."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO service_instances (package, instance, config_file, data_dir, port, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(package, instance) DO UPDATE SET
                config_file = excluded.config_file,
                data_dir = excluded.data_dir,
                port = excluded.port,
                notes = excluded.notes,
                updated_at = datetime('now')
            """,
            (package, instance, config_file, data_dir, port, notes),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_service_instance(
    db_path: Path,
    package: str,
    instance: str,
) -> ServiceInstance | None:
    """Get a service instance by package and instance name."""
    with get_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, package, instance, config_file, data_dir, port, created_at, updated_at, notes
            FROM service_instances
            WHERE package = ? AND instance = ?
            """,
            (package, instance),
        ).fetchone()
        if row:
            return ServiceInstance(
                id=row["id"],
                package=row["package"],
                instance=row["instance"],
                config_file=row["config_file"],
                data_dir=row["data_dir"],
                port=row["port"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                notes=row["notes"],
            )
        return None


def get_service_instances(
    db_path: Path,
    package: str | None = None,
) -> list[ServiceInstance]:
    """Get all service instances, optionally filtered by package."""
    with get_connection(db_path) as conn:
        if package:
            rows = conn.execute(
                """
                SELECT id, package, instance, config_file, data_dir, port,
                       created_at, updated_at, notes
                FROM service_instances
                WHERE package = ?
                ORDER BY package, instance
                """,
                (package,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, package, instance, config_file, data_dir, port,
                       created_at, updated_at, notes
                FROM service_instances
                ORDER BY package, instance
                """,
            ).fetchall()

        return [
            ServiceInstance(
                id=row["id"],
                package=row["package"],
                instance=row["instance"],
                config_file=row["config_file"],
                data_dir=row["data_dir"],
                port=row["port"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                notes=row["notes"],
            )
            for row in rows
        ]


def delete_service_instance(
    db_path: Path,
    package: str,
    instance: str,
) -> bool:
    """Delete a service instance record. Returns True if deleted."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            "DELETE FROM service_instances WHERE package = ? AND instance = ?",
            (package, instance),
        )
        conn.commit()
        return cursor.rowcount > 0


def record_service_action(
    db_path: Path,
    package: str,
    instance: str,
    action: str,
    success: bool = True,
    notes: str | None = None,
) -> int:
    """Record a service action to the audit trail. Returns the action ID."""
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO service_actions (package, instance, action, success, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (package, instance, action, 1 if success else 0, notes),
        )
        conn.commit()
        return cursor.lastrowid or 0


def get_service_actions(
    db_path: Path,
    package: str | None = None,
    instance: str | None = None,
    limit: int = 50,
) -> list[ServiceAction]:
    """Get service action history, optionally filtered."""
    with get_connection(db_path) as conn:
        if package and instance:
            rows = conn.execute(
                """
                SELECT id, timestamp, package, instance, action, success, notes
                FROM service_actions
                WHERE package = ? AND instance = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (package, instance, limit),
            ).fetchall()
        elif package:
            rows = conn.execute(
                """
                SELECT id, timestamp, package, instance, action, success, notes
                FROM service_actions
                WHERE package = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (package, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, timestamp, package, instance, action, success, notes
                FROM service_actions
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            ServiceAction(
                id=row["id"],
                timestamp=row["timestamp"],
                package=row["package"],
                instance=row["instance"],
                action=row["action"],
                success=bool(row["success"]),
                notes=row["notes"],
            )
            for row in rows
        ]
