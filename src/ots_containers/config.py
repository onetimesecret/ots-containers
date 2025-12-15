# src/ots_containers/config.py

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    base_dir: Path = Path("/opt/onetimesecret")
    image: str = field(
        default_factory=lambda: os.environ.get(
            "IMAGE", "ghcr.io/onetimesecret/onetimesecret"
        )
    )
    tag: str = field(default_factory=lambda: os.environ.get("TAG", "current"))
    template_path: Path = Path("/etc/containers/systemd/onetime@.container")
    network_path: Path = Path("/etc/containers/systemd/onetime.network")
    network_name: str = "onetime"

    # Macvlan network settings - read from environment or use defaults
    # These must match the private network where maindb lives
    parent_interface: str = field(
        default_factory=lambda: os.environ.get("NETWORK_INTERFACE", "eth1")
    )
    network_subnet: str = field(
        default_factory=lambda: os.environ.get("NETWORK_SUBNET", "10.0.0.0/24")
    )
    network_gateway: str = field(
        default_factory=lambda: os.environ.get("NETWORK_GATEWAY", "10.0.0.1")
    )

    @property
    def image_with_tag(self) -> str:
        return f"{self.image}:{self.tag}"

    def env_file(self, port: int) -> Path:
        return self.base_dir / f".env-{port}"

    def validate(self) -> None:
        required = [
            self.base_dir / "config" / ".env",
            self.base_dir / "config" / "config.yaml",
        ]
        missing = [f for f in required if not f.exists()]
        if missing:
            raise SystemExit(f"Missing required files: {missing}")
