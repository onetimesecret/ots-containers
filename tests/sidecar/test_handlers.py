# tests/sidecar/test_handlers.py

"""Tests for src/rots/sidecar/handlers.py

Covers:
- Lifecycle operations (start/stop/restart for web/worker/scheduler)
- handle_status and handle_health
- Phased restart handlers
- Rolling restart handler
- HANDLERS registry and dispatch
"""

from unittest.mock import patch

import pytest

from rots.sidecar.handlers import (
    HANDLERS,
    dispatch,
    handle_health,
    handle_restart_scheduler,
    handle_restart_web,
    handle_restart_worker,
    handle_rolling_restart,
    handle_start_scheduler,
    handle_start_web,
    handle_start_worker,
    handle_status,
    handle_stop_scheduler,
    handle_stop_web,
    handle_stop_worker,
)


class TestHandlerRegistry:
    """Tests for HANDLERS registry and dispatch."""

    def test_all_expected_handlers_registered(self):
        """All expected command handlers are in the registry."""
        expected_commands = [
            "restart.web",
            "stop.web",
            "start.web",
            "restart.worker",
            "stop.worker",
            "start.worker",
            "restart.scheduler",
            "stop.scheduler",
            "start.scheduler",
            "phased_restart.web",
            "phased_restart.worker",
            "status",
            "health",
            "rolling_restart",
        ]
        for cmd in expected_commands:
            assert cmd in HANDLERS, f"Missing handler for: {cmd}"

    def test_dispatch_unknown_command(self):
        """Dispatch returns error for unknown commands."""
        result = dispatch("unknown.command", {})

        assert result["status"] == "error"
        assert "Unknown command" in result["error"]
        assert "available_commands" in result

    def test_dispatch_calls_handler(self):
        """Dispatch routes to correct handler."""
        with patch.object(
            __import__("rots.sidecar.handlers", fromlist=["handle_health"]),
            "handle_health",
            return_value={"status": "ok", "health": "test"},
        ):
            # Access via HANDLERS dict directly
            result = dispatch("health", {"test": "param"})

            # Handler was called and returned result
            assert result["status"] == "ok"


