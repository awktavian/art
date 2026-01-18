
from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_unit


import asyncio

from fastapi import FastAPI

from kagami.boot import BootGraph, BootGraphExecutionError, BootNode


@pytest.mark.asyncio
async def test_boot_graph_records_failure_status_in_report():
    app = FastAPI()
    started: list[str] = []

    async def start_ok(_app: FastAPI) -> None:
        started.append("ok")

    async def start_bad(_app: FastAPI) -> None:
        raise RuntimeError("boom")

    graph = BootGraph(
        [
            BootNode(name="ok", start=start_ok),
            BootNode(name="bad", start=start_bad, dependencies=("ok",)),
        ]
    )

    with pytest.raises(BootGraphExecutionError) as excinfo:
        await graph.start(app)

    assert excinfo.value.node == "bad"
    report = excinfo.value.report
    assert report.statuses["ok"].success is True
    assert report.statuses["bad"].success is False
    assert report.statuses["bad"].error and "boom" in report.statuses["bad"].error


@pytest.mark.asyncio
async def test_boot_graph_retries_flaky_node_then_succeeds():
    app = FastAPI()
    calls = 0

    async def flaky(_app: FastAPI) -> None:
        nonlocal calls
        calls += 1
        if calls < 2:
            raise RuntimeError("transient")

    graph = BootGraph([BootNode(name="flaky", start=flaky, retries=1, retry_backoff_s=0.0)])
    report = await graph.start(app)

    assert report.success is True
    assert report.statuses["flaky"].success is True
    assert report.statuses["flaky"].attempts == 2


@pytest.mark.asyncio
async def test_boot_graph_timeout_marks_timed_out_and_fails():
    app = FastAPI()

    async def slow(_app: FastAPI) -> None:
        await asyncio.sleep(0.2)

    graph = BootGraph([BootNode(name="slow", start=slow, timeout_s=0.01, retries=0)])

    with pytest.raises(BootGraphExecutionError) as excinfo:
        await graph.start(app)

    report = excinfo.value.report
    assert report.statuses["slow"].success is False
    assert report.statuses["slow"].timed_out is True
    assert report.statuses["slow"].attempts == 1


@pytest.mark.asyncio
async def test_boot_graph_stop_runs_reverse_of_started_order():
    app = FastAPI()
    calls: list[str] = []

    async def start_a(_app: FastAPI) -> None:
        calls.append("start_a")

    async def stop_a(_app: FastAPI) -> None:
        calls.append("stop_a")

    async def start_b(_app: FastAPI) -> None:
        calls.append("start_b")

    async def stop_b(_app: FastAPI) -> None:
        calls.append("stop_b")

    graph = BootGraph(
        [
            BootNode(name="a", start=start_a, stop=stop_a),
            BootNode(name="b", start=start_b, stop=stop_b, dependencies=("a",)),
        ]
    )

    report = await graph.start(app)
    assert report.success is True

    await graph.stop(app)
    assert calls == ["start_a", "start_b", "stop_b", "stop_a"]


@pytest.mark.asyncio
async def test_boot_graph_rejects_unknown_dependencies():
    app = FastAPI()

    async def noop(_app: FastAPI) -> None:
        return None

    graph = BootGraph([BootNode(name="a", start=noop, dependencies=("missing",))])
    with pytest.raises(ValueError, match=r"depends on unknown nodes"):
        await graph.start(app)


@pytest.mark.asyncio
async def test_boot_graph_rejects_cycles():
    app = FastAPI()

    async def noop(_app: FastAPI) -> None:
        return None

    graph = BootGraph(
        [
            BootNode(name="a", start=noop, dependencies=("b",)),
            BootNode(name="b", start=noop, dependencies=("a",)),
        ]
    )
    with pytest.raises(ValueError, match=r"contains cycles"):
        await graph.start(app)
