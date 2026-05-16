"""Pytest configuration and fallbacks for the test suite."""

from __future__ import annotations

import os
import sys

# ── Test environment defaults ──────────────────────────────────────────────
# Must be set before any AVI module is imported.  Individual test files may
# also set these at the top, but this conftest guarantees they are present
# for any execution order.
os.environ.setdefault("AVI_TEST_MODE", "1")
os.environ.setdefault("REQUIRE_API_KEY", "false")

# ── sys.path ───────────────────────────────────────────────────────────────
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# AVI repo root must be first so its namespace 'src' package wins.
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# research_toolkit exposes modules under research_toolkit/src/.
# We add research_toolkit/src directly (NOT research_toolkit/) to avoid the
# research_toolkit/src/__init__.py shadowing AVI's own 'src' namespace package.
_RTK_SRC = os.path.join(_REPO, "research_toolkit", "src")
if _RTK_SRC not in sys.path:
    sys.path.append(_RTK_SRC)


# The test suite prefers to run with ``pytest-asyncio``.  In some execution
# environments (for example, where only ``requirements.main.txt`` is installed)
# the plugin might be missing which causes ``@pytest.mark.asyncio`` tests to
# fail during collection.  We attempt to import the plugin first; if it is not
# available we register a very small fallback that provides enough behaviour for
# our asynchronous tests.
try:  # pragma: no cover - simply guards optional dependency import.
    import pytest_asyncio  # type: ignore  # noqa: F401
except ImportError:  # pragma: no cover - executed only when plugin missing.
    import asyncio
    import inspect

    import pytest

    @pytest.hookimpl(tryfirst=True)
    def pytest_configure(config: pytest.Config) -> None:
        """Register the ``asyncio`` marker when the plugin is unavailable."""

        config.addinivalue_line(
            "markers",
            "asyncio: mark a test function as using the asyncio event loop",
        )

    @pytest.hookimpl(tryfirst=True)
    def pytest_pyfunc_call(pyfuncitem: pytest.Function) -> bool | None:
        """Execute coroutine test functions using a dedicated event loop.

        This mirrors the minimal behaviour we need from ``pytest-asyncio`` so
        that our async tests keep working when the third-party plugin is not
        installed.  The hook returns ``True`` to signal that the call has been
        handled and pytest should not try to execute the test again.
        """

        test_function = pyfuncitem.obj
        if not (inspect.iscoroutinefunction(test_function) or "asyncio" in pyfuncitem.keywords):
            return None

        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            loop.run_until_complete(test_function(**pyfuncitem.funcargs))
            loop.run_until_complete(loop.shutdown_asyncgens())
        finally:
            asyncio.set_event_loop(None)
            loop.close()
        return True
