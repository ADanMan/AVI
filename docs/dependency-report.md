# Dependency Maintenance Report

## Installation attempt
- Command: `pip install -r requirements.dev.txt`
- Result: failed to download packages because the environment blocks outbound PyPI traffic via proxy (`Tunnel connection failed: 403 Forbidden`).
- Follow-up commands such as `pip install pipdeptree` were also blocked, so an automated dependency tree report could not be generated.

## Static review highlights
- Identified unpinned runtime dependencies (`streamlit`, `plotly`) and pinned them to the latest stable releases compatible with the existing stack.
- Heavy research libraries (Torch, Transformers, datasets, notebook tooling, etc.) caused large downloads and potential solver slowdowns. They are now isolated in `requirements.research.txt` so CI installs remain fast.
- Added `constraints.txt` to keep shared numerical stacks (`numpy`, `pandas`, `scipy`) and optional ML libraries within safe version bands.

## Next steps for local environments
- Re-run `pip install -r requirements.dev.txt` (and optionally `requirements.research.txt`) once network access to PyPI is available.
- After installation succeeds, execute `pipdeptree --warn fail > dependency-tree.txt` to capture the resolved dependency graph without warnings.
- Monitor upcoming releases of heavy ML libraries; update `constraints.txt` to widen ranges only after validating compatibility.