class TestLifecycleHandlers:
    """Tests for start/stop/restart lifecycle operations."""

    @pytest.fixture
    def mock_systemd(self):
        """Mock systemd module for all lifecycle tests."""
        with patch("rots.sidecar.handlers.systemd") as mock:
            # Make unit_name return proper format
            mock.unit_name.side_effect = lambda t, i: f"onetime-{t}@{i}"
            yield mock

    def test_restart_web_success(self, mock_systemd):
        """restart.web calls systemd.restart with correct unit."""
        mock_systemd.restart.return_value = None

        result = handle_restart_web({"identifier": "7043"})

        assert result["status"] == "ok"
        assert result["unit"] == "onetime-web@7043.service"
        assert result["action"] == "restart"
        mock_systemd.restart.assert_called_once_with("onetime-web@7043.service")

    def test_restart_web_missing_identifier(self, mock_systemd):
        """restart.web fails without identifier."""
        result = handle_restart_web({})

        assert result["status"] == "error"
        assert "identifier" in result["error"].lower()

    def test_restart_web_systemd_error(self, mock_systemd):
        """restart.web reports systemd errors."""
        from rots import systemd as real_systemd

        # Use real SystemctlError class
        mock_systemd.SystemctlError = real_systemd.SystemctlError
        mock_systemd.restart.side_effect = real_systemd.SystemctlError(
            "onetime-web@7043.service",
            "restart",
            "Failed to restart: unit not found",
        )

        result = handle_restart_web({"identifier": "7043"})

        assert result["status"] == "error"
        assert "journal" in result

    def test_stop_web_success(self, mock_systemd):
        """stop.web calls systemd.stop with correct unit."""
        mock_systemd.stop.return_value = None

        result = handle_stop_web({"identifier": "7044"})

        assert result["status"] == "ok"
        assert result["action"] == "stop"
        mock_systemd.stop.assert_called_once_with("onetime-web@7044.service")

    def test_start_web_success(self, mock_systemd):
        """start.web calls systemd.start with correct unit."""
        mock_systemd.start.return_value = None

        result = handle_start_web({"identifier": "7045"})

        assert result["status"] == "ok"
        assert result["action"] == "start"
        mock_systemd.start.assert_called_once_with("onetime-web@7045.service")

    def test_restart_worker_success(self, mock_systemd):
        """restart.worker handles worker identifiers."""
        mock_systemd.restart.return_value = None

        result = handle_restart_worker({"identifier": "billing"})

        assert result["status"] == "ok"
        assert result["unit"] == "onetime-worker@billing.service"
        mock_systemd.restart.assert_called_once_with("onetime-worker@billing.service")

    def test_stop_worker_success(self, mock_systemd):
        """stop.worker calls systemd.stop for worker."""
        mock_systemd.stop.return_value = None

        result = handle_stop_worker({"identifier": "email"})

        assert result["status"] == "ok"
        mock_systemd.stop.assert_called_once_with("onetime-worker@email.service")

    def test_start_worker_success(self, mock_systemd):
        """start.worker calls systemd.start for worker."""
        mock_systemd.start.return_value = None

        result = handle_start_worker({"identifier": "notifications"})

        assert result["status"] == "ok"
        mock_systemd.start.assert_called_once_with("onetime-worker@notifications.service")

    def test_restart_scheduler_success(self, mock_systemd):
        """restart.scheduler handles scheduler unit."""
        mock_systemd.restart.return_value = None

        result = handle_restart_scheduler({"identifier": "default"})

        assert result["status"] == "ok"
        assert result["unit"] == "onetime-scheduler@default.service"

    def test_stop_scheduler_success(self, mock_systemd):
        """stop.scheduler calls systemd.stop for scheduler."""
        mock_systemd.stop.return_value = None

        result = handle_stop_scheduler({"identifier": "default"})

        assert result["status"] == "ok"

    def test_start_scheduler_success(self, mock_systemd):
        """start.scheduler calls systemd.start for scheduler."""
        mock_systemd.start.return_value = None

        result = handle_start_scheduler({"identifier": "default"})

        assert result["status"] == "ok"


class TestStatusHandler:
    """Tests for handle_status."""

    @pytest.fixture
    def mock_systemd(self):
        """Mock systemd module."""
        with patch("rots.sidecar.handlers.systemd") as mock:
            # Default mocks
            mock.discover_web_instances.return_value = [7043, 7044]
            mock.discover_worker_instances.return_value = ["billing"]
            mock.discover_scheduler_instances.return_value = ["default"]
            mock.is_active.return_value = True
            mock.get_container_health_map.return_value = {
                ("web", "7043"): {"health": "healthy", "uptime": "Up 3 days"},
                ("web", "7044"): {"health": "healthy", "uptime": "Up 1 day"},
                ("worker", "billing"): {"health": "healthy", "uptime": "Up 2 hours"},
                ("scheduler", "default"): {"health": "healthy", "uptime": "Up 5 days"},
            }
            yield mock

    def test_status_all_instances(self, mock_systemd):
        """status returns info for all instance types."""
        result = handle_status({})

        assert result["status"] == "ok"
        assert "instances" in result
        assert len(result["instances"]) == 4  # 2 web + 1 worker + 1 scheduler

    def test_status_filter_by_type(self, mock_systemd):
        """status filters by instance_type."""
        result = handle_status({"instance_type": "web"})

        assert result["status"] == "ok"
        instances = result["instances"]
        assert len(instances) == 2
        assert all(i["type"] == "web" for i in instances)

    def test_status_filter_by_identifier(self, mock_systemd):
        """status filters by specific identifier."""
        result = handle_status({"instance_type": "web", "identifier": "7043"})

        assert result["status"] == "ok"
        instances = result["instances"]
        assert len(instances) == 1
        assert instances[0]["identifier"] == "7043"

    def test_status_includes_health_info(self, mock_systemd):
        """status includes health and uptime from health map."""
        result = handle_status({"instance_type": "web", "identifier": "7043"})

        assert result["status"] == "ok"
        instance = result["instances"][0]
        assert instance["health"] == "healthy"
        assert instance["uptime"] == "Up 3 days"
        assert instance["active"] is True


