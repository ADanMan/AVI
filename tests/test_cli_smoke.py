from __future__ import annotations

import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from click.testing import CliRunner

import avi.cli as avi_cli


runner = CliRunner()


@pytest.fixture(autouse=True)
def restore_cli_providers() -> None:
    avi_cli.reset_providers()
    yield
    avi_cli.reset_providers()


async def _async_stub(result: Any = None) -> Any:
    return result


def test_index_data_command_invokes_provider() -> None:
    calls: list[str] = []

    async def stub_index() -> dict[str, Any]:
        calls.append("index")
        return {"ok": True}

    avi_cli.set_providers(
        avi_cli.CLIProviders(
            index_data_runner=lambda: stub_index(),
            setup_data_runner=lambda _path: None,
            benchmark_runner=lambda _models=None, _benchmarks=None: _async_stub(),
        )
    )

    result = runner.invoke(avi_cli.app, ["index-data"])

    assert result.exit_code == 0
    assert "Indexing completed." in result.output
    assert calls == ["index"]


def test_setup_data_command_accepts_output_dir(tmp_path: Path) -> None:
    captured: list[Path] = []

    def stub_setup(path: Path) -> None:
        captured.append(path)

    avi_cli.set_providers(
        avi_cli.CLIProviders(
            index_data_runner=lambda: _async_stub({}),
            setup_data_runner=stub_setup,
            benchmark_runner=lambda _models=None, _benchmarks=None: _async_stub(),
        )
    )

    result = runner.invoke(avi_cli.app, ["setup-data", "--output-dir", str(tmp_path / "out")])

    assert result.exit_code == 0
    assert captured and captured[0] == tmp_path / "out"


def test_run_benchmarks_command_invokes_provider() -> None:
    calls: list[str] = []

    async def stub_benchmarks(models: Any = None, benchmarks: Any = None) -> None:
        calls.append((models, benchmarks))

    avi_cli.set_providers(
        avi_cli.CLIProviders(
            index_data_runner=lambda: _async_stub({}),
            setup_data_runner=lambda _path: None,
            benchmark_runner=lambda models=None, benchmarks=None: stub_benchmarks(
                models=models,
                benchmarks=benchmarks,
            ),
        )
    )

    result = runner.invoke(avi_cli.app, ["run-benchmarks"])

    assert result.exit_code == 0
    assert "Benchmarks finished." in result.output
    assert calls == [(None, None)]


def test_run_benchmarks_command_accepts_filters() -> None:
    captured: list[tuple[Any, Any]] = []

    async def stub_benchmarks(models: Any = None, benchmarks: Any = None) -> None:
        captured.append((models, benchmarks))

    avi_cli.set_providers(
        avi_cli.CLIProviders(
            index_data_runner=lambda: _async_stub({}),
            setup_data_runner=lambda _path: None,
            benchmark_runner=lambda models=None, benchmarks=None: stub_benchmarks(
                models=models,
                benchmarks=benchmarks,
            ),
        )
    )

    result = runner.invoke(
        avi_cli.app,
        [
            "run-benchmarks",
            "--model",
            "model-a",
            "--model",
            "model-b",
            "--benchmark",
            "safety.csv",
        ],
    )

    assert result.exit_code == 0
    assert captured == [(["model-a", "model-b"], ["safety.csv"])]
