# deployment/>=v0.23/ots-containers/src/ots_containers/assets.py

import subprocess

from .config import Config


def update(cfg: Config, create_volume: bool = True) -> None:
    if create_volume:
        subprocess.run(
            ["podman", "volume", "create", "static_assets"], check=False
        )

    result = subprocess.run(
        ["podman", "volume", "mount", "static_assets"],
        capture_output=True,
        text=True,
        check=True,
    )
    assets_dir = Path(result.stdout.strip())

    container_id = subprocess.run(
        ["podman", "create", cfg.image_with_tag],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    try:
        subprocess.run(
            ["podman", "cp", f"{container_id}:/app/public/.", str(assets_dir)],
            check=True,
        )
        manifest = assets_dir / "web/dist/.vite/manifest.json"
        if manifest.exists():
            print(f"Manifest found: {manifest}")
        else:
            print(f"Warning: manifest not found at {manifest}")
    finally:
        subprocess.run(["podman", "rm", container_id], check=True)
