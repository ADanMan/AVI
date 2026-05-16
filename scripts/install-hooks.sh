#!/bin/bash
# Install Git hooks for AVI project

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "🔧 Installing Git hooks..."

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# ============================================
# PRE-COMMIT HOOK
# ============================================
cat > "$HOOKS_DIR/pre-commit" << 'EOF'
#!/bin/bash
# AVI Pre-commit hook
# Runs fast checks before allowing commit

set -e

echo "🔍 Running pre-commit checks..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "validate.py" ]; then
    print_error "Not in AVI project root directory"
    exit 1
fi

# 1. Check for large files
echo "📦 Checking for large files..."
MAX_SIZE=5242880  # 5MB in bytes
LARGE_FILES=$(git diff --cached --name-only --diff-filter=ACM | \
    while read -r file; do
        if [ -f "$file" ]; then
            SIZE=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null || echo 0)
            if [ "$SIZE" -gt "$MAX_SIZE" ]; then
                echo "$file ($SIZE bytes)"
            fi
        fi
    done)

if [ -n "$LARGE_FILES" ]; then
    print_error "Large files detected (>5MB):"
    echo "$LARGE_FILES"
    print_warning "Consider using Git LFS or .gitignore"
    exit 1
fi
print_success "No large files"

# 2. Check for secrets
echo "🔒 Checking for potential secrets..."
SECRETS_PATTERN='(password|secret|token|api[_-]?key|private[_-]?key).*=.*["\047][^"\047]{8,}["\047]'
if git diff --cached | grep -iE "$SECRETS_PATTERN" > /dev/null; then
    print_error "Potential secrets detected in staged changes"
    print_warning "Review your changes and use environment variables for secrets"
    exit 1
fi
print_success "No secrets detected"

# 3. Quick validation (API only - fast)
echo "🔍 Running API validation..."
if ! python validate.py --only api --format json > /dev/null 2>&1; then
    print_error "API validation failed"
    echo ""
    echo "Run 'make validate-api' to see details"
    echo "Or skip with: git commit --no-verify"
    exit 1
fi
print_success "API validation passed"

# 4. Python linting (if Python files changed)
PYTHON_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep '\.py$' || true)
if [ -n "$PYTHON_FILES" ]; then
    echo "🐍 Checking Python code style..."

    # Check if ruff is installed
    if command -v ruff &> /dev/null; then
        if ! echo "$PYTHON_FILES" | xargs ruff check --quiet 2>/dev/null; then
            print_error "Python linting failed"
            echo "Run 'make lint-fix' to auto-fix issues"
            echo "Or skip with: git commit --no-verify"
            exit 1
        fi
        print_success "Python linting passed"
    else
        print_warning "ruff not installed, skipping Python linting"
    fi
fi

# 5. TypeScript linting (if TS files changed)
TS_FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E '\.(ts|tsx)$' || true)
if [ -n "$TS_FILES" ]; then
    echo "📘 Checking TypeScript code style..."

    if [ -f "ui/package.json" ]; then
        cd ui
        if npm run lint --silent > /dev/null 2>&1; then
            print_success "TypeScript linting passed"
        else
            print_error "TypeScript linting failed"
            echo "Run 'cd ui && npm run lint' to see issues"
            echo "Or skip with: git commit --no-verify"
            exit 1
        fi
        cd ..
    fi
fi

echo ""
print_success "All pre-commit checks passed!"
echo ""
EOF

chmod +x "$HOOKS_DIR/pre-commit"
echo "✓ Installed pre-commit hook"

# ============================================
# PRE-PUSH HOOK
# ============================================
cat > "$HOOKS_DIR/pre-push" << 'EOF'
#!/bin/bash
# AVI Pre-push hook
# Runs comprehensive checks before pushing

set -e

echo "🚀 Running pre-push checks..."

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Check if we're in the right directory
if [ ! -f "validate.py" ]; then
    print_error "Not in AVI project root directory"
    exit 1
fi

# 1. Full validation pipeline
echo "🔍 Running full validation pipeline..."
if ! python validate.py --format json > /dev/null 2>&1; then
    print_error "Validation pipeline failed"
    echo ""
    echo "Critical issues found. Run 'make validate' to see details"
    echo ""
    print_warning "Fix high severity issues before pushing"
    print_warning "Or skip with: git push --no-verify"
    exit 1
fi
print_success "Validation pipeline passed"

# 2. Run unit tests (smoke tests)
echo "🧪 Running smoke tests..."
if [ -f "tests/unit" ]; then
    if ! pytest tests/unit -x --quiet --tb=no > /dev/null 2>&1; then
        print_error "Unit tests failed"
        echo "Run 'make test' to see details"
        echo "Or skip with: git push --no-verify"
        exit 1
    fi
    print_success "Unit tests passed"
else
    print_warning "No unit tests found, skipping"
fi

# 3. Check test coverage (if tests ran)
# echo "📊 Checking test coverage..."
# Disabled for now - can be enabled later

echo ""
print_success "All pre-push checks passed!"
echo ""
print_warning "Remember to create a PR for review before merging to main"
echo ""
EOF

chmod +x "$HOOKS_DIR/pre-push"
echo "✓ Installed pre-push hook"

# ============================================
# COMMIT-MSG HOOK (optional)
# ============================================
cat > "$HOOKS_DIR/commit-msg" << 'EOF'
#!/bin/bash
# AVI Commit message hook
# Validates commit message format

COMMIT_MSG_FILE=$1
COMMIT_MSG=$(cat "$COMMIT_MSG_FILE")

# Allow merge commits
if echo "$COMMIT_MSG" | grep -qE "^Merge "; then
    exit 0
fi

# Check for conventional commit format
# Format: type(scope): description
# Example: feat(api): add new endpoint
if ! echo "$COMMIT_MSG" | grep -qE "^(feat|fix|docs|style|refactor|perf|test|chore|ci|build|revert)(\(.+\))?:\s.+"; then
    echo "❌ Invalid commit message format"
    echo ""
    echo "Commit message should follow conventional commits format:"
    echo "  type(scope): description"
    echo ""
    echo "Types: feat, fix, docs, style, refactor, perf, test, chore, ci, build, revert"
    echo ""
    echo "Examples:"
    echo "  feat(api): add chat endpoint"
    echo "  fix(ui): resolve navigation bug"
    echo "  docs: update README"
    echo ""
    echo "Or skip with: git commit --no-verify"
    exit 1
fi

exit 0
EOF

chmod +x "$HOOKS_DIR/commit-msg"
echo "✓ Installed commit-msg hook"

echo ""
echo "✅ Git hooks installed successfully!"
echo ""
echo "Hooks installed:"
echo "  • pre-commit  - Fast checks (linting, API validation)"
echo "  • pre-push    - Comprehensive checks (full validation, tests)"
echo "  • commit-msg  - Conventional commit format validation"
echo ""
echo "To skip hooks temporarily:"
echo "  git commit --no-verify"
echo "  git push --no-verify"
echo ""
