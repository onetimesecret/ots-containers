# src/ots_containers/assets.py

from pathlib import Path

from .config import Config
from .podman import podman


def update(cfg: Config, create_volume: bool = True) -> None:
    if create_volume:
        podman.volume.create("static_assets", check=False)

    result = podman.volume.mount(
        "static_assets", capture_output=True, text=True, check=True
    )
    assets_dir = Path(result.stdout.strip())

    result = podman.create(
        cfg.image_with_tag, capture_output=True, text=True, check=True
    )
    container_id = result.stdout.strip()

    try:
        podman.cp(f"{container_id}:/app/public/.", str(assets_dir), check=True)
        manifest = assets_dir / "web/dist/.vite/manifest.json"
        if manifest.exists():
            print(f"Manifest found: {manifest}")
        else:
            print(f"Warning: manifest not found at {manifest}")
    finally:
        podman.rm(container_id, check=True)
