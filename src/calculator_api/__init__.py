"""Calculator API package."""

from .config import Settings, load_settings
from .core import add, divide, multiply, subtract

__all__ = [
    "Settings",
    "add",
    "divide",
    "load_settings",
    "multiply",
    "subtract",
]

__version__ = "0.1.0"
