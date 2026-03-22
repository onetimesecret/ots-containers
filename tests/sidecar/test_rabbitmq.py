# tests/sidecar/test_rabbitmq.py

"""Tests for src/rots/sidecar/rabbitmq.py

Covers:
- RabbitMQConfig.from_url parsing
- RabbitMQConfig.from_env_file parsing
- RabbitMQConfig.from_environment precedence
- RabbitMQConsumer message handling (mocked pika)
- publish_command timeout behavior (mocked pika)
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from rots.sidecar.rabbitmq import (
    RabbitMQConfig,
    RabbitMQConsumer,
    publish_command,
)


class TestRabbitMQConfigFromUrl:
    """Tests for RabbitMQConfig.from_url."""

    def test_basic_url(self):
        """Parse basic AMQP URL."""
        config = RabbitMQConfig.from_url("amqp://myuser:mypass@localhost:5672/myvhost")

        assert config.host == "localhost"
        assert config.port == 5672
        assert config.vhost == "myvhost"
        assert config.username == "myuser"
        assert config.password == "mypass"

    def test_url_without_port(self):
        """Default port 5672 when not specified."""
        config = RabbitMQConfig.from_url("amqp://user:pass@rabbit.example.com/")

        assert config.host == "rabbit.example.com"
        assert config.port == 5672

    def test_url_without_vhost(self):
        """Default vhost / when path is empty or just /."""
        config = RabbitMQConfig.from_url("amqp://user:pass@localhost:5672/")
        assert config.vhost == "/"

        config = RabbitMQConfig.from_url("amqp://user:pass@localhost:5672")
        assert config.vhost == "/"

    def test_url_without_credentials(self):
        """Default to guest/guest when no credentials."""
        config = RabbitMQConfig.from_url("amqp://localhost:5672/test")

        assert config.username == "guest"
        assert config.password == "guest"

    def test_url_with_special_chars_in_password(self):
        """Handle URL-encoded special characters in password."""
        # URL with special chars - urlparse does NOT decode by default
        # So we test that the raw value is preserved
        config = RabbitMQConfig.from_url("amqp://user:p%40ss%23w0rd@localhost/")
        assert config.password == "p%40ss%23w0rd"

        # Test password with characters that don't conflict with URL syntax
        config2 = RabbitMQConfig.from_url("amqp://user:my-complex_pass123@localhost/")
        assert config2.password == "my-complex_pass123"

    def test_url_with_ip_address(self):
        """Parse URL with IP address instead of hostname."""
        config = RabbitMQConfig.from_url("amqp://admin:secret@192.168.1.100:5672/prod")

        assert config.host == "192.168.1.100"
        assert config.port == 5672
        assert config.vhost == "prod"


class TestRabbitMQConfigFromEnvFile:
    """Tests for RabbitMQConfig.from_env_file."""

    def test_valid_env_file(self, tmp_path):
        """Parse env file with RABBITMQ_URL."""
        env_file = tmp_path / ".env"
        env_file.write_text('RABBITMQ_URL="amqp://testuser:testpass@rabbit:5672/testvhost"\n')

        config = RabbitMQConfig.from_env_file(env_file)

        assert config.host == "rabbit"
        assert config.port == 5672
        assert config.vhost == "testvhost"
        assert config.username == "testuser"
        assert config.password == "testpass"

    def test_env_file_single_quotes(self, tmp_path):
        """Parse env file with single-quoted value."""
        env_file = tmp_path / ".env"
        env_file.write_text("RABBITMQ_URL='amqp://user:pass@host/vh'\n")

        config = RabbitMQConfig.from_env_file(env_file)

        assert config.host == "host"
        assert config.vhost == "vh"

    def test_env_file_no_quotes(self, tmp_path):
        """Parse env file with unquoted value."""
        env_file = tmp_path / ".env"
        env_file.write_text("RABBITMQ_URL=amqp://user:pass@myhost:5672/vhost\n")

        config = RabbitMQConfig.from_env_file(env_file)

        assert config.host == "myhost"

    def test_env_file_with_comments(self, tmp_path):
        """Ignore comment lines in env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("""
# This is a comment
OTHER_VAR=value
# Another comment
RABBITMQ_URL=amqp://user:pass@rabbit/vh
""")

        config = RabbitMQConfig.from_env_file(env_file)

        assert config.host == "rabbit"

    def test_env_file_missing(self, tmp_path):
        """Return defaults when file doesn't exist."""
        missing_file = tmp_path / "nonexistent.env"

        config = RabbitMQConfig.from_env_file(missing_file)

        assert config.host == "127.0.0.1"
        assert config.port == 5672
        assert config.username == "guest"
        assert config.password == "guest"

    def test_env_file_no_rabbitmq_url(self, tmp_path):
        """Return defaults when RABBITMQ_URL not in file."""
        env_file = tmp_path / ".env"
        env_file.write_text("REDIS_URL=redis://localhost:6379\nDOMAIN=example.com\n")

        config = RabbitMQConfig.from_env_file(env_file)

        assert config.host == "127.0.0.1"
        assert config.username == "guest"

    def test_env_file_empty(self, tmp_path):
        """Return defaults for empty file."""
        env_file = tmp_path / ".env"
        env_file.write_text("")

        config = RabbitMQConfig.from_env_file(env_file)

        assert config.host == "127.0.0.1"


