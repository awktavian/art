#!/usr/bin/env python3
"""K os Metrics Health Check Script.

Validates metrics infrastructure health, cardinality, and performance.
Created: October 29, 2025
"""

import requests
import sys
from collections import defaultdict


def check_metrics_endpoint(url: str = "http://localhost:8001/metrics") -> dict[str, any]:
    """Validate /metrics endpoint health and performance."""
    print(f"🔍 Checking metrics endpoint: {url}")
    print("=" * 70)

    try:
        import time

        start = time.time()
        resp = requests.get(url, timeout=5)
        duration_ms = (time.time() - start) * 1000

        if resp.status_code != 200:
            print(f"❌ FAILED: HTTP {resp.status_code}")
            return {"status": "error", "code": resp.status_code}

        print(f"✅ Endpoint OK (latency: {duration_ms:.1f}ms)")

        # Parse metrics
        lines = resp.text.split("\n")
        metrics = [l for l in lines if l and not l.startswith("#")]
        metric_count = len(metrics)
        size_kb = len(resp.text) / 1024

        print(f"📊 Response size: {size_kb:.1f} KB")
        print(f"📈 Total metric lines: {metric_count}")

        # Check for high cardinality
        unique_series = defaultdict(int)
        for line in metrics:
            if "{" in line:
                metric_name = line.split("{")[0]
                unique_series[metric_name] += 1

        print(f"\n📊 Unique time series: {len(unique_series)}")

        # Identify high-cardinality metrics
        high_cardinality = {k: v for k, v in unique_series.items() if v > 100}
        if high_cardinality:
            print(f"\n⚠️  HIGH CARDINALITY RISKS ({len(high_cardinality)} metrics):")
            for metric, count in sorted(high_cardinality.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]:
                print(f"  {metric:50} → {count:4} time series")
        else:
            print("\n✅ No high-cardinality risks detected")

        # Check scrape duration
        if duration_ms > 2000:
            print(f"\n⚠️  SLOW SCRAPE: {duration_ms:.1f}ms (>2s threshold)")
        elif duration_ms > 500:
            print(f"\n⚠️  Moderate scrape time: {duration_ms:.1f}ms")
        else:
            print(f"\n✅ Fast scrape: {duration_ms:.1f}ms")

        # Check for required metrics
        required_metrics = [
            "kagami_http_request_duration_seconds",
            "kagami_receipts_total",
            "kagami_errors_total",
            "kagami_db_pool_size",
            "kagami_redis_pool_size",
            "kagami_agent_mitosis_total",
            "kagami_cbf_blocks_total",
        ]

        missing = []
        for req in required_metrics:
            if not any(req in line for line in metrics):
                missing.append(req)

        if missing:
            print("\n⚠️  MISSING REQUIRED METRICS:")
            for m in missing:
                print(f"  - {m}")
        else:
            print("\n✅ All required metrics present")

        # Overall health score
        score = 100
        if high_cardinality:
            score -= len(high_cardinality) * 5
        if duration_ms > 2000:
            score -= 20
        elif duration_ms > 500:
            score -= 10
        if missing:
            score -= len(missing) * 10

        score = max(0, score)

        print(f"\n🎯 Overall Health Score: {score}/100")

        if score >= 90:
            print("   Status: ✅ EXCELLENT")
        elif score >= 70:
            print("   Status: ⚠️  GOOD (minor issues)")
        elif score >= 50:
            print("   Status: ⚠️  FAIR (needs attention)")
        else:
            print("   Status: ❌ POOR (immediate action required)")

        return {
            "status": "ok" if score >= 70 else "degraded",
            "score": score,
            "latency_ms": duration_ms,
            "size_kb": size_kb,
            "metric_count": metric_count,
            "unique_series": len(unique_series),
            "high_cardinality_count": len(high_cardinality),
            "missing_count": len(missing),
        }

    except requests.exceptions.ConnectionError:
        print("❌ FAILED: Cannot connect to metrics endpoint")
        print("   Ensure K os API is running: make run-api")
        return {"status": "error", "error": "connection_refused"}
    except requests.exceptions.Timeout:
        print("❌ FAILED: Request timed out after 5s")
        return {"status": "error", "error": "timeout"}
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return {"status": "error", "error": str(e)}


def check_label_cardinality(url: str = "http://localhost:8001/metrics") -> None:
    """Analyze label cardinality for all metrics."""
    print("\n\n🔍 LABEL CARDINALITY ANALYSIS")
    print("=" * 70)

    try:
        resp = requests.get(url, timeout=5)
        lines = resp.text.split("\n")

        # Parse metrics with labels
        label_cardinality = defaultdict(lambda: defaultdict(set))

        for line in lines:
            if "{" in line and "}" in line:
                metric_name = line.split("{")[0]
                labels_str = line.split("{")[1].split("}")[0]

                # Parse label key-value pairs
                for label_pair in labels_str.split(","):
                    if "=" in label_pair:
                        key, value = label_pair.split("=", 1)
                        key = key.strip()
                        value = value.strip('"')
                        label_cardinality[metric_name][key].add(value)

        # Report high-cardinality labels
        risky_labels = []
        for metric, labels in label_cardinality.items():
            for label_name, values in labels.items():
                if len(values) > 20:  # >20 unique values = potential issue
                    risky_labels.append((metric, label_name, len(values)))

        if risky_labels:
            risky_labels.sort(key=lambda x: x[2], reverse=True)
            print(f"\n⚠️  HIGH-CARDINALITY LABELS ({len(risky_labels)} found):")
            print(f"{'Metric':<50} | {'Label':<20} | Values")
            print("-" * 70)
            for metric, label, count in risky_labels[:15]:
                print(f"{metric:<50} | {label:<20} | {count:>6}")
            if len(risky_labels) > 15:
                print(f"... and {len(risky_labels) - 15} more")
        else:
            print("✅ No high-cardinality label risks detected")

    except Exception as e:
        print(f"❌ Label analysis failed: {e}")


def check_orphaned_metrics() -> None:
    """Check for metrics defined but not emitting data."""
    print("\n\n🔍 ORPHANED METRICS CHECK")
    print("=" * 70)
    print("(This check requires historical data in Prometheus)")
    print("Metrics with zero values in last 24h may be orphaned.")
    print("\n💡 To run: Query Prometheus for metrics with rate[24h] == 0")
    print("   Example: kagami_agent_workload == 0")


if __name__ == "__main__":
    # Check main metrics endpoint
    result = check_metrics_endpoint()

    # Check label cardinality
    check_label_cardinality()

    # Note about orphaned metrics
    check_orphaned_metrics()

    # Exit code based on health
    if result.get("status") == "ok":
        sys.exit(0)
    elif result.get("status") == "degraded":
        sys.exit(1)
    else:
        sys.exit(2)