class TestHealthHandler:
    """Tests for handle_health."""

    def test_health_returns_ok(self):
        """health returns basic health info."""
        result = handle_health({})

        assert result["status"] == "ok"
        assert result["health"] == "healthy"
        assert "pid" in result
        assert "timestamp" in result

    def test_health_includes_pid(self):
        """health includes current process PID."""
        import os

        result = handle_health({})

        assert result["pid"] == os.getpid()


class TestRollingRestartHandler:
    """Tests for handle_rolling_restart."""

    @pytest.fixture
    def mock_systemd(self):
        """Mock systemd module."""
        with patch("rots.sidecar.handlers.systemd") as mock:
            mock.unit_name.side_effect = lambda t, i: f"onetime-{t}@{i}"
            mock.discover_web_instances.return_value = [7043]
            mock.discover_worker_instances.return_value = ["billing"]
            mock.discover_scheduler_instances.return_value = ["default"]
            mock.restart.return_value = None
            mock.is_active.return_value = True
            mock.get_container_health_map.return_value = {
                ("web", "7043"): {"health": "healthy"},
            }
            yield mock

    def test_rolling_restart_order(self, mock_systemd):
        """rolling_restart processes workers, schedulers, then web."""
        result = handle_rolling_restart({"delay": 0, "health_check_timeout": 1})

        assert result["status"] == "ok"
        assert "workers" in result["results"]
        assert "schedulers" in result["results"]
        assert "web" in result["results"]

        # Verify order of restart calls
        calls = mock_systemd.restart.call_args_list
        assert len(calls) == 3
        # First call should be worker
        assert "worker" in str(calls[0])
        # Second should be scheduler
        assert "scheduler" in str(calls[1])
        # Third should be web
        assert "web" in str(calls[2])

    def test_rolling_restart_stops_on_web_failure(self, mock_systemd):
        """rolling_restart stops and reports partial on web failure."""
        from rots import systemd as real_systemd

        # Use real SystemctlError class
        mock_systemd.SystemctlError = real_systemd.SystemctlError

        # Make web restart fail
        def restart_side_effect(unit):
            if "web" in unit:
                raise real_systemd.SystemctlError(unit, "restart", "Failed")

        mock_systemd.restart.side_effect = restart_side_effect

        result = handle_rolling_restart({"delay": 0, "health_check_timeout": 1})

        assert result["status"] == "partial"
        assert "7043" in result["message"]


class TestPhasedRestartHandlers:
    """Tests for phased restart handlers."""

    @pytest.fixture
    def mock_systemd(self):
        """Mock systemd module."""
        with patch("rots.sidecar.handlers.systemd") as mock:
            mock.discover_web_instances.return_value = [7043, 7044]
            mock.discover_worker_instances.return_value = ["billing", "email"]
            mock.restart.return_value = None
            yield mock

    def test_phased_restart_web_discovers_instances(self, mock_systemd):
        """phased_restart.web discovers instances when not specified."""
        from rots.sidecar.handlers import handle_phased_restart_web

        result = handle_phased_restart_web({"delay": 0})

        assert result["status"] == "ok"
        assert len(result["results"]) == 2
        mock_systemd.discover_web_instances.assert_called_once()

    def test_phased_restart_web_uses_provided_ids(self, mock_systemd):
        """phased_restart.web uses provided identifiers."""
        from rots.sidecar.handlers import handle_phased_restart_web

        result = handle_phased_restart_web({"identifiers": [7043], "delay": 0})

        assert result["status"] == "ok"
        assert len(result["results"]) == 1
        # Should not call discover since identifiers provided
        mock_systemd.discover_web_instances.assert_not_called()

    def test_phased_restart_worker_discovers_instances(self, mock_systemd):
        """phased_restart.worker discovers instances when not specified."""
        from rots.sidecar.handlers import handle_phased_restart_worker

        result = handle_phased_restart_worker({"delay": 0})

        assert result["status"] == "ok"
        assert len(result["results"]) == 2
        mock_systemd.discover_worker_instances.assert_called_once()
