#!/bin/bash
# Wait for Docker services to be healthy before running tests

set -e

echo "Waiting for Redis..."
timeout 30 bash -c 'until docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; do sleep 1; done' || {
    echo "❌ Redis failed to become healthy"
    exit 1
}
echo "✅ Redis is healthy"

echo "Waiting for CockroachDB..."
timeout 30 bash -c 'until docker-compose exec -T cockroachdb curl -sf http://localhost:8080/health?ready=1 >/dev/null 2>&1; do sleep 1; done' || {
    echo "❌ CockroachDB failed to become healthy"
    exit 1
}
echo "✅ CockroachDB is healthy"

echo "✅ All services healthy and ready"
