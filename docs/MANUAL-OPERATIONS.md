# Manual Operations Reference

This document describes the system changes made by `ots-containers` as equivalent manual shell commands. Use this to understand what the tool does, troubleshoot issues, or perform operations without the tool.

The tool has two operational modes:
1. **Container management**: OTS Podman Quadlets (systemd-managed containers)
2. **Service management**: Native systemd services (Valkey, Redis)

---

# Part 1: Container Management (OTS Quadlets)

## Directory Structure (FHS-Compliant)

The container management commands use this layout:

```
/etc/onetimesecret/           # YAML configs mounted as /app/etc:ro
├── config.yaml               # Application config (must exist)
├── auth.yaml                 # Auth configuration
├── logging.yaml              # Logging configuration
└── billing.yaml              # Billing configuration

/etc/default/onetimesecret    # Infrastructure env vars (shared by all instances)

/var/lib/onetimesecret/       # Variable runtime data
└── deployments.db            # Deployment tracking database

/etc/containers/systemd/
└── onetime@.container        # Generated quadlet template
```

## Podman Secrets

Secrets are managed via Podman secrets (not environment files):

```bash
# Create app secrets (one-time setup, use strong random values)
openssl rand -hex 32 | podman secret create ots_hmac_secret -
openssl rand -hex 32 | podman secret create ots_secret -
openssl rand -hex 32 | podman secret create ots_session_secret -

# Create service integration secrets (from provider dashboards)
echo "sk_live_..." | podman secret create ots_stripe_api_key -
echo "whsec_..." | podman secret create ots_stripe_webhook_secret -
echo "smtp-password" | podman secret create ots_smtp_password -

# List secrets
podman secret ls

# Remove a secret (to recreate)
podman secret rm ots_hmac_secret
```

---

## Systemd Quadlet Template

**Location**: `/etc/containers/systemd/onetime@.container`

The tool generates a systemd quadlet file (a declarative container unit that systemd-podman converts into a service):

```bash
sudo mkdir -p /etc/containers/systemd
sudo tee /etc/containers/systemd/onetime@.container << 'EOF'
[Unit]
Description=OneTimeSecret Container %i
After=local-fs.target network-online.target
Wants=network-online.target

[Service]
Restart=on-failure
RestartSec=5

[Container]
Image=ghcr.io/onetimesecret/onetimesecret:current
Network=host
Environment=PORT=%i
EnvironmentFile=/etc/default/onetimesecret
Secret=ots_hmac_secret,type=env,target=HMAC_SECRET
Secret=ots_secret,type=env,target=SECRET
Secret=ots_session_secret,type=env,target=SESSION_SECRET
Secret=ots_stripe_api_key,type=env,target=STRIPE_API_KEY
Secret=ots_stripe_webhook_secret,type=env,target=STRIPE_WEBHOOK_SIGNING_SECRET
Secret=ots_smtp_password,type=env,target=SMTP_PASSWORD
Volume=/etc/onetimesecret:/app/etc:ro
Volume=static_assets:/app/public:ro
HealthCmd=curl -sf http://localhost:%i/health || exit 1
HealthInterval=30s
HealthRetries=3
HealthStartPeriod=10s

[Install]
WantedBy=multi-user.target
EOF
```

After modifying the quadlet, reload systemd:

```bash
sudo systemctl daemon-reload
```

---

## Infrastructure Environment File

All instances share a single environment file for infrastructure configuration:

**Create /etc/default/onetimesecret**:

```bash
sudo tee /etc/default/onetimesecret << 'EOF'
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgres://localhost:5432/onetimesecret
RABBITMQ_URL=amqp://localhost:5672
LOG_LEVEL=info
EOF
```

---

## Static Assets Volume

The container image's `/app/public` directory is extracted to a shared podman volume so static assets persist and can be served efficiently.

**Create the volume**:

```bash
podman volume create static_assets
```

**Extract assets from the container image**:

```bash
# Mount the volume
MOUNT_PATH=$(podman volume mount static_assets)

# Create temporary container
CONTAINER_ID=$(podman create ghcr.io/onetimesecret/onetimesecret:current)

# Copy assets
podman cp "$CONTAINER_ID:/app/public/." "$MOUNT_PATH"

# Cleanup
podman rm "$CONTAINER_ID"
```

---

## Service Lifecycle Commands

### Start an Instance

```bash
sudo systemctl start onetime@7043
```

### Stop an Instance

```bash
sudo systemctl stop onetime@7043
```

### Restart an Instance

```bash
sudo systemctl restart onetime@7043
```

### Check Status

```bash
sudo systemctl --no-pager -n25 status onetime@7043
```

### View Logs

