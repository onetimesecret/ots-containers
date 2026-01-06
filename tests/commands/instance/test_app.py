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

    def test_run_function_exists(self):
        """run command should be defined."""
        assert hasattr(instance, "run")
        assert callable(instance.run)


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

    def test_instance_run_help(self, capsys):
        """instance run --help should work."""
        from ots_containers.cli import app

        with pytest.raises(SystemExit) as exc_info:
            app(["instance", "run", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "port" in captured.out.lower() or "run" in captured.out.lower()


class TestRunCommand:
    """Test run command for direct podman execution."""

    def test_run_builds_correct_command(self, mocker, tmp_path):
        """run should build correct podman command."""
        import subprocess

        # Mock Config
        mock_config = mocker.MagicMock()
        mock_config.resolve_image_tag.return_value = ("onetimesecret", "v0.23.0")
        mock_config.config_dir = tmp_path / "etc"
        mock_config.config_dir.mkdir()
        mock_config.registry = None
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)

        # Mock env file not existing
        mocker.patch(
            "ots_containers.commands.instance.app.quadlet.DEFAULT_ENV_FILE",
            tmp_path / "nonexistent",
        )

        # Mock subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="abc123")

        # Call run command in detached mode
        instance.run(port=7143, detach=True, quiet=True)

        # Verify podman run was called
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "podman"
        assert cmd[1] == "run"
        assert "-d" in cmd
        assert "--rm" in cmd
        assert "--network=host" in cmd
        assert "onetimesecret:v0.23.0" in cmd

    def test_run_includes_secrets_with_production_flag(self, mocker, tmp_path):
        """run --production should include secrets from env file."""
        import subprocess

        # Mock Config
        mock_config = mocker.MagicMock()
        mock_config.resolve_image_tag.return_value = ("onetimesecret", "latest")
        mock_config.config_dir = tmp_path / "etc"
        mock_config.config_dir.mkdir()
        mock_config.registry = None
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)

        # Create env file with secrets
        env_file = tmp_path / "onetimesecret"
        env_file.write_text("SECRET_VARIABLE_NAMES=HMAC_SECRET,API_KEY\n")
        mocker.patch(
            "ots_containers.commands.instance.app.quadlet.DEFAULT_ENV_FILE",
            env_file,
        )

        # Mock get_secrets_from_env_file (imported inside run function)
        from ots_containers.environment_file import SecretSpec

        mock_secrets = [
            SecretSpec(env_var_name="HMAC_SECRET", secret_name="ots_hmac_secret"),
            SecretSpec(env_var_name="API_KEY", secret_name="ots_api_key"),
        ]
        mocker.patch(
            "ots_containers.environment_file.get_secrets_from_env_file",
            return_value=mock_secrets,
        )

        # Mock subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="abc123")

        # Call run command with production flag
        instance.run(port=7143, detach=True, quiet=True, production=True)

        # Verify secrets were included
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "--secret" in cmd_str
        assert "ots_hmac_secret" in cmd_str

    def test_run_minimal_without_production_flag(self, mocker, tmp_path):
        """run without --production should be minimal (no secrets/volumes)."""
        import subprocess

        # Mock Config
        mock_config = mocker.MagicMock()
        mock_config.resolve_image_tag.return_value = ("onetimesecret", "latest")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)

        # Mock subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="abc123")

        # Call run command without production flag
        instance.run(port=7143, detach=True, quiet=True)

        # Verify minimal command (no secrets, no volumes)
        cmd = mock_run.call_args[0][0]
        cmd_str = " ".join(cmd)
        assert "--secret" not in cmd_str
        assert "-v" not in cmd_str
        assert "--env-file" not in cmd_str

    def test_run_prints_command_when_not_quiet(self, mocker, tmp_path, capsys):
        """run should print command when not in quiet mode."""
        import subprocess

        # Mock Config
        mock_config = mocker.MagicMock()
        mock_config.resolve_image_tag.return_value = ("onetimesecret", "latest")
        mock_config.config_dir = tmp_path / "etc"
        mock_config.config_dir.mkdir()
        mock_config.registry = None
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)

        # Mock env file not existing
        mocker.patch(
            "ots_containers.commands.instance.app.quadlet.DEFAULT_ENV_FILE",
            tmp_path / "nonexistent",
        )

        # Mock subprocess.run
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess([], 0, stdout="abc123")

        # Call run command without quiet
        instance.run(port=7143, detach=True, quiet=False)

        # Verify command was printed
        captured = capsys.readouterr()
        assert "$ podman run" in captured.out


