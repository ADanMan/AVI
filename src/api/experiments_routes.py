"""
Experiments and benchmarks API routes.
Provides notebook execution and MLflow integration.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.auth import APIKey, Role, optional_auth


router = APIRouter(
    prefix="/experiments",
    tags=["Experiments"],
    responses={404: {"description": "Not found"}},
)


# =====================
# Models
# =====================


class NotebookStatus(str, Enum):
    """Notebook execution status."""

    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class NotebookInfo(BaseModel):
    """Information about an available notebook."""

    id: str = Field(..., description="Notebook ID")
    name: str = Field(..., description="Notebook filename")
    title: str = Field(..., description="Human-readable title")
    description: str = Field(..., description="Notebook description")
    category: str = Field(..., description="Category: safety, performance, quality")
    status: NotebookStatus = Field(..., description="Current status")
    last_run: datetime | None = Field(None, description="Last execution time")
    duration_seconds: float | None = Field(None, description="Last run duration")


class ExperimentRun(BaseModel):
    """Single experiment run record."""

    id: str = Field(..., description="Run ID")
    notebook_id: str = Field(..., description="Notebook ID")
    status: NotebookStatus = Field(..., description="Run status")
    started_at: datetime = Field(..., description="Start time")
    completed_at: datetime | None = Field(None, description="Completion time")
    duration_seconds: float | None = Field(None, description="Duration")
    metrics: dict[str, float] = Field(default_factory=dict, description="Experiment metrics")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Run parameters")
    error: str | None = Field(None, description="Error message if failed")


class RunRequest(BaseModel):
    """Request to run a notebook."""

    notebook_id: str = Field(..., description="Notebook ID to run")
    parameters: dict[str, Any] | None = Field(None, description="Execution parameters")


class ExperimentMetrics(BaseModel):
    """Metrics from experiment runs."""

    accuracy: float | None = Field(None, description="Accuracy score")
    precision: float | None = Field(None, description="Precision score")
    recall: float | None = Field(None, description="Recall score")
    f1_score: float | None = Field(None, description="F1 score")
    latency_ms: float | None = Field(None, description="Latency in milliseconds")
    throughput: float | None = Field(None, description="Throughput (requests/sec)")


class ComparisonData(BaseModel):
    """Comparison data for multiple runs."""

    run_ids: list[str]
    metrics: dict[str, list[float]]  # metric_name -> [values_per_run]
    timestamps: list[datetime]


# =====================
# Endpoints
# =====================


@router.get("/notebooks", response_model=list[NotebookInfo])
async def list_notebooks(
    category: str | None = Query(None, description="Filter by category"),
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
) -> list[NotebookInfo]:
    """
    List available experiment notebooks.

    Returns all notebooks with their current status and last run information.
    In production, this would scan the notebooks/ directory or query MLflow.
    """
    # TODO: Implement actual notebook discovery
    # For now, returning hardcoded list matching the notebooks/ directory

    notebooks = [
        NotebookInfo(
            id="toxicity_detection",
            name="toxicity_detection.ipynb",
            title="Toxicity Detection Benchmark",
            description="Evaluate toxicity detection accuracy and false positive rates",
            category="safety",
            status=NotebookStatus.READY,
            last_run=datetime.now(),
            duration_seconds=45.2,
        ),
        NotebookInfo(
            id="pii_masking",
            name="pii_masking.ipynb",
            title="PII Detection & Masking",
            description="Test PII detection accuracy across different data types",
            category="safety",
            status=NotebookStatus.READY,
            last_run=datetime.now(),
            duration_seconds=32.8,
        ),
        NotebookInfo(
            id="prompt_injection",
            name="prompt_injection.ipynb",
            title="Prompt Injection Detection",
            description="Evaluate detection of jailbreak and prompt manipulation attempts",
            category="safety",
            status=NotebookStatus.READY,
            last_run=None,
            duration_seconds=None,
        ),
        NotebookInfo(
            id="rag_relevance",
            name="rag_relevance.ipynb",
            title="RAG Relevance Analysis",
            description="Measure RAG retrieval accuracy and relevance scores",
            category="quality",
            status=NotebookStatus.READY,
            last_run=datetime.now(),
            duration_seconds=120.5,
        ),
        NotebookInfo(
            id="latency_benchmark",
            name="latency_benchmark.ipynb",
            title="Latency & Performance Benchmark",
            description="Measure end-to-end latency and throughput under load",
            category="performance",
            status=NotebookStatus.READY,
            last_run=datetime.now(),
            duration_seconds=180.0,
        ),
    ]

    if category:
        notebooks = [nb for nb in notebooks if nb.category == category]

    return notebooks


@router.post("/run", response_model=ExperimentRun)
async def run_notebook(
    request: RunRequest, api_key: APIKey | None = Depends(optional_auth(Role.USER))
) -> ExperimentRun:
    """
    Run an experiment notebook.

    Executes the notebook asynchronously and returns the run ID.
    The actual execution would be done via papermill or nbconvert in production.
    """
    # TODO: Implement actual notebook execution
    # In production, this would:
    # 1. Use papermill to execute the notebook with parameters
    # 2. Store results in MLflow
    # 3. Return the run ID for tracking

    # For now, returning a mock run
    run_id = f"run_{request.notebook_id}_{int(datetime.now().timestamp())}"

    return ExperimentRun(
        id=run_id,
        notebook_id=request.notebook_id,
        status=NotebookStatus.RUNNING,
        started_at=datetime.now(),
        parameters=request.parameters or {},
        metrics={},
    )


@router.get("/runs", response_model=list[ExperimentRun])
async def list_runs(
    notebook_id: str | None = Query(None, description="Filter by notebook ID"),
    status: NotebookStatus | None = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of runs to return"),
    api_key: APIKey | None = Depends(optional_auth(Role.USER)),
) -> list[ExperimentRun]:
    """
    List experiment runs.

    Returns run history with filtering options.
    In production, this would query MLflow tracking server.
    """
    # TODO: Implement actual run history from MLflow
    # For now, returning mock data

    from datetime import timedelta

    now = datetime.now()

    mock_runs = [
        ExperimentRun(
            id="run_001",
            notebook_id="toxicity_detection",
            status=NotebookStatus.COMPLETED,
            started_at=now - timedelta(hours=2),
            completed_at=now - timedelta(hours=2, minutes=-45),
            duration_seconds=45.2,
            metrics={
                "accuracy": 0.94,
                "precision": 0.92,
                "recall": 0.96,
                "f1_score": 0.94,
            },
            parameters={"threshold": 0.5},
        ),
        ExperimentRun(
            id="run_002",
            notebook_id="pii_masking",
            status=NotebookStatus.COMPLETED,
            started_at=now - timedelta(hours=4),
            completed_at=now - timedelta(hours=4, minutes=-32),
            duration_seconds=32.8,
            metrics={
                "accuracy": 0.98,
                "precision": 0.97,
                "recall": 0.99,
                "f1_score": 0.98,
            },
            parameters={},
        ),
        ExperimentRun(
            id="run_003",
            notebook_id="latency_benchmark",
            status=NotebookStatus.COMPLETED,
            started_at=now - timedelta(days=1),
            completed_at=now - timedelta(days=1, minutes=-3),
            duration_seconds=180.0,
            metrics={
                "latency_ms": 247.5,
                "throughput": 12.3,
            },
            parameters={"concurrency": 10},
        ),
    ]

    # Filter by notebook_id
    if notebook_id:
        mock_runs = [run for run in mock_runs if run.notebook_id == notebook_id]

    # Filter by status
    if status:
        mock_runs = [run for run in mock_runs if run.status == status]

    return mock_runs[:limit]


@router.get("/runs/{run_id}", response_model=ExperimentRun)
async def get_run(run_id: str, api_key: APIKey | None = Depends(optional_auth(Role.USER))) -> ExperimentRun:
    """
    Get details for a specific run.

    Returns complete run information including metrics and parameters.
    """
    # TODO: Implement actual run retrieval from MLflow
    # For now, returning mock data

    if run_id == "run_001":
        return ExperimentRun(
            id=run_id,
            notebook_id="toxicity_detection",
            status=NotebookStatus.COMPLETED,
            started_at=datetime.now(),
            completed_at=datetime.now(),
            duration_seconds=45.2,
            metrics={
                "accuracy": 0.94,
                "precision": 0.92,
                "recall": 0.96,
                "f1_score": 0.94,
            },
            parameters={"threshold": 0.5},
        )

    raise HTTPException(status_code=404, detail=f"Run {run_id} not found")


@router.post("/compare", response_model=ComparisonData)
async def compare_runs(
    run_ids: list[str], api_key: APIKey | None = Depends(optional_auth(Role.USER))
) -> ComparisonData:
    """
    Compare multiple experiment runs.

    Returns comparison data for metrics across the specified runs.
    Useful for A/B testing and experiment tracking.
    """
    # TODO: Implement actual comparison from MLflow
    # For now, returning mock comparison data

    if not run_ids:
        raise HTTPException(status_code=400, detail="At least one run_id required")

    # Mock comparison data
    return ComparisonData(
        run_ids=run_ids,
        metrics={
            "accuracy": [0.94, 0.92, 0.96],
            "precision": [0.92, 0.90, 0.94],
            "recall": [0.96, 0.94, 0.98],
            "f1_score": [0.94, 0.92, 0.96],
        },
        timestamps=[datetime.now() for _ in run_ids],
    )


# Export router
__all__ = ["router"]
