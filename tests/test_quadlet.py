# tests/test_quadlet.py
"""Tests for quadlet module - Podman quadlet file generation."""


class TestContainerTemplate:
    """Test container quadlet template generation."""

    def test_write_template_creates_file(self, mocker, tmp_path):
        """write_template should create the container quadlet file."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        assert cfg.template_path.exists()

    def test_write_template_includes_image(self, mocker, tmp_path, monkeypatch):
        """Container quadlet should include Image from config."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        monkeypatch.setenv("IMAGE", "myregistry/myimage")
        monkeypatch.setenv("TAG", "v1.0.0")

        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Image=myregistry/myimage:v1.0.0" in content

    def test_write_template_uses_host_network(self, mocker, tmp_path):
        """Container quadlet should use host networking."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Network=host" in content

    def test_write_template_sets_port_env_var(self, mocker, tmp_path):
        """Container quadlet should set PORT env var from instance."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Environment=PORT=%i" in content

    def test_write_template_includes_environment_file(self, mocker, tmp_path):
        """Container quadlet should reference shared environment file."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        # Uses fixed path for infrastructure config (not per-instance)
        assert "EnvironmentFile=/etc/default/onetimesecret" in content

    def test_write_template_includes_volumes(self, mocker, tmp_path):
        """Container quadlet should mount config directory and static assets."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        config_dir = tmp_path / "etc"
        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            config_dir=config_dir,
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        # Mounts entire config directory (not just config.yaml)
        assert f"Volume={config_dir}:/app/etc:ro" in content
        assert "Volume=static_assets:/app/public:ro" in content

    def test_write_template_includes_podman_secrets(self, mocker, tmp_path):
        """Container quadlet should include Podman secret directives."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        # Secrets are injected as environment variables via Podman
        assert "Secret=ots_hmac_secret,type=env,target=HMAC_SECRET" in content
        assert "Secret=ots_secret,type=env,target=SECRET" in content
        assert "Secret=ots_session_secret,type=env,target=SESSION_SECRET" in content

    def test_write_template_includes_systemd_dependencies(self, mocker, tmp_path):
        """Container quadlet should have proper systemd dependencies."""
        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=tmp_path / "var",
        )

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
        cfg = Config(
            template_path=nested_path,
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        assert nested_path.exists()

    def test_write_template_reloads_daemon(self, mocker, tmp_path):
        """write_template should reload systemd daemon after writing."""
        mock_reload = mocker.patch("ots_containers.quadlet.systemd.daemon_reload")
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            var_dir=tmp_path / "var",
        )

        quadlet.write_template(cfg)

        mock_reload.assert_called_once()
