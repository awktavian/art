#!/bin/bash
# Robust training wrapper - prevents macOS sleep/throttling
#
# Usage: ./scripts/training/run_training_robust.sh [--resume]
#
# Features:
# - Uses caffeinate to prevent system sleep
# - Saves checkpoint on SIGTERM/SIGINT
# - Auto-restarts on crash (up to 3 times)
# - Logs with timestamps

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"
CHECKPOINT_DIR="$PROJECT_ROOT/checkpoints/kagami"
VENV="$PROJECT_ROOT/.venv/bin/activate"

mkdir -p "$LOG_DIR" "$CHECKPOINT_DIR"

# Log file with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="$LOG_DIR/train_robust_$TIMESTAMP.log"

# Parse args
RESUME_ARG=""
if [[ "$1" == "--resume" ]] || [[ -f "$CHECKPOINT_DIR/latest.pt" ]]; then
    if [[ -f "$CHECKPOINT_DIR/latest.pt" ]]; then
        RESUME_ARG="--resume $CHECKPOINT_DIR/latest.pt"
        echo "Resuming from checkpoint: $CHECKPOINT_DIR/latest.pt"
    fi
fi

# Training parameters
MAX_STEPS=100000
BATCH_SIZE=16

echo "=============================================="
echo "K OS Robust Training Launcher"
echo "=============================================="
echo "Log file: $LOG_FILE"
echo "Checkpoint dir: $CHECKPOINT_DIR"
echo "Max steps: $MAX_STEPS"
echo "Using caffeinate to prevent sleep"
echo "=============================================="

cd "$PROJECT_ROOT"
source "$VENV"

# Function to handle signals
cleanup() {
    echo ""
    echo "$(date): Received signal, training will save checkpoint and exit..."
    # Give the Python process a chance to save
    sleep 5
    exit 0
}

trap cleanup SIGINT SIGTERM

# Save PID for monitoring
echo $$ > "$LOG_DIR/train_robust.pid"

# Run with caffeinate to prevent sleep
# -i: Prevent idle sleep
# -s: Prevent system sleep (AC power required for full effect on battery)
# -d: Prevent display sleep (optional, remove if display should sleep)
# -w: Wait for process to finish

caffeinate -is -w $$ &
CAFFEINATE_PID=$!

echo "Caffeinate PID: $CAFFEINATE_PID"
echo "Training PID: $$"

# Retry loop (up to 3 restarts on crash)
MAX_RETRIES=3
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    echo "$(date): Starting training (attempt $((RETRY_COUNT + 1))/$MAX_RETRIES)..."

    # Run training with signal handling
    python scripts/training/train_kagami.py \
        --batch-size $BATCH_SIZE \
        --max-steps $MAX_STEPS \
        --log-dir runs/train_robust \
        $RESUME_ARG \
        2>&1 | tee -a "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}

    if [ $EXIT_CODE -eq 0 ]; then
        echo "$(date): Training completed successfully!"
        break
    elif [ $EXIT_CODE -eq 130 ] || [ $EXIT_CODE -eq 143 ]; then
        # SIGINT (130) or SIGTERM (143) - user interrupted
        echo "$(date): Training interrupted by user (exit code $EXIT_CODE)"
        break
    else
        echo "$(date): Training crashed with exit code $EXIT_CODE"
        RETRY_COUNT=$((RETRY_COUNT + 1))

        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            # Auto-resume from latest checkpoint
            if [[ -f "$CHECKPOINT_DIR/latest.pt" ]]; then
                RESUME_ARG="--resume $CHECKPOINT_DIR/latest.pt"
            fi
            echo "$(date): Waiting 30s before restart..."
            sleep 30
        fi
    fi
done

# Cleanup
kill $CAFFEINATE_PID 2>/dev/null || true
rm -f "$LOG_DIR/train_robust.pid"

echo "$(date): Training script finished."
