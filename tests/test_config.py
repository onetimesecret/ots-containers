# tests/test_config.py
"""Tests for config module - Config dataclass and network detection."""

from pathlib import Path

import pytest


class TestConfigDefaults:
    """Test Config dataclass default values."""

    def test_default_base_dir(self):
        """Should default to /opt/onetimesecret."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.base_dir == Path("/opt/onetimesecret")

    def test_default_template_path(self):
        """Should default to systemd quadlet location."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.template_path == Path(
            "/etc/containers/systemd/onetime@.container"
        )

    def test_default_network_path(self):
        """Should default to systemd quadlet location."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.network_path == Path(
            "/etc/containers/systemd/onetime.network"
        )

    def test_default_network_name(self):
        """Should default to 'onetime'."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.network_name == "onetime"


class TestConfigImageSettings:
    """Test Config image-related settings."""

    def test_default_image(self, monkeypatch):
        """Should default to ghcr.io/onetimesecret/onetimesecret."""
        monkeypatch.delenv("IMAGE", raising=False)
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.image == "ghcr.io/onetimesecret/onetimesecret"

    def test_image_from_env(self, monkeypatch):
        """Should use IMAGE env var when set."""
        monkeypatch.setenv("IMAGE", "custom/image")
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.image == "custom/image"

    def test_default_tag(self, monkeypatch):
        """Should default to 'current'."""
        monkeypatch.delenv("TAG", raising=False)
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.tag == "current"

    def test_tag_from_env(self, monkeypatch):
        """Should use TAG env var when set."""
        monkeypatch.setenv("TAG", "v1.2.3")
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.tag == "v1.2.3"

    def test_image_with_tag_property(self, monkeypatch):
        """Should combine image and tag correctly."""
        monkeypatch.setenv("IMAGE", "myregistry/myimage")
        monkeypatch.setenv("TAG", "latest")
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.image_with_tag == "myregistry/myimage:latest"


class TestConfigEnvFile:
    """Test Config.env_file method."""

    def test_env_file_path(self):
        """Should return correct path for given port."""
        from ots_containers.config import Config

        cfg = Config(base_dir=Path("/opt/ots"))
        assert cfg.env_file(7043) == Path("/opt/ots/.env-7043")

    def test_env_file_different_ports(self):
        """Should return different paths for different ports."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.env_file(7043) != cfg.env_file(7044)


class TestConfigValidate:
    """Test Config.validate method."""

    def test_validate_missing_files_raises(self, tmp_path):
        """Should raise SystemExit when required files missing."""
        from ots_containers.config import Config

        cfg = Config(base_dir=tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            cfg.validate()

        assert "Missing required files" in str(exc_info.value)

    def test_validate_with_all_files(self, tmp_path):
        """Should not raise when all required files exist."""
        from ots_containers.config import Config

        config_dir = tmp_path / "config"
        config_dir.mkdir()
        (config_dir / ".env").touch()
        (config_dir / "config.yaml").touch()

        cfg = Config(base_dir=tmp_path)
        cfg.validate()  # Should not raise


class TestNetworkDetection:
    """Test network auto-detection functions."""

    def test_detect_network_uses_env_vars(self, monkeypatch):
        """Should use env vars when all three are set."""
        monkeypatch.setenv("NETWORK_INTERFACE", "eth0")
        monkeypatch.setenv("NETWORK_SUBNET", "192.168.1.0/24")
        monkeypatch.setenv("NETWORK_GATEWAY", "192.168.1.1")

        from ots_containers.config import _detect_network

        iface, subnet, gateway = _detect_network()

        assert iface == "eth0"
        assert subnet == "192.168.1.0/24"
        assert gateway == "192.168.1.1"

    def test_detect_network_partial_env_falls_back(self, monkeypatch):
        """Should fall back to auto-detect if not all env vars set."""
        monkeypatch.setenv("NETWORK_INTERFACE", "eth0")
        monkeypatch.delenv("NETWORK_SUBNET", raising=False)
        monkeypatch.delenv("NETWORK_GATEWAY", raising=False)

        from ots_containers.config import _detect_network

        # On macOS (no /proc), falls back to defaults
        iface, subnet, gateway = _detect_network()

        # Should be fallback values since /proc doesn't exist on macOS
        assert iface == "eth1"
        assert subnet == "10.0.0.0/24"
        assert gateway == "10.0.0.1"

    def test_get_private_interface_fallback(self):
        """Should return fallback values when detection fails."""
        from ots_containers.config import _get_private_interface

        # On macOS, this will always fall back since /proc doesn't exist
        iface, subnet, gateway = _get_private_interface()

        assert iface == "eth1"
        assert subnet == "10.0.0.0/24"
        assert gateway == "10.0.0.1"


class TestConfigNetworkSettings:
    """Test Config network settings from auto-detection."""

    def test_network_settings_from_env(self, monkeypatch):
        """Should use network settings from environment."""
        monkeypatch.setenv("NETWORK_INTERFACE", "ens192")
        monkeypatch.setenv("NETWORK_SUBNET", "10.10.0.0/16")
        monkeypatch.setenv("NETWORK_GATEWAY", "10.10.0.1")

        from ots_containers.config import Config

        cfg = Config()

        assert cfg.parent_interface == "ens192"
        assert cfg.network_subnet == "10.10.0.0/16"
        assert cfg.network_gateway == "10.10.0.1"

    def test_network_settings_fallback(self, monkeypatch):
        """Should use fallback network settings on macOS."""
        monkeypatch.delenv("NETWORK_INTERFACE", raising=False)
        monkeypatch.delenv("NETWORK_SUBNET", raising=False)
        monkeypatch.delenv("NETWORK_GATEWAY", raising=False)

        from ots_containers.config import Config

        cfg = Config()

        # On macOS, always falls back
        assert cfg.parent_interface == "eth1"
        assert cfg.network_subnet == "10.0.0.0/24"
        assert cfg.network_gateway == "10.0.0.1"
