# tests/test_instance.py
"""Tests for instance management commands.

These tests verify that instance commands can be imported and invoked
without attribute errors or import failures. They use mocking to avoid
requiring actual podman/systemd infrastructure.
"""

import pytest

from ots_containers.commands import instance


class TestInstanceImports:
    """Verify instance module imports correctly without AttributeError."""

    def test_instance_app_exists(self):
        """Instance app should be importable."""
        assert instance.app is not None

    def test_deploy_function_exists(self):
        """deploy command should be defined."""
        assert hasattr(instance, "deploy")
        assert callable(instance.deploy)

    def test_redeploy_function_exists(self):
        """redeploy command should be defined."""
        assert hasattr(instance, "redeploy")
        assert callable(instance.redeploy)

    def test_undeploy_function_exists(self):
        """undeploy command should be defined."""
        assert hasattr(instance, "undeploy")
        assert callable(instance.undeploy)


class TestInstanceHelp:
    """Test instance command help output."""

    def test_instance_deploy_help(self, capsys):
        """instance deploy --help should work."""
        from ots_containers.cli import app

        with pytest.raises(SystemExit) as exc_info:
            app(["instance", "deploy", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert (
            "port" in captured.out.lower() or "deploy" in captured.out.lower()
        )

    def test_instance_redeploy_help(self, capsys):
        """instance redeploy --help should work."""
        from ots_containers.cli import app

        with pytest.raises(SystemExit) as exc_info:
            app(["instance", "redeploy", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert (
            "force" in captured.out.lower()
            or "redeploy" in captured.out.lower()
        )


class TestDeployCommand:
    """Test deploy command execution with mocked dependencies."""

    def test_deploy_validates_config(self, mocker):
        """deploy should validate config before proceeding."""
        mock_validate = mocker.patch(
            "ots_containers.commands.instance.Config.validate",
            side_effect=SystemExit("Missing required files"),
        )

        with pytest.raises(SystemExit):
            instance.deploy(ports=(7143,))

        mock_validate.assert_called_once()

    def test_deploy_calls_assets_update(self, mocker):
        """deploy should update assets."""
        mock_config = mocker.MagicMock()
        mock_config.base_dir = mocker.MagicMock()
        mock_config.template_path = mocker.MagicMock()
        mocker.patch(
            "ots_containers.commands.instance.Config", return_value=mock_config
        )
        mock_assets = mocker.patch(
            "ots_containers.commands.instance.assets.update"
        )
        mock_quadlet = mocker.patch(
            "ots_containers.commands.instance.quadlet.write_all"
        )
        _mock_systemd = mocker.patch(
            "ots_containers.commands.instance.systemd.start"
        )
        mock_config.env_file.return_value = mocker.MagicMock()
        mock_config.env_file.return_value.write_text = mocker.MagicMock()
        mocker.patch.object(
            mock_config.base_dir / "config" / ".env",
            "read_text",
            return_value="PORT=${PORT}",
        )

        # Mock the path operations
        mock_env_template = mocker.MagicMock()
        mock_env_template.read_text.return_value = "PORT=${PORT}"
        mock_config.base_dir.__truediv__ = mocker.MagicMock(
            return_value=mocker.MagicMock(
                __truediv__=mocker.MagicMock(return_value=mock_env_template)
            )
        )

        instance.deploy(ports=(7143,))

        mock_assets.assert_called_once_with(mock_config, create_volume=True)
        mock_quadlet.assert_called_once_with(mock_config)


class TestRedeployCommand:
    """Test redeploy command execution with mocked dependencies."""

    def test_redeploy_with_no_instances_found(self, mocker, capsys):
        """redeploy with no ports should discover instances."""
        mocker.patch(
            "ots_containers.commands.instance.systemd.discover_instances",
            return_value=[],
        )

        instance.redeploy(ports=())

        captured = capsys.readouterr()
        assert "No running instances found" in captured.out

    def test_redeploy_uses_cfg_template_path(self, mocker, tmp_path):
        """redeploy should use cfg.template_path (not quadlet.template_path)."""
        # This test verifies the fix for the AttributeError
        mock_config = mocker.MagicMock()
        mock_config.base_dir = mocker.MagicMock()
        mock_config.template_path = tmp_path / "template"
        mocker.patch(
            "ots_containers.commands.instance.Config", return_value=mock_config
        )
        mocker.patch(
            "ots_containers.commands.instance.systemd.discover_instances",
            return_value=[7143],
        )
        mocker.patch("ots_containers.commands.instance.assets.update")
        mocker.patch("ots_containers.commands.instance.quadlet.write_all")
        mocker.patch("ots_containers.commands.instance.systemd.restart")
        mocker.patch(
            "ots_containers.commands.instance.systemd.unit_exists",
            return_value=True,
        )

        mock_env_template = mocker.MagicMock()
        mock_env_template.read_text.return_value = "PORT=${PORT}"
        mock_config.base_dir.__truediv__ = mocker.MagicMock(
            return_value=mocker.MagicMock(
                __truediv__=mocker.MagicMock(return_value=mock_env_template)
            )
        )
        mock_config.env_file.return_value = mocker.MagicMock()

        # Should not raise AttributeError
        instance.redeploy(ports=())

    def test_redeploy_starts_new_unit_if_not_exists(self, mocker, tmp_path):
        """redeploy should start (not restart) if unit doesn't exist yet."""
        mock_config = mocker.MagicMock()
        mock_config.base_dir = mocker.MagicMock()
        mock_config.template_path = tmp_path / "template"
        mocker.patch(
            "ots_containers.commands.instance.Config", return_value=mock_config
        )
        mocker.patch(
            "ots_containers.commands.instance.systemd.discover_instances",
            return_value=[7143],
        )
        mocker.patch("ots_containers.commands.instance.assets.update")
        mocker.patch("ots_containers.commands.instance.quadlet.write_all")
        mock_start = mocker.patch(
            "ots_containers.commands.instance.systemd.start"
        )
        mock_restart = mocker.patch(
            "ots_containers.commands.instance.systemd.restart"
        )
        mocker.patch(
            "ots_containers.commands.instance.systemd.unit_exists",
            return_value=False,
        )

        mock_env_template = mocker.MagicMock()
        mock_env_template.read_text.return_value = "PORT=${PORT}"
        mock_config.base_dir.__truediv__ = mocker.MagicMock(
            return_value=mocker.MagicMock(
                __truediv__=mocker.MagicMock(return_value=mock_env_template)
            )
        )
        mock_config.env_file.return_value = mocker.MagicMock()

        instance.redeploy(ports=())

        # Should call start, not restart
        mock_start.assert_called_once_with("onetime@7143")
        mock_restart.assert_not_called()
