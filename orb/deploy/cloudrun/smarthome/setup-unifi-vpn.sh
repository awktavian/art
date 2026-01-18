#!/bin/bash
# Setup UniFi WireGuard VPN for Cloud Run Tunnel
#
# This script:
# 1. Generates WireGuard keypair for Cloud Run
# 2. Guides you through UniFi VPN setup
# 3. Stores secrets in GCP Secret Manager
# 4. Deploys Cloud Run with VPN sidecar
#
# Prerequisites:
# - UniFi Dream Machine / Dream Router / UDR / UDM-Pro
# - UniFi Network 7.0+ (WireGuard support)
# - gcloud CLI authenticated
#
# Run: ./setup-unifi-vpn.sh

set -euo pipefail

PROJECT_ID="gen-lang-client-0509316009"
REGION="us-west1"
HOME_SUBNET="192.168.1.0/24"
VPN_ADDRESS="10.0.0.2/32"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 UniFi WireGuard VPN Setup for Kagami Cloud Run"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check for wg command
if ! command -v wg &> /dev/null; then
    echo "📦 Installing WireGuard tools..."
    brew install wireguard-tools
fi

# Generate keypair for Cloud Run client
echo "🔑 Generating WireGuard keypair for Cloud Run..."
PRIVATE_KEY=$(wg genkey)
PUBLIC_KEY=$(echo "$PRIVATE_KEY" | wg pubkey)

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 1: Configure UniFi WireGuard VPN Server"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Open UniFi Network Console: https://192.168.1.1"
echo ""
echo "2. Go to: Settings → Teleport & VPN → VPN Server"
echo ""
echo "3. Create a new WireGuard VPN Server:"
echo "   - Enable: ON"
echo "   - Server Address: 10.0.0.1/24"
echo "   - Listen Port: 51820 (or custom)"
echo "   - DNS: 192.168.1.1"
echo ""
echo "4. Under 'Users', add a new VPN client:"
echo "   - Name: kagami-cloudrun"
echo "   - IP Address: $VPN_ADDRESS"
echo ""
echo "5. Enter this PUBLIC KEY for the client:"
echo ""
echo "   ╔════════════════════════════════════════════════════╗"
echo "   ║  $PUBLIC_KEY  ║"
echo "   ╚════════════════════════════════════════════════════╝"
echo ""
echo "6. Copy the SERVER PUBLIC KEY from UniFi (shown after saving)"
echo ""
read -p "Enter UniFi WireGuard Server PUBLIC KEY: " SERVER_PUBLIC_KEY
echo ""

# Get external IP/hostname
read -p "Enter your home's public IP or hostname (e.g., home.example.com): " HOME_ENDPOINT
read -p "Enter WireGuard port (default 51820): " WG_PORT
WG_PORT="${WG_PORT:-51820}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 2: Port Forwarding (if behind NAT)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "If your UniFi is behind another router, forward:"
echo "   UDP port $WG_PORT → 192.168.1.1:$WG_PORT"
echo ""
echo "UniFi should handle this automatically if it's the edge router."
echo ""
read -p "Press Enter when port forwarding is configured..."

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 3: Storing Secrets in GCP"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Create WireGuard config
WG_CONFIG=$(cat << EOF
[Interface]
PrivateKey = ${PRIVATE_KEY}
Address = ${VPN_ADDRESS}
DNS = 192.168.1.1

[Peer]
PublicKey = ${SERVER_PUBLIC_KEY}
AllowedIPs = ${HOME_SUBNET}
Endpoint = ${HOME_ENDPOINT}:${WG_PORT}
PersistentKeepalive = 25
EOF
)

echo "Creating/updating GCP secrets..."

# Store WireGuard config as secret
echo "$WG_CONFIG" | gcloud secrets create wireguard-config \
    --data-file=- \
    --project="$PROJECT_ID" 2>/dev/null || \
echo "$WG_CONFIG" | gcloud secrets versions add wireguard-config \
    --data-file=- \
    --project="$PROJECT_ID"

echo "✅ wireguard-config secret stored"

# Store individual values for flexibility
echo -n "$PRIVATE_KEY" | gcloud secrets create wireguard-private-key \
    --data-file=- \
    --project="$PROJECT_ID" 2>/dev/null || \
echo -n "$PRIVATE_KEY" | gcloud secrets versions add wireguard-private-key \
    --data-file=- \
    --project="$PROJECT_ID"

echo "✅ wireguard-private-key secret stored"

echo -n "$SERVER_PUBLIC_KEY" | gcloud secrets create wireguard-peer-pubkey \
    --data-file=- \
    --project="$PROJECT_ID" 2>/dev/null || \
echo -n "$SERVER_PUBLIC_KEY" | gcloud secrets versions add wireguard-peer-pubkey \
    --data-file=- \
    --project="$PROJECT_ID"

echo "✅ wireguard-peer-pubkey secret stored"

echo -n "${HOME_ENDPOINT}:${WG_PORT}" | gcloud secrets create wireguard-endpoint \
    --data-file=- \
    --project="$PROJECT_ID" 2>/dev/null || \
echo -n "${HOME_ENDPOINT}:${WG_PORT}" | gcloud secrets versions add wireguard-endpoint \
    --data-file=- \
    --project="$PROJECT_ID"

echo "✅ wireguard-endpoint secret stored"

# Grant Cloud Run service account access to secrets
SA_EMAIL="kagami-smarthome@${PROJECT_ID}.iam.gserviceaccount.com"

for SECRET in wireguard-config wireguard-private-key wireguard-peer-pubkey wireguard-endpoint; do
    gcloud secrets add-iam-policy-binding "$SECRET" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="roles/secretmanager.secretAccessor" \
        --project="$PROJECT_ID" --quiet
done

echo "✅ Secret access granted to service account"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 STEP 4: Build and Deploy"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

read -p "Deploy now? (y/n): " DEPLOY_NOW

if [ "$DEPLOY_NOW" = "y" ]; then
    echo ""
    echo "🏗️ Building WireGuard sidecar..."
    
    # Build WireGuard sidecar image
    cd "$(dirname "$0")"
    gcloud builds submit ./wireguard \
        --tag="gcr.io/${PROJECT_ID}/kagami-wireguard:latest" \
        --project="$PROJECT_ID"
    
    echo ""
    echo "🚀 Deploying Cloud Run with VPN..."
    
    # Deploy using the multi-container service definition
    gcloud run services replace service-wireguard.yaml \
        --region="$REGION" \
        --project="$PROJECT_ID"
    
    echo ""
    echo "✅ Deployment complete!"
else
    echo ""
    echo "To deploy later, run:"
    echo ""
    echo "  # Build WireGuard sidecar"
    echo "  gcloud builds submit deploy/cloudrun/smarthome/wireguard \\"
    echo "    --tag=gcr.io/${PROJECT_ID}/kagami-wireguard:latest"
    echo ""
    echo "  # Deploy service"
    echo "  gcloud run services replace deploy/cloudrun/smarthome/service-wireguard.yaml \\"
    echo "    --region=$REGION --project=$PROJECT_ID"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SETUP COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Cloud Run Public Key (for reference):"
echo "  $PUBLIC_KEY"
echo ""
echo "VPN Endpoint: ${HOME_ENDPOINT}:${WG_PORT}"
echo "VPN Address: $VPN_ADDRESS"
echo "Home Subnet: $HOME_SUBNET"
echo ""
echo "Test connectivity after deployment:"
echo "  curl https://kagami-smarthome-927213148610.us-west1.run.app/health"
echo "  curl https://kagami-smarthome-927213148610.us-west1.run.app/state"