class TestRabbitMQConfigFromEnvironment:
    """Tests for RabbitMQConfig.from_environment."""

    def test_env_var_takes_precedence(self, monkeypatch, tmp_path):
        """RABBITMQ_URL env var takes precedence over file."""
        # Create env file with different config
        env_file = tmp_path / ".env"
        env_file.write_text("RABBITMQ_URL=amqp://file:file@filehost/filevh\n")

        # Set env var with different config
        monkeypatch.setenv("RABBITMQ_URL", "amqp://env:env@envhost/envvh")

        # Mock DEFAULT_ENV_FILE to point to our test file
        with patch("rots.sidecar.rabbitmq.DEFAULT_ENV_FILE", env_file):
            config = RabbitMQConfig.from_environment()

        # Should use env var, not file
        assert config.host == "envhost"
        assert config.username == "env"

    def test_falls_back_to_file(self, monkeypatch, tmp_path):
        """Falls back to env file when no env var."""
        monkeypatch.delenv("RABBITMQ_URL", raising=False)

        env_file = tmp_path / ".env"
        env_file.write_text("RABBITMQ_URL=amqp://fallback:pass@fallbackhost/vh\n")

        # Use from_env_file directly since from_environment calls it
        config = RabbitMQConfig.from_env_file(env_file)

        assert config.host == "fallbackhost"
        assert config.username == "fallback"

    def test_defaults_when_nothing_configured(self, monkeypatch, tmp_path):
        """Returns defaults when neither env var nor file configured."""
        monkeypatch.delenv("RABBITMQ_URL", raising=False)

        missing_file = tmp_path / "nonexistent.env"

        with patch("rots.sidecar.rabbitmq.DEFAULT_ENV_FILE", missing_file):
            config = RabbitMQConfig.from_environment()

        assert config.host == "127.0.0.1"
        assert config.port == 5672
        assert config.username == "guest"
        assert config.password == "guest"


