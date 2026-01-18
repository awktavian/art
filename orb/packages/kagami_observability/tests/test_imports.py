def test_import_kagami_observability() -> None:
    import kagami_observability

    assert hasattr(kagami_observability, "Counter")

    # This module should be importable even when FastAPI isn't installed
    # (FastAPI is only required when init_metrics() is called).
    import kagami_observability.metrics_prometheus
