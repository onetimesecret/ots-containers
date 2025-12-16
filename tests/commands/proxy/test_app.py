# tests/commands/proxy/test_app.py
"""Tests for proxy app commands."""

import pytest


class TestRenderCommand:
    """Test render command."""

    def test_render_dry_run_prints_output(self, tmp_path, mocker, capsys):
        """Should print rendered content in dry-run mode."""
        from ots_containers.commands.proxy.app import render

        template = tmp_path / "test.template"
        template.write_text("Hello $WORLD")

        # Patch where it's used, not where it's defined
        mocker.patch(
            "ots_containers.commands.proxy.app.render_template",
            return_value="Hello Rendered",
        )

        render(template=template, output=tmp_path / "out", dry_run=True)

        captured = capsys.readouterr()
        assert "Hello Rendered" in captured.out

    def test_render_writes_to_output(self, tmp_path, mocker, capsys):
        """Should write rendered content to output file."""
        from ots_containers.commands.proxy.app import render

        template = tmp_path / "test.template"
        template.write_text("Hello $WORLD")
        output = tmp_path / "output.conf"

        mocker.patch(
            "ots_containers.commands.proxy.app.render_template",
            return_value="Hello Rendered",
        )
        mocker.patch("ots_containers.commands.proxy.app.validate_caddy_config")

        render(template=template, output=output, dry_run=False)

        assert output.exists()
        assert output.read_text() == "Hello Rendered"
        captured = capsys.readouterr()
        assert "[ok]" in captured.out

    def test_render_validates_before_writing(self, tmp_path, mocker):
        """Should call validate_caddy_config before writing."""
        from ots_containers.commands.proxy.app import render

        template = tmp_path / "test.template"
        template.write_text("Hello")
        output = tmp_path / "output.conf"

        mocker.patch(
            "ots_containers.commands.proxy.app.render_template",
            return_value="rendered content",
        )
        mock_validate = mocker.patch("ots_containers.commands.proxy.app.validate_caddy_config")

        render(template=template, output=output, dry_run=False)

        mock_validate.assert_called_once_with("rendered content")

    def test_render_error_exits(self, tmp_path, mocker):
        """Should exit with error message on ProxyError."""
        from ots_containers.commands.proxy._helpers import ProxyError
        from ots_containers.commands.proxy.app import render

        template = tmp_path / "test.template"
        template.write_text("Hello")

        mocker.patch(
            "ots_containers.commands.proxy.app.render_template",
            side_effect=ProxyError("test error"),
        )

        with pytest.raises(SystemExit) as exc_info:
            render(template=template, output=tmp_path / "out", dry_run=False)

        assert "[error]" in str(exc_info.value)
        assert "test error" in str(exc_info.value)

    def test_render_uses_config_defaults(self, mocker):
        """Should use Config paths when no args provided."""
        from pathlib import Path

        from ots_containers.commands.proxy.app import render
        from ots_containers.config import Config

        mock_render = mocker.patch(
            "ots_containers.commands.proxy.app.render_template",
            return_value="content",
        )
        mocker.patch("ots_containers.commands.proxy.app.validate_caddy_config")
        # Mock the file write
        mocker.patch.object(Path, "write_text")
        mocker.patch.object(Path, "mkdir")

        cfg = Config()

        render(template=None, output=None, dry_run=False)

        mock_render.assert_called_once_with(cfg.proxy_template)


class TestReloadCommand:
    """Test reload command."""

    def test_reload_calls_helper(self, mocker, capsys):
        """Should call reload_caddy helper."""
        from ots_containers.commands.proxy.app import reload

        mock_reload = mocker.patch("ots_containers.commands.proxy.app.reload_caddy")

        reload()

        mock_reload.assert_called_once()
        captured = capsys.readouterr()
        assert "[ok]" in captured.out

    def test_reload_error_exits(self, mocker):
        """Should exit with error message on ProxyError."""
        from ots_containers.commands.proxy._helpers import ProxyError
        from ots_containers.commands.proxy.app import reload

        mocker.patch(
            "ots_containers.commands.proxy.app.reload_caddy",
            side_effect=ProxyError("reload failed"),
        )

        with pytest.raises(SystemExit) as exc_info:
            reload()

        assert "[error]" in str(exc_info.value)
        assert "reload failed" in str(exc_info.value)
