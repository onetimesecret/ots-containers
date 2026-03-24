# src/rots/_dbus.py

"""D-Bus backend for systemd operations using pystemd.

Provides direct D-Bus access to systemd's Manager and Unit interfaces,
replacing fragile CLI output parsing. Used automatically for local
operations when pystemd is available, with transparent fallback to the
CLI path when it is not.

Requires: pystemd (``pip install pystemd``), libsystemd, systemd 245+.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

logger = logging.getLogger(__name__)

try:
    from pystemd.systemd1 import Manager, Unit

    PYSTEMD_AVAILABLE = True
except ImportError:
    Manager = None  # type: ignore[assignment,misc]
    Unit = None  # type: ignore[assignment,misc]
    PYSTEMD_AVAILABLE = False


class UnitInfo(NamedTuple):
    """Decoded unit information from ListUnitsByPatterns."""

    name: str
    load_state: str
    active_state: str
    sub_state: str


def _decode(value: bytes | str) -> str:
    """Decode pystemd bytes to str."""
    return value.decode() if isinstance(value, bytes) else value


def available() -> bool:
    """Return True if pystemd is importable and the system bus is reachable."""
    if not PYSTEMD_AVAILABLE:
        return False
    try:
        with Manager() as m:
            _decode(m.Manager.Version)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Manager operations
# ---------------------------------------------------------------------------


def list_units_by_pattern(pattern: str) -> list[UnitInfo]:
    """List units matching a glob pattern via ListUnitsByPatterns (systemd 230+).

    Returns a list of :class:`UnitInfo` tuples with decoded string fields.
    """
    with Manager() as m:
        raw = m.Manager.ListUnitsByPatterns([], [pattern.encode()])
    return [
        UnitInfo(
            name=_decode(u[0]),
            load_state=_decode(u[2]),
            active_state=_decode(u[3]),
            sub_state=_decode(u[4]),
        )
        for u in raw
    ]


def reload_manager() -> None:
    """Reload systemd manager configuration (``daemon-reload``)."""
    with Manager() as m:
        m.Manager.Reload()


def start_unit(name: str) -> None:
    """Start a unit (``systemctl start``)."""
    with Manager() as m:
        m.Manager.StartUnit(name.encode(), b"replace")


def stop_unit(name: str) -> None:
    """Stop a unit (``systemctl stop``)."""
    with Manager() as m:
        m.Manager.StopUnit(name.encode(), b"replace")


def restart_unit(name: str) -> None:
    """Restart a unit (``systemctl restart``)."""
    with Manager() as m:
        m.Manager.RestartUnit(name.encode(), b"replace")


def enable_unit_files(names: list[str]) -> None:
    """Enable unit files (``systemctl enable``)."""
    with Manager() as m:
        m.Manager.EnableUnitFiles([n.encode() for n in names], False, True)


def disable_unit_files(names: list[str]) -> None:
    """Disable unit files (``systemctl disable``)."""
    with Manager() as m:
        m.Manager.DisableUnitFiles([n.encode() for n in names], False)


def reset_failed_unit(name: str) -> None:
    """Clear failed state for a unit (``systemctl reset-failed``)."""
    with Manager() as m:
        m.Manager.ResetFailedUnit(name.encode())


# ---------------------------------------------------------------------------
# Unit property queries
# ---------------------------------------------------------------------------


def get_active_state(name: str) -> str:
    """Return ActiveState property (e.g. ``'active'``, ``'inactive'``, ``'failed'``)."""
    with Unit(name.encode(), _autoload=True) as u:
        return _decode(u.Unit.ActiveState)


def get_load_state(name: str) -> str:
    """Return LoadState property (e.g. ``'loaded'``, ``'not-found'``)."""
    with Unit(name.encode(), _autoload=True) as u:
        return _decode(u.Unit.LoadState)


def unit_file_exists(name: str) -> bool:
    """Check whether a unit file exists by querying LoadState != 'not-found'."""
    try:
        return get_load_state(name) != "not-found"
    except Exception:
        return False
