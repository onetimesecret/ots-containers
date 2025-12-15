# tests/test_quadlet.py
"""Tests for quadlet module - Podman quadlet file generation."""

from pathlib import Path


class TestNetworkTemplate:
    """Test network quadlet template generation."""

    def test_write_network_creates_file(self, mocker, tmp_path):
        """write_network should create the network quadlet file."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(network_path=tmp_path / "onetime.network")

        quadlet.write_network(cfg)

        assert cfg.network_path.exists()

    def test_write_network_uses_macvlan_driver(self, mocker, tmp_path):
        """Network quadlet should use macvlan driver."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(network_path=tmp_path / "onetime.network")

        quadlet.write_network(cfg)

        content = cfg.network_path.read_text()
        assert "Driver=macvlan" in content

    def test_write_network_includes_interface_name(self, mocker, tmp_path):
        """Network quadlet should include InterfaceName from config."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            network_path=tmp_path / "onetime.network",
            parent_interface="ens192",
        )

        quadlet.write_network(cfg)

        content = cfg.network_path.read_text()
        assert "InterfaceName=ens192" in content

    def test_write_network_includes_subnet(self, mocker, tmp_path):
        """Network quadlet should include Subnet from config."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            network_path=tmp_path / "onetime.network",
            network_subnet="192.168.1.0/24",
        )

        quadlet.write_network(cfg)

        content = cfg.network_path.read_text()
        assert "Subnet=192.168.1.0/24" in content

    def test_write_network_includes_gateway(self, mocker, tmp_path):
        """Network quadlet should include Gateway from config."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            network_path=tmp_path / "onetime.network",
            network_gateway="192.168.1.1",
        )

        quadlet.write_network(cfg)

        content = cfg.network_path.read_text()
        assert "Gateway=192.168.1.1" in content

    def test_write_network_includes_dns(self, mocker, tmp_path):
        """Network quadlet should include DNS setting."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(network_path=tmp_path / "onetime.network")

        quadlet.write_network(cfg)

        content = cfg.network_path.read_text()
        assert "DNS=9.9.9.9" in content

    def test_write_network_creates_parent_dirs(self, mocker, tmp_path):
        """write_network should create parent directories if needed."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        nested_path = tmp_path / "subdir" / "onetime.network"
        cfg = Config(network_path=nested_path)

        quadlet.write_network(cfg)

        assert nested_path.exists()


class TestContainerTemplate:
    """Test container quadlet template generation."""

    def test_write_template_creates_file(self, mocker, tmp_path):
        """write_template should create the container quadlet file."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        assert cfg.template_path.exists()

    def test_write_template_includes_image(self, mocker, tmp_path, monkeypatch):
        """Container quadlet should include Image from config."""
        monkeypatch.setenv("IMAGE", "myregistry/myimage")
        monkeypatch.setenv("TAG", "v1.0.0")

        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Image=myregistry/myimage:v1.0.0" in content

    def test_write_template_includes_network(self, mocker, tmp_path):
        """Container quadlet should reference network quadlet."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            network_name="onetime",
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "Network=onetime.network" in content

    def test_write_template_includes_publish_port(self, mocker, tmp_path):
        """Container quadlet should include PublishPort with instance."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(template_path=tmp_path / "onetime@.container")

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "PublishPort=%i:3000" in content

    def test_write_template_includes_environment_file(self, mocker, tmp_path):
        """Container quadlet should reference environment file with instance."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            base_dir=Path("/opt/ots"),
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert "EnvironmentFile=/opt/ots/.env-%i" in content

    def test_write_template_includes_volumes(self, mocker, tmp_path):
        """Container quadlet should mount config and static assets."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            base_dir=Path("/opt/ots"),
        )

        quadlet.write_template(cfg)

        content = cfg.template_path.read_text()
        assert (
            "Volume=/opt/ots/config/config.yaml:/app/etc/config.yaml:ro"
            in content
        )
        assert "Volume=static_assets:/app/public:ro" in content

    def test_write_template_includes_systemd_dependencies(
        self, mocker, tmp_path
    ):
        """Container quadlet should have proper systemd dependencies."""
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
        from ots_containers import quadlet
        from ots_containers.config import Config

        nested_path = tmp_path / "subdir" / "onetime@.container"
        cfg = Config(template_path=nested_path)

        quadlet.write_template(cfg)

        assert nested_path.exists()


class TestWriteAll:
    """Test write_all function."""

    def test_write_all_creates_both_files(self, mocker, tmp_path):
        """write_all should create both network and container quadlet files."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        mock_daemon_reload = mocker.patch(
            "ots_containers.quadlet.systemd.daemon_reload"
        )

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            network_path=tmp_path / "onetime.network",
        )

        quadlet.write_all(cfg)

        assert cfg.template_path.exists()
        assert cfg.network_path.exists()
        mock_daemon_reload.assert_called_once()

    def test_write_all_network_content(self, mocker, tmp_path):
        """write_all should generate correct network content."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            network_path=tmp_path / "onetime.network",
        )

        quadlet.write_all(cfg)

        network_content = cfg.network_path.read_text()
        assert "Driver=macvlan" in network_content
        assert f"InterfaceName={cfg.parent_interface}" in network_content

    def test_write_all_container_content(self, mocker, tmp_path):
        """write_all should generate correct container content."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        mocker.patch("ots_containers.quadlet.systemd.daemon_reload")

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            network_path=tmp_path / "onetime.network",
        )

        quadlet.write_all(cfg)

        container_content = cfg.template_path.read_text()
        assert "Network=onetime.network" in container_content
        assert "PublishPort=%i:3000" in container_content

    def test_write_all_reloads_daemon_after_writes(self, mocker, tmp_path):
        """write_all should reload systemd after writing files."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        call_order = []

        original_write_network = quadlet.write_network
        original_write_template = quadlet.write_template

        def track_network(cfg):
            original_write_network(cfg)
            call_order.append("network")

        def track_template(cfg):
            original_write_template(cfg)
            call_order.append("template")

        def track_reload():
            call_order.append("reload")

        mocker.patch(
            "ots_containers.quadlet.write_network", side_effect=track_network
        )
        mocker.patch(
            "ots_containers.quadlet.write_template", side_effect=track_template
        )
        mocker.patch(
            "ots_containers.quadlet.systemd.daemon_reload",
            side_effect=track_reload,
        )

        cfg = Config(
            template_path=tmp_path / "onetime@.container",
            network_path=tmp_path / "onetime.network",
        )

        quadlet.write_all(cfg)

        assert call_order == ["network", "template", "reload"]
