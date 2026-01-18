"""Load production tokenizer for KagamiOS."""

import logging
from pathlib import Path

import sentencepiece as spm

logger = logging.getLogger(__name__)

# Default tokenizer path (relative to this file)
TOKENIZER_PATH = (
    Path(__file__).parent.parent.parent / "assets" / "tokenizer" / "kagami_tokenizer_16000.model"
)


def load_production_tokenizer(
    model_path: Path | None = None,
) -> spm.SentencePieceProcessor:
    """Load the production 16K vocab tokenizer.

    Args:
        model_path: Optional custom path to tokenizer model.
                   Defaults to kagami/assets/tokenizer/kagami_tokenizer_16000.model

    Returns:
        SentencePieceProcessor instance

    Raises:
        FileNotFoundError: If tokenizer model not found
    """
    path = model_path or TOKENIZER_PATH

    if not path.exists():
        raise FileNotFoundError(
            f"Production tokenizer not found at {path}.\n"
            "Options:\n"
            "  1. Quick-start: python scripts/data/train_tokenizer_minimal.py\n"
            "  2. Production: python scripts/data/train_tokenizer.py\n"
            "  3. Install: bash scripts/install_tokenizer.sh"
        )

    logger.info(f"Loading production tokenizer from {path}")
    sp = spm.SentencePieceProcessor(model_file=str(path))
    logger.info(f"Loaded tokenizer with vocab size: {sp.get_piece_size()}")

    return sp


def get_vocab_size(model_path: Path | None = None) -> int:
    """Get vocabulary size of production tokenizer.

    Args:
        model_path: Optional custom path to tokenizer model

    Returns:
        Vocabulary size
    """
    sp = load_production_tokenizer(model_path)
    size: int = sp.get_piece_size()
    return size


def get_special_token_ids(
    model_path: Path | None = None,
) -> dict[str, int]:
    """Get special token IDs from production tokenizer.

    Args:
        model_path: Optional custom path to tokenizer model

    Returns:
        Dictionary mapping special token names to IDs
    """
    sp = load_production_tokenizer(model_path)

    return {
        "pad": sp.pad_id(),
        "unk": sp.unk_id(),
        "bos": sp.bos_id(),
        "eos": sp.eos_id(),
    }
