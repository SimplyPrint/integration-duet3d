"""Initialize the duet_simplyprint_connector package."""

import importlib.metadata

try:
    __version__ = importlib.metadata.version("simplyprint_duet3d")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"
