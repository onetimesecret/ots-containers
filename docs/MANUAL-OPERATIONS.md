# Manual Operations Reference

This document describes the system changes made by `ots-containers` as equivalent manual shell commands. Use this to understand what the tool does, troubleshoot issues, or perform operations without the tool.

## Directory Structure (FHS-Compliant)

The tool uses a Filesystem Hierarchy Standard (FHS) compliant layout:

```
/etc/onetimesecret/           # System configuration
├── .env                      # Environment template (must exist)
└── config.yaml               # Application config (must exist)

/var/opt/onetimesecret/       # Variable runtime data
├── .env-7043                 # Generated per-instance
├── .env-7044                 # Generated per-instance
└── ...

/etc/containers/systemd/
└── onetime@.container        # Generated quadlet template
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

[Container]
Image=ghcr.io/onetimesecret/onetimesecret:current
Network=host
Environment=PORT=%i
EnvironmentFile=/var/opt/onetimesecret/.env-%i
Volume=/etc/onetimesecret/config.yaml:/app/etc/config.yaml:ro
Volume=static_assets:/app/public:ro

[Install]
WantedBy=multi-user.target
EOF
```

After modifying the quadlet, reload systemd:

```bash
sudo systemctl daemon-reload
```

---

## Instance Environment Files

Each instance gets its own `.env` file with the port substituted.

**Create .env for port 7043**:

```bash
sudo mkdir -p /var/opt/onetimesecret
sed 's/${PORT}/7043/g; s/$PORT/7043/g' \
    /etc/onetimesecret/.env > /var/opt/onetimesecret/.env-7043
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

# 3. Write quadlet template (if not exists)
sudo mkdir -p /etc/containers/systemd
sudo tee /etc/containers/systemd/onetime@.container << 'EOF'
[Unit]
Description=OneTimeSecret Container %i
After=local-fs.target network-online.target
Wants=network-online.target

[Container]
Image=ghcr.io/onetimesecret/onetimesecret:current
Network=host
Environment=PORT=%i
EnvironmentFile=/var/opt/onetimesecret/.env-%i
Volume=/etc/onetimesecret/config.yaml:/app/etc/config.yaml:ro
Volume=static_assets:/app/public:ro

[Install]
WantedBy=multi-user.target
EOF

# 4. Reload systemd
sudo systemctl daemon-reload

# 5. Create instance .env file
sudo mkdir -p /var/opt/onetimesecret
sed 's/${PORT}/7043/g; s/$PORT/7043/g' \
    /etc/onetimesecret/.env > /var/opt/onetimesecret/.env-7043

# 6. Start the service
sudo systemctl start onetime@7043
```

### Redeploy Existing Instance

Same as deploy, but use restart instead of start:

```bash
# Steps 1-5 same as deploy
sudo systemctl restart onetime@7043
```

### Force Redeploy (Full Teardown)

This is `ots instance redeploy 7043 --force`:

```bash
# Steps 1-4 same as deploy

# 5. Stop and remove existing config
sudo systemctl stop onetime@7043
rm /var/opt/onetimesecret/.env-7043

# 6. Recreate .env and start fresh
sed 's/${PORT}/7043/g; s/$PORT/7043/g' \
    /etc/onetimesecret/.env > /var/opt/onetimesecret/.env-7043
sudo systemctl start onetime@7043
```

### Undeploy Instance

This is `ots instance undeploy 7043`:

```bash
sudo systemctl stop onetime@7043
rm /var/opt/onetimesecret/.env-7043
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

## Summary of Files Written

| Path | Purpose | Created By |
|------|---------|------------|
| `/etc/containers/systemd/onetime@.container` | Systemd quadlet template | `ots instance deploy` |
| `/var/opt/onetimesecret/.env-{port}` | Per-instance environment | `ots instance deploy` |

## Summary of Files Required

| Path | Purpose |
|------|---------|
| `/etc/onetimesecret/.env` | Environment template |
| `/etc/onetimesecret/config.yaml` | Application configuration |

## Summary of Commands Used

| Command | Purpose |
|---------|---------|
| `podman volume create` | Create shared assets volume |
| `podman volume mount` | Get volume mount path |
| `podman create` | Create temp container for asset extraction |
| `podman cp` | Copy assets from container to volume |
| `podman rm` | Remove temp container |
| `podman exec -it` | Interactive shell in running container |
| `systemctl daemon-reload` | Reload after quadlet changes |
| `systemctl start/stop/restart` | Service lifecycle |
| `systemctl list-units` | Discover running instances |
| `journalctl` | View container logs |