class TestDeployCommand:
    """Test deploy command execution with mocked dependencies."""

    def test_deploy_validates_config(self, mocker):
        """deploy should validate config before proceeding."""
        mock_validate = mocker.patch(
            "ots_containers.commands.instance.app.Config.validate",
            side_effect=SystemExit("Missing required files"),
        )

        with pytest.raises(SystemExit):
            instance.deploy(ids=("7143",))

        mock_validate.assert_called_once()

    def test_deploy_calls_assets_update(self, mocker, tmp_path):
        """deploy should update assets for web containers."""
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

        instance.deploy(ids=("7143",))

        mock_assets.assert_called_once_with(mock_config, create_volume=True)
        mock_quadlet.assert_called_once_with(mock_config)


class TestDeployWorkerCommand:
    """Test deploy command with --type worker flag."""

    def test_deploy_worker_calls_write_worker_template(self, mocker, tmp_path):
        """deploy --type worker should write worker quadlet template."""
        from ots_containers.commands.instance.annotations import InstanceType

        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.worker_template_path = mocker.MagicMock()
        mock_config.worker_template_path.parent = mocker.MagicMock()
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mock_quadlet = mocker.patch(
            "ots_containers.commands.instance.app.quadlet.write_worker_template"
        )
        mocker.patch("ots_containers.commands.instance.app.systemd.start")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")

        instance.deploy(ids=("1",), instance_type=InstanceType.WORKER)

        mock_quadlet.assert_called_once_with(mock_config)

    def test_deploy_worker_does_not_update_assets(self, mocker, tmp_path):
        """deploy --type worker should NOT update static assets."""
        from ots_containers.commands.instance.annotations import InstanceType

        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.worker_template_path = mocker.MagicMock()
        mock_config.worker_template_path.parent = mocker.MagicMock()
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mock_assets = mocker.patch("ots_containers.commands.instance.app.assets.update")
        mocker.patch("ots_containers.commands.instance.app.quadlet.write_worker_template")
        mocker.patch("ots_containers.commands.instance.app.systemd.start")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")

        instance.deploy(ids=("1",), instance_type=InstanceType.WORKER)

        mock_assets.assert_not_called()

    def test_deploy_worker_starts_worker_unit(self, mocker, tmp_path):
        """deploy --type worker should start onetime-worker@{id} unit."""
        from ots_containers.commands.instance.annotations import InstanceType

        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.worker_template_path = mocker.MagicMock()
        mock_config.worker_template_path.parent = mocker.MagicMock()
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mocker.patch("ots_containers.commands.instance.app.quadlet.write_worker_template")
        mock_start = mocker.patch("ots_containers.commands.instance.app.systemd.start")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")

        instance.deploy(ids=("billing",), instance_type=InstanceType.WORKER)

        mock_start.assert_called_once_with("onetime-worker@billing")

    def test_deploy_worker_with_numeric_id(self, mocker, tmp_path):
        """deploy --type worker 1 should start onetime-worker@1 unit."""
        from ots_containers.commands.instance.annotations import InstanceType

        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.worker_template_path = mocker.MagicMock()
        mock_config.worker_template_path.parent = mocker.MagicMock()
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mocker.patch("ots_containers.commands.instance.app.quadlet.write_worker_template")
        mock_start = mocker.patch("ots_containers.commands.instance.app.systemd.start")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")

        instance.deploy(ids=("1",), instance_type=InstanceType.WORKER)

        mock_start.assert_called_once_with("onetime-worker@1")

    def test_deploy_worker_records_deployment(self, mocker, tmp_path):
        """deploy --type worker should record deployment with worker action."""
        from ots_containers.commands.instance.annotations import InstanceType

        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.worker_template_path = mocker.MagicMock()
        mock_config.worker_template_path.parent = mocker.MagicMock()
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mocker.patch("ots_containers.commands.instance.app.quadlet.write_worker_template")
        mocker.patch("ots_containers.commands.instance.app.systemd.start")
        mock_record = mocker.patch("ots_containers.commands.instance.app.db.record_deployment")

        instance.deploy(ids=("billing",), instance_type=InstanceType.WORKER)

        mock_record.assert_called_once()
        call_kwargs = mock_record.call_args[1]
        assert call_kwargs["action"] == "deploy-worker"
        assert call_kwargs["port"] == 0
        assert "worker_id=billing" in call_kwargs["notes"]

    def test_deploy_multiple_workers(self, mocker, tmp_path):
        """deploy --type worker 1 2 billing should deploy multiple workers."""
        from ots_containers.commands.instance.annotations import InstanceType

        mock_config = mocker.MagicMock()
        mock_config.config_dir = mocker.MagicMock()
        mock_config.config_yaml = mocker.MagicMock()
        mock_config.var_dir = mocker.MagicMock()
        mock_config.worker_template_path = mocker.MagicMock()
        mock_config.worker_template_path.parent = mocker.MagicMock()
        mock_config.db_path = tmp_path / "test.db"
        mock_config.resolve_image_tag.return_value = ("ghcr.io/test/image", "v1.0.0")
        mocker.patch("ots_containers.commands.instance.app.Config", return_value=mock_config)
        mocker.patch("ots_containers.commands.instance.app.quadlet.write_worker_template")
        mock_start = mocker.patch("ots_containers.commands.instance.app.systemd.start")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")

        instance.deploy(ids=("1", "2", "billing"), instance_type=InstanceType.WORKER, delay=0)

        assert mock_start.call_count == 3
        calls = [c[0][0] for c in mock_start.call_args_list]
        assert "onetime-worker@1" in calls
        assert "onetime-worker@2" in calls
        assert "onetime-worker@billing" in calls


