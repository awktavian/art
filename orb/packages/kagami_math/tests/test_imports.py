def test_import_kagami_math() -> None:
    import kagami_math

    assert hasattr(kagami_math, "nearest_e8")

    # Ensure a deep module is importable (packaging smoke test)
    import kagami_math.e8_lattice_quantizer
