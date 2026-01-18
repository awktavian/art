"""BPE Tokenizer Tests"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.tier_unit


import tempfile
from pathlib import Path

from kagami.core.language_model.bpe_tokenizer import BPETokenizer


class TestBPETokenizer:
    """Test BPE tokenizer implementation."""

    def test_train_basic(self) -> None:
        """Test basic BPE training."""
        tokenizer = BPETokenizer(vocab_size=50)
        corpus = [
            "hello world",
            "hello there",
            "world peace",
        ]

        tokenizer.train(corpus)

        assert tokenizer._trained
        assert len(tokenizer.vocab) > 0
        assert len(tokenizer.merges) > 0

    def test_encode_decode_roundtrip(self) -> None:
        """Test encode/decode roundtrip."""
        tokenizer = BPETokenizer(vocab_size=50)
        corpus = [
            "the quick brown fox",
            "the lazy dog",
        ]

        tokenizer.train(corpus)

        text = "the quick fox"
        ids = tokenizer.encode(text)
        decoded = tokenizer.decode(ids)

        # Should preserve content (whitespace may differ)
        assert "quick" in decoded
        assert "fox" in decoded

    def test_unknown_tokens(self) -> None:
        """Test handling of unknown tokens."""
        tokenizer = BPETokenizer(vocab_size=20)
        tokenizer.train(["cat dog"])

        # Encode text with unknown word
        ids = tokenizer.encode("cat elephant")

        # Should contain <unk> token
        assert tokenizer.token_to_id["<unk>"] in ids

    def test_save_load(self) -> None:
        """Test save/load persistence."""
        tokenizer = BPETokenizer(vocab_size=30)
        tokenizer.train(["hello world", "hello there"])

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir)

            # Save
            tokenizer.save(path)

            # Load into new instance
            tokenizer2 = BPETokenizer()
            tokenizer2.load(path)

            # Should match
            assert tokenizer.vocab == tokenizer2.vocab
            assert tokenizer.merges == tokenizer2.merges
            assert tokenizer.vocab_size == tokenizer2.vocab_size

    def test_encode_decode_consistency(self) -> None:
        """Test encode/decode consistency."""
        tokenizer = BPETokenizer(vocab_size=100)
        corpus = [
            "machine learning is fun",
            "deep learning is powerful",
            "natural language processing",
        ]

        tokenizer.train(corpus)

        for text in corpus:
            ids = tokenizer.encode(text)
            decoded = tokenizer.decode(ids)

            # Core words should be preserved
            words = text.split()
            for word in words:
                assert word in decoded or word in decoded.replace(" ", "")

    def test_special_tokens(self) -> None:
        """Test special tokens in vocab."""
        tokenizer = BPETokenizer(vocab_size=50)
        tokenizer.train(["test"])

        # Should have special tokens
        assert "<pad>" in tokenizer.vocab
        assert "<unk>" in tokenizer.vocab
        assert "<s>" in tokenizer.vocab
        assert "</s>" in tokenizer.vocab

    def test_deterministic_training(self) -> None:
        """Test training is deterministic."""
        corpus = ["hello world"] * 10

        tokenizer1 = BPETokenizer(vocab_size=30, min_frequency=1)
        tokenizer1.train(corpus)

        tokenizer2 = BPETokenizer(vocab_size=30, min_frequency=1)
        tokenizer2.train(corpus)

        # Should produce same vocab
        assert tokenizer1.vocab == tokenizer2.vocab
        assert tokenizer1.merges == tokenizer2.merges


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
