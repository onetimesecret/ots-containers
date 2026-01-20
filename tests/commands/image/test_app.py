# tests/commands/image/test_app.py
"""Tests for image app commands."""

import pytest


class TestImageAppImports:
    """Test image app structure."""

    def test_image_app_exists(self):
        """Test image app is defined."""
        from ots_containers.commands.image.app import app

        assert app is not None

    def test_rm_function_exists(self):
        """Test rm function is defined."""
        from ots_containers.commands.image.app import rm

        assert rm is not None

    def test_prune_function_exists(self):
        """Test prune function is defined."""
        from ots_containers.commands.image.app import prune

        assert prune is not None

    def test_ls_function_exists(self):
        """Test ls (list) function is defined."""
        from ots_containers.commands.image.app import ls

        assert ls is not None


class TestRmCommand:
    """Test rm command."""

    def test_rm_no_tags_exits(self):
        """Should exit if no tags provided."""
        from ots_containers.commands.image.app import rm

        with pytest.raises(SystemExit) as exc_info:
            rm(tags=(), yes=True)

        assert exc_info.value.code == 1

    def test_rm_aborts_without_confirmation(self, mocker, capsys):
        """Should abort if user doesn't confirm."""
        from ots_containers.commands.image.app import rm

        mocker.patch("builtins.input", return_value="n")

        rm(tags=("v0.22.0",), yes=False)

        captured = capsys.readouterr()
        assert "Aborted" in captured.out

    def test_rm_removes_image_with_yes(self, mocker, capsys):
        """Should remove image when --yes is provided."""
        from ots_containers.commands.image.app import rm

        mock_rmi = mocker.patch(
            "ots_containers.commands.image.app.podman.rmi",
        )

        rm(tags=("v0.22.0",), yes=True)

        mock_rmi.assert_called()
        captured = capsys.readouterr()
        assert "Removed" in captured.out

    def test_rm_tries_multiple_patterns(self, mocker, capsys):
        """Should try multiple image patterns."""
        from ots_containers.commands.image.app import rm

        call_count = 0

        def mock_rmi_fail_twice(*_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Image not found")
            return mocker.MagicMock()

        mocker.patch(
            "ots_containers.commands.image.app.podman.rmi",
            side_effect=mock_rmi_fail_twice,
        )

        rm(tags=("v0.22.0",), yes=True)

        assert call_count == 3  # Tried 3 patterns before success
        captured = capsys.readouterr()
        assert "Removed" in captured.out

    def test_rm_reports_not_found(self, mocker, capsys):
        """Should report when image not found."""
        from ots_containers.commands.image.app import rm

        mocker.patch(
            "ots_containers.commands.image.app.podman.rmi",
            side_effect=Exception("not found"),
        )

        rm(tags=("nonexistent",), yes=True)

        captured = capsys.readouterr()
        assert "Image not found" in captured.out

    def test_rm_with_force(self, mocker):
        """Should pass force flag to podman."""
        from ots_containers.commands.image.app import rm

        mock_rmi = mocker.patch("ots_containers.commands.image.app.podman.rmi")

        rm(tags=("v0.22.0",), force=True, yes=True)

        # Check force was passed to at least one call
        calls = mock_rmi.call_args_list
        assert any("force" in str(call) for call in calls)


class TestPruneCommand:
    """Test prune command."""

    def test_prune_aborts_without_confirmation(self, mocker, capsys):
        """Should abort if user doesn't confirm."""
        from ots_containers.commands.image.app import prune

        mocker.patch("builtins.input", return_value="n")

        prune(yes=False)

        captured = capsys.readouterr()
        assert "Aborted" in captured.out

    def test_prune_calls_podman(self, mocker, capsys):
        """Should call podman image prune."""
        from ots_containers.commands.image.app import prune

        # Mock subprocess.run since the podman wrapper calls it
        mock_run = mocker.patch(
            "ots_containers.podman.subprocess.run",
            return_value=mocker.MagicMock(stdout="removed images", returncode=0),
        )

        prune(yes=True)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "podman" in cmd
        assert "image" in cmd
        assert "prune" in cmd

        captured = capsys.readouterr()
        assert "Pruned" in captured.out

    def test_prune_with_all_flag(self, mocker, capsys):
        """Should pass all flag to podman."""
        from ots_containers.commands.image.app import prune

        # Mock subprocess.run since the podman wrapper calls it
        mock_run = mocker.patch(
            "ots_containers.podman.subprocess.run",
            return_value=mocker.MagicMock(stdout="removed images", returncode=0),
        )

        prune(all_images=True, yes=True)

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "--all" in cmd

        captured = capsys.readouterr()
        assert "Pruned" in captured.out

    def test_prune_failure_exits(self, mocker):
        """Should exit on prune failure."""
        from ots_containers.commands.image.app import prune

        mocker.patch(
            "ots_containers.podman.subprocess.run",
            side_effect=Exception("prune failed"),
        )

        with pytest.raises(SystemExit) as exc_info:
            prune(yes=True)

        assert exc_info.value.code == 1

    def test_prune_prompts_different_for_all(self, mocker, capsys):
        """Should show different prompt for --all."""
        from ots_containers.commands.image.app import prune

        mocker.patch("builtins.input", return_value="n")

        prune(all_images=True, yes=False)

        captured = capsys.readouterr()
        assert "all unused images" in captured.out

        prune(all_images=False, yes=False)

        captured = capsys.readouterr()
        assert "dangling" in captured.out


class TestLsCommand:
    """Test ls (list) command."""

    def test_ls_calls_podman(self, mocker, capsys):
        """Should call podman image list."""
        from ots_containers.commands.image.app import ls

        mocker.patch(
            "ots_containers.podman.subprocess.run",
            return_value=mocker.MagicMock(
                stdout="REPOSITORY:TAG  ID  SIZE  CREATED\nonetimesecret:v1  abc  100MB  1 day"
            ),
        )

        ls(all_tags=False, json_output=False)

        captured = capsys.readouterr()
        assert "Local images:" in captured.out

    def test_ls_with_json_output(self, mocker, capsys):
        """Should output JSON when --json flag is used."""
        from ots_containers.commands.image.app import ls

        mocker.patch(
            "ots_containers.podman.subprocess.run",
            return_value=mocker.MagicMock(stdout='[{"Names": ["onetimesecret:v1"], "Id": "abc"}]'),
        )

        ls(all_tags=False, json_output=True)

        captured = capsys.readouterr()
        assert "onetimesecret" in captured.out

    def test_ls_with_all_tags(self, mocker, capsys):
        """Should show all images when --all flag is used."""
        from ots_containers.commands.image.app import ls

        mocker.patch(
            "ots_containers.podman.subprocess.run",
            return_value=mocker.MagicMock(
                stdout="REPOSITORY:TAG  ID  SIZE  CREATED\nother:v1  def  50MB  1 day"
            ),
        )

        ls(all_tags=True, json_output=False)

        captured = capsys.readouterr()
        assert "Local images:" in captured.out
