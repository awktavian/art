"""Model fixtures for Kagami test suite.

Provides standardized model fixtures for testing:
- Mocked transformers models
- Lightweight test models
- Model loading utilities
- Cache management for tests

Usage:
    def test_model_inference(mock_transformer):
        # Use mock_transformer for testing
        pass
"""

from __future__ import annotations

from typing import Any, Dict
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
import torch
import torch.nn as nn


class MockTransformer(nn.Module):
    """Lightweight mock transformer for testing."""

    def __init__(self, vocab_size: int = 1000, hidden_size: int = 64) -> None:
        super().__init__()
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.config = MagicMock()
        self.config.vocab_size = vocab_size
        self.config.hidden_size = hidden_size

        # Minimal layers for testing
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.linear = nn.Linear(hidden_size, vocab_size)

    def forward(self, input_ids: torch.Tensor, **kwargs: Any) -> Any:
        """Simple forward pass for testing."""
        x = self.embedding(input_ids)
        # Average pooling over sequence dimension
        x = x.mean(dim=1)
        logits = self.linear(x)

        # Return object that mimics transformers output
        result = MagicMock()
        result.logits = logits
        result.last_hidden_state = x
        return result

    def generate(self, input_ids: torch.Tensor, **kwargs: Any) -> torch.Tensor:
        """Mock generation for testing."""
        batch_size = input_ids.shape[0]
        max_length = kwargs.get("max_length", 50)
        # Return random token sequence
        return torch.randint(0, self.vocab_size, (batch_size, max_length))


@pytest.fixture
def mock_transformer() -> MockTransformer:
    """Provide a lightweight mock transformer for testing."""
    return MockTransformer()


@pytest.fixture
def mock_tokenizer() -> MagicMock:
    """Provide a mock tokenizer for testing."""
    tokenizer = MagicMock()
    tokenizer.encode = MagicMock(return_value=[1, 2, 3, 4, 5])
    tokenizer.decode = MagicMock(return_value="test output")
    tokenizer.vocab_size = 1000
    tokenizer.pad_token_id = 0
    tokenizer.eos_token_id = 2
    return tokenizer


@pytest.fixture
def mock_embeddings() -> torch.Tensor:
    """Provide mock embeddings for testing."""
    return torch.randn(100, 64)  # 100 embeddings of size 64


class MockWorldModel(nn.Module):
    """Mock world model for testing."""

    def __init__(self, latent_dim: int = 32) -> None:
        super().__init__()
        self.latent_dim = latent_dim
        self.encoder = nn.Linear(128, latent_dim)
        self.decoder = nn.Linear(latent_dim, 128)

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        """Forward pass returning dict like real world model."""
        z = self.encoder(x)
        x_recon = self.decoder(z)
        return {
            "latent": z,
            "reconstruction": x_recon,
            "loss": nn.MSELoss()(x_recon, x),
        }


@pytest.fixture
def mock_world_model() -> MockWorldModel:
    """Provide a mock world model for testing."""
    return MockWorldModel()


@pytest.fixture
def disable_model_loading() -> Generator[None, None, None]:
    """Disable actual model loading during tests."""
    with patch("kagami.core.world_model.service.WorldModelService.load_model") as mock:
        mock.return_value = MockWorldModel()
        yield


@pytest.fixture
def mock_model_cache() -> MagicMock:
    """Provide a mock model cache for testing."""
    cache = MagicMock()
    cache.get = MagicMock(return_value=None)
    cache.set = MagicMock()
    cache.clear = MagicMock()
    cache.size = MagicMock(return_value=0)
    return cache


class MockMatryoshkaModel(nn.Module):
    """Mock Matryoshka embedding model for testing."""

    def __init__(self, embedding_dims: list[int] | None = None) -> None:
        super().__init__()
        self.embedding_dims = embedding_dims or [64, 128, 256, 512]
        self.base_model = nn.Linear(768, max(self.embedding_dims))

    def forward(self, input_ids: torch.Tensor, **kwargs: Any) -> torch.Tensor:
        """Return embeddings truncated to different dimensions."""
        base_emb = self.base_model(torch.randn(*input_ids.shape, 768))
        return base_emb


@pytest.fixture
def mock_matryoshka_model() -> MockMatryoshkaModel:
    """Provide a mock Matryoshka model for testing."""
    return MockMatryoshkaModel()


__all__ = [
    "MockTransformer",
    "MockWorldModel",
    "MockMatryoshkaModel",
    "mock_transformer",
    "mock_tokenizer",
    "mock_embeddings",
    "mock_world_model",
    "mock_matryoshka_model",
    "mock_model_cache",
    "disable_model_loading",
]
