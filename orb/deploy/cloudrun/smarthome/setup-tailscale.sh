#!/bin/bash
# Setup Tailscale for Kagami Cloud Run ↔ Home Network tunnel
#
# This script:
# 1. Installs Tailscale on your Mac
# 2. Configures it as a subnet router for your home network
# 3. Creates the auth key secret in GCP
#
# Run: ./setup-tailscale.sh

set -euo pipefail

PROJECT_ID="gen-lang-client-0509316009"
HOME_SUBNET="192.168.1.0/24"

echo "🔐 Kagami Tailscale Tunnel Setup"
echo "================================="
echo ""

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    echo "📦 Installing Tailscale..."
    brew install tailscale
else
    echo "✅ Tailscale already installed"
fi

# Check if tailscaled is running
if ! pgrep -x "tailscaled" > /dev/null; then
    echo "🚀 Starting Tailscale daemon..."
    # On macOS, use the app or run manually
    if [ -d "/Applications/Tailscale.app" ]; then
        open -a Tailscale
        sleep 3
    else
        echo "⚠️  Please install Tailscale.app from https://tailscale.com/download/mac"
        echo "   Or run: sudo tailscaled &"
        exit 1
    fi
fi

# Connect and advertise subnet routes
echo ""
echo "🌐 Connecting to Tailscale..."
echo "   Advertising subnet: $HOME_SUBNET"
echo ""

tailscale up \
    --advertise-routes="$HOME_SUBNET" \
    --accept-dns=false \
    --hostname="kagami-home-router"

echo ""
echo "✅ Tailscale connected!"
echo ""

# Show status
tailscale status

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 NEXT STEPS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. APPROVE SUBNET ROUTES in Tailscale Admin Console:"
echo "   https://login.tailscale.com/admin/machines"
echo ""
echo "   Find 'kagami-home-router' → Edit route settings → Enable $HOME_SUBNET"
echo ""
echo "2. GENERATE AUTH KEY for Cloud Run:"
echo "   https://login.tailscale.com/admin/settings/keys"
echo ""
echo "   Settings:"
echo "   - Reusable: Yes"
echo "   - Ephemeral: Yes"
echo "   - Pre-authorized: Yes"
echo "   - Tags: tag:cloudrun (optional)"
echo ""
echo "3. STORE AUTH KEY in GCP Secret Manager:"
echo ""
echo "   gcloud secrets create tailscale-authkey \\"
echo "     --project=$PROJECT_ID"
echo ""
echo "   echo -n 'tskey-auth-XXXXX' | \\"
echo "     gcloud secrets versions add tailscale-authkey \\"
echo "       --data-file=- --project=$PROJECT_ID"
echo ""
echo "4. DEPLOY Cloud Run with Tailscale sidecar:"
echo ""
echo "   gcloud run services replace deploy/cloudrun/smarthome/service-tailscale.yaml \\"
echo "     --region=us-west1 --project=$PROJECT_ID"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
