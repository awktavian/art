#!/bin/bash
# Pre-start checks for K os Extreme Scale deployment
# Validates system requirements and configuration

set -e

echo "🔍 K os Pre-Start Checks"
echo "================================"

# Check if running as correct user
if [ "$(whoami)" != "kagami" ]; then
    echo "⚠️  WARNING: Not running as 'kagami' user"
fi

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python: $PYTHON_VERSION"

# Check system resources
TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
FREE_RAM=$(free -g | awk '/^Mem:/{print $7}')
CPU_CORES=$(nproc)
DISK_FREE=$(df -BG /opt/kagami | awk 'NR==2 {print $4}' | sed 's/G//')

echo "✓ RAM: ${TOTAL_RAM}GB total, ${FREE_RAM}GB free"
echo "✓ CPUs: ${CPU_CORES} cores"
echo "✓ Disk: ${DISK_FREE}GB free"

# Validate minimum requirements
if [ "$TOTAL_RAM" -lt 32 ]; then
    echo "⚠️  WARNING: RAM < 32GB (have ${TOTAL_RAM}GB)"
fi

if [ "$CPU_CORES" -lt 8 ]; then
    echo "⚠️  WARNING: CPUs < 8 cores (have ${CPU_CORES})"
fi

if [ "$DISK_FREE" -lt 50 ]; then
    echo "⚠️  WARNING: Disk < 50GB free (have ${DISK_FREE}GB)"
fi

# Check database connectivity
if command -v pg_isready &> /dev/null; then
    if pg_isready -h localhost -p 26257 -U kagami &> /dev/null; then
        echo "✓ Database: Connected (CockroachDB)"
    else
        echo "❌ Database: NOT reachable"
        exit 1
    fi
else
    echo "⚠️  pg_isready not found, skipping DB check"
fi

# Check Redis connectivity
if command -v redis-cli &> /dev/null; then
    if redis-cli -h localhost -p 6379 ping | grep -q PONG; then
        echo "✓ Redis: Connected"
    else
        echo "❌ Redis: NOT reachable"
        exit 1
    fi
else
    echo "⚠️  redis-cli not found, skipping Redis check"
fi

# Check ulimits
NOFILE=$(ulimit -n)
NPROC=$(ulimit -u)

echo "✓ File descriptors: $NOFILE"
echo "✓ Max processes: $NPROC"

if [ "$NOFILE" -lt 65536 ]; then
    echo "⚠️  WARNING: File descriptors < 65536 (have $NOFILE)"
fi

# Check kernel parameters
if [ -f /proc/sys/net/core/somaxconn ]; then
    SOMAXCONN=$(cat /proc/sys/net/core/somaxconn)
    echo "✓ somaxconn: $SOMAXCONN"

    if [ "$SOMAXCONN" -lt 4096 ]; then
        echo "⚠️  WARNING: somaxconn < 4096 (have $SOMAXCONN)"
        echo "   Recommend: sysctl -w net.core.somaxconn=4096"
    fi
fi

# Check if extreme scale mode
if [ "$KAGAMI_MAX_TOTAL_POPULATION" -gt 10000 ]; then
    echo ""
    echo "🔥 EXTREME SCALE MODE ENABLED"
    echo "   Max population: $KAGAMI_MAX_TOTAL_POPULATION"
    echo "   This will use significant resources!"
fi

echo ""
echo "✅ Pre-start checks complete"
exit 0
