# ots-containers

Service orchestration CLI for [OneTimeSecret](https://github.com/onetimesecret/onetimesecret) infrastructure.

**Dual-purpose management tool:**
- **Container orchestration**: Containerized OTS deployments via Podman Quadlets (systemd integration)
- **Service management**: Native systemd services for dependencies (Valkey, Redis)

## Installation

### With pipx (Recommended)

```bash
pipx install git+https://github.com/onetimesecret/ots-containers.git
```

### With pip

```bash
pip install git+https://github.com/onetimesecret/ots-containers.git
```

### From source

```bash
git clone https://github.com/onetimesecret/ots-containers.git
cd ots-containers
pipx install .
```

### Specific version

```bash
pipx install git+https://github.com/onetimesecret/ots-containers.git@v0.1.0
```

## Usage

```bash
ots-containers --help
ots-containers --version
```

### Viewing running containers

These commands auto-discover running instances - no need to specify ports:

```bash
# Show systemd status for all running instances
ots-containers status

# Show status for specific instance only
ots-containers status 7043

# View logs (last 50 lines by default)
ots-containers logs

# Follow logs in real-time
ots-containers logs -f

# View more log lines
ots-containers logs -n 200

# Show running containers (podman view)
ots-containers ps

# List running instances
ots-containers list
```

### Managing OTS containers

```bash
# Setup new instance on port 7043
ots-containers setup 7043

# Setup multiple instances
ots-containers setup 7043 7044 7045

# Update all running instances
ots-containers update

# Update specific instance(s)
ots-containers update 7043

# Update with custom delay between operations
ots-containers update 7043 7044 --delay 10

# Remove instance (requires explicit port)
ots-containers remove 7043

# Replace instance: remove + setup (requires explicit port)
ots-containers replace 7043

# Update static assets only
ots-containers static
```

### Managing systemd services (Valkey, Redis)

```bash
# Initialize new Valkey instance on port 6379
ots-containers service init valkey 6379

# Initialize Redis instance with custom bind address
ots-containers service init redis 6380 --bind 0.0.0.0

# Start/stop/restart service instances
ots-containers service start valkey 6379
ots-containers service stop redis 6380
ots-containers service restart valkey 6379

# Check service status
ots-containers service status valkey 6379

# View service logs
ots-containers service logs valkey 6379
ots-containers service logs redis 6380 --follow

# Enable/disable at boot
ots-containers service enable valkey 6379
ots-containers service disable redis 6380

# List available service packages
ots-containers service
```

## Environment Variables

Override defaults:

```bash
# Use a specific image tag
TAG=v0.23.0 ots-containers update 7043

# Use a different image
IMAGE=ghcr.io/onetimesecret/onetimesecret TAG=latest ots-containers setup 7044
```

## Prerequisites

- Linux with systemd
- Podman installed and configured
- Python 3.11+

## Server Setup

The tool uses an FHS-compliant directory structure:

### OTS Container Configuration

```
/etc/onetimesecret/           # System configuration (must exist)
├── .env                      # Template env file (PORT gets substituted per instance)
└── config.yaml               # Application configuration

/var/lib/onetimesecret/       # Variable runtime data (created by tool)
├── .env-7043                 # Generated: instance-specific env for port 7043
├── .env-7044                 # Generated: instance-specific env for port 7044
└── ...

/etc/containers/systemd/
└── onetime@.container        # Quadlet template (managed by this tool)
```

### Service Configuration (Valkey/Redis)

Uses package-provided systemd templates with instance-specific configs:

```
/etc/valkey/                  # Valkey system configuration (from package)
├── valkey.conf               # Default config template
└── instances/                # Instance configs (created by tool)
    ├── 6379.conf             # Instance-specific config
    ├── 6379-secrets.conf     # Secrets file (mode 0640)
    └── 6380.conf

/var/lib/valkey/              # Variable runtime data (created by tool)
├── 6379/                     # Instance data directory
│   └── dump.rdb
└── 6380/

/usr/lib/systemd/system/
└── valkey-server@.service    # Template from package (not modified)
```

Similar structure for Redis (`/etc/redis/`, `/var/lib/redis/`).

## How It Works

### Container Management (OTS instances)

1. **Static assets**: Extracts `/app/public` from the container image into a shared Podman volume
2. **Quadlet template**: Writes a systemd unit template to `/etc/containers/systemd/onetime@.container`
3. **Instance env files**: Creates `/var/lib/onetimesecret/.env-{port}` from the template with PORT substituted
4. **systemd**: Starts/restarts `onetime@{port}` service

### Service Management (Valkey, Redis)

1. **Config files**: Copies package defaults to `/etc/{package}/instances/{instance}.conf`
2. **Port configuration**: Updates `port` and `bind` settings in instance config
3. **Secrets**: Optionally creates `/etc/{package}/instances/{instance}-secrets.conf` with restricted permissions
4. **Data directories**: Creates `/var/lib/{package}/{instance}/` with correct ownership
5. **systemd**: Manages `{package}-server@{instance}` services using package-provided templates

## Troubleshooting

```bash
# Check service status (via CLI or systemctl)
ots-containers status
sudo systemctl status onetime@7043

# View logs (via CLI or journalctl)
ots-containers logs -f
sudo journalctl -u onetime@7043 --since '5 minutes ago'

# List all onetime systemd units
systemctl list-units 'onetime@*'

# Verify Quadlet template
cat /etc/containers/systemd/onetime@.container

# Reload systemd after manual changes
sudo systemctl daemon-reload
```

## Development

For an editable install (changes take effect immediately):

```bash
git clone https://github.com/onetimesecret/ots-containers.git /opt/ots-containers
chown -R youruser:youruser /opt/ots-containers
pipx install -e /opt/ots-containers
```

The `-e` flag is important: without it, pipx copies the package into its venv and source changes won't be reflected until you reinstall.

### Running Tests

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install with dev and test dependencies
pip install -e ".[dev,test]"

# Run tests
pytest tests/

# Run with coverage (CI threshold: 70%)
pytest tests/ --cov=ots_containers --cov-report=term-missing --cov-fail-under=70
```

Pre-commit hooks run automatically on `git commit`. Install them with:

```bash
pre-commit install
```

### Running as root

When running as root (e.g., via sudo), the user's PATH doesn't include `~/.local/bin`. Use the full path:

```bash
sudo /home/youruser/.local/bin/ots-containers ps
```

Or create a symlink for convenience:

```bash
sudo ln -s /home/youruser/.local/bin/ots-containers /usr/local/bin/ots-containers
sudo ots-containers ps
```

## License

MIT
