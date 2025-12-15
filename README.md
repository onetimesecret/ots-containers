# ots-containers

Podman Quadlet container management CLI for [OneTimeSecret](https://github.com/onetimesecret/onetimesecret).

Manages containerized OTS instances using systemd Quadlets - the modern way to run Podman containers as services.

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

# Setup new instance on port 7043
ots-containers setup 7043

# Setup multiple instances
ots-containers setup 7043 7044 7045

# Update existing instance(s)
ots-containers update 7043

# Update with custom delay between operations
ots-containers update 7043 7044 --delay 10

# Remove instance
ots-containers remove 7043

# Replace instance (remove + setup)
ots-containers replace 7043

# Update static assets only
ots-containers static

# Show running OTS containers
ots-containers ps

# List containers that would be processed
ots-containers list 7043 7044 7045
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

The tool expects this directory structure on the target system:

```
/opt/onetimesecret/
├── config/
│   ├── .env          # Template env file (PORT gets substituted per instance)
│   └── config.yaml   # Application configuration
├── .env-7043         # Generated: instance-specific env for port 7043
├── .env-7044         # Generated: instance-specific env for port 7044
└── ...

/etc/containers/systemd/
└── onetime@.container  # Quadlet template (managed by this tool)
```

## How It Works

1. **Static assets**: Extracts `/app/public` from the container image into a shared Podman volume
2. **Quadlet template**: Writes a systemd unit template to `/etc/containers/systemd/onetime@.container`
3. **Instance env files**: Creates `/opt/onetimesecret/.env-{port}` from the template with PORT substituted
4. **systemd**: Starts/restarts `onetime@{port}` service

## Troubleshooting

```bash
# Check service status
sudo systemctl status onetime@7043

# View logs
sudo journalctl -u onetime@7043 --since '5 minutes ago'

# Verify Quadlet template
cat /etc/containers/systemd/onetime@.container

# Reload systemd after manual changes
sudo systemctl daemon-reload
```

## License

MIT
