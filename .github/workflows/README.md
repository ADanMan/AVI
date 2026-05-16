# AVI Workflows

This directory contains GitHub Actions workflows for CI/CD automation.

## Workflows

- **ci.yml** - Full CI pipeline (linting, type-checking, tests, Docker builds)
- **smoke-tests.yml** - Quick smoke tests on every PR
- **bench.yml** - Performance benchmarks (manual trigger or weekly)

## Usage

All workflows run automatically on relevant events. To run benchmarks manually:
1. Go to Actions tab
2. Select "Benchmarks" workflow
3. Click "Run workflow"
