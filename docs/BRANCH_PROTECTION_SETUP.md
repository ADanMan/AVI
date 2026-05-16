# Branch Protection Rules Setup Guide

This guide explains how to configure GitHub Branch Protection Rules for the AVI project to maintain code quality and prevent accidental changes to important branches.

## Overview

Branch Protection Rules enforce certain workflows and quality standards before code can be merged into protected branches. This ensures that all code goes through proper review and testing.

## Recommended Protection for Main Branches

### Protected Branches

Configure protection for these branches:
- `main` - Production-ready code
- `develop` - Development integration branch

## Step-by-Step Setup

### 1. Access Branch Protection Settings

1. Go to your GitHub repository
2. Click on **Settings**
3. In the left sidebar, click **Branches**
4. Under "Branch protection rules", click **Add rule**

### 2. Configure Protection for `main` Branch

#### Branch Name Pattern
```
main
```

#### Required Settings

**Protect matching branches:**
- ✅ **Require a pull request before merging**
  - Required approvals: `1`
  - ✅ Dismiss stale pull request approvals when new commits are pushed
  - ✅ Require review from Code Owners (if using CODEOWNERS file)
  - ✅ Require approval of the most recent reviewable push

- ✅ **Require status checks to pass before merging**
  - ✅ Require branches to be up to date before merging
  - **Required status checks** (select these from your GitHub Actions):
    - `Validation Pipeline`
    - `Python Linting`
    - `TypeScript Linting`
    - `Type Check`
    - `Unit Tests (Python 3.11)` (or all Python versions)
    - `Integration Tests`
    - `Docker Build`
    - `UI Build`

- ✅ **Require conversation resolution before merging**
  - All conversations on PR must be resolved

- ✅ **Require signed commits** (optional but recommended)

- ✅ **Require linear history**
  - Prevents merge commits, requires rebase or squash

- ✅ **Include administrators**
  - Apply these rules to administrators too

- ❌ **Allow force pushes** (keep disabled)
  - Prevents rewriting history

- ❌ **Allow deletions** (keep disabled)
  - Prevents accidental branch deletion

#### Optional Settings

- **Require deployments to succeed before merging** (if you have deployment workflows)
- **Lock branch** (for emergency lockdown only)

### 3. Configure Protection for `develop` Branch

Use the same settings as `main` but with potentially more relaxed requirements:

#### Branch Name Pattern
```
develop
```

#### Adjusted Settings

- Required approvals: `1` (can be 0 for faster integration)
- May skip some status checks for faster iteration
- Still require:
  - Validation Pipeline
  - Linting (Python + TypeScript)
  - Unit Tests

### 4. Configure Protection for Feature Branches (Optional)

For Claude-generated branches or feature branches:

#### Branch Name Pattern
```
claude/*
```
or
```
feature/*
```

#### Minimal Settings

- ✅ Require a pull request before merging (with 0-1 approvals)
- ✅ Require status checks:
  - Validation Pipeline
  - Unit Tests
- ❌ Include administrators (allow admins to bypass for quick fixes)

## Required Status Checks Details

### What Status Checks to Require

Based on the GitHub Actions workflows created, select these status checks:

1. **Validation Pipeline** (`.github/workflows/validation.yml`)
   - Job: `validate`
   - Critical for catching API mismatches

2. **Lint & Format** (`.github/workflows/lint.yml`)
   - Job: `python-lint`
   - Job: `typescript-lint`

3. **Type Check** (if you add typecheck.yml)
   - Job: `python-types`
   - Job: `typescript-types`

4. **Tests** (`.github/workflows/test.yml`)
   - Job: `unit-tests` (Python 3.11 at minimum)
   - Job: `integration-tests`
   - Job: `ui-tests`

5. **Docker Build** (`.github/workflows/docker.yml`)
   - Job: `build-and-test` (cpu target)
   - Job: `docker-compose-test`

6. **Security Scan** (`.github/workflows/security.yml`)
   - Optional but recommended:
     - Job: `python-security`
     - Job: `secret-scan`

### How Status Checks Appear

After you merge some PRs with these workflows, GitHub will automatically detect them and list them in the "Require status checks to pass" section. You can then select which ones are required.

## CODEOWNERS File (Optional)

Create a `.github/CODEOWNERS` file to automatically request reviews from specific people or teams:

```
# Global owners
* @your-team

# Backend code
/src/ @backend-team
/tests/ @backend-team

# Frontend code
/ui/ @frontend-team

# Infrastructure
/docker-compose.yml @devops-team
/Dockerfile @devops-team
/.github/ @devops-team

# Documentation
/docs/ @tech-writers

# Validation Pipeline
/validation_pipeline/ @qa-team
```