```bash
# Last 50 lines
sudo journalctl --no-pager -n50 -u onetime@7043

# Follow logs
sudo journalctl -f -u onetime@7043

# Multiple instances
sudo journalctl --no-pager -n50 -u onetime@7043 -u onetime@7044
```

---

## Discovery Commands

### Find Running Instances

```bash
systemctl list-units 'onetime@*' --plain --no-legend
```

### Check if Instance Exists

```bash
systemctl list-unit-files 'onetime@7043' --plain --no-legend
```

### List Running Containers

```bash
podman ps --filter name=onetime \
    --format 'table {{.ID}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}'
```

### Execute Shell in Container

```bash
podman exec -it onetime@7043 /bin/sh
```

---

## Complete Workflows

### Prerequisites (One-Time Setup)

Before deploying instances, ensure Podman secrets and infrastructure config exist:

```bash
# 1. Create app secrets (use strong random values)
openssl rand -hex 32 | podman secret create ots_hmac_secret -
openssl rand -hex 32 | podman secret create ots_secret -
openssl rand -hex 32 | podman secret create ots_session_secret -

# 2. Create service integration secrets (from provider dashboards)
echo "sk_live_..." | podman secret create ots_stripe_api_key -
echo "whsec_..." | podman secret create ots_stripe_webhook_secret -
echo "smtp-password" | podman secret create ots_smtp_password -

# 3. Create infrastructure environment file
sudo tee /etc/default/onetimesecret << 'EOF'
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgres://localhost:5432/onetimesecret
RABBITMQ_URL=amqp://localhost:5672
LOG_LEVEL=info
EOF

# 4. Create config directory with YAML configs
sudo mkdir -p /etc/onetimesecret
# Copy config.yaml, auth.yaml, etc. to /etc/onetimesecret/
```

### Deploy New Instance (port 7043)

This is the full sequence for `ots instance deploy 7043`:

```bash
# 1. Create static assets volume
podman volume create static_assets

# 2. Extract assets from container image
MOUNT_PATH=$(podman volume mount static_assets)
CONTAINER_ID=$(podman create ghcr.io/onetimesecret/onetimesecret:current)
podman cp "$CONTAINER_ID:/app/public/." "$MOUNT_PATH"
podman rm "$CONTAINER_ID"

# 3. Write quadlet template
sudo mkdir -p /etc/containers/systemd
sudo tee /etc/containers/systemd/onetime@.container << 'EOF'
[Unit]
Description=OneTimeSecret Container %i
After=local-fs.target network-online.target
Wants=network-online.target

[Service]
Restart=on-failure
RestartSec=5

[Container]
Image=ghcr.io/onetimesecret/onetimesecret:current
Network=host
Environment=PORT=%i
EnvironmentFile=/etc/default/onetimesecret
Secret=ots_hmac_secret,type=env,target=HMAC_SECRET
Secret=ots_secret,type=env,target=SECRET
Secret=ots_session_secret,type=env,target=SESSION_SECRET
Secret=ots_stripe_api_key,type=env,target=STRIPE_API_KEY
Secret=ots_stripe_webhook_secret,type=env,target=STRIPE_WEBHOOK_SIGNING_SECRET
Secret=ots_smtp_password,type=env,target=SMTP_PASSWORD
Volume=/etc/onetimesecret:/app/etc:ro
Volume=static_assets:/app/public:ro
HealthCmd=curl -sf http://localhost:%i/health || exit 1
HealthInterval=30s
HealthRetries=3
HealthStartPeriod=10s

[Install]
WantedBy=multi-user.target
EOF

# 4. Reload systemd
sudo systemctl daemon-reload

# 5. Start the service
sudo systemctl start onetime@7043
```

### Redeploy Existing Instance

Same as deploy, but use restart instead of start:

```bash
# Steps 1-4 same as deploy
sudo systemctl restart onetime@7043
```

### Force Redeploy (Full Teardown)

This is `ots instance redeploy 7043 --force`:

```bash
# Steps 1-4 same as deploy

# 5. Stop and start fresh
sudo systemctl stop onetime@7043
sudo systemctl start onetime@7043
```

### Undeploy Instance

This is `ots instance undeploy 7043`:

```bash
sudo systemctl stop onetime@7043
```

---

## Image Management

### Pull Latest Image

```bash
podman pull ghcr.io/onetimesecret/onetimesecret:current
```

### List Local Images

```bash
podman image ls --filter reference='*onetimesecret*'
```

### Inspect Image Metadata

```bash
podman image inspect ghcr.io/onetimesecret/onetimesecret:current \
    --format '{{.Created}} {{.Size}}'
```

### Remove Old Images

```bash
# Remove specific image
podman image rm ghcr.io/onetimesecret/onetimesecret:v0.19.0

# Prune unused images
podman image prune -f
```

---

## Reverse Proxy Configuration (Caddy)

