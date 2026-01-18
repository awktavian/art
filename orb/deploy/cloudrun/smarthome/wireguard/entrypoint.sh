#!/bin/bash
# WireGuard Sidecar Entrypoint
#
# Connects to UniFi WireGuard VPN using userspace implementation.

set -e

WG_INTERFACE="${WG_INTERFACE:-wg0}"
WG_CONFIG="/etc/wireguard/${WG_INTERFACE}.conf"

echo "🔐 WireGuard Sidecar Starting..."

# Check if config exists (from secret mount)
if [ ! -f "$WG_CONFIG" ]; then
    # Generate config from environment variables
    if [ -z "$WG_PRIVATE_KEY" ] || [ -z "$WG_PEER_PUBLIC_KEY" ] || [ -z "$WG_ENDPOINT" ]; then
        echo "❌ Missing WireGuard configuration!"
        echo "   Set WG_PRIVATE_KEY, WG_PEER_PUBLIC_KEY, WG_ENDPOINT"
        echo "   Or mount config at $WG_CONFIG"
        exit 1
    fi

    echo "📝 Generating WireGuard config from environment..."
    
    cat > "$WG_CONFIG" << EOF
[Interface]
PrivateKey = ${WG_PRIVATE_KEY}
Address = ${WG_ADDRESS:-10.0.0.2/24}
DNS = ${WG_DNS:-192.168.1.1}

[Peer]
PublicKey = ${WG_PEER_PUBLIC_KEY}
AllowedIPs = ${WG_ALLOWED_IPS:-192.168.1.0/24}
Endpoint = ${WG_ENDPOINT}
PersistentKeepalive = 25
EOF

    chmod 600 "$WG_CONFIG"
fi

echo "📋 WireGuard config loaded"

# Start userspace WireGuard
echo "🚀 Starting WireGuard (userspace mode)..."

# Create the interface using wireguard-go
WG_I_PREFER_BUGGY_CLOCKS=1 wireguard-go -f "$WG_INTERFACE" &
WG_PID=$!

# Wait for interface to come up
sleep 2

# Configure the interface
wg setconf "$WG_INTERFACE" <(grep -v "^Address\|^DNS" "$WG_CONFIG" | grep -v "^\[Interface\]")

# Set IP address
WG_ADDRESS=$(grep "^Address" "$WG_CONFIG" | cut -d= -f2 | tr -d ' ')
ip addr add "$WG_ADDRESS" dev "$WG_INTERFACE" 2>/dev/null || true
ip link set "$WG_INTERFACE" up

# Add routes for home network
WG_ALLOWED_IPS=$(grep "^AllowedIPs" "$WG_CONFIG" | cut -d= -f2 | tr -d ' ')
for route in $(echo "$WG_ALLOWED_IPS" | tr ',' '\n'); do
    ip route add "$route" dev "$WG_INTERFACE" 2>/dev/null || true
done

echo "✅ WireGuard connected!"
echo "   Interface: $WG_INTERFACE"
echo "   Address: $WG_ADDRESS"
echo "   Routes: $WG_ALLOWED_IPS"

# Show connection status
wg show "$WG_INTERFACE"

# Keep running
wait $WG_PID