## Rulesets (New GitHub Feature)

GitHub now offers **Rulesets** as an alternative to Branch Protection Rules with more flexibility:

### Create a Ruleset

1. Go to **Settings** → **Rules** → **Rulesets**
2. Click **New ruleset**
3. Name it "Main Branch Protection"

### Ruleset Configuration

**Target branches:**
- Include by pattern: `main`

**Rules:**
- ✅ Restrict deletions
- ✅ Require a pull request before merging
  - Required approvals: 1
  - Dismiss stale reviews
- ✅ Require status checks to pass
  - Add all required checks
- ✅ Require conversation resolution
- ✅ Block force pushes

**Bypass list:**
- Allow admins to bypass in emergencies only

## Verification

After setting up branch protection:

1. **Test with a PR:**
   - Create a test branch
   - Make a small change
   - Open a PR to `main` or `develop`
   - Verify that all required checks run
   - Verify that you cannot merge without approvals/checks

2. **Try to bypass:**
   - Attempt to push directly to `main`
   - Should be blocked with error message

3. **Check status:**
   - Go to your repo → Settings → Branches
   - Verify green checkmarks next to protected branches

## Troubleshooting

### Status Checks Not Appearing

**Problem:** Can't find status checks to require

**Solution:**
1. Merge at least one PR that runs the workflows
2. Wait for workflows to complete
3. Refresh the branch protection settings page
4. Status checks should now appear in dropdown

### Bypass Protection (Emergency)

**When you absolutely need to bypass:**

1. Temporarily disable branch protection
2. Make emergency fix
3. Re-enable protection immediately
4. Create follow-up PR for proper review

**Better approach:**
- Use `--no-verify` on hooks locally
- Create PR and get emergency approval
- Use admin bypass if configured

### Too Strict / Blocks Development

**If protection is slowing down development:**

- Use `develop` branch for integration
- Protect only `main` strictly
- Allow force pushes on feature branches
- Reduce required approvals on `develop`

## Best Practices

1. **Start Strict:** Easier to relax than to tighten later
2. **Document Exceptions:** If you bypass, document why
3. **Review Regularly:** Check protection rules quarterly
4. **Monitor Metrics:** Track PR approval times, failure rates
5. **Team Agreement:** Get buy-in from all developers

## Integration with Validation Pipeline

The Validation Pipeline provides early feedback on code quality:

- **Pre-commit hook:** Fast local checks before commit
- **Pre-push hook:** Comprehensive checks before push
- **CI validation:** Runs on PR creation
- **Branch protection:** Blocks merge if validation fails

This multi-layered approach ensures:
1. Fast feedback locally (seconds)
2. Comprehensive check on push (1-2 minutes)
3. Full suite on PR (3-5 minutes)
4. Protection from merging bad code

## Example PR Workflow

With protection enabled:

```
1. Developer creates feature branch from `develop`
   └─ git checkout -b feature/new-api

2. Developer makes changes
   └─ Pre-commit hook runs on each commit (fast checks)

3. Developer pushes branch
   └─ Pre-push hook runs (full validation)
   └─ GitHub Actions trigger automatically

4. Developer creates PR to `develop`
   └─ All required status checks run
   └─ Validation pipeline comments on PR
   └─ Code review requested automatically (CODEOWNERS)

5. Reviewer reviews code
   └─ Requests changes or approves

6. Developer makes updates
   └─ New commits trigger checks again
   └─ Stale approvals dismissed automatically

7. All checks pass + approval received
   └─ Merge button enabled
   └─ Developer merges (squash or rebase)

8. Branch automatically deleted
   └─ Clean history maintained
```

## Resources

- [GitHub Branch Protection Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/defining-the-mergeability-of-pull-requests/about-protected-branches)
- [GitHub Rulesets Docs](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
- [CODEOWNERS Documentation](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-code-owners)

## Summary Checklist

- [ ] Branch protection configured for `main`
- [ ] Branch protection configured for `develop`
- [ ] Required status checks selected
- [ ] Pull request reviews required
- [ ] Conversation resolution required
- [ ] Force pushes disabled
- [ ] Deletions disabled
- [ ] Linear history enabled
- [ ] CODEOWNERS file created (optional)
- [ ] Protection tested with test PR
- [ ] Team notified of new rules
- [ ] Documentation added to project README

---

**Last Updated:** 2025-11-15
**Maintained By:** DevOps Team
