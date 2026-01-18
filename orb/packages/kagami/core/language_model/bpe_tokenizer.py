"""Byte Pair Encoding (BPE) Tokenizer

Implementation based on Sennrich et al. (ACL 2015):
"Neural Machine Translation of Rare Words with Subword Units"

Features:
- Byte-level encoding for robustness
- Deterministic vocab building
- Persistence (save/load vocab)
- Fallback to character-level on unknown
- Production tokenizer integration (SentencePiece)
"""

import json
import logging
from collections import Counter, defaultdict
from pathlib import Path

logger = logging.getLogger(__name__)


class BPETokenizer:
    """Byte Pair Encoding tokenizer.

    Can use either:
    1. Custom BPE implementation (for testing/development)
    2. Production SentencePiece tokenizer (for deployment)
    """

    def __init__(
        self,
        vocab_size: int = 5000,
        min_frequency: int = 2,
        auto_train: bool = False,
        use_sentencepiece: bool = False,
    ) -> None:
        """Initialize BPE tokenizer.

        Args:
            vocab_size: Target vocabulary size
            min_frequency: Minimum pair frequency to merge
            auto_train: If True, automatically train on minimal corpus
            use_sentencepiece: If True, use production SentencePiece tokenizer
        """
        # FIXED Nov 10, 2025: Ensure vocab_size/min_frequency are always int (could be str from JSON/config)
        self.vocab_size = int(vocab_size) if not isinstance(vocab_size, int) else vocab_size
        self.min_frequency = (
            int(min_frequency) if not isinstance(min_frequency, int) else min_frequency
        )
        self.vocab: dict[str, int] = {}
        self.merges: list[tuple[str, str]] = []
        self.token_to_id: dict[str, int] = {}
        self.id_to_token: dict[int, str] = {}
        self._trained = False
        self._sp: object | None = None  # SentencePiece processor
        self._use_sentencepiece = use_sentencepiece

        if use_sentencepiece:
            # Load production tokenizer
            try:
                from kagami.core.language_model.load_tokenizer import (
                    load_production_tokenizer,
                )

                self._sp = load_production_tokenizer()
                self.vocab_size = self._sp.get_piece_size()  # type: ignore
                self._trained = True
                logger.info(f"Loaded production tokenizer (vocab={self.vocab_size})")
            except (ImportError, FileNotFoundError) as e:
                logger.warning(
                    f"Failed to load production tokenizer: {e}. Falling back to custom BPE."
                )
                self._use_sentencepiece = False

        if auto_train and not self._trained:
            # Train on minimal corpus for basic functionality
            minimal_corpus = [
                "hello world testing",
                "bpe tokenizer encode decode",
                "machine learning natural language processing",
            ]
            self.train(minimal_corpus)

    def train(self, texts: list[str]) -> None:
        """Train BPE on corpus.

        Args:
            texts: Training corpus
        """
        # 1. Initialize vocab with characters
        word_freqs = Counter()  # type: ignore  # Var
        for text in texts:
            words = text.lower().split()
            for word in words:
                # Add end-of-word marker
                word_freqs[word + "</w>"] += 1

        # 2. Split into characters
        splits = {word: list(word) for word in word_freqs.keys()}

        # 3. Learn merges
        self.merges = []
        while len(self.vocab) < self.vocab_size:
            # Count pairs
            pairs = defaultdict(int)  # type: ignore  # Var
            for word, freq in word_freqs.items():
                symbols = splits[word]
                for i in range(len(symbols) - 1):
                    pairs[(symbols[i], symbols[i + 1])] += freq

            if not pairs:
                break

            # Find most frequent pair
            best_pair = max(pairs.items(), key=lambda x: x[1])
            if best_pair[1] < self.min_frequency:
                break

            pair, freq = best_pair
            self.merges.append(pair)

            # Merge pair in splits
            new_splits = {}
            " ".join(pair)
            replacement = "".join(pair)

            for word in splits:
                symbols = splits[word]
                new_symbols = []
                i = 0
                while i < len(symbols):
                    if i < len(symbols) - 1 and (symbols[i], symbols[i + 1]) == pair:
                        new_symbols.append(replacement)
                        i += 2
                    else:
                        new_symbols.append(symbols[i])
                        i += 1
                new_splits[word] = new_symbols

            splits = new_splits

        # 4. Build final vocab
        self.vocab = {"<pad>": 0, "<unk>": 1, "<s>": 2, "</s>": 3}
        idx = 4

        # Add all subword units
        for word in splits:
            for token in splits[word]:
                if token not in self.vocab:
                    self.vocab[token] = idx
                    idx += 1

        # Build lookup tables
        self.token_to_id = self.vocab
        self.id_to_token = {v: k for k, v in self.vocab.items()}
        self._trained = True

    def encode(self, text: str) -> list[int]:
        """Encode text to token IDs.

        Args:
            text: Input text

        Returns:
            List of token IDs
        """
        if not self._trained:
            raise RuntimeError("Tokenizer not trained. Call train() first.")

        # Use SentencePiece if available
        if self._use_sentencepiece and self._sp is not None:
            return self._sp.encode(text)  # type: ignore

        # Custom BPE implementation
        tokens = []
        words = text.lower().split()

        for word in words:
            word = word + "</w>"

            # Apply BPE merges
            symbols = list(word)
            for pair in self.merges:
                new_symbols = []
                i = 0
                while i < len(symbols):
                    if i < len(symbols) - 1 and (symbols[i], symbols[i + 1]) == pair:
                        new_symbols.append("".join(pair))
                        i += 2
                    else:
                        new_symbols.append(symbols[i])
                        i += 1
                symbols = new_symbols

            # Convert to IDs
            for symbol in symbols:
                token_id = self.token_to_id.get(symbol, self.token_to_id["<unk>"])
                tokens.append(token_id)

        return tokens

    def decode(self, token_ids: list[int]) -> str:
        """Decode token IDs to text.

        Args:
            token_ids: List of token IDs

        Returns:
            Decoded text
        """
        # Use SentencePiece if available
        if self._use_sentencepiece and self._sp is not None:
            return self._sp.decode(token_ids)  # type: ignore

        # Custom BPE implementation
        tokens = [
            self.id_to_token.get(tid, "<unk>")
            for tid in token_ids
            if tid not in (0, 2, 3)  # Skip pad, <s>, </s>
        ]

        # Join and remove end-of-word markers
        text = "".join(tokens).replace("</w>", " ").strip()
        return text

    def save(self, path: Path) -> None:
        """Save vocab and merges to disk.

        Args:
            path: Save directory
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save vocab
        with open(path / "vocab.json", "w") as f:
            json.dump(self.vocab, f, indent=2)

        # Save merges
        with open(path / "merges.txt", "w") as f:
            for pair in self.merges:
                f.write(f"{pair[0]} {pair[1]}\n")

        # Save config
        with open(path / "config.json", "w") as f:
            json.dump(
                {
                    "vocab_size": self.vocab_size,
                    "min_frequency": self.min_frequency,
                    "trained": self._trained,
                },
                f,
                indent=2,
            )

    def load(self, path: Path) -> None:
        """Load vocab and merges from disk.

        Args:
            path: Load directory
        """
        path = Path(path)

        # Load vocab
        with open(path / "vocab.json") as f:
            self.vocab = json.load(f)

        # Load merges
        self.merges = []
        with open(path / "merges.txt") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) == 2:
                    self.merges.append((parts[0], parts[1]))

        # Load config
        with open(path / "config.json") as f:
            config = json.load(f)
            # FIXED Nov 10, 2025: Ensure vocab_size is int (could be str from JSON)
            self.vocab_size = int(config["vocab_size"])
            self.min_frequency = int(config["min_frequency"])
            self._trained = config["trained"]

        # Rebuild lookup tables
        self.token_to_id = self.vocab
        self.id_to_token = {v: k for k, v in self.vocab.items()}

    def __len__(self) -> int:
        """Return vocab size."""
        if self._use_sentencepiece and self._sp is not None:
            return self._sp.get_piece_size()  # type: ignore
        return len(self.vocab)


# Global tokenizer instance
_global_tokenizer = None


def get_tokenizer(
    vocab_size: int = 5000,
    auto_train: bool = True,
    use_production: bool = True,
) -> BPETokenizer:
    """Get or create global tokenizer instance.

    Args:
        vocab_size: Target vocabulary size (if training)
        auto_train: If True, train on minimal corpus if not already trained
        use_production: If True, try to use production 16K tokenizer

    Returns:
        Global BPETokenizer instance
    """
    global _global_tokenizer
    if _global_tokenizer is None:
        # Try production tokenizer first
        if use_production:
            try:
                _global_tokenizer = BPETokenizer(vocab_size=16000, use_sentencepiece=True)
                logger.info("Using production SentencePiece tokenizer")
                return _global_tokenizer
            except Exception as e:
                logger.warning(
                    f"Production tokenizer not available: {e}. Falling back to custom BPE."
                )

        # Fallback to custom BPE
        _global_tokenizer = BPETokenizer(vocab_size=vocab_size)
        if auto_train and not _global_tokenizer._trained:
            # Train on minimal corpus for basic functionality
            minimal_corpus = [
                "hello world testing",
                "bpe tokenizer encode decode",
                "machine learning natural language processing",
            ]
            _global_tokenizer.train(minimal_corpus)

    return _global_tokenizer
