"""PyTradeKit public package root.

The root package deliberately exposes only the package version. Domain and
application types are exported from their bounded package surfaces instead of
being promoted to a broad implicit root API.
"""

__version__ = "0.6.0rc1"

__all__ = ["__version__"]
