# Deployment and Local Runbook

This guide replaces the former `run.txt` helper file and documents the
minimum steps required to seed the project data, configure outbound network
proxies, and launch the API process.

## 1. Prepare the data artifacts

Seed and index the dataset before starting the API. Run the helpers from the
repository root:

```bash
python -m avi.cli setup-data
python -m avi.cli index-data
```

These scripts populate the `data/` directory with the content required by the
retrieval pipeline. They are idempotent; rerun them whenever new source
material is added.

## 2. Configure proxy environment variables

If your deployment requires outbound HTTP/HTTPS proxies, export the following
variables with values provided by your infrastructure secrets store (for
example, Vault, Doppler, 1Password CLI, or environment-specific deployment
configuration):

```bash
export HTTP_PROXY="$OUTBOUND_HTTP_PROXY"
export HTTPS_PROXY="$OUTBOUND_HTTPS_PROXY"
export NO_PROXY="localhost,127.0.0.1,0.0.0.0"
```

- Replace `OUTBOUND_HTTP_PROXY` and `OUTBOUND_HTTPS_PROXY` with the actual proxy
  URLs supplied by your platform team.
- Do **not** commit real proxy credentials or hard-coded values to the
  repository; prefer runtime environment injection instead.

Skip this step if your environment can reach upstream services directly.

## 3. Run the API server

Start the FastAPI application using Uvicorn once data seeding and proxy
configuration (if any) are complete:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Use `--reload` only for development. Production deployments should rely on a
process manager such as systemd, supervisord, or ASGI servers like gunicorn
with uvicorn workers.

## Appendix: Regenerating a project tree overview

To inspect the repository structure without checking large artifacts into git,
run:

```bash
make project-tree
```

The command emits a `tree.txt` summary in the working directory that is ignored
by version control. Regenerate it on demand for documentation or debugging.
