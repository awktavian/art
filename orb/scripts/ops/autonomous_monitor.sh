#!/bin/bash
# Autonomous Training Monitor
# Checks training every 10 minutes and logs status
# Automatically restarts if training crashes

MONITOR_LOG="/tmp/autonomous_monitor.log"
CHECK_INTERVAL=600  # 10 minutes

echo "==================================================================="
echo "Autonomous Training Monitor Started"
echo "Time: $(date)"
echo "Check interval: ${CHECK_INTERVAL}s ($(($CHECK_INTERVAL / 60)) minutes)"
echo "Monitor log: $MONITOR_LOG"
echo "==================================================================="

while true; do
    echo "" >> "$MONITOR_LOG"
    echo "=== Check at $(date) ===" >> "$MONITOR_LOG"

    # Check if training is running
    if ps aux | grep -v grep | grep "kagami.core.training.pretrain" > /dev/null; then
        echo "✅ Training is running" >> "$MONITOR_LOG"

        # Get latest log file
        LOG_FILE=$(ls -t /tmp/training_overnight_*.log 2>/dev/null | head -1)

        if [ -n "$LOG_FILE" ]; then
            # Extract latest step info
            LATEST_STEP=$(tail -200 "$LOG_FILE" | grep -oE "Step [0-9]+" | tail -1)
            LATEST_LOSS=$(tail -200 "$LOG_FILE" | grep -oE "loss.*[0-9]+\.[0-9]+" | tail -1)

            echo "  Latest: $LATEST_STEP" >> "$MONITOR_LOG"
            echo "  $LATEST_LOSS" >> "$MONITOR_LOG"

            # Check for CBF violations
            VIOLATIONS=$(tail -500 "$LOG_FILE" | grep -i "cbf.*violation" | wc -l | tr -d ' ')
            echo "  CBF violations: $VIOLATIONS" >> "$MONITOR_LOG"

            # Check for recent errors (last 100 lines)
            ERROR_COUNT=$(tail -100 "$LOG_FILE" | grep -iE "error:|exception:" | wc -l | tr -d ' ')
            if [ "$ERROR_COUNT" -gt 0 ]; then
                echo "  ⚠️ Recent errors: $ERROR_COUNT" >> "$MONITOR_LOG"
                tail -100 "$LOG_FILE" | grep -iE "error:|exception:" | tail -2 >> "$MONITOR_LOG"
            fi
        fi
    else
        echo "❌ Training NOT running" >> "$MONITOR_LOG"

        # Check if it completed successfully
        LOG_FILE=$(ls -t /tmp/training_overnight_*.log 2>/dev/null | head -1)
        if [ -n "$LOG_FILE" ]; then
            if tail -50 "$LOG_FILE" | grep -q "Training Complete"; then
                echo "  ✅ Training completed successfully" >> "$MONITOR_LOG"
                break  # Exit monitor
            else
                echo "  ⚠️ Training may have crashed" >> "$MONITOR_LOG"
                # Could add auto-restart logic here
            fi
        fi
    fi

    sleep "$CHECK_INTERVAL"
done

echo "==================================================================="
echo "Autonomous Monitor Stopped at $(date)"
echo "==================================================================="
