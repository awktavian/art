from __future__ import annotations
from typing import Any

import pytest

pytestmark = pytest.mark.tier_integration
import logging
from types import SimpleNamespace
from kagami_api import middleware_stack
from kagami_api.middleware_stack import MiddlewareSpec, configure_gateway_middlewares


class DummyApp:
    def __init__(self) -> None:
        self.http_installs: list[tuple[str, object]] = []
        self.add_installs: list[object] = []

    def middleware(self, kind: str) -> None:
        def registrar(handler: Any) -> Any:
            self.http_installs.append((kind, handler))
            return handler

        return registrar

    def add_middleware(self, middleware_cls: Any) -> Any:
        self.add_installs.append(middleware_cls)


def test_configure_gateway_middlewares_installs_stack(monkeypatch: Any) -> None:
    http_handler = object()
    add_middleware_cls = type("AddMiddleware", (), {})
    modules = {
        "pkg.http": SimpleNamespace(handler=http_handler),
        "pkg.add": SimpleNamespace(MW=add_middleware_cls),
    }

    def fake_import(name: str):
        return modules[name]

    monkeypatch.setattr(middleware_stack.importlib, "import_module", fake_import)
    custom_stack = (
        MiddlewareSpec(name="HTTP", target="pkg.http:handler", kind="http"),
        MiddlewareSpec(name="ADD", target="pkg.add:MW", kind="add"),
        MiddlewareSpec(
            name="Disabled",
            target="pkg.add:MW",
            kind="add",
            enabled=lambda: False,
        ),
    )
    monkeypatch.setattr(middleware_stack, "STACK", custom_stack)
    app = DummyApp()
    configure_gateway_middlewares(app, logger=logging.getLogger("test"))
    assert app.http_installs == [("http", http_handler)]
    assert app.add_installs == [add_middleware_cls]
