def test_import_kagami_integrations() -> None:
    import kagami_integrations

    assert hasattr(kagami_integrations, "get_integration")

    # Should not raise even if optional dependencies aren't installed.
    kagami_integrations.get_integration("langchain")
