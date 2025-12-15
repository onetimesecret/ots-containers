# deployment/>=v0.23/ots-containers/src/ots_containers/quadlet.py

from . import systemd
from .config import Config

TEMPLATE = """\
[Unit]
Description=OneTimeSecret Container %i
After=local-fs.target network-online.target
Wants=network-online.target

[Container]
Image={image}
Network=host
EnvironmentFile={base_dir}/.env-%i
Volume={base_dir}/config/config.yaml:/app/etc/config.yaml:ro
Volume=static_assets:/app/public:ro

[Install]
WantedBy=multi-user.target
"""


def write_template(cfg: Config) -> None:
    content = TEMPLATE.format(
        image=cfg.image_with_tag,
        base_dir=cfg.base_dir,
    )
    cfg.template_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.template_path.write_text(content)
    systemd.daemon_reload()
