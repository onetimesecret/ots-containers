# src/ots_containers/quadlet.py

from . import systemd
from .config import Config

CONTAINER_TEMPLATE = """\
[Unit]
Description=OneTimeSecret Container %i
After=local-fs.target network-online.target
Wants=network-online.target

[Container]
Image={image}
Network=host
Environment=PORT=%i
EnvironmentFile={var_dir}/.env-%i
Volume={config_dir}/config.yaml:/app/etc/config.yaml:ro
Volume=static_assets:/app/public:ro

[Install]
WantedBy=multi-user.target
"""


def write_template(cfg: Config) -> None:
    """Write the container quadlet template."""
    content = CONTAINER_TEMPLATE.format(
        image=cfg.image_with_tag,
        config_dir=cfg.config_dir,
        var_dir=cfg.var_dir,
    )
    cfg.template_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.template_path.write_text(content)
    systemd.daemon_reload()