The `ots proxy` commands manage Caddy reverse proxy configuration using HOST environment variables.

### Template Rendering with envsubst

**Prerequisite**: Install `gettext` package for `envsubst`:

```bash
# RHEL/Fedora
sudo dnf install gettext

# Debian/Ubuntu
sudo apt install gettext-base
```

**Render template manually**:

```bash
# Set required environment variables
export OTS_HOST=secrets.example.com
export OTS_PORT=7043

# Render template to stdout
envsubst < /etc/onetimesecret/Caddyfile.template

# Render to output file
envsubst < /etc/onetimesecret/Caddyfile.template > /etc/caddy/Caddyfile
```

This is equivalent to `ots proxy render --dry-run` and `ots proxy render`.

### Validate Caddy Configuration

```bash
caddy validate --config /etc/caddy/Caddyfile
```

### Reload Caddy

```bash
sudo systemctl reload caddy
```

This is equivalent to `ots proxy reload`.

### Complete Proxy Workflow

This is `ots proxy render` followed by `ots proxy reload`:

```bash
# 1. Set HOST environment variables
export OTS_HOST=secrets.example.com
export OTS_PORT=7043

# 2. Render template
envsubst < /etc/onetimesecret/Caddyfile.template > /tmp/Caddyfile.new

# 3. Validate before applying
caddy validate --config /tmp/Caddyfile.new

# 4. Apply if valid
sudo mv /tmp/Caddyfile.new /etc/caddy/Caddyfile

# 5. Reload Caddy
sudo systemctl reload caddy
```

---

## Network Configuration

The tool uses **host networking mode**:

- Containers share the host's network namespace
- Each container listens directly on its configured port (7043, 7044, etc.)
- No port mapping or NAT involved
- The `PORT` environment variable tells the application which port to bind

This is functionally equivalent to running the app directly on the host.

---

# Part 2: Service Management (Valkey, Redis)

## Directory Structure

Service management uses package-provided paths with instance-specific configs:

```
/etc/valkey/                          # Package-provided base config
├── valkey.conf                       # Default template
└── instances/                        # Created by ots-containers
    ├── 6379.conf                     # Instance config (copy-on-write from default)
    ├── 6379-secrets.conf             # Secrets file (mode 0640, optional)
    └── 6380.conf

/var/lib/valkey/                      # Runtime data (created by ots-containers)
├── 6379/                             # Instance-specific data directory
│   └── dump.rdb
└── 6380/

/usr/lib/systemd/system/
└── valkey-server@.service            # Package-provided template (not modified)
```

Redis follows the same pattern at `/etc/redis/` and `/var/lib/redis/`.

---

## Service Lifecycle Commands

### Initialize New Instance

**What `ots-containers service init valkey 6379` does:**

```bash
# 1. Create instances directory if needed
sudo mkdir -p /etc/valkey/instances
sudo chown valkey:valkey /etc/valkey/instances
sudo chmod 755 /etc/valkey/instances

# 2. Copy default config to instance config
sudo cp /etc/valkey/valkey.conf /etc/valkey/instances/6379.conf
sudo chown valkey:valkey /etc/valkey/instances/6379.conf
sudo chmod 644 /etc/valkey/instances/6379.conf

# 3. Update port in instance config
sudo sed -i 's/^port .*/port 6379/' /etc/valkey/instances/6379.conf

# 4. Update bind address (default: 127.0.0.1)
sudo sed -i 's/^bind .*/bind 127.0.0.1/' /etc/valkey/instances/6379.conf

# 5. Create data directory
sudo mkdir -p /var/lib/valkey/6379
sudo chown valkey:valkey /var/lib/valkey/6379
sudo chmod 750 /var/lib/valkey/6379

# 6. Update dir path in config
sudo sed -i 's|^dir .*|dir /var/lib/valkey/6379|' /etc/valkey/instances/6379.conf

# 7. (Optional) Create secrets file
sudo tee /etc/valkey/instances/6379-secrets.conf << 'EOF'
# Secrets for valkey instance 6379
requirepass your_password_here
masterauth your_password_here
EOF
sudo chmod 640 /etc/valkey/instances/6379-secrets.conf
sudo chown valkey:valkey /etc/valkey/instances/6379-secrets.conf

# 8. Add include directive to main config
echo "include /etc/valkey/instances/6379-secrets.conf" | \
    sudo tee -a /etc/valkey/instances/6379.conf

# 9. Enable and start service
sudo systemctl enable valkey-server@6379
sudo systemctl start valkey-server@6379
```

### Start/Stop/Restart Service

```bash
# Start
sudo systemctl start valkey-server@6379

# Stop
sudo systemctl stop redis-server@6380

# Restart
sudo systemctl restart valkey-server@6379
```

### Check Status

