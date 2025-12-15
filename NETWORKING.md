# Networking Configuration

This document explains how container networking is configured and why.

## Current Setup: Macvlan + Port Publishing

Containers use two networking mechanisms:

1. **Macvlan network** - Containers get their own MAC address on the host's
   private network interface, allowing direct access to other hosts (like the
   database server `maindb`).

2. **Port publishing** - Each container's internal port 3000 is mapped to its
   instance port on the host (e.g., 7043:3000, 7044:3000).

### Generated Quadlet Files

**onetime.network** (macvlan network definition):
```ini
[Network]
Driver=macvlan
Options=parent=eth1
Subnet=10.0.0.0/24
Gateway=10.0.0.1
```

**onetime@.container** (container template):
```ini
[Container]
Image=ghcr.io/onetimesecret/onetimesecret:current
Network=onetime.network
PublishPort=%i:3000
...
```

### Auto-Detection

Network settings are auto-detected from the host by reading `/proc/net/route`
and `/proc/net/dev`. The code finds the first non-loopback interface with a
private IP (10.x, 172.16-31.x, 192.168.x) and extracts:

- Interface name (e.g., `eth1`)
- Subnet CIDR (e.g., `10.0.0.0/24`)
- Gateway (from routing table, or `.1` of the subnet)

Override with environment variables if needed:
```bash
export NETWORK_INTERFACE=ens192
export NETWORK_SUBNET=172.16.0.0/16
export NETWORK_GATEWAY=172.16.0.1
```

## What We Tried

### Host Networking (didn't work)

```ini
Network=host
```

**Problem**: All containers share the host's network stack. When multiple
instances try to bind to port 3000, only the first succeeds. The others fail
with "port is in use."

**Also**: Host networking provides no network isolation - containers can see
and bind to any host port, which is a security concern.

### Port Publishing Only (didn't work)

```ini
PublishPort=%i:3000
```

**Problem**: Port publishing creates an isolated network namespace for each
container. They can reach the internet via NAT, but cannot reach hosts on the
private network where `maindb` lives. Containers failed with "Cannot connect
to redis" because `maindb` was unreachable.

### Bridge Network + host-gateway (not applicable)

```ini
Network=mybridge.network
AddHost=maindb:host-gateway
```

**Problem**: `host-gateway` points to the container's gateway (the host
machine), not to `maindb`. This only works if the database runs on the same
host as the containers. Our database is on a separate server.

## Future Options

### Option 1: Bridge Network + Host as Router

If macvlan causes issues (some switches don't like multiple MACs on one port,
or you need container-to-host communication which macvlan blocks), you could:

1. Use a standard bridge network
2. Configure the host as a router/gateway
3. Set up NAT or routing rules to forward traffic to the private network

**Pros**: Works with any switch, containers can talk to host
**Cons**: More complex setup, additional latency through host routing

### Option 2: IPVLAN Instead of Macvlan

IPVLAN shares the host's MAC address but gives containers their own IPs. Some
cloud providers block macvlan but allow ipvlan.

```ini
[Network]
Driver=ipvlan
Options=parent=eth1
Options=mode=l2
```

**Pros**: Works in environments that block multiple MACs
**Cons**: Slightly different L2/L3 behavior, less common

### Option 3: Separate Database Hostname Resolution

If the database has a public or VPN-accessible IP, configure containers to
resolve `maindb` to that IP instead of relying on private network access:

```ini
AddHost=maindb:203.0.113.50
```

Or use the IP directly in the app config.

**Pros**: Simplest networking (just port publishing)
**Cons**: Requires database to be accessible outside private network

### Option 4: WireGuard/VPN Sidecar

Run a WireGuard container that joins the private network, then route container
traffic through it.

**Pros**: Works across cloud providers, encrypted
**Cons**: Additional container, complexity, latency

## Troubleshooting

### Container can't reach maindb

1. Check the detected network settings:
   ```bash
   python -c "from ots_containers.config import Config; c = Config(); print(c.parent_interface, c.network_subnet, c.network_gateway)"
   ```

2. Verify the interface exists and has the expected IP:
   ```bash
   ip addr show eth1
   ```

3. Check if maindb is reachable from the host:
   ```bash
   ping maindb
   redis-cli -h maindb ping
   ```

4. Inspect the generated network file:
   ```bash
   cat /etc/containers/systemd/onetime.network
   ```

### Macvlan container can't reach its own host

This is a known macvlan limitation. The container and host cannot communicate
directly over the macvlan interface. If needed, create a macvlan sub-interface
on the host:

```bash
ip link add macvlan0 link eth1 type macvlan mode bridge
ip addr add 10.0.0.254/32 dev macvlan0
ip link set macvlan0 up
ip route add 10.0.0.0/24 dev macvlan0
```

Or use a different networking approach (see Future Options above).
