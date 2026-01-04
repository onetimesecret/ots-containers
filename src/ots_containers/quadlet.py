# src/ots_containers/quadlet.py

from . import systemd
from .config import Config

CONTAINER_TEMPLATE = """\
# OneTimeSecret Quadlet - Systemd-managed Podman container
# Location: /etc/containers/systemd/onetime@.container
#
# PREREQUISITES (one-time setup):
#
# 1. Create Podman secrets (use strong random values):
#    openssl rand -hex 32 | podman secret create ots_hmac_secret -
#    openssl rand -hex 32 | podman secret create ots_secret -
#    openssl rand -hex 32 | podman secret create ots_session_secret -
#
# 2. Create infrastructure env file /etc/default/onetimesecret:
#    REDIS_URL=redis://localhost:6379
#    DATABASE_URL=postgres://localhost:5432/onetimesecret
#    RABBITMQ_URL=amqp://localhost:5672
#    LOG_LEVEL=info
#
# 3. Place YAML configs in {config_dir}/:
#    config.yaml, auth.yaml, logging.yaml, billing.yaml
#
# OPERATIONS:
#   Start:    systemctl start onetime@7043
#   Stop:     systemctl stop onetime@7043
#   Logs:     journalctl -u onetime@7043 -f
#   Status:   systemctl status onetime@7043
#
# SECRET ROTATION:
#   podman secret rm ots_hmac_secret
#   openssl rand -hex 32 | podman secret create ots_hmac_secret -
#   systemctl restart onetime@7043
#
# TROUBLESHOOTING:
#   List secrets:  podman secret ls
#   Inspect:       podman secret inspect ots_hmac_secret
#   Container:     podman exec -it systemd-onetime@7043 /bin/sh

[Unit]
Description=OneTimeSecret Container %i
After=local-fs.target network-online.target
Wants=network-online.target

[Service]
Restart=on-failure
RestartSec=5

[Container]
Image={image}
Network=host

# Port is derived from instance name: onetime@7043 -> PORT=7043
Environment=PORT=%i

# Infrastructure config (connection strings, log level)
# Edit this file and restart to apply changes
EnvironmentFile=/etc/default/onetimesecret

# Cryptographic secrets via Podman secret store (not on disk)
# These are injected as environment variables at container start
Secret=ots_hmac_secret,type=env,target=HMAC_SECRET
Secret=ots_secret,type=env,target=SECRET
Secret=ots_session_secret,type=env,target=SESSION_SECRET

# Config directory mounted read-only (all YAML configs)
Volume={config_dir}:/app/etc:ro

# Static assets extracted from container image
Volume=static_assets:/app/public:ro

# Health check endpoint
HealthCmd=curl -sf http://localhost:%i/health || exit 1
HealthInterval=30s
HealthRetries=3
HealthStartPeriod=10s

[Install]
WantedBy=multi-user.target
"""


def write_template(cfg: Config) -> None:
    """Write the container quadlet template."""
    content = CONTAINER_TEMPLATE.format(
        image=cfg.resolved_image_with_tag,
        config_dir=cfg.config_dir,
    )
    cfg.template_path.parent.mkdir(parents=True, exist_ok=True)
    cfg.template_path.write_text(content)
    systemd.daemon_reload()
