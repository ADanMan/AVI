# AVI Notebooks

Jupyter notebooks for reproducing paper results and demonstrating AVI API usage.

## Setup

```bash
pip install -r notebooks/requirements-notebooks.txt
```

## Notebooks

### Reproduce_Results.ipynb

**Purpose**: Generates the figures and tables from the AVI paper.

**Prerequisites**: Run benchmarks first to generate data:
```bash
make benchmark
```

**Contents**:
- Figure 1: Indexing Time Comparison (ChromaDB vs Qdrant)
- Figure 2: Memory Usage Comparison
- Figure 3: Throughput Analysis
- Table 1: Summary Statistics

Output saved to `data/benchmarks/`.

### Demo_Usage.ipynb

**Purpose**: Demonstrates how to use the AVI API as a client.

**Prerequisites**: Start the AVI server:
```bash
docker compose up --build
```

**Contents**:
- Health check
- Query submission with RAG and safety filtering
- Content filtering examples
- System settings retrieval
- Filter rules management
- Streaming responses (SSE)
- Reindexing trigger

## Running Notebooks

1. Install notebook dependencies:
   ```bash
   pip install -r notebooks/requirements-notebooks.txt
   ```

2. Start the AVI server (for Demo_Usage):
   ```bash
   docker compose up --build
   ```

3. Launch Jupyter:
   ```bash
   jupyter lab notebooks/
   ```

4. Open and run notebooks.

## Notes

- **Reproduce_Results.ipynb** works offline with pre-generated benchmark CSV files
- **Demo_Usage.ipynb** requires a running AVI server
- All visualizations use relative paths (`../data/benchmarks/`)
- Figures are saved as PNG files for paper inclusion
