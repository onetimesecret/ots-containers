# tests/commands/instance/test_app.py
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
        assert "port" in captured.out.lower() or "deploy" in captured.out.lower()

    def test_instance_redeploy_help(self, capsys):
        """instance redeploy --help should work."""
        from ots_containers.cli import app

        with pytest.raises(SystemExit) as exc_info:
            app(["instance", "redeploy", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "force" in captured.out.lower() or "redeploy" in captured.out.lower()


class TestDeployCommand:
    """Test deploy command execution with mocked dependencies."""

    def test_deploy_validates_config(self, mocker):
        """deploy should validate config before proceeding."""
        mock_validate = mocker.patch(
            "ots_containers.commands.instance.app.Config.validate",
            side_effect=SystemExit("Missing required files"),
        )

        with pytest.raises(SystemExit):
            instance.deploy(ports=(7143,))

        mock_validate.assert_called_once()

    def test_deploy_calls_assets_update(self, mocker, tmp_path):
        """deploy should update assets."""
        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.env_template = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.template_path = mocker.MagicMock()
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mock_assets = mocker.patch("ots_containers.commands.instance.app.assets.update")
        mock_quadlet = mocker.patch("ots_containers.commands.instance.app.quadlet.write_template")
        _mock_systemd = mocker.patch("ots_containers.commands.instance.app.systemd.start")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")
        mock_config.env_file.return_value = mocker.MagicMock()
        mock_config.env_file.return_value.write_text = mocker.MagicMock()

        # Mock the env_template read
        mock_config.env_template.read_text.return_value = "PORT=${PORT}"
        mock_config.var_dir.mkdir = mocker.MagicMock()

        instance.deploy(ports=(7143,))

        mock_assets.assert_called_once_with(mock_config, create_volume=True)
        mock_quadlet.assert_called_once_with(mock_config)


class TestRedeployCommand:
    """Test redeploy command execution with mocked dependencies."""

    def test_redeploy_with_no_instances_found(self, mocker, capsys):
        """redeploy with no ports should discover instances."""
        mocker.patch(
            "ots_containers.commands.instance._helpers.systemd.discover_instances",
            return_value=[],
        )

        instance.redeploy(ports=())

        captured = capsys.readouterr()
        assert "No running instances found" in captured.out

    def test_redeploy_uses_cfg_template_path(self, mocker, tmp_path):
        """redeploy should use cfg.template_path (not quadlet.template_path)."""
        # This test verifies the fix for the AttributeError
        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.env_template = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.template_path = tmp_path / "template"
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mocker.patch(
            "ots_containers.commands.instance._helpers.systemd.discover_instances",
            return_value=[7143],
        )
        mocker.patch("ots_containers.commands.instance.app.assets.update")
        mocker.patch("ots_containers.commands.instance.app.quadlet.write_template")
        mocker.patch("ots_containers.commands.instance.app.systemd.restart")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")
        mocker.patch(
            "ots_containers.commands.instance.app.systemd.unit_exists",
            return_value=True,
        )

        # Mock the env_template read
        mock_config.env_template.read_text.return_value = "PORT=${PORT}"
        mock_config.var_dir.mkdir = mocker.MagicMock()
        mock_config.env_file.return_value = mocker.MagicMock()

        # Should not raise AttributeError
        instance.redeploy(ports=())

    def test_redeploy_starts_new_unit_if_not_exists(self, mocker, tmp_path):
        """redeploy should start (not restart) if unit doesn't exist yet."""
        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.env_template = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.template_path = tmp_path / "template"
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mocker.patch(
            "ots_containers.commands.instance._helpers.systemd.discover_instances",
            return_value=[7143],
        )
        mocker.patch("ots_containers.commands.instance.app.assets.update")
        mocker.patch("ots_containers.commands.instance.app.quadlet.write_template")
        mock_start = mocker.patch("ots_containers.commands.instance.app.systemd.start")
        mock_restart = mocker.patch("ots_containers.commands.instance.app.systemd.restart")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")
        mocker.patch(
            "ots_containers.commands.instance.app.systemd.unit_exists",
            return_value=False,
        )

        # Mock the env_template read
        mock_config.env_template.read_text.return_value = "PORT=${PORT}"
        mock_config.var_dir.mkdir = mocker.MagicMock()
        mock_config.env_file.return_value = mocker.MagicMock()

        instance.redeploy(ports=())

        # Should call start, not restart
        mock_start.assert_called_once_with("onetime@7143")
        mock_restart.assert_not_called()


class TestEnvCommand:
    """Test env command."""

    def test_env_function_exists(self):
        """env command should be defined."""
        assert hasattr(instance, "env")
        assert callable(instance.env)

    def test_env_with_no_instances(self, mocker, capsys):
        """env with no running instances should report none found."""
        mocker.patch(
            "ots_containers.commands.instance._helpers.systemd.discover_instances",
            return_value=[],
        )
        instance.env(ports=())
        captured = capsys.readouterr()
        assert "No running instances found" in captured.out

    def test_env_displays_sorted_env_vars(self, mocker, capsys, tmp_path):
        """env should display sorted environment variables."""
        mock_config = mocker.MagicMock()
        env_file = tmp_path / ".env-7043"
        env_file.write_text("ZZZ_VAR=last\nAAA_VAR=first\n# comment\nMMM_VAR=middle\n")
        mock_config.env_file.return_value = env_file
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)

        instance.env(ports=(7043,))

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Find the env var lines (skip header "=== ... ===" and empty lines)
        env_lines = [l for l in lines if "=" in l and not l.startswith("===")]
        assert env_lines == ["AAA_VAR=first", "MMM_VAR=middle", "ZZZ_VAR=last"]

    def test_env_handles_missing_file(self, mocker, capsys, tmp_path):
        """env should handle missing .env file gracefully."""
        mock_config = mocker.MagicMock()
        env_file = tmp_path / ".env-7043"  # Does not exist
        mock_config.env_file.return_value = env_file
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)

        instance.env(ports=(7043,))

        captured = capsys.readouterr()
        assert "(file not found)" in captured.out


class TestExecCommand:
    """Test exec command."""

    def test_exec_shell_function_exists(self):
        """exec_shell command should be defined."""
        assert hasattr(instance, "exec_shell")
        assert callable(instance.exec_shell)

    def test_exec_with_no_instances(self, mocker, capsys):
        """exec with no running instances should report none found."""
        mocker.patch(
            "ots_containers.commands.instance._helpers.systemd.discover_instances",
            return_value=[],
        )
        instance.exec_shell(ports=())
        captured = capsys.readouterr()
        assert "No running instances found" in captured.out

    def test_exec_calls_podman_exec(self, mocker, capsys):
        """exec should call podman exec with correct container name."""
        mock_run = mocker.patch("ots_containers.commands.instance.app.subprocess.run")
        mocker.patch.dict("os.environ", {"SHELL": "/bin/bash"})

        instance.exec_shell(ports=(7043,))

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[:3] == ["podman", "exec", "-it"]
        assert "onetime@7043" in call_args
        assert "/bin/bash" in call_args

    def test_exec_uses_custom_command(self, mocker, capsys):
        """exec should use custom command when provided."""
        mock_run = mocker.patch("ots_containers.commands.instance.app.subprocess.run")

        instance.exec_shell(ports=(7043,), command="/bin/sh")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "/bin/sh" in call_args
