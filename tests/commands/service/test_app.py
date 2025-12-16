# tests/commands/service/test_app.py
"""Tests for service command app."""

from unittest.mock import MagicMock, patch

from ots_containers.commands.service.app import (
    _default,
    app,
    disable,
    enable,
    init,
    list_instances,
    logs,
    restart,
    start,
    status,
    stop,
)


class TestServiceAppExists:
    """Tests for service app structure."""

    def test_app_exists(self):
        """Test service app is defined."""
        assert app is not None
        assert app.name == ("service",)

    def test_init_command_exists(self):
        """Test init command is registered."""
        assert init is not None

    def test_enable_command_exists(self):
        """Test enable command is registered."""
        assert enable is not None

    def test_disable_command_exists(self):
        """Test disable command is registered."""
        assert disable is not None

    def test_start_command_exists(self):
        """Test start command is registered."""
        assert start is not None

    def test_stop_command_exists(self):
        """Test stop command is registered."""
        assert stop is not None

    def test_restart_command_exists(self):
        """Test restart command is registered."""
        assert restart is not None

    def test_status_command_exists(self):
        """Test status command is registered."""
        assert status is not None

    def test_logs_command_exists(self):
        """Test logs command is registered."""
        assert logs is not None

    def test_list_command_exists(self):
        """Test list command is registered."""
        assert list_instances is not None


class TestDefaultCommand:
    """Tests for default command."""

    def test_default_prints_packages(self, capsys):
        """Test default command lists available packages."""
        _default()
        captured = capsys.readouterr()
        assert "Available packages:" in captured.out
        assert "valkey" in captured.out
        assert "redis" in captured.out


class TestInitCommand:
    """Tests for init command."""

    @patch("ots_containers.commands.service.app.systemctl")
    @patch("ots_containers.commands.service.app.create_secrets_file")
    @patch("ots_containers.commands.service.app.ensure_data_dir")
    @patch("ots_containers.commands.service.app.update_config_value")
    @patch("ots_containers.commands.service.app.copy_default_config")
    def test_init_calls_copy_default_config(
        self, mock_copy, mock_update, mock_data, mock_secrets, mock_systemctl, capsys, tmp_path
    ):
        """Test init copies default config."""
        mock_copy.return_value = tmp_path / "test.conf"
        mock_data.return_value = tmp_path / "data"
        mock_secrets.return_value = None

        init("valkey", "6379", start=False, enable=False)

        mock_copy.assert_called_once()
        call_args = mock_copy.call_args
        assert call_args[0][0].name == "valkey"
        assert call_args[0][1] == "6379"

    @patch("ots_containers.commands.service.app.systemctl")
    @patch("ots_containers.commands.service.app.create_secrets_file")
    @patch("ots_containers.commands.service.app.ensure_data_dir")
    @patch("ots_containers.commands.service.app.update_config_value")
    @patch("ots_containers.commands.service.app.copy_default_config")
    def test_init_updates_port_and_bind(
        self, mock_copy, mock_update, mock_data, mock_secrets, mock_systemctl, tmp_path
    ):
        """Test init updates port and bind in config."""
        mock_copy.return_value = tmp_path / "test.conf"
        mock_data.return_value = tmp_path / "data"
        mock_secrets.return_value = None

        init("valkey", "6379", port=6379, bind="0.0.0.0", start=False, enable=False)

        # Check update_config_value was called for port and bind
        call_keys = [call[0][1] for call in mock_update.call_args_list]
        assert "port" in call_keys
        assert "bind" in call_keys

    @patch("ots_containers.commands.service.app.systemctl")
    @patch("ots_containers.commands.service.app.create_secrets_file")
    @patch("ots_containers.commands.service.app.add_secrets_include")
    @patch("ots_containers.commands.service.app.ensure_data_dir")
    @patch("ots_containers.commands.service.app.update_config_value")
    @patch("ots_containers.commands.service.app.copy_default_config")
    def test_init_creates_secrets_file(
        self,
        mock_copy,
        mock_update,
        mock_data,
        mock_add_include,
        mock_secrets,
        mock_systemctl,
        tmp_path,
    ):
        """Test init creates secrets file when not skipped."""
        mock_copy.return_value = tmp_path / "test.conf"
        mock_data.return_value = tmp_path / "data"
        mock_secrets.return_value = tmp_path / "test.secrets"

        init("valkey", "6379", no_secrets=False, start=False, enable=False)

        mock_secrets.assert_called_once()

    @patch("ots_containers.commands.service.app.systemctl")
    @patch("ots_containers.commands.service.app.create_secrets_file")
    @patch("ots_containers.commands.service.app.ensure_data_dir")
    @patch("ots_containers.commands.service.app.update_config_value")
    @patch("ots_containers.commands.service.app.copy_default_config")
    def test_init_skips_secrets_with_no_secrets(
        self, mock_copy, mock_update, mock_data, mock_secrets, mock_systemctl, tmp_path
    ):
        """Test init skips secrets file with --no-secrets."""
        mock_copy.return_value = tmp_path / "test.conf"
        mock_data.return_value = tmp_path / "data"

        init("valkey", "6379", no_secrets=True, start=False, enable=False)

        mock_secrets.assert_not_called()

    @patch("ots_containers.commands.service.app.systemctl")
    @patch("ots_containers.commands.service.app.create_secrets_file")
    @patch("ots_containers.commands.service.app.ensure_data_dir")
    @patch("ots_containers.commands.service.app.update_config_value")
    @patch("ots_containers.commands.service.app.copy_default_config")
    def test_init_enables_service(
        self, mock_copy, mock_update, mock_data, mock_secrets, mock_systemctl, tmp_path
    ):
        """Test init enables service when enable=True."""
        mock_copy.return_value = tmp_path / "test.conf"
        mock_data.return_value = tmp_path / "data"
        mock_secrets.return_value = None

        init("valkey", "6379", enable=True, start=False)

        mock_systemctl.assert_called()
        calls = [str(call) for call in mock_systemctl.call_args_list]
        assert any("enable" in call for call in calls)

    @patch("ots_containers.commands.service.app.systemctl")
    @patch("ots_containers.commands.service.app.create_secrets_file")
    @patch("ots_containers.commands.service.app.ensure_data_dir")
    @patch("ots_containers.commands.service.app.update_config_value")
    @patch("ots_containers.commands.service.app.copy_default_config")
    def test_init_starts_service(
        self, mock_copy, mock_update, mock_data, mock_secrets, mock_systemctl, tmp_path
    ):
        """Test init starts service when start=True."""
        mock_copy.return_value = tmp_path / "test.conf"
        mock_data.return_value = tmp_path / "data"
        mock_secrets.return_value = None

        init("valkey", "6379", enable=False, start=True)

        mock_systemctl.assert_called()
        calls = [str(call) for call in mock_systemctl.call_args_list]
        assert any("start" in call for call in calls)


