# tests/test_config.py
"""Tests for config module - Config dataclass."""

from pathlib import Path

import pytest


class TestConfigDefaults:
    """Test Config dataclass default values."""

    def test_default_config_dir(self):
        """Should default to /etc/onetimesecret."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.config_dir == Path("/etc/onetimesecret")

    def test_default_var_dir(self):
        """Should default to /var/lib/onetimesecret."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.var_dir == Path("/var/lib/onetimesecret")

    def test_default_template_path(self):
        """Should default to systemd quadlet location."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.template_path == Path("/etc/containers/systemd/onetime@.container")


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


class TestConfigPaths:
    """Test Config path properties and methods."""

    def test_config_yaml_path(self):
        """Should return correct path for config.yaml."""
        from ots_containers.config import Config

        cfg = Config(config_dir=Path("/etc/ots"))
        assert cfg.config_yaml == Path("/etc/ots/config.yaml")

    def test_db_path(self):
        """Should return correct path for deployments database."""
        from ots_containers.config import Config

        cfg = Config(var_dir=Path("/var/lib/ots"))
        assert cfg.db_path == Path("/var/lib/ots/deployments.db")


class TestConfigValidate:
    """Test Config.validate method."""

    def test_validate_missing_files_raises(self, tmp_path):
        """Should raise SystemExit when required files missing."""
        from ots_containers.config import Config

        cfg = Config(config_dir=tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            cfg.validate()

        assert "Missing required files" in str(exc_info.value)

    def test_validate_with_all_files(self, tmp_path):
        """Should not raise when all required files exist."""
        from ots_containers.config import Config

        # Only config.yaml is required now (secrets via Podman, infra env in /etc/default)
        (tmp_path / "config.yaml").touch()

        cfg = Config(config_dir=tmp_path)
        cfg.validate()  # Should not raise
