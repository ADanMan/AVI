"""Application-wide logging helper with optional Loguru support."""

from __future__ import annotations

import contextvars
import logging
import sys
from pathlib import Path
from typing import Any

try:  # pragma: no cover - exercised through dedicated test
    from loguru import logger as _loguru_logger
except ImportError:  # pragma: no cover - executed when Loguru is absent
    _loguru_logger = None


_correlation_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "correlation_id", default=None
)


class _CorrelationIdFilter(logging.Filter):
    """Attach the current correlation ID to logging records."""

    def filter(self, record: logging.LogRecord) -> bool:  # pragma: no cover - trivial
        record.correlation_id = _correlation_id.get()
        return True


def _coerce_message(message: Any, *args: Any, **kwargs: Any) -> str:
    """Mimic Loguru's `{}` formatting semantics for the fallback logger."""

    if isinstance(message, str):
        if args or kwargs:
            try:
                return message.format(*args, **kwargs)
            except Exception:  # pragma: no cover - defensive formatting
                suffix_parts = [
                    *(str(arg) for arg in args),
                    *(f"{key}={value}" for key, value in kwargs.items()),
                ]
                suffix = f" {' '.join(suffix_parts)}" if suffix_parts else ""
                return f"{message}{suffix}"
        return message
    return str(message)


class _FallbackLogger:
    """Thin wrapper around :mod:`logging` replicating Loguru's API surface used."""

    def __init__(self) -> None:
        self._logger = logging.getLogger("avi")

    def configure(self, level: int) -> None:
        """Configure logging handlers for the fallback implementation."""

        self._logger.setLevel(level)
        self._logger.propagate = False
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.addFilter(_CorrelationIdFilter())
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)s | correlation_id=%(correlation_id)s | "
                    "%(name)s | %(message)s"
                )
            )
            self._logger.addHandler(handler)

    def debug(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._logger.debug(_coerce_message(message, *args, **kwargs))

    def info(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._logger.info(_coerce_message(message, *args, **kwargs))

    def warning(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._logger.warning(_coerce_message(message, *args, **kwargs))

    def error(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._logger.error(_coerce_message(message, *args, **kwargs))

    def exception(self, message: Any, *args: Any, **kwargs: Any) -> None:
        self._logger.exception(_coerce_message(message, *args, **kwargs))

    def bind(self, **_: Any) -> _FallbackLogger:  # pragma: no cover - compatibility
        return self

    def __getattr__(self, item: str) -> Any:  # pragma: no cover - delegated methods
        return getattr(self._logger, item)


_using_loguru = _loguru_logger is not None
logger = _loguru_logger if _using_loguru else _FallbackLogger()


def set_correlation_id(value: str | None) -> contextvars.Token[str | None]:
    """Bind a correlation ID to the current context."""

    return _correlation_id.set(value)


def reset_correlation_id(token: contextvars.Token[str | None]) -> None:
    """Reset the correlation ID context to a previous token."""

    _correlation_id.reset(token)


def get_correlation_id() -> str | None:
    """Return the correlation ID for the current execution context."""

    return _correlation_id.get()


def _debug_enabled() -> bool:
    try:
        from config.settings import settings  # type: ignore

        return bool(getattr(settings, "DEBUG", False))
    except Exception:  # pragma: no cover - defensive fallback when settings unavailable
        return False


def setup_logger() -> None:
    """Configure logging sinks for the available backend."""

    level = "DEBUG" if _debug_enabled() else "INFO"
    if _using_loguru:
        log_dir = Path("logs")
        # Use DirectoryManager to avoid duplication (lazy import to avoid circular dependency)
        try:
            from config.settings import directory_manager

            directory_manager.ensure_directory(log_dir)
        except ImportError:
            # Fallback if DirectoryManager is not available yet
            log_dir.mkdir(exist_ok=True)

        handlers = [
            {
                "sink": sys.stdout,
                "level": level,
                "serialize": True,
                "enqueue": True,
                "backtrace": False,
                "diagnose": False,
            },
            {
                "sink": log_dir / "app.log",
                "level": level,
                "serialize": True,
                "rotation": "1 day",
                "retention": "7 days",
                "compression": "zip",
                "enqueue": True,
            },
            {
                "sink": log_dir / "errors.log",
                "level": "ERROR",
                "serialize": True,
                "rotation": "1 day",
                "retention": "30 days",
                "compression": "zip",
                "enqueue": True,
            },
        ]

        logger.remove()
        logger.configure(
            handlers=handlers,
            extra={"correlation_id": None},
            patcher=lambda record: record["extra"].update(
                {"correlation_id": _correlation_id.get()}
            ),
        )
    else:
        numeric_level = logging.DEBUG if level == "DEBUG" else logging.INFO
        logger.configure(numeric_level)  # type: ignore[assignment]


# Note: setup_logger() is called explicitly in main.py:init_application()
# Do not call it here to avoid double initialization


__all__ = [
    "get_correlation_id",
    "logger",
    "reset_correlation_id",
    "set_correlation_id",
    "setup_logger",
]
