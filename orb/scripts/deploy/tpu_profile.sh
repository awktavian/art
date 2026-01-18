#!/bin/bash
# TPU Remote Profiling Setup
#
# This script sets up profiling on a TPU VM and streams results to GCS.
#
# Usage:
#   ./scripts/deploy/tpu_profile.sh start <tpu-name> <zone>
#   ./scripts/deploy/tpu_profile.sh stop <tpu-name> <zone>
#   ./scripts/deploy/tpu_profile.sh status <tpu-name> <zone>
#   ./scripts/deploy/tpu_profile.sh logs <tpu-name> <zone>
#   ./scripts/deploy/tpu_profile.sh download <tpu-name> <zone>
#
# Created: January 11, 2026

set -e

# Configuration
GCS_BUCKET="${GCS_BUCKET:-gs://kagami-training-profiles}"
PROJECT="${GCP_PROJECT:-kagami-prod}"
PROFILE_DIR="/tmp/kagami_profiles"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    echo "Usage: $0 <command> <tpu-name> <zone>"
    echo ""
    echo "Commands:"
    echo "  start     Start profiling on TPU"
    echo "  stop      Stop profiling and collect results"
    echo "  status    Check profiling status"
    echo "  logs      Show profiling logs"
    echo "  download  Download profile results"
    echo ""
    echo "Environment variables:"
    echo "  GCS_BUCKET   GCS bucket for profiles (default: gs://kagami-training-profiles)"
    echo "  GCP_PROJECT  GCP project ID (default: kagami-prod)"
    exit 1
}

# Check arguments
if [ $# -lt 3 ]; then
    usage
fi

COMMAND=$1
TPU_NAME=$2
ZONE=$3

ssh_tpu() {
    gcloud compute tpus tpu-vm ssh "$TPU_NAME" \
        --zone="$ZONE" \
        --project="$PROJECT" \
        --command="$1"
}

scp_from_tpu() {
    gcloud compute tpus tpu-vm scp "$TPU_NAME:$1" "$2" \
        --zone="$ZONE" \
        --project="$PROJECT"
}

case $COMMAND in
    start)
        log_info "Starting profiling on TPU: $TPU_NAME"

        # Install dependencies if needed
        log_info "Checking dependencies..."
        ssh_tpu "pip install -q tensorboard-plugin-profile tensorboard"

        # Create profile directory
        ssh_tpu "mkdir -p $PROFILE_DIR"

        # Start TensorBoard in background
        log_info "Starting TensorBoard on port 6006..."
        ssh_tpu "nohup tensorboard --logdir=$PROFILE_DIR --port=6006 > /tmp/tensorboard.log 2>&1 &"

        # Get external IP
        EXTERNAL_IP=$(gcloud compute tpus tpu-vm describe "$TPU_NAME" \
            --zone="$ZONE" \
            --project="$PROJECT" \
            --format="value(networkEndpoints[0].accessConfig.externalIp)")

        log_info "TensorBoard started!"
        log_info "Access at: http://$EXTERNAL_IP:6006"
        log_info ""
        log_info "To capture a profile, run training with:"
        log_info "  JAX_TRACEBACK_FILTERING=off python train_tpu.py --profile-dir $PROFILE_DIR"
        log_info ""
        log_info "Or use the CLI:"
        log_info "  kagami-train benchmark --output $PROFILE_DIR"
        ;;

    stop)
        log_info "Stopping profiling on TPU: $TPU_NAME"

        # Kill TensorBoard
        ssh_tpu "pkill -f tensorboard || true"

        # Sync profiles to GCS
        RUN_ID=$(date +%Y%m%d-%H%M%S)
        GCS_PATH="$GCS_BUCKET/$TPU_NAME/$RUN_ID"

        log_info "Uploading profiles to $GCS_PATH..."
        ssh_tpu "gsutil -m cp -r $PROFILE_DIR/* $GCS_PATH/ || true"

        log_info "Profiles uploaded to: $GCS_PATH"
        log_info ""
        log_info "View with:"
        log_info "  tensorboard --logdir=$GCS_PATH"
        ;;

    status)
        log_info "Checking profiling status on TPU: $TPU_NAME"

        # Check TensorBoard
        TB_STATUS=$(ssh_tpu "pgrep -f tensorboard && echo 'running' || echo 'stopped'" 2>/dev/null)
        if [[ "$TB_STATUS" == *"running"* ]]; then
            log_info "TensorBoard: RUNNING"

            # Get port
            ssh_tpu "netstat -tlnp 2>/dev/null | grep 6006 || true"
        else
            log_warn "TensorBoard: STOPPED"
        fi

        # Check profile files
        log_info "Profile files:"
        ssh_tpu "ls -la $PROFILE_DIR 2>/dev/null || echo 'No profile directory'"
        ;;

    logs)
        log_info "Fetching profiling logs from TPU: $TPU_NAME"

        # TensorBoard logs
        log_info "=== TensorBoard Logs ==="
        ssh_tpu "tail -100 /tmp/tensorboard.log 2>/dev/null || echo 'No TensorBoard logs'"

        # Training logs
        log_info ""
        log_info "=== Training Logs (last 50 lines) ==="
        ssh_tpu "tail -50 ~/training.log 2>/dev/null || echo 'No training logs'"
        ;;

    download)
        log_info "Downloading profiles from TPU: $TPU_NAME"

        LOCAL_DIR="./profiles/$TPU_NAME-$(date +%Y%m%d-%H%M%S)"
        mkdir -p "$LOCAL_DIR"

        # Download from TPU
        scp_from_tpu "$PROFILE_DIR/*" "$LOCAL_DIR/" || true

        log_info "Profiles downloaded to: $LOCAL_DIR"
        log_info ""
        log_info "View with:"
        log_info "  tensorboard --logdir=$LOCAL_DIR"
        ;;

    *)
        log_error "Unknown command: $COMMAND"
        usage
        ;;
esac
