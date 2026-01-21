# tests/commands/image/test_build.py
"""Tests for image build command.

These tests verify the build command functionality for building
OTS container images from source with proper version detection
and podman buildx invocation.
"""

import json
import subprocess

import pytest

from ots_containers.commands.image.app import build


class TestBuildVersionDetection:
    """Test version extraction from package.json."""

    def test_build_detects_version_from_package_json(self, mocker, tmp_path):
        """build should extract version from package.json."""
        # Create a mock project directory with package.json
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        # Mock subprocess.run for git and podman
        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        # Mock Config
        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(project_dir=project_dir, quiet=True)

        # Verify podman buildx was called with the version tag
        calls = mock_run.call_args_list
        buildx_calls = [c for c in calls if "buildx" in str(c)]
        assert len(buildx_calls) >= 1
        # Check that v0.25.0 is in the tag
        assert any("v0.25.0" in str(c) for c in buildx_calls)

    def test_build_uses_git_hash_for_dev_version(self, mocker, tmp_path):
        """build should use git commit hash for dev versions (0.0.0-rc0, etc.)."""
        # Create a mock project directory with dev version
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.0.0-rc0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        # Mock git rev-parse and status to return a commit hash
        git_hash = "abc12345"

        def mock_run_side_effect(cmd, *args, **kwargs):
            if "git" in cmd and "rev-parse" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout=git_hash + "\n", stderr="")
            if "git" in cmd and "status" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")  # Clean
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_side_effect)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(project_dir=project_dir, quiet=True)

        # Verify the git hash was used in the tag
        calls = [str(call) for call in mock_run.call_args_list]
        # Should have git rev-parse, status, and buildx calls
        assert any("rev-parse" in c for c in calls)
        buildx_calls = [c for c in calls if "buildx" in c]
        assert len(buildx_calls) >= 1
        assert any(git_hash in c for c in buildx_calls)


class TestBuildValidation:
    """Test project directory validation."""

    def test_build_validates_project_directory_missing_containerfile(self, mocker, tmp_path):
        """build should error when Containerfile is missing."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        # Create package.json but no Containerfile
        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        with pytest.raises(SystemExit) as exc:
            build(project_dir=project_dir)
        assert "No Containerfile or Dockerfile" in str(exc.value)

    def test_build_validates_project_directory_missing_package_json(self, mocker, tmp_path):
        """build should error when package.json is missing."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        # Create Containerfile but no package.json
        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        with pytest.raises(SystemExit) as exc:
            build(project_dir=project_dir)
        assert "No package.json" in str(exc.value)

    def test_build_validates_project_directory_not_exists(self, mocker, tmp_path):
        """build should error when project directory doesn't exist."""
        project_dir = tmp_path / "nonexistent"

        with pytest.raises(SystemExit) as exc:
            build(project_dir=project_dir)
        assert "not found" in str(exc.value)


class TestBuildPodmanInvocation:
    """Test podman buildx command building."""

    def test_build_runs_podman_buildx(self, mocker, tmp_path):
        """build should invoke podman buildx build with correct arguments."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(project_dir=project_dir, quiet=True)

        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]

        # Should use podman buildx build
        assert "podman" in call_args
        assert "buildx" in call_args
        assert "build" in call_args

    def test_build_with_push_requires_registry(self, mocker, tmp_path, capsys):
        """build --push without registry should error."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,  # No registry configured
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        with pytest.raises(SystemExit) as exc:
            build(project_dir=project_dir, push=True)
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "--push requires --registry" in captured.out

    def test_build_with_push_and_registry(self, mocker, tmp_path):
        """build --push with registry should tag and push the image."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry="registry.example.com",
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(project_dir=project_dir, push=True, quiet=True)

        # Verify podman tag and push were called
        calls = [str(call) for call in mock_run.call_args_list]
        assert any("tag" in c for c in calls)
        assert any("push" in c for c in calls)

    def test_build_custom_platform(self, mocker, tmp_path):
        """build --platform should override default platform."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(project_dir=project_dir, platform="linux/arm64", quiet=True)

        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]

        # Should include custom platform
        assert "--platform" in call_args
        platform_idx = call_args.index("--platform")
        assert call_args[platform_idx + 1] == "linux/arm64"

    def test_build_custom_tag(self, mocker, tmp_path):
        """build --tag should override version-based tag."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(project_dir=project_dir, tag="custom-tag", quiet=True)

        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]

        # Should use custom tag instead of version
        assert "custom-tag" in " ".join(call_args)
        # Should NOT use the package.json version
        assert "v0.25.0" not in " ".join(call_args)


class TestBuildDefaultBehavior:
    """Test default behavior and sensible defaults."""

    def test_build_uses_current_directory_by_default(self, mocker, tmp_path, monkeypatch):
        """build with no project_dir should use current working directory."""
        # Set up the current directory as a valid project
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        # Change to the project directory
        monkeypatch.chdir(project_dir)

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        # Call without project_dir argument
        build(quiet=True)

        mock_run.assert_called()

    def test_build_default_platform_multi_arch(self, mocker, tmp_path):
        """build should default to linux/amd64,linux/arm64 platforms."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(project_dir=project_dir, quiet=True)

        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]

        # Should include default multi-arch platform
        assert "--platform" in call_args
        platform_idx = call_args.index("--platform")
        assert "linux/amd64" in call_args[platform_idx + 1]
        assert "linux/arm64" in call_args[platform_idx + 1]

    def test_build_uses_local_image_name(self, mocker, tmp_path):
        """build should use onetimesecret:{tag} as local image name."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(project_dir=project_dir, quiet=True)

        mock_run.assert_called()
        call_args = " ".join(mock_run.call_args[0][0])

        # Should include local image name with version tag
        assert "onetimesecret:v0.25.0" in call_args


class TestBuildErrorHandling:
    """Test error handling during build process."""

    def test_build_handles_podman_failure(self, mocker, tmp_path, capsys):
        """build should handle podman build failures gracefully."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        mock_run = mocker.patch("subprocess.run")
        mock_run.side_effect = subprocess.CalledProcessError(1, "podman")

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        with pytest.raises(SystemExit) as exc:
            build(project_dir=project_dir)
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Build failed" in captured.out

    def test_build_handles_invalid_package_json(self, mocker, tmp_path):
        """build should handle malformed package.json gracefully."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text("{ invalid json }")

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        with pytest.raises(SystemExit) as exc:
            build(project_dir=project_dir)
        assert "Invalid package.json" in str(exc.value)

    def test_build_handles_missing_version_in_package_json(self, mocker, tmp_path):
        """build should handle package.json without version field."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"name": "onetimesecret"}))

        containerfile = project_dir / "Containerfile"
        containerfile.write_text("FROM ruby:3.2\n")

        with pytest.raises(SystemExit) as exc:
            build(project_dir=project_dir)
        assert "No 'version' field" in str(exc.value)


