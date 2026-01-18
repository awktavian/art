#!/bin/bash
# WireGuard Healthcheck
#
# Verifies VPN tunnel is up and home network is reachable.

WG_INTERFACE="${WG_INTERFACE:-wg0}"
HOME_GATEWAY="${HOME_GATEWAY:-192.168.1.1}"

# Check if interface exists
if ! ip link show "$WG_INTERFACE" &>/dev/null; then
    echo "❌ WireGuard interface $WG_INTERFACE not found"
    exit 1
fi

# Check if interface is up
if ! ip link show "$WG_INTERFACE" | grep -q "UP"; then
    echo "❌ WireGuard interface is down"
    exit 1
fi

# Check handshake (connection established)
LAST_HANDSHAKE=$(wg show "$WG_INTERFACE" latest-handshakes 2>/dev/null | awk '{print $2}')
if [ -z "$LAST_HANDSHAKE" ] || [ "$LAST_HANDSHAKE" -eq 0 ]; then
    echo "⚠️ No WireGuard handshake yet"
    # Don't fail - might still be connecting
    exit 0
fi

# Check if handshake is recent (within 3 minutes)
NOW=$(date +%s)
HANDSHAKE_AGE=$((NOW - LAST_HANDSHAKE))
if [ "$HANDSHAKE_AGE" -gt 180 ]; then
    echo "⚠️ Last handshake was ${HANDSHAKE_AGE}s ago"
fi

# Ping home gateway
if ping -c 1 -W 2 "$HOME_GATEWAY" &>/dev/null; then
    echo "✅ VPN healthy - home network reachable"
    exit 0
else
    echo "❌ Cannot reach home gateway $HOME_GATEWAY"
    exit 1
fi
