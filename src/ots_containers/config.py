# src/ots_containers/config.py

import os
from dataclasses import dataclass, field
from pathlib import Path

# Default image registry
DEFAULT_IMAGE = "ghcr.io/onetimesecret/onetimesecret"
DEFAULT_TAG = "current"


@dataclass
class Config:
    """FHS-compliant configuration paths.

    Directory layout:
        /etc/onetimesecret/          - System configuration (config.yaml, .env template)
        /var/lib/onetimesecret/      - Variable runtime data (.env-{port} files, deployments.db)
        /etc/containers/systemd/     - Quadlet unit files
    """

    config_dir: Path = Path("/etc/onetimesecret")
    var_dir: Path = Path("/var/lib/onetimesecret")
    image: str = field(default_factory=lambda: os.environ.get("IMAGE", DEFAULT_IMAGE))
    tag: str = field(default_factory=lambda: os.environ.get("TAG", DEFAULT_TAG))
    template_path: Path = Path("/etc/containers/systemd/onetime@.container")

    # Proxy (Caddy) configuration - uses HOST environment, not container .env
    proxy_template: Path = Path("/etc/onetimesecret/Caddyfile.template")
    proxy_config: Path = Path("/etc/caddy/Caddyfile")

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

    @property
    def db_path(self) -> Path:
        """SQLite database for deployment tracking."""
        return self.var_dir / "deployments.db"

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

    def resolve_image_tag(self) -> tuple[str, str]:
        """Resolve image and tag, checking database aliases if tag is an alias.

        If tag is 'current' or 'rollback', looks up the actual tag from the
        deployment database. Falls back to the literal tag if no alias found.

        Returns (image, tag) tuple.
        """
        from . import db

        # Check if tag is an alias
        if self.tag.lower() in ("current", "rollback"):
            alias = db.get_alias(self.db_path, self.tag)
            if alias:
                return (alias.image, alias.tag)

        return (self.image, self.tag)

    @property
    def resolved_image_with_tag(self) -> str:
        """Image with tag, resolving aliases like 'current' and 'rollback'."""
        image, tag = self.resolve_image_tag()
        return f"{image}:{tag}"
