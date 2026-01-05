# src/ots_containers/config.py

import os
from dataclasses import dataclass, field
from pathlib import Path

# Default image registry (public)
DEFAULT_IMAGE = "ghcr.io/onetimesecret/onetimesecret"
DEFAULT_TAG = "current"


@dataclass
class Config:
    """FHS-compliant configuration paths.

    Directory layout:
        /etc/onetimesecret/          - YAML configs mounted as /app/etc:ro
        /etc/default/onetimesecret   - Infrastructure env vars (REDIS_URL, etc.)
        /var/lib/onetimesecret/      - Variable runtime data (deployments.db)
        /etc/containers/systemd/     - Quadlet unit files

    Secrets (via podman secret):
        ots_hmac_secret              - HMAC_SECRET env var
        ots_secret                   - SECRET env var
        ots_session_secret           - SESSION_SECRET env var
    """

    config_dir: Path = Path("/etc/onetimesecret")
    var_dir: Path = Path("/var/lib/onetimesecret")
    image: str = field(default_factory=lambda: os.environ.get("IMAGE", DEFAULT_IMAGE))
    tag: str = field(default_factory=lambda: os.environ.get("TAG", DEFAULT_TAG))
    template_path: Path = Path("/etc/containers/systemd/onetime@.container")

    # Private registry configuration (optional, set via OTS_REGISTRY env var)
    registry: str | None = field(default_factory=lambda: os.environ.get("OTS_REGISTRY"))
    registry_auth_file: Path = Path("/etc/containers/auth.json")

    # Proxy (Caddy) configuration - uses HOST environment, not container .env
    proxy_template: Path = Path("/etc/onetimesecret/Caddyfile.template")
    proxy_config: Path = Path("/etc/caddy/Caddyfile")

    @property
    def image_with_tag(self) -> str:
        return f"{self.image}:{self.tag}"

    @property
    def private_image(self) -> str | None:
        """Image path for private registry (requires OTS_REGISTRY env var)."""
        if not self.registry:
            return None
        return f"{self.registry}/onetimesecret"

    @property
    def private_image_with_tag(self) -> str | None:
        """Full image reference for private registry."""
        if not self.private_image:
            return None
        return f"{self.private_image}:{self.tag}"

    @property
    def config_yaml(self) -> Path:
        """Application configuration file."""
        return self.config_dir / "config.yaml"

    @property
    def db_path(self) -> Path:
        """SQLite database for deployment tracking."""
        return self.var_dir / "deployments.db"

    def validate(self) -> None:
        required = [
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
