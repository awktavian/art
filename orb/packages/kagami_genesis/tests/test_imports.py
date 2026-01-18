def test_import_kagami_genesis() -> None:
    import kagami_genesis

    assert hasattr(kagami_genesis, "GenesisVideoGenerator")
