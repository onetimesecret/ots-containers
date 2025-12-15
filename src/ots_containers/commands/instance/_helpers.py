# src/ots_containers/commands/instance/_helpers.py
"""Internal helper functions for instance commands."""

from collections.abc import Callable

from ots_containers import systemd
from ots_containers.config import Config


def resolve_ports(ports: tuple[int, ...]) -> tuple[int, ...]:
    """Return provided ports, or discover running instances if none given."""
    if ports:
        return ports
    discovered = systemd.discover_instances()
    if not discovered:
        print("No running instances found")
        return ()
    return tuple(discovered)


def for_each(
    ports: tuple[int, ...],
    delay: int,
    action: Callable[[int], None],
    verb: str,
) -> None:
    """Run action for each port with delay between."""
    import time

    total = len(ports)
    for i, port in enumerate(ports, 1):
        print(f"[{i}/{total}] {verb} container on port {port}...")
        action(port)
        if i < total and delay > 0:
            print(f"Waiting {delay}s...")
            time.sleep(delay)
    print(f"Processed {total} container(s)")


def write_env_file(cfg: Config, port: int) -> None:
    """Write .env-{port} from template with port substitution."""
    template = (cfg.base_dir / "config" / ".env").read_text()
    content = template.replace("${PORT}", str(port)).replace("$PORT", str(port))
    cfg.env_file(port).write_text(content)
