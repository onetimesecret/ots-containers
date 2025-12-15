# src/ots_containers/config.py

import ipaddress
import os
import socket
import struct
from dataclasses import dataclass, field
from pathlib import Path


def _get_private_interface() -> tuple[str, str, str]:
    """
    Auto-detect private network interface, subnet, and gateway.

    Returns the first non-loopback interface with a private IP
    (10.x, 172.16-31.x, 192.168.x). Falls back to eth1 if detection fails.
    """
    try:
        import fcntl

        # Get routing table to find default gateway per interface
        gateways: dict[str, str] = {}
        with open("/proc/net/route") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 3:
                    iface, _dest, gw = parts[0], parts[1], parts[2]
                    # dest 00000000 = default route; we want interface-specific
                    if gw != "00000000":
                        # Convert hex to IP
                        gw_ip = socket.inet_ntoa(struct.pack("<L", int(gw, 16)))
                        gateways[iface] = gw_ip

        # Get all interfaces and their IPs
        SIOCGIFADDR = 0x8915
        SIOCGIFNETMASK = 0x891B

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            # Read interface names from /proc/net/dev
            with open("/proc/net/dev") as f:
                interfaces = [
                    line.split(":")[0].strip()
                    for line in f.readlines()[2:]
                    if ":" in line
                ]

            for iface in interfaces:
                if iface == "lo":
                    continue
                try:
                    # Get IP address
                    ip_bytes = fcntl.ioctl(
                        s.fileno(),
                        SIOCGIFADDR,
                        struct.pack("256s", iface.encode()[:15]),
                    )[20:24]
                    ip = socket.inet_ntoa(ip_bytes)
                    ip_obj = ipaddress.ip_address(ip)

                    # Check if private
                    if ip_obj.is_private and not ip_obj.is_loopback:
                        # Get netmask
                        mask_bytes = fcntl.ioctl(
                            s.fileno(),
                            SIOCGIFNETMASK,
                            struct.pack("256s", iface.encode()[:15]),
                        )[20:24]
                        mask = socket.inet_ntoa(mask_bytes)

                        # Calculate subnet
                        network = ipaddress.ip_network(
                            f"{ip}/{mask}", strict=False
                        )
                        subnet = str(network)

                        # Get gateway (from routing table or guess .1)
                        gateway = gateways.get(
                            iface, str(network.network_address + 1)
                        )

                        return iface, subnet, gateway
                except OSError:
                    continue

    except Exception:
        pass

    # Fallback
    return "eth1", "10.0.0.0/24", "10.0.0.1"


def _detect_network() -> tuple[str, str, str]:
    """Return (interface, subnet, gateway) from env vars or auto-detect."""
    if all(
        os.environ.get(k)
        for k in ["NETWORK_INTERFACE", "NETWORK_SUBNET", "NETWORK_GATEWAY"]
    ):
        return (
            os.environ["NETWORK_INTERFACE"],
            os.environ["NETWORK_SUBNET"],
            os.environ["NETWORK_GATEWAY"],
        )
    return _get_private_interface()


@dataclass
class Config:
    base_dir: Path = Path("/opt/onetimesecret")
    image: str = field(
        default_factory=lambda: os.environ.get(
            "IMAGE", "ghcr.io/onetimesecret/onetimesecret"
        )
    )
    tag: str = field(default_factory=lambda: os.environ.get("TAG", "current"))
    template_path: Path = Path("/etc/containers/systemd/onetime@.container")
    network_path: Path = Path("/etc/containers/systemd/onetime.network")
    network_name: str = "onetime"

    # Macvlan network settings - auto-detected or from environment
    parent_interface: str = field(default_factory=lambda: _detect_network()[0])
    network_subnet: str = field(default_factory=lambda: _detect_network()[1])
    network_gateway: str = field(default_factory=lambda: _detect_network()[2])

    @property
    def image_with_tag(self) -> str:
        return f"{self.image}:{self.tag}"

    def env_file(self, port: int) -> Path:
        return self.base_dir / f".env-{port}"

    def validate(self) -> None:
        required = [
            self.base_dir / "config" / ".env",
            self.base_dir / "config" / "config.yaml",
        ]
        missing = [f for f in required if not f.exists()]
        if missing:
            raise SystemExit(f"Missing required files: {missing}")
