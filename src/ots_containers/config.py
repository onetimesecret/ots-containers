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
