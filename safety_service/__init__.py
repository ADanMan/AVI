"""Safety service package providing HTTP and gRPC interfaces."""

from .app import create_app


__all__ = ["create_app"]
