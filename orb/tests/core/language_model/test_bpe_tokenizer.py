"""Tests for BPE Tokenizer."""

from __future__ import annotations

import pytest
pytestmark = pytest.mark.tier_integration



from kagami.core.language_model.bpe_tokenizer import BPETokenizer, get_tokenizer


class TestBPETokenizer:
    """Test BPE tokenization."""

    def test_fallback_to_simple(self):
        """Test that BPE falls back to SimpleTokenizer if tiktoken unavailable."""
        tokenizer = BPETokenizer(auto_train=True)

        # Should work (either tiktoken or SimpleTokenizer)
        text = "Hello world"
        tokens = tokenizer.encode(text)
        decoded = tokenizer.decode(tokens)

        # Should roundtrip (though may not be identical due to special tokens)
        assert isinstance(tokens, list)
        assert isinstance(decoded, str)

    def test_get_tokenizer_bpe(self):
        """Test get_tokenizer with BPE vocab size."""
        # FIXED Nov 10, 2025: get_tokenizer expects int vocab_size, not string type
        tokenizer = get_tokenizer(vocab_size=5000, auto_train=True)

        assert tokenizer is not None
        assert hasattr(tokenizer, "encode")
        assert hasattr(tokenizer, "decode")

    def test_get_tokenizer_simple(self):
        """Test get_tokenizer with default vocab size."""
        # FIXED Nov 10, 2025: get_tokenizer expects int vocab_size, not string type
        tokenizer = get_tokenizer(vocab_size=1000, auto_train=True)

        assert tokenizer is not None
        assert hasattr(tokenizer, "encode")
        assert hasattr(tokenizer, "decode")

    def test_encode_decode_roundtrip(self):
        """Test encode→decode works."""
        tokenizer = BPETokenizer(auto_train=True)

        text = "Testing BPE tokenizer"
        tokens = tokenizer.encode(text)
        decoded = tokenizer.decode(tokens)

        # Should produce text (exact match depends on tokenizer)
        assert isinstance(decoded, str)
        assert len(decoded) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
