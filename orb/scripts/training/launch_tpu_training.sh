#!/bin/bash
# Launch TPU Training for OrganismRSSM
#
# Prerequisites:
# 1. GCS buckets created (run setup_gcs_buckets.py)
# 2. Training data generated (run data generators)
# 3. TPU VM created in us-central2-b
#
# Usage:
#   ./launch_tpu_training.sh
#
# Created: January 12, 2026

set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT:-kagami-prod}"
TPU_NAME="${TPU_NAME:-kagami-tpu-v6e-4}"
TPU_ZONE="${TPU_ZONE:-us-central2-b}"
TPU_TYPE="${TPU_TYPE:-v6e-4}"
TPU_VERSION="${TPU_VERSION:-v2-alpha-tpuv6e}"

# Training configuration
DATA_DIR="${DATA_DIR:-gs://kagami-training-data/genesis/v1}"
CHECKPOINT_DIR="${CHECKPOINT_DIR:-gs://kagami-checkpoints/organism-rssm/run-$(date +%Y%m%d-%H%M%S)}"
MODEL_DIR="${MODEL_DIR:-gs://kagami-models/teacher}"

TOTAL_STEPS="${TOTAL_STEPS:-500000}"
BATCH_SIZE="${BATCH_SIZE:-256}"
SEQ_LEN="${SEQ_LEN:-32}"
LEARNING_RATE="${LEARNING_RATE:-1e-4}"

echo "============================================"
echo "OrganismRSSM TPU Training Launcher"
echo "============================================"
echo ""
echo "Project: ${PROJECT_ID}"
echo "TPU: ${TPU_NAME} (${TPU_TYPE})"
echo "Zone: ${TPU_ZONE}"
echo ""
echo "Data: ${DATA_DIR}"
echo "Checkpoints: ${CHECKPOINT_DIR}"
echo "Models: ${MODEL_DIR}"
echo ""
echo "Steps: ${TOTAL_STEPS}"
echo "Batch Size: ${BATCH_SIZE}"
echo "Sequence Length: ${SEQ_LEN}"
echo "Learning Rate: ${LEARNING_RATE}"
echo "============================================"

# Check if TPU exists
echo ""
echo "Checking TPU status..."
if gcloud compute tpus tpu-vm describe ${TPU_NAME} --zone=${TPU_ZONE} --project=${PROJECT_ID} >/dev/null 2>&1; then
    echo "✓ TPU ${TPU_NAME} exists"
    TPU_EXISTS=true
else
    echo "✗ TPU ${TPU_NAME} does not exist"
    TPU_EXISTS=false
fi

# Create TPU if needed
if [ "${TPU_EXISTS}" = false ]; then
    echo ""
    echo "Creating TPU VM ${TPU_NAME}..."
    gcloud compute tpus tpu-vm create ${TPU_NAME} \
        --zone=${TPU_ZONE} \
        --accelerator-type=${TPU_TYPE} \
        --version=${TPU_VERSION} \
        --project=${PROJECT_ID}
    echo "✓ TPU created"
fi

# Install dependencies on TPU
echo ""
echo "Installing dependencies on TPU..."
gcloud compute tpus tpu-vm ssh ${TPU_NAME} \
    --zone=${TPU_ZONE} \
    --project=${PROJECT_ID} \
    --command="
        pip install -q jax[tpu] -f https://storage.googleapis.com/jax-releases/libtpu_releases.html
        pip install -q flax optax tqdm tensorflow
        echo '✓ Dependencies installed'
    "

# Copy training code to TPU
echo ""
echo "Copying training code to TPU..."
TRAIN_SCRIPT="packages/kagami/core/training/jax/train_tpu.py"

gcloud compute tpus tpu-vm scp ${TRAIN_SCRIPT} ${TPU_NAME}:~/train_tpu.py \
    --zone=${TPU_ZONE} \
    --project=${PROJECT_ID}

echo "✓ Training code copied"

# Launch training
echo ""
echo "Launching training..."
echo ""

gcloud compute tpus tpu-vm ssh ${TPU_NAME} \
    --zone=${TPU_ZONE} \
    --project=${PROJECT_ID} \
    --command="
        export JAX_PLATFORMS=tpu
        export TF_CPP_MIN_LOG_LEVEL=2

        python3 train_tpu.py \
            --data-dir ${DATA_DIR} \
            --steps ${TOTAL_STEPS} \
            --batch-size ${BATCH_SIZE} \
            --seq-len ${SEQ_LEN} \
            --lr ${LEARNING_RATE} \
            --checkpoint-dir ${CHECKPOINT_DIR}
    "

echo ""
echo "============================================"
echo "Training complete!"
echo ""
echo "Checkpoints: ${CHECKPOINT_DIR}"
echo "============================================"

# Optional: Delete TPU after training
if [ "${DELETE_TPU_AFTER:-false}" = "true" ]; then
    echo ""
    echo "Deleting TPU ${TPU_NAME}..."
    gcloud compute tpus tpu-vm delete ${TPU_NAME} \
        --zone=${TPU_ZONE} \
        --project=${PROJECT_ID} \
        --quiet
    echo "✓ TPU deleted"
fi
