"""Experiment tracking and notebook execution utilities."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import click


class ExperimentRunner:
    """Handles notebook execution with MLflow tracking."""

    def __init__(self, mlflow_enabled: bool = True):
        """Initialize experiment runner.

        Args:
            mlflow_enabled: Whether to enable MLflow tracking
        """
        self.mlflow_enabled = mlflow_enabled and self._check_mlflow()

    def _check_mlflow(self) -> bool:
        """Check if MLflow is available."""
        try:
            import mlflow  # noqa: F401
            return True
        except ImportError:
            return False

    def run_notebook(
        self,
        notebook_path: Path,
        output_dir: Path | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute a Jupyter notebook with papermill.

        Args:
            notebook_path: Path to the notebook file
            output_dir: Directory for output notebook (defaults to artifacts/results/)
            parameters: Parameters to inject into the notebook

        Returns:
            dict with execution metadata

        Raises:
            FileNotFoundError: If notebook doesn't exist
            RuntimeError: If execution fails
        """
        if not notebook_path.exists():
            raise FileNotFoundError(f"Notebook not found: {notebook_path}")

        # Setup output directory
        if output_dir is None:
            output_dir = Path("artifacts/results")
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate output notebook name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_name = f"{notebook_path.stem}_{timestamp}.ipynb"
        output_path = output_dir / output_name

        # Check if papermill is available
        try:
            import papermill as pm
        except ImportError:
            click.echo(
                "Error: papermill not installed. Install with: pip install papermill",
                err=True,
            )
            raise RuntimeError("papermill is required for notebook execution")

        # Start MLflow run if enabled
        mlflow_run_id = None
        if self.mlflow_enabled:
            mlflow_run_id = self._start_mlflow_run(notebook_path.stem, parameters)

        # Execute notebook
        click.echo(f"Executing notebook: {notebook_path}")
        click.echo(f"Output will be saved to: {output_path}")

        try:
            pm.execute_notebook(
                str(notebook_path),
                str(output_path),
                parameters=parameters or {},
                kernel_name="python3",
            )

            click.echo(f"✓ Notebook executed successfully")
            click.echo(f"✓ Output saved to: {output_path}")

            metadata = {
                "notebook": str(notebook_path),
                "output": str(output_path),
                "timestamp": timestamp,
                "status": "success",
            }

            if mlflow_run_id:
                metadata["mlflow_run_id"] = mlflow_run_id
                self._end_mlflow_run(output_path)

            return metadata

        except Exception as e:
            click.echo(f"✗ Notebook execution failed: {e}", err=True)

            if mlflow_run_id:
                self._fail_mlflow_run(str(e))

            raise RuntimeError(f"Notebook execution failed: {e}") from e

    def _start_mlflow_run(self, experiment_name: str, parameters: dict[str, Any] | None) -> str:
        """Start MLflow run and log parameters.

        Args:
            experiment_name: Name of the experiment
            parameters: Parameters to log

        Returns:
            MLflow run ID
        """
        import mlflow

        # Set experiment
        mlflow.set_experiment(experiment_name)

        # Start run
        run = mlflow.start_run()

        # Log parameters
        if parameters:
            for key, value in parameters.items():
                mlflow.log_param(key, value)

        click.echo(f"✓ MLflow run started: {run.info.run_id}")
        return run.info.run_id

    def _end_mlflow_run(self, output_path: Path) -> None:
        """End MLflow run and log artifacts.

        Args:
            output_path: Path to output notebook
        """
        import mlflow

        # Log output notebook as artifact
        mlflow.log_artifact(str(output_path))

        # End run
        mlflow.end_run()
        click.echo("✓ MLflow run completed")

    def _fail_mlflow_run(self, error_message: str) -> None:
        """Mark MLflow run as failed.

        Args:
            error_message: Error message
        """
        import mlflow

        mlflow.log_param("error", error_message)
        mlflow.end_run(status="FAILED")
        click.echo("✗ MLflow run marked as failed")

    def list_notebooks(self, notebooks_dir: Path = Path("notebooks")) -> list[Path]:
        """List available notebooks.

        Args:
            notebooks_dir: Directory containing notebooks

        Returns:
            List of notebook paths
        """
        if not notebooks_dir.exists():
            return []

        # Find all .ipynb files (excluding checkpoints and outputs)
        notebooks = []
        for nb_path in notebooks_dir.glob("*.ipynb"):
            if ".ipynb_checkpoints" not in str(nb_path):
                notebooks.append(nb_path)

        return sorted(notebooks)


def run_notebook_cli(
    notebook_path: Path,
    output_dir: Path | None = None,
    parameters: dict[str, Any] | None = None,
) -> None:
    """CLI wrapper for running notebooks.

    Args:
        notebook_path: Path to notebook
        output_dir: Output directory
        parameters: Notebook parameters
    """
    runner = ExperimentRunner()
    try:
        metadata = runner.run_notebook(notebook_path, output_dir, parameters)
        click.echo("\nExecution summary:")
        click.echo(json.dumps(metadata, indent=2))
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def list_experiments_cli(notebooks_dir: Path = Path("notebooks")) -> None:
    """CLI wrapper for listing experiments.

    Args:
        notebooks_dir: Directory containing notebooks
    """
    runner = ExperimentRunner()
    notebooks = runner.list_notebooks(notebooks_dir)

    if not notebooks:
        click.echo(f"No notebooks found in {notebooks_dir}")
        return

    click.echo(f"Available notebooks in {notebooks_dir}:\n")
    for i, nb in enumerate(notebooks, 1):
        click.echo(f"  {i}. {nb.name}")

    click.echo(f"\nTotal: {len(notebooks)} notebook(s)")
    click.echo("\nRun with: avi experiment run notebooks/<name>.ipynb")
