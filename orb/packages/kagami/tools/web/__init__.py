# SPDX-License-Identifier: MIT
"""Web research tooling for K os."""

from kagami.tools.web.browser import RenderResult, render
from kagami.tools.web.fetcher import FetchResult, fetch
from kagami.tools.web.search import SearchHit, search_web

__all__ = [
    "FetchResult",
    "RenderResult",
    "SearchHit",
    "fetch",
    "render",
    "search_web",
]
