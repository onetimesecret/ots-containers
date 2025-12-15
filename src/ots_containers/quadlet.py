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
Network={network_name}.network
PublishPort=%i:3000
EnvironmentFile={base_dir}/.env-%i
Volume={base_dir}/config/config.yaml:/app/etc/config.yaml:ro
Volume=static_assets:/app/public:ro

[Install]
WantedBy=multi-user.target
"""

NETWORK_TEMPLATE = """\
[Network]
Driver=macvlan
InterfaceName={parent_interface}
Subnet={network_subnet}
Gateway={network_gateway}
DNS=9.9.9.9
"""


def write_network(cfg: Config) -> None:
    """Write the Podman network quadlet file."""
    content = NETWORK_TEMPLATE.format(
        parent_interface=cfg.parent_interface,
        network_subnet=cfg.network_subnet,
        network_gateway=cfg.network_gateway,
    )
    cfg.network_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.network_path.write_text(content)


def write_template(cfg: Config) -> None:
    """Write the container quadlet template."""
    content = CONTAINER_TEMPLATE.format(
        image=cfg.image_with_tag,
        base_dir=cfg.base_dir,
        network_name=cfg.network_name,
    )
    cfg.template_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.template_path.write_text(content)


def write_all(cfg: Config) -> None:
    """Write both network and container quadlet files."""
    write_network(cfg)
    write_template(cfg)
    systemd.daemon_reload()
