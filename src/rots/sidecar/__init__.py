# src/rots/sidecar/__init__.py

"""Sidecar daemon for remote OTS instance control.

The sidecar listens on both a Unix socket (for local CLI tools) and
RabbitMQ (for remote control plane commands), dispatching incoming
requests to command handlers.
"""
