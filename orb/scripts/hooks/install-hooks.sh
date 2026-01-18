#!/bin/bash
# Install Kagami git hooks
#
# Usage: ./scripts/hooks/install-hooks.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
HOOKS_DIR="$PROJECT_ROOT/.git/hooks"

echo "🔧 Installing Kagami git hooks..."

# Create hooks directory if it doesn't exist
mkdir -p "$HOOKS_DIR"

# Install post-commit hook
if [ -f "$HOOKS_DIR/post-commit" ]; then
    echo "  ⚠️  post-commit hook exists, backing up to post-commit.bak"
    cp "$HOOKS_DIR/post-commit" "$HOOKS_DIR/post-commit.bak"
fi

cp "$SCRIPT_DIR/post-commit" "$HOOKS_DIR/post-commit"
chmod +x "$HOOKS_DIR/post-commit"
echo "  ✅ Installed post-commit hook"

# Install pre-commit via pre-commit framework
if command -v pre-commit &> /dev/null; then
    echo "  Installing pre-commit hooks..."
    cd "$PROJECT_ROOT"
    pre-commit install
    echo "  ✅ Pre-commit hooks installed"
else
    echo "  ⚠️  pre-commit not found. Install with: pip install pre-commit"
    echo "     Then run: pre-commit install"
fi

echo ""
echo "✅ Git hooks installed!"
echo ""
echo "Installed hooks:"
echo "  - post-commit: Verifies integration status after commits"
echo "  - pre-commit: Runs linting, type checking, quality score"
echo ""
echo "To verify integrations manually:"
echo "  python scripts/verify_integrations.py"
