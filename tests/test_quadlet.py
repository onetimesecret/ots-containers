# tests/test_quadlet.py
"""Tests for quadlet module - Podman quadlet file generation."""

from pathlib import Path


class TestContainerTemplate:
    """Test container quadlet template generation."""

    def test_write_template_creates_file(self, mocker, tmp_path):
        """write_template should create the container quadlet file."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        assert cfg.template_path.exists()

    def test_write_template_includes_image(self, mocker, tmp_path, monkeypatch):
        """Container quadlet should include Image from config."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        monkeypatch.setenv("IMAGE", "myregistry/myimage")
        monkeypatch.setenv("TAG", "v1.0.0")

        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Image=myregistry/myimage:v1.0.0" in content

    def test_write_template_uses_host_network(self, mocker, tmp_path):
        """Container quadlet should use host networking."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Network=host" in content

    def test_write_template_sets_port_env_var(self, mocker, tmp_path):
        """Container quadlet should set PORT env var from instance."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Environment=PORT=%i" in content

    def test_write_template_includes_environment_file(self, mocker, tmp_path):
        """Container quadlet should reference environment file with instance."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=Path("/var/lib/ots"),
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "EnvironmentFile=/var/lib/ots/.env-%i" in content

    def test_write_template_includes_volumes(self, mocker, tmp_path):
        """Container quadlet should mount config and static assets."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            config_dir=Path("/etc/ots"),
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Volume=/etc/ots/config.yaml:/app/etc/config.yaml:ro" in content
        assert "Volume=static_assets:/app/public:ro" in content

    def test_write_template_includes_systemd_dependencies(self, mocker, tmp_path):
        """Container quadlet should have proper systemd dependencies."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "After=local-fs.target network-online.target" in content
        assert "Wants=network-online.target" in content
        assert "WantedBy=multi-user.target" in content

    def test_write_template_creates_parent_dirs(self, mocker, tmp_path):
        """write_template should create parent directories if needed."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        nested_path = tmp_path / "subdir" / "onetime@.container"
        cfg = Config(template_path=nested_path)

        quadlet.write_template(cfg)

        assert nested_path.exists()

    def test_write_template_reloads_daemon(self, mocker, tmp_path):
        """write_template should reload systemd daemon after writing."""
        mock_reload = mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        mock_reload.assert_called_once()
