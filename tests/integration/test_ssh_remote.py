# tests/integration/test_ssh_remote.py
"""Integration tests exercising remote code paths through FakeSSHServer.

These tests use the FakeSSHServer fixture (paramiko server mode) to run
SSHExecutor against a real transport layer without requiring a remote host.
They verify that the remote executor wiring in db and systemd modules works
end-to-end through the SSH transport.

Unlike unit tests that mock executor.run(), these tests exercise:
- SSHExecutor command serialisation (shlex quoting)
- Paramiko transport round-trip
- sqlite3 CLI invocation patterns (scripted responses)
- Remote branch selection in db/systemd modules
"""

from __future__ import annotations

import json

from ots_shared.ssh.executor import SSHExecutor


class TestSSHExecutorBasic:
    """Verify SSHExecutor works against FakeSSHServer."""

    def test_echo_roundtrip(self, fake_ssh_server):
        """SSHExecutor.run should capture stdout from the remote command."""
        fake_ssh_server.add_response("echo", stdout="hello\n")
        client = fake_ssh_server.connect()
        try:
            executor = SSHExecutor(client)
            result = executor.run(["echo", "hello"])
            assert result.ok
            assert result.stdout.strip() == "hello"
        finally:
            client.close()

    def test_non_zero_exit(self, fake_ssh_server):
        """SSHExecutor.run should capture non-zero exit codes."""
        fake_ssh_server.add_response("false", exit_code=1)
        client = fake_ssh_server.connect()
        try:
            executor = SSHExecutor(client)
            result = executor.run(["false"])
            assert not result.ok
            assert result.returncode == 1
        finally:
            client.close()


class TestDbRemoteViaSsh:
    """Test db module remote paths through a real SSH transport.

    FakeSSHServer returns scripted sqlite3 responses so we can verify
    the db module's remote query/execute wiring end-to-end.
    """

    def test_get_previous_tags_via_ssh(self, fake_ssh_server, tmp_path):
        """get_previous_tags with SSHExecutor should parse sqlite3 -json output."""
        from ots_containers import db

        # Script the sqlite3 response
        fake_ssh_server.add_response(
            "sqlite3",
            stdout=json.dumps(
                [
                    {"image": "img", "tag": "v2", "last_used": "2026-01-02 00:00:00"},
                    {"image": "img", "tag": "v1", "last_used": "2026-01-01 00:00:00"},
                ]
            ),
        )

        client = fake_ssh_server.connect()
        try:
            executor = SSHExecutor(client)
            db_path = tmp_path / "remote.db"
            tags = db.get_previous_tags(db_path, executor=executor)

            assert len(tags) == 2
            assert tags[0] == ("img", "v2", "2026-01-02 00:00:00")
            assert tags[1] == ("img", "v1", "2026-01-01 00:00:00")
        finally:
            client.close()

    def test_get_alias_via_ssh(self, fake_ssh_server, tmp_path):
        """get_alias with SSHExecutor should parse alias JSON from sqlite3."""
        from ots_containers import db

        fake_ssh_server.add_response(
            "sqlite3",
            stdout=json.dumps(
                [
                    {
                        "alias": "CURRENT",
                        "image": "ghcr.io/org/app",
                        "tag": "v3.0.0",
                        "set_at": "2026-01-20 10:00:00",
                    }
                ]
            ),
        )

        client = fake_ssh_server.connect()
        try:
            executor = SSHExecutor(client)
            db_path = tmp_path / "remote.db"
            alias = db.get_alias(db_path, "CURRENT", executor=executor)

            assert alias is not None
            assert alias.image == "ghcr.io/org/app"
            assert alias.tag == "v3.0.0"
        finally:
            client.close()

    def test_get_alias_not_found_via_ssh(self, fake_ssh_server, tmp_path):
        """get_alias with SSHExecutor should return None for empty result."""
        from ots_containers import db

        # Empty response = no rows
        fake_ssh_server.add_response("sqlite3", stdout="")

        client = fake_ssh_server.connect()
        try:
            executor = SSHExecutor(client)
            db_path = tmp_path / "remote.db"
            alias = db.get_alias(db_path, "NONEXISTENT", executor=executor)

            assert alias is None
        finally:
            client.close()


class TestSystemdRemoteViaSsh:
    """Test systemd module remote paths through a real SSH transport."""

    def test_require_systemctl_via_ssh(self, fake_ssh_server):
        """require_systemctl with SSHExecutor should pass when 'which' succeeds."""
        from ots_containers import systemd

        fake_ssh_server.add_response("which", stdout="/usr/bin/systemctl\n")

        client = fake_ssh_server.connect()
        try:
            executor = SSHExecutor(client)
            # Should not raise
            systemd.require_systemctl(executor=executor)
        finally:
            client.close()

    def test_require_podman_via_ssh(self, fake_ssh_server):
        """require_podman with SSHExecutor should pass when 'which' succeeds."""
        from ots_containers import systemd

        fake_ssh_server.add_response("which", stdout="/usr/bin/podman\n")

        client = fake_ssh_server.connect()
        try:
            executor = SSHExecutor(client)
            # Should not raise
            systemd.require_podman(executor=executor)
        finally:
            client.close()
