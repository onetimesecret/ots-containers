# Networking Configuration

This document explains how container networking is configured.

## Current Setup: Host Networking with PORT

Containers use host networking with the `PORT` environment variable to control
which port the application listens on.

### How It Works

1. **Host networking** - Containers share the host's network namespace directly
2. **PORT env var** - Each container listens on its instance port (7043, 7044, etc.)

The quadlet template passes the instance number as the PORT:

**onetime@.container**:
```ini
[Container]
Image=ghcr.io/onetimesecret/onetimesecret:current
Network=host
Environment=PORT=%i
EnvironmentFile=/opt/onetimesecret/.env-%i
...
```

When you deploy instance 7043, the container runs with `PORT=7043` and the app
listens on that port directly on the host network.

### Note on `podman ps` Output

You may see `3000/tcp` in the PORTS column of `podman ps`:

```
CONTAINER ID  IMAGE       STATUS         PORTS      NAMES
ae74f478fef1  ...         Up 5 minutes   3000/tcp   systemd-onetime_7043
```

**This is misleading but harmless.** The `3000/tcp` comes from the `EXPOSE 3000`
directive in the upstream Dockerfile. It's just metadata/documentation - it does
not affect actual port binding when using host networking.

The container is actually listening on port 7043 (or whatever instance port you
deployed). Verify with:

```bash
curl http://localhost:7043/api/v2/status
```

## What We Tried (and why it failed)

### Macvlan Networking

We attempted macvlan to give each container its own IP on the LAN:

```ini
[Network]
Driver=macvlan
Options=parent=eth1
Subnet=10.0.0.0/24
Gateway=10.0.0.1
```

**Problems encountered:**

1. **Invalid quadlet syntax** - `InterfaceName` isn't a valid quadlet key;
   the correct syntax is `Options=parent=eth1`

2. **DNS configuration error** - Adding `DNS=9.9.9.9` requires DNS to be
   explicitly enabled first, otherwise podman errors with "cannot set
   NetworkDNSServers if DNS is not enabled"

3. **Incompatible host subnet** - Cloud VMs often have `/32` subnets
   (point-to-point), which don't work with macvlan that needs a proper
   subnet range for container IPs

### Port Publishing Only

```ini
PublishPort=%i:3000
```

**Problem**: Creates isolated network namespaces. Containers can reach the
internet via NAT but cannot reach hosts on the private network (like a
database server). Also, all containers would try to bind to port 3000
internally.

## Why Host Networking Works

Host networking is the simplest approach:

- **No network isolation overhead** - containers use the host's network directly
- **No port mapping complexity** - the app just listens on its PORT
- **Full network access** - containers can reach anything the host can reach
- **Simple debugging** - `ss -tlnp` on the host shows container ports

The tradeoff is less isolation, but for trusted application containers on a
dedicated host, this is acceptable.

## Troubleshooting

### Container can't reach database

Since containers share the host network, if the host can reach the database,
containers can too:

```bash
# Test from host
ping maindb
redis-cli -h maindb ping
```

### Verify container is listening on correct port

```bash
# From host
ss -tlnp | grep 7043
curl http://localhost:7043/api/v2/status

# Or exec into container
sudo podman exec -it systemd-onetime_7043 ss -tlnp
```

### Port conflict on startup

If a container fails to start with "address already in use", check what's
using that port:

```bash
ss -tlnp | grep :7043
```

Ensure you're not deploying duplicate instances or that another service isn't
using the same port.
