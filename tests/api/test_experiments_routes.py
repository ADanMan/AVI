"""
Tests for experiments API routes.
"""


import pytest


@pytest.mark.asyncio
async def test_list_notebooks(test_client):
    """Test GET /api/v1/experiments/notebooks."""
    response = await test_client.get("/api/v1/experiments/notebooks")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

    # Check notebook structure
    notebook = data[0]
    assert "id" in notebook
    assert "name" in notebook
    assert "title" in notebook
    assert "description" in notebook
    assert "category" in notebook
    assert "status" in notebook


@pytest.mark.asyncio
async def test_list_notebooks_filter_by_category(test_client):
    """Test filtering notebooks by category."""
    response = await test_client.get("/api/v1/experiments/notebooks?category=safety")

    assert response.status_code == 200
    data = response.json()

    # All notebooks should be safety category
    for notebook in data:
        assert notebook["category"] == "safety"


@pytest.mark.asyncio
async def test_run_notebook(test_client):
    """Test POST /api/v1/experiments/run."""
    request_data = {
        "notebook_id": "toxicity_detection",
        "parameters": {"threshold": 0.5},
    }

    response = await test_client.post("/api/v1/experiments/run", json=request_data)

    assert response.status_code == 200
    data = response.json()

    assert "id" in data
    assert data["notebook_id"] == "toxicity_detection"
    assert data["status"] in ["ready", "running", "completed", "failed"]
    assert "started_at" in data
    assert data["parameters"] == {"threshold": 0.5}


@pytest.mark.asyncio
async def test_list_runs(test_client):
    """Test GET /api/v1/experiments/runs."""
    response = await test_client.get("/api/v1/experiments/runs")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


@pytest.mark.asyncio
async def test_list_runs_filter_by_notebook(test_client):
    """Test filtering runs by notebook ID."""
    response = await test_client.get("/api/v1/experiments/runs?notebook_id=toxicity_detection")

    assert response.status_code == 200
    data = response.json()

    for run in data:
        assert run["notebook_id"] == "toxicity_detection"


@pytest.mark.asyncio
async def test_get_run(test_client):
    """Test GET /api/v1/experiments/runs/{run_id}."""
    response = await test_client.get("/api/v1/experiments/runs/run_001")

    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "run_001"
    assert "notebook_id" in data
    assert "status" in data
    assert "metrics" in data


@pytest.mark.asyncio
async def test_get_run_not_found(test_client):
    """Test getting non-existent run."""
    response = await test_client.get("/api/v1/experiments/runs/nonexistent")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_compare_runs(test_client):
    """Test POST /api/v1/experiments/compare."""
    request_data = ["run_001", "run_002", "run_003"]

    response = await test_client.post("/api/v1/experiments/compare", json=request_data)

    assert response.status_code == 200
    data = response.json()

    assert "run_ids" in data
    assert "metrics" in data
    assert "timestamps" in data
    assert len(data["run_ids"]) == 3


@pytest.mark.asyncio
async def test_compare_runs_empty_list(test_client):
    """Test comparing with empty list."""
    response = await test_client.post("/api/v1/experiments/compare", json=[])

    assert response.status_code == 400
