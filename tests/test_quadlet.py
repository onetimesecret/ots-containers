# tests/test_quadlet.py
"""Tests for quadlet module - Podman quadlet file generation."""

from pathlib import Path


class TestSudoWrite:
    """Test _sudo_write helper function."""

    def test_sudo_write_calls_mkdir(self, mocker):
        """Should call sudo mkdir -p for parent directory."""
        from ots_containers import quadlet

        mock_run = mocker.patch("ots_containers.quadlet.subprocess.run")

        quadlet._sudo_write(
            Path("/etc/containers/systemd/test.network"), "content"
        )

        # First call should be mkdir
        assert mock_run.call_args_list[0][0][0] == [
            "sudo",
            "mkdir",
            "-p",
            "/etc/containers/systemd",
        ]

    def test_sudo_write_calls_tee(self, mocker):
        """Should call sudo tee with content."""
        from ots_containers import quadlet

        mock_run = mocker.patch("ots_containers.quadlet.subprocess.run")

        quadlet._sudo_write(
            Path("/etc/containers/systemd/test.network"), "content"
        )

        # Second call should be tee
        call = mock_run.call_args_list[1]
        assert call[0][0] == [
            "sudo",
            "tee",
            "/etc/containers/systemd/test.network",
        ]
        assert call[1]["input"] == "content"


class TestNetworkTemplate:
    """Test network quadlet template generation."""

    def test_write_network_generates_content(self, mocker):
        """write_network should generate correct content."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        mock_sudo_write = mocker.patch("ots_containers.quadlet._sudo_write")

        cfg = Config(
            network_path=Path("/etc/containers/systemd/onetime.network"),
            parent_interface="ens192",
            network_subnet="10.0.0.0/24",
            network_gateway="10.0.0.1",
        )

        quadlet.write_network(cfg)

        mock_sudo_write.assert_called_once()
        path, content = mock_sudo_write.call_args[0]
        assert path == cfg.network_path
        assert "Driver=macvlan" in content
        assert "InterfaceName=ens192" in content
        assert "Subnet=10.0.0.0/24" in content
        assert "Gateway=10.0.0.1" in content
        assert "DNS=9.9.9.9" in content

    def test_write_network_uses_config_values(self, mocker):
        """write_network should use values from config."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        mock_sudo_write = mocker.patch("ots_containers.quadlet._sudo_write")

        cfg = Config(
            network_path=Path("/custom/path/mynet.network"),
            parent_interface="eth0",
            network_subnet="192.168.100.0/24",
            network_gateway="192.168.100.1",
        )

        quadlet.write_network(cfg)

        path, content = mock_sudo_write.call_args[0]
        assert path == Path("/custom/path/mynet.network")
        assert "InterfaceName=eth0" in content
        assert "Subnet=192.168.100.0/24" in content
        assert "Gateway=192.168.100.1" in content


class TestContainerTemplate:
    """Test container quadlet template generation."""

    def test_write_template_generates_content(self, mocker, monkeypatch):
        """write_template should generate correct content."""
        monkeypatch.setenv("IMAGE", "myregistry/myimage")
        monkeypatch.setenv("TAG", "v1.0.0")

        from ots_containers import quadlet
        from ots_containers.config import Config

        mock_sudo_write = mocker.patch("ots_containers.quadlet._sudo_write")

        cfg = Config(
            template_path=Path("/etc/containers/systemd/onetime@.container"),
            base_dir=Path("/opt/ots"),
            network_name="onetime",
        )

        quadlet.write_template(cfg)

        mock_sudo_write.assert_called_once()
        path, content = mock_sudo_write.call_args[0]
        assert path == cfg.template_path
        assert "Image=myregistry/myimage:v1.0.0" in content
        assert "Network=onetime.network" in content
        assert "PublishPort=%i:3000" in content
        assert "EnvironmentFile=/opt/ots/.env-%i" in content

    def test_write_template_includes_volumes(self, mocker):
        """Container quadlet should mount config and static assets."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        mock_sudo_write = mocker.patch("ots_containers.quadlet._sudo_write")

        cfg = Config(
            template_path=Path("/etc/containers/systemd/onetime@.container"),
            base_dir=Path("/opt/ots"),
        )

        quadlet.write_template(cfg)

        _, content = mock_sudo_write.call_args[0]
        assert (
            "Volume=/opt/ots/config/config.yaml:/app/etc/config.yaml:ro"
            in content
        )
        assert "Volume=static_assets:/app/public:ro" in content

    def test_write_template_includes_systemd_dependencies(self, mocker):
        """Container quadlet should have proper systemd dependencies."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        mock_sudo_write = mocker.patch("ots_containers.quadlet._sudo_write")

        cfg = Config(
            template_path=Path("/etc/containers/systemd/onetime@.container"),
        )

        quadlet.write_template(cfg)

        _, content = mock_sudo_write.call_args[0]
        assert "After=local-fs.target network-online.target" in content
        assert "Wants=network-online.target" in content
        assert "WantedBy=multi-user.target" in content


class TestWriteAll:
    """Test write_all function."""

    def test_write_all_calls_both_writes(self, mocker):
        """write_all should call both write_network and write_template."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        mock_write_network = mocker.patch(
            "ots_containers.quadlet.write_network"
        )
        mock_write_template = mocker.patch(
            "ots_containers.quadlet.write_template"
        )
        mock_daemon_reload = mocker.patch(
            "ots_containers.quadlet.systemd.daemon_reload"
        )

        cfg = Config()

        quadlet.write_all(cfg)

        mock_write_network.assert_called_once_with(cfg)
        mock_write_template.assert_called_once_with(cfg)
        mock_daemon_reload.assert_called_once()

    def test_write_all_reloads_daemon_after_writes(self, mocker):
        """write_all should reload systemd after writing files."""
        from ots_containers import quadlet
        from ots_containers.config import Config

        call_order = []

        def track_network(cfg):
            call_order.append("network")

        def track_template(cfg):
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

        cfg = Config()

        quadlet.write_all(cfg)

        assert call_order == ["network", "template", "reload"]