```bash
# Via systemctl
sudo systemctl status valkey-server@6379

# Check if active
systemctl is-active valkey-server@6379

# Check if enabled at boot
systemctl is-enabled redis-server@6380
```

### View Logs

```bash
# Last 50 lines
sudo journalctl --no-pager -n50 -u valkey-server@6379

# Follow logs
sudo journalctl -f -u redis-server@6380

# Multiple instances
sudo journalctl --no-pager -n50 -u valkey-server@6379 -u redis-server@6380
```

### Enable/Disable at Boot

```bash
# Enable
sudo systemctl enable valkey-server@6379

# Disable
sudo systemctl disable redis-server@6380
```

---

## Service Discovery

### Find Running Service Instances

```bash
# List all running valkey instances
systemctl list-units 'valkey-server@*' --plain --no-legend

# List all redis instances
systemctl list-units 'redis-server@*' --plain --no-legend
```

### Test Service Connectivity

```bash
# Test Valkey
valkey-cli -p 6379 ping

# Test Redis
redis-cli -p 6380 ping

# With authentication
valkey-cli -p 6379 -a your_password ping
```

---

## Configuration Management

### Update Config Value

```bash
# Update a setting in instance config
sudo sed -i 's/^maxmemory .*/maxmemory 2gb/' /etc/valkey/instances/6379.conf

# Restart to apply
sudo systemctl restart valkey-server@6379
```

### View Instance Config

```bash
# Read the instance config
sudo cat /etc/valkey/instances/6379.conf

# Or via the running service
valkey-cli -p 6379 CONFIG GET '*'
```

---

## Summary of Service Files

### Files Created by ots-containers

| Path | Purpose | Permissions |
|------|---------|-------------|
| `/etc/{pkg}/instances/{instance}.conf` | Instance config (copy from default) | 0644, owned by service user |
| `/etc/{pkg}/instances/{instance}-secrets.conf` | Secrets file (optional) | 0640, owned by service user |
| `/var/lib/{pkg}/{instance}/` | Instance data directory | 0750, owned by service user |

### Files Required (from packages)

| Path | Source | Purpose |
|------|--------|---------|
| `/etc/valkey/valkey.conf` | valkey package | Default config template |
| `/etc/redis/redis.conf` | redis package | Default config template |
| `/usr/lib/systemd/system/valkey-server@.service` | valkey package | Systemd template |
| `/usr/lib/systemd/system/redis-server@.service` | redis package | Systemd template |

---

## Summary of Container Files Written

| Path | Purpose | Created By |
|------|---------|------------|
| `/etc/containers/systemd/onetime@.container` | Systemd quadlet template | `ots-containers instance deploy` |
| `/etc/caddy/Caddyfile` | Rendered proxy config | `ots-containers proxy render` |

## Summary of Container Files Required

| Path | Purpose |
|------|---------|
| `/etc/onetimesecret/config.yaml` | Application configuration |
| `/etc/onetimesecret/*.yaml` | Additional YAML configs (auth, logging, billing) |
| `/etc/default/onetimesecret` | Infrastructure environment (REDIS_URL, etc.) |
| `/etc/onetimesecret/Caddyfile.template` | Proxy config template (optional) |

## Summary of Podman Secrets Required

| Secret Name | Target Env Var | Purpose |
|-------------|---------------|---------|
| `ots_hmac_secret` | `HMAC_SECRET` | HMAC signing key |
| `ots_secret` | `SECRET` | Application secret |
| `ots_session_secret` | `SESSION_SECRET` | Session encryption key |
| `ots_stripe_api_key` | `STRIPE_API_KEY` | Stripe API key |
| `ots_stripe_webhook_secret` | `STRIPE_WEBHOOK_SIGNING_SECRET` | Stripe webhook verification |
| `ots_smtp_password` | `SMTP_PASSWORD` | SMTP authentication |

## Summary of Container Commands Used

| Command | Purpose |
|---------|---------|
| `podman volume create` | Create shared assets volume |
| `podman volume mount` | Get volume mount path |
| `podman create` | Create temp container for asset extraction |
| `podman cp` | Copy assets from container to volume |
| `podman rm` | Remove temp container |
| `podman exec -it` | Interactive shell in running container |
| `podman pull` | Pull container image from registry |
| `podman image ls` | List local container images |
| `podman image inspect` | View image metadata |
| `podman image rm` | Remove specific image |
| `podman image prune` | Remove unused images |
| `envsubst` | Substitute environment variables in templates |
| `caddy validate` | Validate Caddyfile syntax |
| `systemctl reload caddy` | Apply Caddy config changes |
| `systemctl daemon-reload` | Reload after quadlet changes |
| `systemctl start/stop/restart` | Service lifecycle |
| `systemctl list-units` | Discover running instances |
| `journalctl` | View container logs |
