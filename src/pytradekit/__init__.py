"""PyTradeKit public package root.

The root package deliberately exposes only the package version during the
0.1.x foundations milestone. Domain types are exported from their bounded
package surfaces instead of being promoted prematurely to the root API.
"""

__version__ = "0.1.0a1"

__all__ = ["__version__"]