class TestBuildVariants:
    """Test building image variants (lite, s6)."""

    def test_build_lite_variant_with_custom_dockerfile(self, mocker, tmp_path):
        """build -f docker/variants/lite.dockerfile --suffix -lite should work."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        # Create the lite dockerfile in a subdirectory
        docker_dir = project_dir / "docker" / "variants"
        docker_dir.mkdir(parents=True)
        lite_dockerfile = docker_dir / "lite.dockerfile"
        lite_dockerfile.write_text("FROM ruby:3.2-slim\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(
            project_dir=project_dir,
            dockerfile="docker/variants/lite.dockerfile",
            suffix="-lite",
            quiet=True,
        )

        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]

        # Should include --file flag
        assert "--file" in call_args
        file_idx = call_args.index("--file")
        assert "lite.dockerfile" in call_args[file_idx + 1]

        # Should use -lite suffix in image name
        assert "--tag" in call_args
        tag_idx = call_args.index("--tag")
        assert "onetimesecret-lite:" in call_args[tag_idx + 1]

    def test_build_s6_variant_with_target(self, mocker, tmp_path):
        """build --target final-s6 --suffix -s6 should work."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        # Main Dockerfile with multi-stage
        dockerfile = project_dir / "Dockerfile"
        dockerfile.write_text("FROM ruby:3.2 AS base\nFROM base AS final-s6\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry=None,
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(
            project_dir=project_dir,
            target="final-s6",
            suffix="-s6",
            quiet=True,
        )

        mock_run.assert_called()
        call_args = mock_run.call_args[0][0]

        # Should include --target flag
        assert "--target" in call_args
        target_idx = call_args.index("--target")
        assert call_args[target_idx + 1] == "final-s6"

        # Should use -s6 suffix in image name
        assert "--tag" in call_args
        tag_idx = call_args.index("--tag")
        assert "onetimesecret-s6:" in call_args[tag_idx + 1]

    def test_build_custom_dockerfile_not_found(self, mocker, tmp_path):
        """build with non-existent dockerfile should error."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        # No Dockerfile created

        with pytest.raises(SystemExit) as exc:
            build(
                project_dir=project_dir,
                dockerfile="nonexistent.dockerfile",
            )
        assert "Dockerfile not found" in str(exc.value)

    def test_build_variant_push_with_suffix(self, mocker, tmp_path):
        """build --push with suffix should push suffixed image name."""
        project_dir = tmp_path / "onetimesecret"
        project_dir.mkdir()

        package_json = project_dir / "package.json"
        package_json.write_text(json.dumps({"version": "0.25.0"}))

        dockerfile = project_dir / "Dockerfile"
        dockerfile.write_text("FROM ruby:3.2\n")

        var_dir = tmp_path / "var"
        var_dir.mkdir()

        def mock_run_factory(cmd, *args, **kwargs):
            if "git" in cmd:
                return subprocess.CompletedProcess(cmd, 0, stdout="abc12345\n", stderr="")
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

        mock_run = mocker.patch("subprocess.run", side_effect=mock_run_factory)

        mocker.patch(
            "ots_containers.commands.image.app.Config",
            return_value=mocker.Mock(
                db_path=var_dir / "deployments.db",
                registry="registry.example.com",
                registry_auth_file=tmp_path / "auth.json",
            ),
        )
        mocker.patch("ots_containers.commands.image.app.db.record_deployment")

        build(
            project_dir=project_dir,
            suffix="-lite",
            push=True,
            quiet=True,
        )

        # Verify the push command uses suffixed image name
        calls = [str(call) for call in mock_run.call_args_list]
        push_calls = [c for c in calls if "push" in c]
        assert len(push_calls) >= 1
        assert any("onetimesecret-lite" in c for c in push_calls)
