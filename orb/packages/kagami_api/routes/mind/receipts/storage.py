"""Receipt storage and persistence logic (Proxy).

Delegates to kagami.core.receipts.ingestor to break Core->API dependency.
"""

from __future__ import annotations

from kagami.core.receipts.ingestor import (
    register_stream_processor,
)

# Auto-register stream processor to maintain API functionality
try:
    from kagami_api.routes.mind.receipts.streaming import fanout_receipt_to_stream_processor

    register_stream_processor(fanout_receipt_to_stream_processor)
except ImportError:
    pass
