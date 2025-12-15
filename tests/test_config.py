# tests/test_config.py
"""Tests for config module - Config dataclass."""

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
