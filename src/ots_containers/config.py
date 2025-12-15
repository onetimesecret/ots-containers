# src/ots_containers/config.py

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    """FHS-compliant configuration paths.

    Directory layout:
        /etc/onetimesecret/          - System configuration (config.yaml, .env template)
        /var/opt/onetimesecret/      - Variable runtime data (.env-{port} files)
        /etc/containers/systemd/     - Quadlet unit files
    """

    config_dir: Path = Path("/etc/onetimesecret")
    var_dir: Path = Path("/var/opt/onetimesecret")
    image: str = field(
        default_factory=lambda: os.environ.get("IMAGE", "ghcr.io/onetimesecret/onetimesecret")
    )
    tag: str = field(default_factory=lambda: os.environ.get("TAG", "current"))
    template_path: Path = Path("/etc/containers/systemd/onetime@.container")

    @property
    def image_with_tag(self) -> str:
        return f"{self.image}:{self.tag}"

    @property
    def config_yaml(self) -> Path:
        """Application configuration file."""
        return self.config_dir / "config.yaml"

    @property
    def env_template(self) -> Path:
        """Environment variable template."""
        return self.config_dir / ".env"

    def env_file(self, port: int) -> Path:
        """Per-instance environment file (variable data)."""
        return self.var_dir / f".env-{port}"

    def validate(self) -> None:
        required = [
            self.env_template,
            self.config_yaml,
        ]
        missing = [f for f in required if not f.exists()]
        if missing:
            raise SystemExit(f"Missing required files: {missing}")
