def test_import_kagami_benchmarks() -> None:
    import kagami_benchmarks

    assert hasattr(kagami_benchmarks, "run_full_benchmark")

    # Ensure a deep submodule is importable (packaging smoke test)
    import kagami_benchmarks.ai.master_harness
