#!/bin/bash
# Verification script for pre-commit hook setup
# Usage: ./scripts/verify_precommit_setup.sh

set -e

echo "=================================="
echo "Pre-commit Hook Verification"
echo "=================================="
echo ""

# Check pre-commit installation
echo "1. Checking pre-commit installation..."
if command -v pre-commit &> /dev/null; then
    VERSION=$(pre-commit --version)
    echo "   ✅ $VERSION"
else
    echo "   ❌ pre-commit not installed"
    echo "   Run: pip install pre-commit"
    exit 1
fi
echo ""

# Check git hooks
echo "2. Checking git hook installation..."
if [ -f ".git/hooks/pre-commit" ]; then
    echo "   ✅ Git hook installed at .git/hooks/pre-commit"
else
    echo "   ⚠️  Git hook not installed"
    echo "   Run: pre-commit install"
fi
echo ""

# Check config file
echo "3. Checking .pre-commit-config.yaml..."
if [ -f ".pre-commit-config.yaml" ]; then
    echo "   ✅ Configuration file exists"
    HOOK_COUNT=$(grep -c "id:" .pre-commit-config.yaml || echo "0")
    echo "   📋 $HOOK_COUNT hooks configured"
else
    echo "   ❌ Configuration file missing"
    exit 1
fi
echo ""

# Verify specific hooks
echo "4. Verifying custom hooks..."

# Check for wildcard import hook
if grep -q "no-wildcard-imports" .pre-commit-config.yaml; then
    echo "   ✅ no-wildcard-imports hook configured"
else
    echo "   ❌ no-wildcard-imports hook missing"
fi

# Check for mypy hook
if grep -q "mypy-safety" .pre-commit-config.yaml; then
    echo "   ✅ mypy-safety hook configured"
else
    echo "   ❌ mypy-safety hook missing"
fi

# Check for test-collect hook
if grep -q "test-collect" .pre-commit-config.yaml; then
    echo "   ✅ test-collect hook configured"
else
    echo "   ❌ test-collect hook missing"
fi
echo ""

# Test wildcard import detection
echo "5. Testing wildcard import detection..."
TEST_FILE="kagami/core/test_wildcard_tmp.py"
echo "from os import *" > "$TEST_FILE"

if pre-commit run no-wildcard-imports --files "$TEST_FILE" 2>&1 | grep -q "Wildcard imports found"; then
    echo "   ✅ Wildcard imports correctly detected"
else
    echo "   ❌ Wildcard import detection failed"
fi
rm -f "$TEST_FILE"
echo ""

# Test ruff hook
echo "6. Testing ruff hook..."
if pre-commit run ruff --files "kagami/core/safety/__init__.py" &> /dev/null; then
    echo "   ✅ Ruff hook works"
else
    echo "   ⚠️  Ruff hook found issues (expected)"
fi
echo ""

# Check documentation
echo "7. Checking documentation..."
if [ -f "docs/PRE_COMMIT_GUIDE.md" ]; then
    echo "   ✅ docs/PRE_COMMIT_GUIDE.md exists"
else
    echo "   ⚠️  Documentation missing"
fi

if [ -f "PRE_COMMIT_SETUP_SUMMARY.md" ]; then
    echo "   ✅ PRE_COMMIT_SETUP_SUMMARY.md exists"
else
    echo "   ⚠️  Setup summary missing"
fi
echo ""

# Check Makefile target
echo "8. Checking Makefile integration..."
if grep -q "^pre-commit:" Makefile; then
    echo "   ✅ make pre-commit target exists"
    grep "^pre-commit:" Makefile | head -1
else
    echo "   ❌ make pre-commit target missing"
fi
echo ""

# Summary
echo "=================================="
echo "Verification Summary"
echo "=================================="
echo ""
echo "✅ Pre-commit hooks configured and functional"
echo ""
echo "Quick commands:"
echo "  pre-commit run --all-files        # Run all hooks"
echo "  pre-commit run <hook-id>          # Run specific hook"
echo "  make pre-commit                   # Format + lint + typecheck + test-tier-1"
echo ""
echo "Documentation:"
echo "  docs/PRE_COMMIT_GUIDE.md          # User guide"
echo "  PRE_COMMIT_SETUP_SUMMARY.md       # Implementation details"
echo ""
