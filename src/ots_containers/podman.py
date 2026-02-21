# src/ots_containers/podman.py

"""Pythonic wrapper for podman CLI commands."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ots_shared.ssh.executor import Executor, Result


class Podman:
    """Wrapper for podman CLI commands.

    Usage:
        podman = Podman()
        podman.ps(filter="name=myapp", format="table {{.ID}}\\t{{.Names}}")
        podman.images()
        podman.inspect("container_id")
        podman.volume.create("myvolume")
        podman.volume.mount("myvolume")

    With executor (SSH support):
        from ots_shared.ssh import LocalExecutor
        p = Podman(executor=LocalExecutor())
        p.ps(capture_output=True, text=True)  # routes through executor
    """

    def __init__(
        self,
        executable: str = "podman",
        _subcommand: list[str] | None = None,
        executor: Executor | None = None,
    ):
        self.executable = executable
        self._subcommand = _subcommand or []
        self._executor = executor

    def __call__(self, *args: str, **kwargs) -> subprocess.CompletedProcess | Result:
        """Run a podman command with the given arguments.

        When executor is None (default), returns subprocess.CompletedProcess.
        When executor is set, returns ots_shared.ssh.Result.
        """
        cmd = [self.executable, *self._subcommand]
        for key, value in kwargs.items():
            if key in ("capture_output", "text", "check", "timeout"):
                continue
            flag = f"--{key.replace('_', '-')}"
            if isinstance(value, bool):
                if value:
                    cmd.append(flag)
            elif isinstance(value, list | tuple):
                for v in value:
                    cmd.extend([flag, str(v)])
            else:
                cmd.extend([flag, str(value)])
        cmd.extend(args)

        if self._executor is None:
            return subprocess.run(
                cmd,
                capture_output=kwargs.get("capture_output", False),
                text=kwargs.get("text", False),
                check=kwargs.get("check", False),
            )

        return self._executor.run(
            cmd,
            timeout=kwargs.get("timeout"),
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
            executor=self._executor,
        )


podman = Podman()
