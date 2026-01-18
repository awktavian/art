def test_import_kagami_hal() -> None:
    import kagami_hal

    assert hasattr(kagami_hal, "HALManager")
    assert hasattr(kagami_hal, "get_hal_manager")
