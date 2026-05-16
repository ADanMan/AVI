# Codecov Integration Setup Guide

This guide explains how to set up Codecov for code coverage tracking in the AVI project.

## What is Codecov?

Codecov is a code coverage reporting tool that integrates with your CI/CD pipeline to:
- Track test coverage over time
- Show coverage diff on PRs
- Block merges if coverage drops
- Visualize which code is tested

## Prerequisites

- GitHub repository with CI/CD workflows
- Tests that generate coverage reports
- Codecov account (free for public repositories)

## Step 1: Sign Up for Codecov

1. Go to [codecov.io](https://codecov.io)
2. Click "Sign up with GitHub"
3. Authorize Codecov to access your repositories
4. Select the AVI repository

## Step 2: Get Upload Token

1. In Codecov dashboard, go to your repository
2. Click on **Settings**
3. Copy the **Upload Token** (CODECOV_TOKEN)
4. Keep this token secret!

## Step 3: Add Token to GitHub Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Name: `CODECOV_TOKEN`
5. Value: Paste the token from Step 2
6. Click **Add secret**

## Step 4: Verify Workflow Configuration

The test workflows (`.github/workflows/test.yml`) already include Codecov upload:

```yaml
- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
    flags: unittests
    name: codecov-umbrella
```

No changes needed! The upload will happen automatically on the next PR.

## Step 5: Configure Coverage Requirements

The `.codecov.yml` file is already configured with:

- **Minimum coverage:** 70%
- **Coverage drop threshold:** 5% (PRs can't reduce coverage by more than 5%)
- **Patch coverage:** 70% (new code must be 70% tested)

You can adjust these in `.codecov.yml`:

```yaml
coverage:
  status:
    project:
      default:
        target: 70%        # Minimum overall coverage
        threshold: 5%      # Max allowed drop

    patch:
      default:
        target: 70%        # Minimum coverage for new code
```

## Step 6: Add Codecov Badge to README

Add this badge to your README.md:

```markdown
[![codecov](https://codecov.io/gh/YOUR_USERNAME/AVI/branch/main/graph/badge.svg)](https://codecov.io/gh/YOUR_USERNAME/AVI)
```

Replace `YOUR_USERNAME` with your actual GitHub username or organization.

## Step 7: Test Integration

1. Create a test branch and PR
2. Push some code changes
3. Wait for CI to complete
4. Check Codecov comment on PR
5. Visit Codecov dashboard to see reports

## Understanding Codecov Reports

### On Pull Requests

Codecov will comment on your PR with:

```
Coverage: 72.5% (target 70%)
+5 lines added, 4 covered (+80%)

Files Changed:
src/api/routes.py: 85% → 87% (+2%)
src/services/chat.py: 70% → 65% (-5%) ⚠️
```

### Coverage Types

1. **Project Coverage** - Overall codebase coverage
2. **Patch Coverage** - Coverage of changes in PR
3. **File Coverage** - Coverage per file

### Status Checks

Codecov creates GitHub status checks:
- ✅ `codecov/project` - Overall coverage meets target
- ✅ `codecov/patch` - PR changes are adequately tested
- ❌ Failed checks block PR merge (if configured)

## Codecov Dashboard Features

### Coverage Trends

View coverage over time:
- Line graph showing coverage percentage
- Identify when coverage dropped
- Compare branches

### Sunburst Chart

Interactive visualization:
- See which directories/files need tests
- Click to drill down into specific files
- Red = low coverage, Green = high coverage

### File Browser

Browse your codebase:
- See coverage for each file
- View which lines are covered/uncovered
- Compare coverage between commits

## Advanced Configuration

### Ignore Paths

Already configured in `.codecov.yml`:

```yaml
ignore:
  - "tests/**/*"          # Don't count test files
  - "**/node_modules/**/*"  # Ignore dependencies
  - "scripts/**/*"         # Ignore scripts
```

### Component Tracking

Track coverage for different parts of the codebase:

```yaml
component_management:
  individual_components:
    - component_id: backend
      paths:
        - src/**/*.py

    - component_id: frontend
      paths:
        - ui/src/**/*.ts
```

### Flags for Different Test Types

```yaml
flags:
  unittests:
    paths:
      - src/

  uitests:
    paths:
      - ui/src/
```

## Troubleshooting

### Coverage Not Uploading

**Problem:** No coverage data in Codecov

**Solutions:**
1. Check that `CODECOV_TOKEN` secret is set
2. Verify coverage.xml is generated: `ls -la coverage.xml`
3. Check CI logs for upload errors
4. Ensure `codecov/codecov-action@v3` is used

### Coverage Lower Than Expected

**Problem:** Coverage shows 0% or very low

**Solutions:**
1. Check that tests are actually running
2. Verify coverage report includes all source files
3. Check ignore patterns in `.codecov.yml`
4. Ensure pytest is configured correctly:
   ```ini
   [tool:pytest]
   addopts = --cov=src --cov-report=xml
   ```

### Token Issues

**Problem:** "Could not find a repository, try using repo upload token"

**Solutions:**
1. Regenerate token in Codecov dashboard
2. Update GitHub secret
3. Re-run workflow

### PR Comments Not Appearing

**Problem:** Codecov not commenting on PRs

**Solutions:**
1. Check GitHub App permissions
2. Re-install Codecov GitHub App
3. Verify comment settings in `.codecov.yml`

## Best Practices

### 1. Set Realistic Targets

Don't aim for 100% coverage immediately:
- Start at current coverage level
- Gradually increase target (e.g., 70% → 75% → 80%)
- Focus on critical paths first

### 2. Use Coverage as Guide, Not Goal

High coverage doesn't mean good tests:
- Focus on meaningful tests
- Test edge cases and error paths
- Don't write tests just to hit coverage

### 3. Monitor Trends

- Review coverage weekly
- Investigate sudden drops
- Celebrate improvements
- Set coverage goals for new features

### 4. Enforce on Critical Branches

Only block merges for important branches:
- `main` - Strict coverage requirements
- `develop` - Moderate requirements
- Feature branches - Warning only

### 5. Educate Team

- Share coverage reports in standups
- Discuss uncovered code in reviews
- Make coverage part of definition of done

## Integration with Branch Protection

Add Codecov status checks to branch protection:

1. Go to GitHub Settings → Branches
2. Edit protection rule for `main`
3. Under "Require status checks", add:
   - `codecov/project`
   - `codecov/patch`

Now PRs can't merge unless coverage requirements are met!

## Makefile Commands

Add coverage commands to Makefile:

```makefile
coverage: ## Run tests with coverage report
	pytest tests/unit --cov=src --cov-report=html --cov-report=term
	@echo "Open htmlcov/index.html to view report"

coverage-report: ## Generate and open coverage report
	pytest tests/unit --cov=src --cov-report=html
	open htmlcov/index.html  # macOS
	# xdg-open htmlcov/index.html  # Linux
```

## Resources

- [Codecov Documentation](https://docs.codecov.com)
- [Codecov GitHub Action](https://github.com/codecov/codecov-action)
- [Coverage.py Documentation](https://coverage.readthedocs.io)

## Example Workflow

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e ".[dev,testing]"

      - name: Run tests with coverage
        run: pytest tests/ --cov=src --cov-report=xml

      - name: Upload to Codecov
        uses: codecov/codecov-action@v3
        with:
          token: ${{ secrets.CODECOV_TOKEN }}
          files: ./coverage.xml
          flags: unittests
          fail_ci_if_error: true
```

## Summary Checklist

- [ ] Signed up for Codecov
- [ ] Added CODECOV_TOKEN to GitHub secrets
- [ ] Configured .codecov.yml
- [ ] Updated test workflows to upload coverage
- [ ] Added Codecov badge to README
- [ ] Set up branch protection with Codecov checks
- [ ] Tested integration with PR
- [ ] Reviewed coverage reports
- [ ] Set coverage targets
- [ ] Documented for team

---

**Last Updated:** 2025-11-15
**Maintained By:** QA Team
