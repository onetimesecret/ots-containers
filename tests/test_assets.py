# tests/test_assets.py
"""Tests for assets module - exposing the volume.mount bug."""

import subprocess

import pytest

from ots_containers import assets
from ots_containers.config import Config


class TestAssetsUpdate:
    """Test the assets.update function."""

    def test_update_raises_user_friendly_error_on_volume_mount_failure(self, mocker):
        """Volume mount failure should raise SystemExit with helpful message.

        Currently broken: raises raw CalledProcessError with traceback.
        Expected: raises SystemExit with user-friendly error message.

        Reproduces:
            $ ots-containers assets sync
            # Should show: "Failed to mount volume 'static_assets': <reason>"
            # Instead shows: raw Python traceback
        """
        mock_run = mocker.patch("subprocess.run")

        mock_run.side_effect = [
            subprocess.CompletedProcess(
                args=["podman", "volume", "create", "static_assets"],
                returncode=0,
            ),
            subprocess.CalledProcessError(
                returncode=1,
                cmd=["podman", "volume", "mount", "static_assets"],
                output="",
                stderr="Error: volume static_assets does not exist",
            ),
        ]

        cfg = mocker.MagicMock(spec=Config)
        cfg.image_with_tag = "ghcr.io/onetimesecret/onetimesecret:current"

        with pytest.raises(SystemExit) as exc_info:
            assets.update(cfg, create_volume=True)

        # Should contain helpful context, not just exit code
        error_msg = str(exc_info.value)
        assert "volume" in error_msg.lower() or "mount" in error_msg.lower()

    def test_update_volume_mount_returns_empty_path(self, mocker):
        """Test behavior when volume mount returns empty stdout."""
        mock_run = mocker.patch("subprocess.run")

        mock_run.side_effect = [
            # volume.create succeeds
            subprocess.CompletedProcess(
                args=["podman", "volume", "create", "static_assets"],
                returncode=0,
            ),
            # volume.mount returns empty path
            subprocess.CompletedProcess(
                args=["podman", "volume", "mount", "static_assets"],
                returncode=0,
                stdout="",
            ),
            # podman.create succeeds
            subprocess.CompletedProcess(
                args=["podman", "create", "image:tag"],
                returncode=0,
                stdout="abc123\n",
            ),
            # podman.cp succeeds
            subprocess.CompletedProcess(
                args=["podman", "cp", "abc123:/app/public/.", "/"],
                returncode=0,
            ),
            # podman.rm succeeds
            subprocess.CompletedProcess(
                args=["podman", "rm", "abc123"],
                returncode=0,
            ),
        ]

        cfg = mocker.MagicMock(spec=Config)
        cfg.image_with_tag = "ghcr.io/onetimesecret/onetimesecret:current"

        # This will use empty path "/" which is dangerous
        assets.update(cfg, create_volume=True)

        # Verify podman.cp was called with empty/current dir path (dangerous!)
        cp_call = mock_run.call_args_list[3]
        # When stdout is empty, Path("").strip() becomes "." (current dir)
        assert cp_call[0][0][3] == "."  # Empty path becomes current dir

    def test_update_without_create_volume(self, mocker):
        """Test update skips volume creation when create_volume=False."""
        mock_run = mocker.patch("subprocess.run")

        mock_run.side_effect = [
            # volume.mount succeeds (no volume.create call)
            subprocess.CompletedProcess(
                args=["podman", "volume", "mount", "static_assets"],
                returncode=0,
                stdout="/var/lib/containers/storage/volumes/static_assets/_data\n",
            ),
            # podman.create succeeds
            subprocess.CompletedProcess(
                args=["podman", "create", "image:tag"],
                returncode=0,
                stdout="abc123\n",
            ),
            # podman.cp succeeds
            subprocess.CompletedProcess(
                args=["podman", "cp", "abc123:/app/public/.", "..."],
                returncode=0,
            ),
            # podman.rm succeeds
            subprocess.CompletedProcess(
                args=["podman", "rm", "abc123"],
                returncode=0,
            ),
        ]

        cfg = mocker.MagicMock(spec=Config)
        cfg.image_with_tag = "ghcr.io/onetimesecret/onetimesecret:current"

        assets.update(cfg, create_volume=False)

        # First call should be volume.mount, not volume.create
        first_call = mock_run.call_args_list[0]
        assert "mount" in first_call[0][0]
        assert "create" not in first_call[0][0]

    def test_update_cleans_up_container_on_cp_failure(self, mocker):
        """Test container is removed even when cp fails."""
        mock_run = mocker.patch("subprocess.run")

        mock_run.side_effect = [
            # volume.mount succeeds
            subprocess.CompletedProcess(
                args=["podman", "volume", "mount", "static_assets"],
                returncode=0,
                stdout="/var/lib/containers/storage/volumes/static_assets/_data\n",
            ),
            # podman.create succeeds
            subprocess.CompletedProcess(
                args=["podman", "create", "image:tag"],
                returncode=0,
                stdout="container123\n",
            ),
            # podman.cp fails
            subprocess.CalledProcessError(
                returncode=125,
                cmd=["podman", "cp", "container123:/app/public/.", "..."],
                stderr="Error: no such container",
            ),
            # podman.rm should still be called (cleanup)
            subprocess.CompletedProcess(
                args=["podman", "rm", "container123"],
                returncode=0,
            ),
        ]

        cfg = mocker.MagicMock(spec=Config)
        cfg.image_with_tag = "ghcr.io/onetimesecret/onetimesecret:current"

        with pytest.raises(subprocess.CalledProcessError):
            assets.update(cfg, create_volume=False)

        # Verify rm was called for cleanup despite cp failure
        rm_call = mock_run.call_args_list[3]
        assert "rm" in rm_call[0][0]
        assert "container123" in rm_call[0][0]
