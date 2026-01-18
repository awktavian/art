#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
#                     K OS OVERNIGHT PRETRAINING
# ═══════════════════════════════════════════════════════════════════════════════
#
# Usage:
#   ./scripts/benchmark/overnight_train.sh           # Run in foreground
#   ./scripts/benchmark/overnight_train.sh --bg      # Run in background
#
# Monitor:
#   tail -f logs/overnight_train.log                # Watch logs
#   W&B Dashboard: https://wandb.ai                 # Metrics
#
# Stop:
#   kill $(cat logs/overnight_train.pid)            # Stop background run
#
# Generated: December 8, 2025
# Updated: December 27, 2025 - Migrated from TensorBoard to W&B
# ═══════════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# ─────────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────────

# Model
BULK_DIM=${BULK_DIM:-1024}              # 1024D maximal config

# Training
BATCH_SIZE=${BATCH_SIZE:-32}            # Effective batch = 32 * 16 = 512
MAX_STEPS=${MAX_STEPS:-15000}           # ~10 hours @ 2.6s/step
LEARNING_RATE=${LEARNING_RATE:-5.65e-4} # Scaled for effective batch size

# Intervals
LOG_INTERVAL=${LOG_INTERVAL:-100}
SAVE_INTERVAL=${SAVE_INTERVAL:-1000}    # Checkpoint every ~40 mins

# Paths
LOG_DIR="$PROJECT_ROOT/logs"
LOG_FILE="$LOG_DIR/overnight_train.log"
PID_FILE="$LOG_DIR/overnight_train.pid"

mkdir -p "$LOG_DIR" checkpoints/kagami

# ─────────────────────────────────────────────────────────────────────────────────
# ENVIRONMENT
# ─────────────────────────────────────────────────────────────────────────────────

# Activate virtual environment
if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Set bulk dimension
export KAGAMI_BULK_DIM="$BULK_DIM"

# ─────────────────────────────────────────────────────────────────────────────────
# TRAINING COMMAND
# ─────────────────────────────────────────────────────────────────────────────────

TRAIN_CMD="python scripts/training/train_kagami.py \
    --config config/training_optimal.yaml \
    --bulk-dim $BULK_DIM \
    --batch-size $BATCH_SIZE \
    --max-steps $MAX_STEPS \
    --lr $LEARNING_RATE"

# ─────────────────────────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════════════════════"
echo "                     K OS OVERNIGHT PRETRAINING"
echo "═══════════════════════════════════════════════════════════════════════════════"
echo ""
echo "Configuration:"
echo "  Model:      ${BULK_DIM}D bulk dimension"
echo "  Batch:      ${BATCH_SIZE} (effective: $(($BATCH_SIZE * 16)))"
echo "  Steps:      ${MAX_STEPS}"
echo "  Est. time:  ~$((($MAX_STEPS * 3) / 3600)) hours"
echo ""
echo "Outputs:"
echo "  Logs:       $LOG_FILE"
echo "  Checkpoints: checkpoints/kagami/"
echo "  W&B:        https://wandb.ai (project: kagami-world-model)"
echo ""

if [ "$1" = "--bg" ]; then
    echo "Starting in background..."
    nohup $TRAIN_CMD > "$LOG_FILE" 2>&1 &
    echo $! > "$PID_FILE"
    echo "PID: $(cat $PID_FILE)"
    echo ""
    echo "Monitor with: tail -f $LOG_FILE"
    echo "W&B:          https://wandb.ai (project: kagami-world-model)"
    echo "Stop with:    kill \$(cat $PID_FILE)"
else
    echo "Starting in foreground (Ctrl+C to stop)..."
    echo ""
    exec $TRAIN_CMD 2>&1 | tee "$LOG_FILE"
fi
