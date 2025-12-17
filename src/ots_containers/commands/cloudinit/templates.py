# src/ots_containers/commands/cloudinit/templates.py
"""Cloud-init configuration templates with Debian 13 DEB822 apt sources."""


def generate_cloudinit_config(
    *,
    include_postgresql: bool = False,
    include_valkey: bool = False,
    postgresql_gpg_key: str | None = None,
    valkey_gpg_key: str | None = None,
) -> str:
    """Generate cloud-init YAML with Debian 13 DEB822-style apt sources.

    Args:
        include_postgresql: Include PostgreSQL official repository
        include_valkey: Include Valkey repository
        postgresql_gpg_key: PostgreSQL GPG public key content
        valkey_gpg_key: Valkey GPG public key content

    Returns:
        Complete cloud-init YAML configuration as string
    """
    # Base configuration with Debian 13 main repositories
    config_parts = [
        "#cloud-config",
        "# Generated cloud-init configuration for OTS infrastructure",
        "# Debian 13 (Trixie) with DEB822-style apt sources",
        "",
        "package_update: true",
        "package_upgrade: true",
        "package_reboot_if_required: true",
        "",
        "apt:",
        "  sources_list: |",
        "    Types: deb",
        "    URIs: http://deb.debian.org/debian",
        "    Suites: trixie trixie-updates",
        "    Components: main contrib non-free non-free-firmware",
        "    Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg",
        "",
        "    Types: deb",
        "    URIs: http://deb.debian.org/debian",
        "    Suites: trixie-backports",
        "    Components: main contrib non-free non-free-firmware",
        "    Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg",
        "",
        "    Types: deb",
        "    URIs: http://security.debian.org/debian-security",
        "    Suites: trixie-security",
        "    Components: main contrib non-free non-free-firmware",
        "    Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg",
    ]

    # Add third-party repositories if requested
    sources = []

    if include_postgresql:
        postgresql_source = {
            "source": "deb http://apt.postgresql.org/pub/repos/apt trixie-pgdg main",
        }
        if postgresql_gpg_key:
            postgresql_source["key"] = postgresql_gpg_key
        else:
            postgresql_source["key"] = "# PostgreSQL GPG key placeholder - replace with actual key"
        sources.append(("postgresql", postgresql_source))

    if include_valkey:
        valkey_source = {
            "source": "deb https://packages.valkey.io/deb/ trixie main",
        }
        if valkey_gpg_key:
            valkey_source["key"] = valkey_gpg_key
        else:
            valkey_source["key"] = "# Valkey GPG key placeholder - replace with actual key"
        sources.append(("valkey", valkey_source))

    # Add sources section if we have any
    if sources:
        config_parts.append("  sources:")
        for name, source_config in sources:
            config_parts.append(f"    {name}:")
            config_parts.append(f'      source: "{source_config["source"]}"')
            if "key" in source_config:
                # Multi-line key handling
                key_content = source_config["key"]
                if "\n" in key_content:
                    config_parts.append("      key: |")
                    for line in key_content.split("\n"):
                        config_parts.append(f"        {line}")
                else:
                    config_parts.append(f'      key: "{key_content}"')

    # Add common packages section
    config_parts.extend(
        [
            "",
            "packages:",
            "  - curl",
            "  - wget",
            "  - git",
            "  - vim",
            "  - podman",
            "  - systemd-container",
        ]
    )

    if include_postgresql:
        config_parts.append("  - postgresql-client")

    if include_valkey:
        config_parts.append("  - valkey")

    return "\n".join(config_parts) + "\n"


def get_debian13_sources_list() -> str:
    """Get just the Debian 13 DEB822 sources.list content.

    Returns:
        DEB822-formatted sources.list content
    """
    return """Types: deb
URIs: http://deb.debian.org/debian
Suites: trixie trixie-updates
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: http://deb.debian.org/debian
Suites: trixie-backports
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: http://security.debian.org/debian-security
Suites: trixie-security
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
"""
