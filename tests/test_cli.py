# tests/test_cli.py
"""Tests for CLI structure and invocation following Cyclopts conventions."""

import pytest

from ots_containers.cli import app


class TestCLIStructure:
    """Test CLI app structure and help output."""

    def test_app_has_version(self):
        """App should expose version."""
        import re

        assert app.version is not None
        version = (
            app.version if isinstance(app.version, str) else str(app.version)
        )

        assert re.match(r"^\d+\.\d+\.\d+$", version)

    def test_app_has_help(self):
        """App should have help text."""
        assert app.help is not None
        assert "Podman" in app.help or "OTS" in app.help

    def test_help_exits_zero(self, capsys):
        """--help should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            app(["--help"])
        assert exc_info.value.code == 0

    def test_version_exits_zero(self, capsys):
        """--version should exit with code 0."""
        with pytest.raises(SystemExit) as exc_info:
            app(["--version"])
        assert exc_info.value.code == 0

    def test_version_output(self, capsys):
        """--version should print version string."""
        with pytest.raises(SystemExit):
            app(["--version"])
        captured = capsys.readouterr()
        assert "0.2.0" in captured.out


class TestCLISubcommands:
    """Test CLI subcommand routing."""

    def test_instance_subcommand_exists(self, capsys):
        """instance subcommand should exist."""
        with pytest.raises(SystemExit) as exc_info:
            app(["instance", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert (
            "instance" in captured.out.lower()
            or "deploy" in captured.out.lower()
        )

    def test_assets_subcommand_exists(self, capsys):
        """assets subcommand should exist."""
        with pytest.raises(SystemExit) as exc_info:
            app(["assets", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert (
            "assets" in captured.out.lower() or "sync" in captured.out.lower()
        )

    def test_invalid_subcommand_fails(self):
        """Invalid subcommand should fail."""
        with pytest.raises(SystemExit) as exc_info:
            app(["nonexistent"])
        assert exc_info.value.code != 0


class TestAssetsSync:
    """Test assets sync command invocation."""

    def test_assets_sync_help(self, capsys):
        """assets sync --help should show create-volume option."""
        with pytest.raises(SystemExit) as exc_info:
            app(["assets", "sync", "--help"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert (
            "create-volume" in captured.out.lower()
            or "volume" in captured.out.lower()
        )

    def test_assets_sync_requires_valid_config(self, mocker, tmp_path):
        """assets sync should validate config before running."""
        # Mock Config.validate to raise SystemExit (missing files)
        mock_validate = mocker.patch(
            "ots_containers.commands.assets.Config.validate",
            side_effect=SystemExit("Missing required files"),
        )

        with pytest.raises(SystemExit) as exc_info:
            app(["assets", "sync"])

        mock_validate.assert_called_once()
        assert "Missing" in str(exc_info.value)
