def test_import_kagami_api() -> None:
    import kagami_api

    assert hasattr(kagami_api, "api_settings")


def test_websocket_alias_resolves_to_socketio_server() -> None:
    import kagami_api

    ws = kagami_api.websocket
    assert hasattr(ws, "get_socketio_server")
