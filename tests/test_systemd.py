# tests/test_systemd.py
"""Tests for systemd module - systemctl wrapper functions."""

import subprocess

import pytest


class TestDiscoverInstances:
    """Test discover_instances function."""

    def test_discover_instances_returns_sorted_ports(self, mocker):
        """Should parse systemctl output and return sorted port list."""
        from ots_containers import systemd

        mock_result = mocker.Mock()
        mock_result.stdout = (
            "onetime@7043.service loaded active running OTS 7043\n"
            "onetime@7044.service loaded active running OTS 7044\n"
            "onetime@7042.service loaded active running OTS 7042\n"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        ports = systemd.discover_instances()

        assert ports == [7042, 7043, 7044]

    def test_discover_instances_empty_output(self, mocker):
        """Should return empty list when no instances running."""
        from ots_containers import systemd

        mock_result = mocker.Mock()
        mock_result.stdout = ""
        mocker.patch("subprocess.run", return_value=mock_result)

        ports = systemd.discover_instances()

        assert ports == []

    def test_discover_instances_ignores_malformed_lines(self, mocker):
        """Should skip lines that don't match expected format."""
        from ots_containers import systemd

        mock_result = mocker.Mock()
        mock_result.stdout = (
            "onetime@7043.service loaded active running OTS\n"
            "some-other.service loaded active running Other\n"
            "onetime@abc.service loaded active running Bad port\n"
            "onetime@7044.service loaded active running OTS\n"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        ports = systemd.discover_instances()

        assert ports == [7043, 7044]

    def test_discover_instances_filters_out_failed_units(self, mocker):
        """Should only return running units, not failed ones."""
        from ots_containers import systemd

        # Real output from: systemctl list-units onetime@* --plain --no-legend
        mock_result = mocker.Mock()
        mock_result.stdout = (
            "onetime@7043.service loaded failed failed OneTimeSecret Container 7043\n"
            "onetime@7044.service loaded failed failed OneTimeSecret Container 7044\n"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        ports = systemd.discover_instances()

        assert ports == []

    def test_discover_instances_mixed_running_and_failed(self, mocker):
        """Should return only running units when mixed with failed."""
        from ots_containers import systemd

        mock_result = mocker.Mock()
        mock_result.stdout = (
            "onetime@7042.service loaded active running OneTimeSecret Container 7042\n"
            "onetime@7043.service loaded failed failed OneTimeSecret Container 7043\n"
            "onetime@7044.service loaded active running OneTimeSecret Container 7044\n"
        )
        mocker.patch("subprocess.run", return_value=mock_result)

        ports = systemd.discover_instances()

        assert ports == [7042, 7044]

    def test_discover_instances_calls_systemctl_correctly(self, mocker):
        """Should call systemctl with correct arguments."""
        from ots_containers import systemd

        mock_result = mocker.Mock()
        mock_result.stdout = ""
        mock_run = mocker.patch("subprocess.run", return_value=mock_result)

        systemd.discover_instances()

        mock_run.assert_called_once_with(
            ["systemctl", "list-units", "onetime@*", "--plain", "--no-legend"],
            capture_output=True,
            text=True,
        )


class TestDaemonReload:
    """Test daemon_reload function."""

    def test_daemon_reload_calls_systemctl(self, mocker):
        """Should call sudo systemctl daemon-reload."""
        from ots_containers import systemd

        mock_run = mocker.patch("subprocess.run")

        systemd.daemon_reload()

        mock_run.assert_called_once_with(["sudo", "systemctl", "daemon-reload"], check=True)

    def test_daemon_reload_raises_on_failure(self, mocker):
        """Should propagate CalledProcessError on failure."""
        from ots_containers import systemd

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "cmd"),
        )

        with pytest.raises(subprocess.CalledProcessError):
            systemd.daemon_reload()


class TestStart:
    """Test start function."""

    def test_start_calls_systemctl_start(self, mocker):
        """Should call sudo systemctl start with unit name."""
        from ots_containers import systemd

        mock_run = mocker.patch("subprocess.run")

        systemd.start("onetime@7043")

        mock_run.assert_called_once_with(["sudo", "systemctl", "start", "onetime@7043"], check=True)

    def test_start_raises_on_failure(self, mocker):
        """Should propagate CalledProcessError on failure."""
        from ots_containers import systemd

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "cmd"),
        )

        with pytest.raises(subprocess.CalledProcessError):
            systemd.start("onetime@7043")


