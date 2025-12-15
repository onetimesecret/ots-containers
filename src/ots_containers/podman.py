# src/ots_containers/podman.py

"""Pythonic wrapper for podman CLI commands."""

import subprocess


class Podman:
    """Wrapper for podman CLI commands.

    Usage:
        podman = Podman()
        podman.ps(filter="name=myapp", format="table {{.ID}}\t{{.Names}}")
        podman.images()
        podman.inspect("container_id")
        podman.volume.create("myvolume")
        podman.volume.mount("myvolume")
    """

    def __init__(
        self, executable: str = "podman", _subcommand: list[str] | None = None
    ):
        self.executable = executable
        self._subcommand = _subcommand or []

    def __call__(self, *args: str, **kwargs) -> subprocess.CompletedProcess:
        """Run a podman command with the given arguments."""
        cmd = [self.executable, *self._subcommand]
        for key, value in kwargs.items():
            if key in ("capture_output", "text", "check"):
                continue
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    cmd.append(flag)
            elif isinstance(value, (list, tuple)):
                for v in value:
                    cmd.extend([flag, str(v)])
            else:
                cmd.extend([flag, str(value)])
        cmd.extend(args)
        return subprocess.run(
            cmd,
            capture_output=kwargs.get("capture_output", False),
            text=kwargs.get("text", False),
            check=kwargs.get("check", False),
        )

    def __getattr__(self, name: str):
        """Dynamically create methods for any podman subcommand.

        Converts underscores to hyphens for subcommand names.
        Supports nested subcommands like podman.volume.create().
        """
        subcommand = name.replace("_", "-")
        return Podman(
            executable=self.executable,
            _subcommand=[*self._subcommand, subcommand],
        )


podman = Podman()
