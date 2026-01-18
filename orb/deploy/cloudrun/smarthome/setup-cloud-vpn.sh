#!/bin/bash
# Setup GCP Cloud VPN to UniFi for Kagami SmartHome
#
# Creates an IPsec VPN tunnel between Google Cloud and your UniFi network.
# Cloud Run connects to home devices through VPC Connector → Cloud VPN → UniFi.
#
# Architecture:
#   Cloud Run → VPC Connector → Cloud VPN Gateway → IPsec → UniFi VPN → Home Network
#
# Cost: ~$36/month (Cloud VPN gateway)
#
# Run: ./setup-cloud-vpn.sh

set -euo pipefail

PROJECT_ID="gen-lang-client-0509316009"
REGION="us-west1"
NETWORK="kagami-vpc"
SUBNET="kagami-subnet"
VPN_GATEWAY="kagami-vpn-gateway"
VPN_TUNNEL="kagami-home-tunnel"
ROUTER="kagami-router"
CONNECTOR="kagami-connector"

# Your home network
HOME_SUBNET="192.168.1.0/24"
CLOUD_SUBNET="10.8.0.0/28"  # For VPC connector

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔐 GCP Cloud VPN + UniFi Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "This will create:"
echo "  - VPC Network: $NETWORK"
echo "  - Cloud VPN Gateway: $VPN_GATEWAY"
echo "  - VPC Connector for Cloud Run"
echo ""
echo "Estimated cost: ~\$36/month"
echo ""
read -p "Continue? (y/n): " CONTINUE
[ "$CONTINUE" != "y" ] && exit 0

# Enable required APIs
echo ""
echo "📦 Enabling APIs..."
gcloud services enable \
    compute.googleapis.com \
    vpcaccess.googleapis.com \
    --project="$PROJECT_ID"

# Create VPC network
echo ""
echo "🌐 Creating VPC network..."
gcloud compute networks create "$NETWORK" \
    --project="$PROJECT_ID" \
    --subnet-mode=custom \
    2>/dev/null || echo "Network already exists"

# Create subnet for VPC connector
echo "📍 Creating subnet..."
gcloud compute networks subnets create "$SUBNET" \
    --project="$PROJECT_ID" \
    --network="$NETWORK" \
    --region="$REGION" \
    --range="$CLOUD_SUBNET" \
    2>/dev/null || echo "Subnet already exists"

# Create Cloud Router (required for VPN)
echo "🔀 Creating Cloud Router..."
gcloud compute routers create "$ROUTER" \
    --project="$PROJECT_ID" \
    --network="$NETWORK" \
    --region="$REGION" \
    2>/dev/null || echo "Router already exists"

# Create VPN Gateway
echo "🚪 Creating VPN Gateway..."
gcloud compute vpn-gateways create "$VPN_GATEWAY" \
    --project="$PROJECT_ID" \
    --network="$NETWORK" \
    --region="$REGION" \
    2>/dev/null || echo "VPN Gateway already exists"

# Get VPN Gateway external IP
VPN_IP=$(gcloud compute vpn-gateways describe "$VPN_GATEWAY" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --format="value(vpnInterfaces[0].ipAddress)" 2>/dev/null || echo "PENDING")

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Configure UniFi Site-to-Site VPN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Open UniFi Network Console: https://192.168.1.1"
echo ""
echo "2. Go to: Settings → Teleport & VPN → Site-to-Site VPN"
echo ""
echo "3. Create new VPN:"
echo "   - VPN Type: IPsec"
echo "   - Remote Gateway: $VPN_IP"
echo "   - Remote Subnets: $CLOUD_SUBNET"
echo "   - Local Subnets: $HOME_SUBNET"
echo ""
echo "4. Generate a strong Pre-Shared Key (PSK)"
echo ""
read -p "Enter the Pre-Shared Key you configured in UniFi: " PSK
read -p "Enter your home's public IP (WAN IP): " HOME_IP

# Create VPN Tunnel
echo ""
echo "🔗 Creating VPN Tunnel..."

# Create external VPN gateway (represents UniFi)
gcloud compute external-vpn-gateways create unifi-gateway \
    --project="$PROJECT_ID" \
    --interfaces="0=$HOME_IP" \
    2>/dev/null || echo "External gateway already exists"

# Create VPN tunnel
gcloud compute vpn-tunnels create "$VPN_TUNNEL" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --vpn-gateway="$VPN_GATEWAY" \
    --peer-external-gateway="unifi-gateway" \
    --peer-external-gateway-interface=0 \
    --shared-secret="$PSK" \
    --router="$ROUTER" \
    --ike-version=2 \
    2>/dev/null || echo "Tunnel already exists"

# Create BGP session or static route
echo "📍 Creating route to home network..."
gcloud compute routers add-interface "$ROUTER" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --interface-name="tunnel-interface" \
    --vpn-tunnel="$VPN_TUNNEL" \
    --ip-address="169.254.0.1" \
    --mask-length=30 \
    2>/dev/null || true

# Add static route to home subnet
gcloud compute routes create route-to-home \
    --project="$PROJECT_ID" \
    --network="$NETWORK" \
    --destination-range="$HOME_SUBNET" \
    --next-hop-vpn-tunnel="$VPN_TUNNEL" \
    --next-hop-vpn-tunnel-region="$REGION" \
    2>/dev/null || echo "Route already exists"

# Create VPC Connector for Cloud Run
echo ""
echo "🔌 Creating VPC Connector..."
gcloud compute networks vpc-access connectors create "$CONNECTOR" \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --network="$NETWORK" \
    --range="10.8.0.16/28" \
    --min-instances=2 \
    --max-instances=3 \
    2>/dev/null || echo "Connector already exists"

# Update Cloud Run service to use VPC connector
echo ""
echo "🚀 Updating Cloud Run service..."
gcloud run services update kagami-smarthome \
    --project="$PROJECT_ID" \
    --region="$REGION" \
    --vpc-connector="$CONNECTOR" \
    --vpc-egress=all-traffic

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ SETUP COMPLETE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "GCP VPN Gateway IP: $VPN_IP"
echo "Home Network: $HOME_SUBNET"
echo "Cloud Subnet: $CLOUD_SUBNET"
echo ""
echo "Verify tunnel status:"
echo "  gcloud compute vpn-tunnels describe $VPN_TUNNEL --region=$REGION"
echo ""
echo "Test connectivity:"
echo "  curl https://kagami-smarthome-927213148610.us-west1.run.app/health"
echo "  curl https://kagami-smarthome-927213148610.us-west1.run.app/state"