class TestStop:
    """Test stop function."""

    def test_stop_calls_systemctl_stop(self, mocker):
        """Should call sudo systemctl stop with unit name."""
        from ots_containers import systemd

        mock_run = mocker.patch("subprocess.run")

        systemd.stop("onetime@7043")

        mock_run.assert_called_once_with(["sudo", "systemctl", "stop", "onetime@7043"], check=True)

    def test_stop_raises_on_failure(self, mocker):
        """Should propagate CalledProcessError on failure."""
        from ots_containers import systemd

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "cmd"),
        )

        with pytest.raises(subprocess.CalledProcessError):
            systemd.stop("onetime@7043")


class TestRestart:
    """Test restart function."""

    def test_restart_calls_systemctl_restart(self, mocker):
        """Should call sudo systemctl restart with unit name."""
        from ots_containers import systemd

        mock_run = mocker.patch("subprocess.run")

        systemd.restart("onetime@7043")

        mock_run.assert_called_once_with(
            ["sudo", "systemctl", "restart", "onetime@7043"], check=True
        )

    def test_restart_raises_on_failure(self, mocker):
        """Should propagate CalledProcessError on failure."""
        from ots_containers import systemd

        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "cmd"),
        )

        with pytest.raises(subprocess.CalledProcessError):
            systemd.restart("onetime@7043")


class TestStatus:
    """Test status function."""

    def test_status_calls_systemctl_status(self, mocker):
        """Should call sudo systemctl status with unit name."""
        from ots_containers import systemd

        mock_run = mocker.patch("subprocess.run")

        systemd.status("onetime@7043")

        mock_run.assert_called_once_with(
            [
                "sudo",
                "systemctl",
                "--no-pager",
                "-n25",
                "status",
                "onetime@7043",
            ],
            check=False,
        )

    def test_status_custom_lines(self, mocker):
        """Should use custom line count when specified."""
        from ots_containers import systemd

        mock_run = mocker.patch("subprocess.run")

        systemd.status("onetime@7043", lines=50)

        mock_run.assert_called_once_with(
            [
                "sudo",
                "systemctl",
                "--no-pager",
                "-n50",
                "status",
                "onetime@7043",
            ],
            check=False,
        )

    def test_status_does_not_raise_on_nonzero_exit(self, mocker):
        """Should not raise when unit is not running (non-zero exit)."""
        from ots_containers import systemd

        # status returns non-zero when unit is not active
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(3, "cmd"),
        )

        # Should not raise because check=False
        # But since we're mocking with side_effect, it will raise
        # Let's fix the mock to just return normally
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value.returncode = 3

        systemd.status("onetime@7043")  # Should not raise

        mock_run.assert_called_once()


class TestUnitExists:
    """Test unit_exists function."""

    def test_unit_exists_returns_true_when_found(self, mocker):
        """Should return True when unit file exists."""
        from ots_containers import systemd

        mock_result = mocker.Mock()
        mock_result.stdout = "onetime@.container enabled enabled"
        mocker.patch("subprocess.run", return_value=mock_result)

        assert systemd.unit_exists("onetime@7043") is True

    def test_unit_exists_returns_false_when_not_found(self, mocker):
        """Should return False when unit file doesn't exist."""
        from ots_containers import systemd

        mock_result = mocker.Mock()
        mock_result.stdout = ""
        mocker.patch("subprocess.run", return_value=mock_result)

        assert systemd.unit_exists("onetime@7043") is False

    def test_unit_exists_calls_systemctl_correctly(self, mocker):
        """Should call systemctl list-unit-files with correct args."""
        from ots_containers import systemd

        mock_result = mocker.Mock()
        mock_result.stdout = ""
        mock_run = mocker.patch("subprocess.run", return_value=mock_result)

        systemd.unit_exists("onetime@7043")

        mock_run.assert_called_once_with(
            [
                "systemctl",
                "list-unit-files",
                "onetime@7043",
                "--plain",
                "--no-legend",
            ],
            capture_output=True,
            text=True,
        )
