# src/ots_containers/__init__.py

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("ots-containers")
except PackageNotFoundError:
    __version__ = "0.0.0+dev"