class TestEnableCommand:
    """Tests for enable command."""

    @patch("ots_containers.commands.service.app.systemctl")
    def test_enable_calls_systemctl(self, mock_systemctl, capsys):
        """Test enable calls systemctl enable."""
        enable("valkey", "6379")

        mock_systemctl.assert_called_once_with("enable", "valkey-server@6379.service")

    @patch("ots_containers.commands.service.app.systemctl")
    def test_enable_prints_enabled(self, mock_systemctl, capsys):
        """Test enable prints enabled message."""
        enable("valkey", "6379")

        captured = capsys.readouterr()
        assert "Enabling" in captured.out
        assert "Enabled" in captured.out


class TestDisableCommand:
    """Tests for disable command."""

    @patch("ots_containers.commands.service.app.systemctl")
    def test_disable_calls_systemctl(self, mock_systemctl, capsys):
        """Test disable calls systemctl stop and disable."""
        disable("valkey", "6379")

        # Should call stop then disable
        assert mock_systemctl.call_count >= 2


class TestStartCommand:
    """Tests for start command."""

    @patch("ots_containers.commands.service.app.systemctl")
    def test_start_calls_systemctl(self, mock_systemctl, capsys):
        """Test start calls systemctl start."""
        start("valkey", "6379")

        mock_systemctl.assert_called_once_with("start", "valkey-server@6379.service")


class TestStopCommand:
    """Tests for stop command."""

    @patch("ots_containers.commands.service.app.systemctl")
    def test_stop_calls_systemctl(self, mock_systemctl, capsys):
        """Test stop calls systemctl stop."""
        stop("valkey", "6379")

        mock_systemctl.assert_called_once_with("stop", "valkey-server@6379.service")


class TestRestartCommand:
    """Tests for restart command."""

    @patch("ots_containers.commands.service.app.systemctl")
    def test_restart_calls_systemctl(self, mock_systemctl, capsys):
        """Test restart calls systemctl restart."""
        restart("valkey", "6379")

        mock_systemctl.assert_called_once_with("restart", "valkey-server@6379.service")


class TestStatusCommand:
    """Tests for status command."""

    @patch("ots_containers.commands.service.app.systemctl")
    def test_status_calls_systemctl_with_instance(self, mock_systemctl, capsys):
        """Test status calls systemctl status for specific instance."""
        mock_systemctl.return_value = MagicMock(stdout="active", stderr="")

        status("valkey", "6379")

        mock_systemctl.assert_called_once_with("status", "valkey-server@6379.service", check=False)

    @patch("subprocess.run")
    def test_status_lists_all_without_instance(self, mock_run, capsys):
        """Test status lists all instances when no instance given."""
        mock_run.return_value = MagicMock(stdout="", stderr="")

        status("valkey", None)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "list-units" in call_args


class TestLogsCommand:
    """Tests for logs command."""

    @patch("subprocess.run")
    def test_logs_calls_journalctl(self, mock_run):
        """Test logs calls journalctl."""
        logs("valkey", "6379")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "journalctl" in call_args
        assert "-u" in call_args
        assert "valkey-server@6379.service" in call_args

    @patch("subprocess.run")
    def test_logs_with_follow(self, mock_run):
        """Test logs with follow flag."""
        logs("valkey", "6379", follow=True)

        call_args = mock_run.call_args[0][0]
        assert "-f" in call_args

    @patch("subprocess.run")
    def test_logs_with_lines(self, mock_run):
        """Test logs with lines parameter."""
        logs("valkey", "6379", lines=100)

        call_args = mock_run.call_args[0][0]
        assert "-n" in call_args
        assert "100" in call_args


class TestListCommand:
    """Tests for list command."""

    @patch("ots_containers.commands.service.app.is_service_enabled")
    @patch("ots_containers.commands.service.app.is_service_active")
    @patch("subprocess.run")
    def test_list_calls_systemctl(self, mock_run, mock_active, mock_enabled, capsys):
        """Test list calls systemctl list-units."""
        mock_run.return_value = MagicMock(stdout="")

        list_instances("valkey")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "list-units" in call_args
        assert "--type=service" in call_args