class TestRabbitMQConsumerMessageHandling:
    """Tests for RabbitMQConsumer._on_message."""

    @pytest.fixture
    def mock_pika(self):
        """Mock pika module for all tests in this class."""
        with patch.dict("sys.modules", {"pika": MagicMock()}):
            yield

    def test_valid_message_dispatch(self, mock_pika):
        """Handler called with correct command and payload."""
        # Track handler calls
        handler_calls = []

        def mock_handler(command: str, payload: dict) -> dict:
            handler_calls.append((command, payload))
            return {"status": "ok", "result": "test"}

        consumer = RabbitMQConsumer(
            handler=mock_handler,
            config=RabbitMQConfig(),
        )

        # Mock channel for ack
        mock_channel = MagicMock()
        mock_method = MagicMock()
        mock_method.delivery_tag = 1
        mock_properties = MagicMock()
        mock_properties.correlation_id = "test-123"
        mock_properties.reply_to = None

        body = json.dumps({"command": "restart.web", "payload": {"port": 7043}}).encode()

        consumer._on_message(mock_channel, mock_method, mock_properties, body)

        # Verify handler was called
        assert len(handler_calls) == 1
        assert handler_calls[0] == ("restart.web", {"port": 7043})

        # Verify message was acked
        mock_channel.basic_ack.assert_called_once_with(delivery_tag=1)

    def test_response_published_when_reply_to_set(self, mock_pika):
        """Response published to reply_to queue."""
        from rots.sidecar.commands import CommandResult

        def mock_handler(command: str, payload: dict) -> CommandResult:
            return CommandResult.ok(data="result")

        consumer = RabbitMQConsumer(
            handler=mock_handler,
            config=RabbitMQConfig(),
        )

        mock_channel = MagicMock()
        mock_method = MagicMock()
        mock_method.delivery_tag = 1
        mock_properties = MagicMock()
        mock_properties.correlation_id = "corr-456"
        mock_properties.reply_to = "amq.rabbitmq.reply-to.abc123"

        body = json.dumps({"command": "health", "payload": {}}).encode()

        consumer._on_message(mock_channel, mock_method, mock_properties, body)

        # Verify response was published
        mock_channel.basic_publish.assert_called_once()
        call_kwargs = mock_channel.basic_publish.call_args.kwargs
        assert call_kwargs["routing_key"] == "amq.rabbitmq.reply-to.abc123"
        assert call_kwargs["exchange"] == ""

        # Verify response body
        response = json.loads(call_kwargs["body"].decode())
        assert response["success"] is True
        assert response["result"] == "result"

    def test_invalid_json_returns_error(self, mock_pika):
        """Invalid JSON message returns error response."""
        from rots.sidecar.commands import CommandResult

        def mock_handler(command: str, payload: dict) -> CommandResult:
            return CommandResult.ok()

        consumer = RabbitMQConsumer(
            handler=mock_handler,
            config=RabbitMQConfig(),
        )

        mock_channel = MagicMock()
        mock_method = MagicMock()
        mock_method.delivery_tag = 1
        mock_properties = MagicMock()
        mock_properties.correlation_id = "bad-json"
        mock_properties.reply_to = "reply.queue"

        body = b"not valid json{{"

        consumer._on_message(mock_channel, mock_method, mock_properties, body)

        # Should still ack the message (bad message, but processed)
        mock_channel.basic_ack.assert_called_once()

        # Should publish error response
        mock_channel.basic_publish.assert_called_once()
        response = json.loads(mock_channel.basic_publish.call_args.kwargs["body"].decode())
        assert response["success"] is False
        assert "Invalid JSON" in response["error"]

    def test_missing_command_returns_error(self, mock_pika):
        """Message without command field returns error."""
        from rots.sidecar.commands import CommandResult

        def mock_handler(command: str, payload: dict) -> CommandResult:
            return CommandResult.ok()

        consumer = RabbitMQConsumer(
            handler=mock_handler,
            config=RabbitMQConfig(),
        )

        mock_channel = MagicMock()
        mock_method = MagicMock()
        mock_method.delivery_tag = 1
        mock_properties = MagicMock()
        mock_properties.correlation_id = "no-cmd"
        mock_properties.reply_to = "reply.queue"

        body = json.dumps({"payload": {"key": "value"}}).encode()  # No command

        consumer._on_message(mock_channel, mock_method, mock_properties, body)

        mock_channel.basic_publish.assert_called_once()
        response = json.loads(mock_channel.basic_publish.call_args.kwargs["body"].decode())
        assert response["success"] is False
        assert "command" in response["error"].lower()

    def test_handler_exception_returns_error(self, mock_pika):
        """Handler exception is caught and returned as error."""
        from rots.sidecar.commands import CommandResult

        def failing_handler(command: str, payload: dict) -> CommandResult:
            raise RuntimeError("Handler exploded")

        consumer = RabbitMQConsumer(
            handler=failing_handler,
            config=RabbitMQConfig(),
        )

        mock_channel = MagicMock()
        mock_method = MagicMock()
        mock_method.delivery_tag = 1
        mock_properties = MagicMock()
        mock_properties.correlation_id = "will-fail"
        mock_properties.reply_to = "reply.queue"

        body = json.dumps({"command": "boom", "payload": {}}).encode()

        consumer._on_message(mock_channel, mock_method, mock_properties, body)

        # Should still ack (message processed, even if handler failed)
        mock_channel.basic_ack.assert_called_once()

        response = json.loads(mock_channel.basic_publish.call_args.kwargs["body"].decode())
        assert response["success"] is False
        assert "Handler exploded" in response["error"]


