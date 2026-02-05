# tests/test_config.py
"""Tests for config module - Config dataclass."""

from pathlib import Path


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

    def test_default_web_template_path(self):
        """Should default to systemd quadlet location for web."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.web_template_path == Path("/etc/containers/systemd/onetime-web@.container")

    def test_default_worker_template_path(self):
        """Should default to systemd quadlet location for worker."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.worker_template_path == Path("/etc/containers/systemd/onetime-worker@.container")

    def test_default_scheduler_template_path(self):
        """Should default to systemd quadlet location for scheduler."""
        from ots_containers.config import Config

        cfg = Config()
        assert cfg.scheduler_template_path == Path(
            "/etc/containers/systemd/onetime-scheduler@.container"
        )


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

    def test_db_path_with_writable_var_dir(self, tmp_path):
        """Should use system path when var_dir is writable."""
        from ots_containers.config import Config

        cfg = Config(var_dir=tmp_path)
        assert cfg.db_path == tmp_path / "deployments.db"

    def test_db_path_falls_back_to_user_space(self):
        """Should fall back to ~/.local/share when var_dir not writable."""
        from ots_containers.config import Config

        # Non-existent path triggers fallback
        cfg = Config(var_dir=Path("/nonexistent/path"))
        assert ".local/share/ots-containers/deployments.db" in str(cfg.db_path)


class TestConfigValidate:
    """Test Config.validate method."""

    def test_validate_is_noop(self, tmp_path):
        """Should not raise even when config files are missing (validate is a no-op)."""
        from ots_containers.config import Config

        cfg = Config(config_dir=tmp_path)
        cfg.validate()  # Should not raise

    def test_validate_with_all_files(self, tmp_path):
        """Should not raise when all required files exist."""
        from ots_containers.config import Config

        # Only config.yaml is required now (secrets via Podman, infra env in /etc/default)
        (tmp_path / "config.yaml").touch()

        cfg = Config(config_dir=tmp_path)
        cfg.validate()  # Should not raise


class TestConfigFiles:
    """Test CONFIG_FILES module-level constant."""

    def test_config_files_contains_expected_files(self):
        """CONFIG_FILES should list the three known config files."""
        from ots_containers.config import CONFIG_FILES

        assert "config.yaml" in CONFIG_FILES
        assert "auth.yaml" in CONFIG_FILES
        assert "logging.yaml" in CONFIG_FILES

    def test_config_files_length(self):
        """CONFIG_FILES should contain exactly 3 entries."""
        from ots_containers.config import CONFIG_FILES

        assert len(CONFIG_FILES) == 3

    def test_config_files_is_tuple(self):
        """CONFIG_FILES should be a tuple (immutable)."""
        from ots_containers.config import CONFIG_FILES

        assert isinstance(CONFIG_FILES, tuple)


class TestExistingConfigFiles:
    """Test Config.existing_config_files property."""

    def test_returns_empty_when_config_dir_missing(self):
        """Should return empty list when config_dir does not exist."""
        from ots_containers.config import Config

        cfg = Config(config_dir=Path("/nonexistent/config/dir"))
        assert cfg.existing_config_files == []

    def test_returns_empty_when_no_yaml_files(self, tmp_path):
        """Should return empty list when config_dir exists but has no yaml files."""
        from ots_containers.config import Config

        config_dir = tmp_path / "etc"
        config_dir.mkdir()

        cfg = Config(config_dir=config_dir)
        assert cfg.existing_config_files == []

    def test_returns_only_existing_files(self, tmp_path):
        """Should return only files that actually exist on disk."""
        from ots_containers.config import Config

        config_dir = tmp_path / "etc"
        config_dir.mkdir()
        (config_dir / "config.yaml").touch()
        (config_dir / "auth.yaml").touch()
        # logging.yaml intentionally not created

        cfg = Config(config_dir=config_dir)
        result = cfg.existing_config_files
        assert len(result) == 2
        assert config_dir / "config.yaml" in result
        assert config_dir / "auth.yaml" in result
        assert config_dir / "logging.yaml" not in result

    def test_returns_all_three_when_all_exist(self, tmp_path):
        """Should return all 3 paths when all config files exist."""
        from ots_containers.config import Config

        config_dir = tmp_path / "etc"
        config_dir.mkdir()
        (config_dir / "config.yaml").touch()
        (config_dir / "auth.yaml").touch()
        (config_dir / "logging.yaml").touch()

        cfg = Config(config_dir=config_dir)
        result = cfg.existing_config_files
        assert len(result) == 3
        assert config_dir / "config.yaml" in result
        assert config_dir / "auth.yaml" in result
        assert config_dir / "logging.yaml" in result

    def test_ignores_non_config_files(self, tmp_path):
        """Should not include files not listed in CONFIG_FILES."""
        from ots_containers.config import Config

        config_dir = tmp_path / "etc"
        config_dir.mkdir()
        (config_dir / "config.yaml").touch()
        (config_dir / "billing.yaml").touch()  # Not in CONFIG_FILES

        cfg = Config(config_dir=config_dir)
        result = cfg.existing_config_files
        assert len(result) == 1
        assert config_dir / "config.yaml" in result
        assert config_dir / "billing.yaml" not in result


class TestHasCustomConfig:
    """Test Config.has_custom_config property."""

    def test_false_when_no_config_dir(self):
        """Should return False when config_dir does not exist."""
        from ots_containers.config import Config

        cfg = Config(config_dir=Path("/nonexistent/config/dir"))
        assert cfg.has_custom_config is False

    def test_false_when_empty_config_dir(self, tmp_path):
        """Should return False when config_dir exists but is empty."""
        from ots_containers.config import Config

        config_dir = tmp_path / "etc"
        config_dir.mkdir()

        cfg = Config(config_dir=config_dir)
        assert cfg.has_custom_config is False

    def test_true_when_one_yaml_exists(self, tmp_path):
        """Should return True when at least one config file exists."""
        from ots_containers.config import Config

        config_dir = tmp_path / "etc"
        config_dir.mkdir()
        (config_dir / "config.yaml").touch()

        cfg = Config(config_dir=config_dir)
        assert cfg.has_custom_config is True

    def test_true_when_all_yaml_files_exist(self, tmp_path):
        """Should return True when all config files exist."""
        from ots_containers.config import Config

        config_dir = tmp_path / "etc"
        config_dir.mkdir()
        (config_dir / "config.yaml").touch()
        (config_dir / "auth.yaml").touch()
        (config_dir / "logging.yaml").touch()

        cfg = Config(config_dir=config_dir)
        assert cfg.has_custom_config is True