class TestRedeployCommand:
    """Test redeploy command execution with mocked dependencies."""

    def test_redeploy_with_no_instances_found(self, mocker, capsys):
        """redeploy with no ports should discover all configured instances."""
        mocker.patch(
            "ots_containers.commands.instance._helpers.systemd.discover_instances",
            return_value=[],
        )

        instance.redeploy(ports=())

        captured = capsys.readouterr()
        assert "No configured instances found" in captured.out

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
        mocker.patch("ots_containers.commands.instance.app.systemd.recreate")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")
        mocker.patch(
            "ots_containers.commands.instance.app.systemd.container_exists",
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
        mock_recreate = mocker.patch("ots_containers.commands.instance.app.systemd.recreate")
        mocker.patch("ots_containers.commands.instance.app.db.record_deployment")
        mocker.patch(
            "ots_containers.commands.instance.app.systemd.container_exists",
            return_value=False,
        )

        # Mock the env_template read
        mock_config.env_template.read_text.return_value = "PORT=${PORT}"
        mock_config.var_dir.mkdir = mocker.MagicMock()
        mock_config.env_file.return_value = mocker.MagicMock()

        instance.redeploy(ports=())

        # Should call start, not recreate
        mock_start.assert_called_once_with("onetime@7143")
        mock_recreate.assert_not_called()


class TestEnvCommand:
    """Test env command - displays shared /etc/default/onetimesecret."""

    def test_env_function_exists(self):
        """env command should be defined."""
        assert hasattr(instance, "env")
        assert callable(instance.env)

    def test_env_displays_shared_env_file(self, mocker, capsys, tmp_path):
        """env should display the shared /etc/default/onetimesecret file."""
        from pathlib import Path

        # Create test env file
        env_file = tmp_path / "onetimesecret"
        env_file.write_text("ZZZ_VAR=last\nAAA_VAR=first\n# comment\nMMM_VAR=middle\n")

        # Patch Path to return our test file
        original_path = Path

        def mock_path(path_str):
            if path_str == "/etc/default/onetimesecret":
                return env_file
            return original_path(path_str)

        mocker.patch("pathlib.Path", side_effect=mock_path)

        instance.env()

        captured = capsys.readouterr()
        lines = captured.out.strip().split("\n")
        # Find the env var lines (skip header "=== ... ===" and empty lines)
        env_lines = [line for line in lines if "=" in line and not line.startswith("===")]
        assert env_lines == ["AAA_VAR=first", "MMM_VAR=middle", "ZZZ_VAR=last"]

    def test_env_handles_missing_file(self, mocker, capsys, tmp_path):
        """env should handle missing env file gracefully."""
        from pathlib import Path

        # Point to non-existent file
        env_file = tmp_path / "nonexistent"
        original_path = Path

        def mock_path(path_str):
            if path_str == "/etc/default/onetimesecret":
                return env_file
            return original_path(path_str)

        mocker.patch("pathlib.Path", side_effect=mock_path)

        instance.env()

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


class TestListInstancesCommand:
    """Tests for list_instances command."""

    def test_list_instances_function_exists(self):
        """list_instances function should exist."""
        assert instance.list_instances is not None

    def test_list_with_no_instances(self, mocker, capsys):
        """list should print message when no instances found."""
        mocker.patch(
            "ots_containers.commands.instance.app.systemd.discover_instances",
            return_value=[],
        )

        instance.list_instances()

        captured = capsys.readouterr()
        assert "No configured instances found" in captured.out

    def test_list_displays_header(self, mocker, capsys, tmp_path):
        """list should display table header."""
        mocker.patch(
            "ots_containers.commands.instance.app.systemd.discover_instances",
            return_value=[7043],
        )
        mocker.patch(
            "ots_containers.commands.instance.app.subprocess.run",
            return_value=mocker.Mock(stdout="active\n", stderr=""),
        )

        # Mock Config and db
        mock_config = mocker.Mock()
        mock_config.db_path = tmp_path / "test.db"
        mocker.patch(
            "ots_containers.commands.instance.app.Config",
            return_value=mock_config,
        )
        mocker.patch(
            "ots_containers.commands.instance.app.db.get_deployments",
            return_value=[],
        )

        instance.list_instances()

        captured = capsys.readouterr()
        assert "PORT" in captured.out
        assert "SERVICE" in captured.out
        assert "CONTAINER" in captured.out
        assert "STATUS" in captured.out
        assert "IMAGE:TAG" in captured.out
        assert "DEPLOYED" in captured.out
        assert "ACTION" in captured.out

    def test_list_shows_instance_details(self, mocker, capsys, tmp_path):
        """list should show instance details from systemd and database."""
        mocker.patch(
            "ots_containers.commands.instance.app.systemd.discover_instances",
            return_value=[7043],
        )
        mocker.patch(
            "ots_containers.commands.instance.app.subprocess.run",
            return_value=mocker.Mock(stdout="active\n", stderr=""),
        )

        # Mock Config
        mock_config = mocker.Mock()
        mock_config.db_path = tmp_path / "test.db"
        mocker.patch(
            "ots_containers.commands.instance.app.Config",
            return_value=mock_config,
        )

        # Mock deployment data
        from ots_containers.db import Deployment

        mock_deployment = Deployment(
            id=1,
            timestamp="2025-12-19T03:00:00.123456",
            port=7043,
            image="ghcr.io/onetimesecret/onetimesecret",
            tag="v0.24.0-rc0",
            action="deploy",
            success=True,
            notes=None,
        )
        mocker.patch(
            "ots_containers.commands.instance.app.db.get_deployments",
            return_value=[mock_deployment],
        )

        instance.list_instances()

        captured = capsys.readouterr()
        assert "7043" in captured.out
        assert "onetime@7043.service" in captured.out
        assert "onetime@7043" in captured.out
        assert "active" in captured.out
        assert "ghcr.io/onetimesecret/onetimesecret:v0.24.0-rc0" in captured.out
        assert "2025-12-19 03:00:00" in captured.out
        assert "deploy" in captured.out

    def test_list_handles_missing_deployment_data(self, mocker, capsys, tmp_path):
        """list should handle instances without deployment data."""
        mocker.patch(
            "ots_containers.commands.instance.app.systemd.discover_instances",
            return_value=[7043],
        )
        mocker.patch(
            "ots_containers.commands.instance.app.subprocess.run",
            return_value=mocker.Mock(stdout="inactive\n", stderr=""),
        )

        # Mock Config
        mock_config = mocker.Mock()
        mock_config.db_path = tmp_path / "test.db"
        mocker.patch(
            "ots_containers.commands.instance.app.Config",
            return_value=mock_config,
        )

        # No deployments found
        mocker.patch(
            "ots_containers.commands.instance.app.db.get_deployments",
            return_value=[],
        )

        instance.list_instances()

        captured = capsys.readouterr()
        assert "7043" in captured.out
        assert "onetime@7043.service" in captured.out
        assert "onetime@7043" in captured.out
        assert "inactive" in captured.out
        assert "unknown" in captured.out
        assert "n/a" in captured.out