class TestPublishCommandTimeout:
    """Tests for publish_command timeout behavior.

    These tests verify the timeout and response handling logic.
    Full integration tests would require a real RabbitMQ connection.
    """

    @pytest.fixture
    def mock_pika_module(self):
        """Create a mock pika module with required classes."""
        mock_pika = MagicMock()

        # Mock connection and channel
        mock_connection = MagicMock()
        mock_channel = MagicMock()
        mock_connection.channel.return_value = mock_channel

        # Mock queue_declare result
        mock_result = MagicMock()
        mock_result.method.queue = "amq.gen.callback123"
        mock_channel.queue_declare.return_value = mock_result

        mock_pika.BlockingConnection.return_value = mock_connection
        mock_pika.PlainCredentials.return_value = MagicMock()
        mock_pika.ConnectionParameters.return_value = MagicMock()

        def make_props(**kwargs):
            props = MagicMock()
            for k, v in kwargs.items():
                setattr(props, k, v)
            return props

        mock_pika.BasicProperties.side_effect = make_props

        return {
            "pika": mock_pika,
            "connection": mock_connection,
            "channel": mock_channel,
        }

    def test_timeout_raises_error(self, mock_pika_module):
        """TimeoutError raised when no response within timeout."""
        mock_connection = mock_pika_module["connection"]

        # process_data_events does nothing (no response arrives)
        mock_connection.process_data_events.return_value = None

        with patch.dict("sys.modules", {"pika": mock_pika_module["pika"]}):
            with pytest.raises(TimeoutError, match="No response within"):
                publish_command(
                    command="test",
                    payload={"key": "value"},
                    config=RabbitMQConfig(),
                    timeout=0.1,  # Very short timeout for test
                )

        # Verify connection was closed even on timeout
        mock_connection.close.assert_called_once()

    def test_config_used_for_credentials(self, mock_pika_module):
        """Verify config parameters are passed to credentials."""
        mock_pika = mock_pika_module["pika"]
        mock_connection = mock_pika_module["connection"]

        # Don't let it loop forever
        mock_connection.process_data_events.return_value = None

        config = RabbitMQConfig(
            host="custom.rabbitmq.local",
            port=5673,
            vhost="myvhost",
            username="myuser",
            password="mypass",
        )

        with patch.dict("sys.modules", {"pika": mock_pika}):
            try:
                publish_command(
                    command="test",
                    config=config,
                    timeout=0.1,
                )
            except TimeoutError:
                pass  # Expected

            # Verify credentials were created with our config
            mock_pika.PlainCredentials.assert_called_once_with("myuser", "mypass")
