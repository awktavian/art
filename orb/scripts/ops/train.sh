#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# KAGAMI UNIFIED TRAINING LAUNCHER
# ═══════════════════════════════════════════════════════════════════════════════
#
# UPDATED: January 6, 2026 - Now uses consolidated.py (single entry point)
#
# FEATURES:
# - Trains OrganismRSSM (the REAL world model)
# - KL collapse prevention (free_bits=3.0)
# - Plateau detection with adaptive LR
# - TPU v6e support
#
# USAGE:
#   ./train.sh              # Start training with defaults
#   ./train.sh --quick      # Quick 100-step test
#   ./train.sh --config config/training_v6e_production.yaml
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# Default config
CONFIG="config/training_stable.yaml"
QUICK_TEST=false
WANDB_ENABLED=true
BACKEND="auto"

# Parse args
for arg in "$@"; do
    case $arg in
        --quick)
            QUICK_TEST=true
            shift
            ;;
        --no-wandb)
            WANDB_ENABLED=false
            shift
            ;;
        --config)
            CONFIG="$2"
            shift 2
            ;;
        --config=*)
            CONFIG="${arg#*=}"
            shift
            ;;
        --backend=*)
            BACKEND="${arg#*=}"
            shift
            ;;
    esac
done

# Activate virtual environment if present
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║              KAGAMI TRAINING (Consolidated Entry Point)          ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""
echo "📊 Training Settings (Jan 6, 2026 fixes):"
echo "   • Model: OrganismRSSM (7-colony RSSM with E8 quantization)"
echo "   • KL free_bits: 3.0 (prevents KL collapse)"
echo "   • Plateau detection: ENABLED"
echo "   • KL monitoring: ENABLED"
echo ""

# Create directories
mkdir -p checkpoints logs

# Configure training
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/training_${TIMESTAMP}.log"

echo "📁 Output:"
echo "   • Config: $CONFIG"
echo "   • Logs: $LOG_FILE"
if [ "$WANDB_ENABLED" = true ]; then
    echo "   • W&B: https://wandb.ai (project: kagami-world-model)"
fi
echo ""

# Build command
CMD="python -m kagami.core.training.consolidated --config $CONFIG --backend $BACKEND"

if [ "$QUICK_TEST" = true ]; then
    echo "⚡ QUICK TEST MODE (100 steps)"
    CMD="$CMD --steps 100 --no-wandb"
fi

if [ "$WANDB_ENABLED" = false ]; then
    CMD="$CMD --no-wandb"
fi

echo "🚀 Starting training..."
echo "   Command: $CMD"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Run training
$CMD 2>&1 | tee "$LOG_FILE"

TRAIN_EXIT=$?

echo ""
echo "═══════════════════════════════════════════════════════════════════"
if [ $TRAIN_EXIT -eq 0 ]; then
    echo "✅ Training completed successfully!"
else
    echo "⚠️  Training exited with code $TRAIN_EXIT"
fi
echo ""
echo "📊 View results:"
if [ "$WANDB_ENABLED" = true ]; then
    echo "   W&B Dashboard: https://wandb.ai (project: kagami-world-model)"
fi
echo "   Log file: $LOG_FILE"
echo ""

exit $TRAIN_EXIT
