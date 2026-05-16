"""Command-line interface for AVI utilities."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from pathlib import Path

import click


@click.group(help="Utilities for managing AVI data workflows.")
def app() -> None:
    """Root CLI group."""
    return None


@dataclass
class CLIProviders:
    """Factories used by the CLI commands.

    The indirection keeps command functions lightweight and easy to stub during
    tests without reaching for ``sys.path`` hacks.
    """

    index_data_runner: Callable[[], Awaitable[dict[str, object]]]
    setup_data_runner: Callable[[Path], None]


def _default_providers() -> CLIProviders:
    from scripts import index_data
    from scripts import setup_data as setup_module

    return CLIProviders(
        index_data_runner=lambda: index_data.reindex_all(),
        setup_data_runner=lambda output_dir: setup_module.prepare_all_datasets(output_dir),
    )


_PROVIDERS: CLIProviders | None = None


def configure_providers(**overrides: Callable) -> None:
    """Override one or more provider callables used by the CLI."""

    global _PROVIDERS
    baseline = get_providers()
    _PROVIDERS = replace(baseline, **overrides)


def get_providers() -> CLIProviders:
    """Return the current provider registry."""

    global _PROVIDERS
    if _PROVIDERS is None:
        _PROVIDERS = _default_providers()
    return _PROVIDERS


def set_providers(providers: CLIProviders) -> None:
    """Replace the provider registry with a custom implementation."""

    global _PROVIDERS
    _PROVIDERS = providers


def reset_providers() -> None:
    """Restore the default provider registry."""

    global _PROVIDERS
    _PROVIDERS = None


@app.command("index-data")
def index_data_command() -> None:
    """Rebuild the vector index from the configured data sources."""

    result = asyncio.run(get_providers().index_data_runner())
    click.echo("Indexing completed.")
    click.echo(str(result))


@app.command("setup-data")
@click.option(
    "--output-dir",
    "output_dir",
    type=click.Path(path_type=Path),
    default=Path("data/raw"),
    show_default=True,
    help="Destination directory for generated CSVs.",
)
def setup_data_command(output_dir: Path) -> None:
    """Download benchmark datasets and materialise helper CSV files."""

    get_providers().setup_data_runner(output_dir)
    click.echo(f"Data prepared under {output_dir}")


@app.command("run-benchmarks", deprecated=True)
def run_benchmarks_command() -> None:
    """[DEPRECATED] Execute benchmarks - use 'avi experiment run' instead.

    This command has been deprecated in favor of the notebooks-only approach.
    """
    click.echo(click.style("\n⚠️  DEPRECATED COMMAND ⚠️\n", fg="yellow", bold=True))
    click.echo("The 'run-benchmarks' command has been deprecated.")
    click.echo("\nPlease use Jupyter notebooks for all experiments:")
    click.echo("\n  1. List available notebooks:")
    click.echo(click.style("     avi experiment list", fg="green"))
    click.echo("\n  2. Run a notebook:")
    click.echo(
        click.style("     avi experiment run notebooks/toxicity_detection.ipynb", fg="green")
    )
    click.echo("\nAvailable experiment notebooks:")
    click.echo("  - notebooks/toxicity_detection.ipynb")
    click.echo("  - notebooks/pii_masking.ipynb")
    click.echo("  - notebooks/prompt_injection.ipynb")
    click.echo("  - notebooks/rag_relevance.ipynb")
    click.echo("  - notebooks/latency_benchmark.ipynb")
    click.echo("\nSee BENCHMARK_GUIDE.md for more details.\n")


@app.group("experiment", help="Manage and run notebook experiments.")
def experiment_group() -> None:
    """Experiment management commands."""
    return None


@experiment_group.command("run")
@click.argument("notebook_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output-dir",
    "output_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory for executed notebook (default: artifacts/results/)",
)
@click.option(
    "--param",
    "parameters",
    multiple=True,
    help="Notebook parameters in key=value format (can be repeated)",
)
def run_experiment(
    notebook_path: Path,
    output_dir: Path | None,
    parameters: tuple[str, ...],
) -> None:
    """Execute a Jupyter notebook experiment with MLflow tracking.

    Example:
        avi experiment run notebooks/toxicity_detection.ipynb

        avi experiment run notebooks/benchmark.ipynb --param model=gpt-4o-mini --param samples=1000
    """
    from avi.experiments import run_notebook_cli

    # Parse parameters
    parsed_params = {}
    for param in parameters:
        if "=" not in param:
            click.echo(f"Warning: Skipping invalid parameter format: {param}", err=True)
            continue
        key, value = param.split("=", 1)
        # Try to parse as JSON-like types
        if value.lower() == "true":
            parsed_params[key] = True
        elif value.lower() == "false":
            parsed_params[key] = False
        elif value.isdigit():
            parsed_params[key] = int(value)
        else:
            try:
                parsed_params[key] = float(value)
            except ValueError:
                parsed_params[key] = value

    run_notebook_cli(notebook_path, output_dir, parsed_params or None)


@experiment_group.command("list")
@click.option(
    "--dir",
    "notebooks_dir",
    type=click.Path(exists=True, path_type=Path),
    default=Path("notebooks"),
    help="Directory containing notebooks (default: notebooks/)",
)
def list_experiments(notebooks_dir: Path) -> None:
    """List available notebook experiments.

    Example:
        avi experiment list

        avi experiment list --dir notebooks/
    """
    from avi.experiments import list_experiments_cli

    list_experiments_cli(notebooks_dir)


def main() -> None:
    """Entry point for ``python -m avi.cli``."""

    app(prog_name="avi.cli")


if __name__ == "__main__":  # pragma: no cover - manual execution hook
    main()
