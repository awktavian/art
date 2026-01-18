#!/usr/bin/env bash
# Seven-Colony Code Review Demo Runner
#
# This script runs the flagship seven-colony code review demo with
# proper PYTHONPATH configuration.
#
# Usage:
#   ./examples/run_seven_colony_demo.sh          # Interactive mode
#   ./examples/run_seven_colony_demo.sh | cat    # Non-interactive mode

set -e

# Get script directory (examples/)
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Get project root (one level up)
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"

# Set PYTHONPATH to include project root
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Run demo
echo "Starting Seven-Colony Code Review Demo..."
echo "Project root: $PROJECT_ROOT"
echo ""

python "$SCRIPT_DIR/seven_colony_code_review.py"
