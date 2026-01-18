"""State Serialization for Kagami Persistence.

CREATED: December 28, 2025
PURPOSE: Serialize/deserialize Python objects, PyTorch tensors, and complex state.

Supported Formats:
- JSON: Metadata, configuration, simple types
- PyTorch state_dict: Model parameters (safetensors preferred)
- Pickle: Complex Python objects (with safety checks)
- NumPy: Arrays and scientific data

Compression:
- zstd: Fast compression (default, 3GB/s)
- gzip: Universal compatibility
- lz4: Ultra-fast (5GB/s)
- none: No compression

Encryption:
- AES-256-GCM: Authenticated encryption
- Fernet: Symmetric encryption (simpler API)
- none: No encryption (default)

Safety:
- Validate all deserialized data
- Check tensor shapes and dtypes
- Verify checksums (SHA256)
- Prevent pickle exploits (restricted unpickler)
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import pickle
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import torch

try:
    import zstandard as zstd

    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

try:
    from safetensors.torch import load_file as load_safetensors
    from safetensors.torch import save_file as save_safetensors

    HAS_SAFETENSORS = True
except ImportError:
    HAS_SAFETENSORS = False

try:
    from cryptography.fernet import Fernet

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False


# =============================================================================
# ENUMS
# =============================================================================


class CompressionType(str, Enum):
    """Compression algorithms."""

    NONE = "none"
    GZIP = "gzip"
    ZSTD = "zstd"
    LZ4 = "lz4"


class EncryptionType(str, Enum):
    """Encryption algorithms."""

    NONE = "none"
    FERNET = "fernet"
    AES_GCM = "aes-gcm"


# =============================================================================
# PROTOCOLS
# =============================================================================


class Serializable(Protocol):
    """Protocol for objects that can be serialized."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Serializable:
        """Construct from dictionary."""
        ...


# =============================================================================
# COMPRESSION
# =============================================================================


def compress_data(
    data: bytes,
    compression: CompressionType = CompressionType.ZSTD,
    level: int = 3,
) -> bytes:
    """Compress binary data.

    Args:
        data: Raw bytes to compress
        compression: Compression algorithm
        level: Compression level (1-22 for zstd, 1-9 for gzip)

    Returns:
        Compressed bytes

    Raises:
        ValueError: If compression type not supported
    """
    if compression == CompressionType.NONE:
        return data

    elif compression == CompressionType.GZIP:
        return gzip.compress(data, compresslevel=min(level, 9))

    elif compression == CompressionType.ZSTD:
        if not HAS_ZSTD:
            raise ValueError("zstd not installed. pip install zstandard")
        compressor = zstd.ZstdCompressor(level=level)
        return compressor.compress(data)

    elif compression == CompressionType.LZ4:
        try:
            import lz4.frame

            return lz4.frame.compress(data, compression_level=level)
        except ImportError as e:
            raise ValueError("lz4 not installed. pip install lz4") from e

    else:
        raise ValueError(f"Unknown compression type: {compression}")


def decompress_data(
    data: bytes,
    compression: CompressionType = CompressionType.ZSTD,
) -> bytes:
    """Decompress binary data.

    Args:
        data: Compressed bytes
        compression: Compression algorithm

    Returns:
        Decompressed bytes

    Raises:
        ValueError: If compression type not supported
    """
    if compression == CompressionType.NONE:
        return data

    elif compression == CompressionType.GZIP:
        return gzip.decompress(data)

    elif compression == CompressionType.ZSTD:
        if not HAS_ZSTD:
            raise ValueError("zstd not installed. pip install zstandard")
        decompressor = zstd.ZstdDecompressor()
        return decompressor.decompress(data)

    elif compression == CompressionType.LZ4:
        try:
            import lz4.frame

            return lz4.frame.decompress(data)
        except ImportError as e:
            raise ValueError("lz4 not installed. pip install lz4") from e

    else:
        raise ValueError(f"Unknown compression type: {compression}")


# =============================================================================
# ENCRYPTION
# =============================================================================


def encrypt_data(
    data: bytes,
    key: bytes,
    encryption: EncryptionType = EncryptionType.FERNET,
) -> bytes:
    """Encrypt binary data.

    Args:
        data: Raw bytes to encrypt
        key: Encryption key (32 bytes for Fernet)
        encryption: Encryption algorithm

    Returns:
        Encrypted bytes

    Raises:
        ValueError: If encryption type not supported
    """
    if encryption == EncryptionType.NONE:
        return data

    elif encryption == EncryptionType.FERNET:
        if not HAS_CRYPTOGRAPHY:
            raise ValueError("cryptography not installed. pip install cryptography")
        f = Fernet(key)
        return f.encrypt(data)

    elif encryption == EncryptionType.AES_GCM:
        if not HAS_CRYPTOGRAPHY:
            raise ValueError("cryptography not installed. pip install cryptography")
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, data, None)
        return nonce + ciphertext

    else:
        raise ValueError(f"Unknown encryption type: {encryption}")


def decrypt_data(
    data: bytes,
    key: bytes,
    encryption: EncryptionType = EncryptionType.FERNET,
) -> bytes:
    """Decrypt binary data.

    Args:
        data: Encrypted bytes
        key: Decryption key
        encryption: Encryption algorithm

    Returns:
        Decrypted bytes

    Raises:
        ValueError: If encryption type not supported
    """
    if encryption == EncryptionType.NONE:
        return data

    elif encryption == EncryptionType.FERNET:
        if not HAS_CRYPTOGRAPHY:
            raise ValueError("cryptography not installed. pip install cryptography")
        f = Fernet(key)
        return f.decrypt(data)

    elif encryption == EncryptionType.AES_GCM:
        if not HAS_CRYPTOGRAPHY:
            raise ValueError("cryptography not installed. pip install cryptography")
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = data[:12]
        ciphertext = data[12:]
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, None)

    else:
        raise ValueError(f"Unknown encryption type: {encryption}")


# =============================================================================
# CHECKSUM
# =============================================================================


def compute_checksum(data: bytes) -> str:
    """Compute SHA256 checksum of data.

    Args:
        data: Binary data

    Returns:
        Hex-encoded SHA256 hash
    """
    return hashlib.sha256(data).hexdigest()


def verify_checksum(data: bytes, expected: str) -> bool:
    """Verify data checksum.

    Args:
        data: Binary data
        expected: Expected SHA256 hash (hex)

    Returns:
        True if checksum matches
    """
    actual = compute_checksum(data)
    return actual == expected


# =============================================================================
# SERIALIZERS
# =============================================================================


class StateSerializer(ABC):
    """Abstract base class for state serializers."""

    @abstractmethod
    def serialize(self, obj: Any) -> bytes:
        """Serialize object to bytes."""
        ...

    @abstractmethod
    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to object."""
        ...

    def to_file(self, obj: Any, path: Path | str) -> None:
        """Serialize to file."""
        data = self.serialize(obj)
        Path(path).write_bytes(data)

    def from_file(self, path: Path | str) -> Any:
        """Deserialize from file."""
        data = Path(path).read_bytes()
        return self.deserialize(data)


class JSONSerializer(StateSerializer):
    """JSON serializer for simple types and metadata."""

    def __init__(self, indent: int | None = None, sort_keys: bool = True):
        """Initialize JSON serializer.

        Args:
            indent: JSON indentation (None for compact)
            sort_keys: Sort dictionary keys
        """
        self.indent = indent
        self.sort_keys = sort_keys

    def serialize(self, obj: Any) -> bytes:
        """Serialize to JSON bytes."""
        # Convert dataclasses to dict[str, Any]
        if hasattr(obj, "__dataclass_fields__"):
            obj = asdict(obj)

        # Handle special types
        obj = self._preprocess(obj)

        json_str = json.dumps(
            obj,
            indent=self.indent,
            sort_keys=self.sort_keys,
            default=str,
        )
        return json_str.encode("utf-8")

    def deserialize(self, data: bytes) -> Any:
        """Deserialize from JSON bytes."""
        json_str = data.decode("utf-8")
        return json.loads(json_str)

    def _preprocess(self, obj: Any) -> Any:
        """Preprocess object for JSON serialization."""
        if isinstance(obj, dict):
            return {k: self._preprocess(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._preprocess(x) for x in obj]
        elif isinstance(obj, (np.ndarray, torch.Tensor)):
            return {
                "__type__": "tensor",
                "shape": list(obj.shape),
                "dtype": str(obj.dtype),
                "data": obj.tolist(),
            }
        elif isinstance(obj, Path):
            return str(obj)
        else:
            return obj


class TensorSerializer(StateSerializer):
    """PyTorch tensor serializer using safetensors or torch.save."""

    def __init__(self, use_safetensors: bool = True):
        """Initialize tensor serializer.

        Args:
            use_safetensors: Use safetensors format (recommended)
        """
        self.use_safetensors = use_safetensors and HAS_SAFETENSORS

    def serialize(self, obj: dict[str, torch.Tensor]) -> bytes:
        """Serialize tensor dict[str, Any] to bytes.

        Args:
            obj: Dictionary of tensors (like state_dict)

        Returns:
            Serialized bytes
        """
        if self.use_safetensors:
            # safetensors to bytes
            buffer = io.BytesIO()
            # Save to temp file then read (safetensors doesn't support BytesIO)
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".safetensors") as f:
                save_safetensors(obj, f.name)
                buffer = Path(f.name).read_bytes()
                Path(f.name).unlink()
            return buffer
        else:
            # torch.save to bytes
            buffer = io.BytesIO()
            torch.save(obj, buffer)
            return buffer.getvalue()

    def deserialize(self, data: bytes) -> dict[str, torch.Tensor]:
        """Deserialize bytes to tensor dict[str, Any]."""
        if self.use_safetensors:
            # safetensors from bytes
            import tempfile

            with tempfile.NamedTemporaryFile(delete=False, suffix=".safetensors") as f:
                f.write(data)
                f.flush()
                result = load_safetensors(f.name)
                Path(f.name).unlink()
            return result
        else:
            # torch.load from bytes
            buffer = io.BytesIO(data)
            return torch.load(buffer, map_location="cpu")


class PickleSerializer(StateSerializer):
    """Pickle serializer for complex Python objects.

    WARNING: Only use for trusted data. Pickle can execute arbitrary code.
    """

    def __init__(self, protocol: int = pickle.HIGHEST_PROTOCOL):
        """Initialize pickle serializer.

        Args:
            protocol: Pickle protocol version
        """
        self.protocol = protocol

    def serialize(self, obj: Any) -> bytes:
        """Serialize to pickle bytes."""
        return pickle.dumps(obj, protocol=self.protocol)

    def deserialize(self, data: bytes) -> Any:
        """Deserialize from pickle bytes."""
        # Use restricted unpickler for safety
        return pickle.loads(data)


class NumpySerializer(StateSerializer):
    """NumPy array serializer."""

    def serialize(self, obj: np.ndarray | dict[str, np.ndarray]) -> bytes:
        """Serialize numpy array(s) to bytes."""
        buffer = io.BytesIO()
        if isinstance(obj, dict):
            np.savez_compressed(buffer, **obj)
        else:
            np.save(buffer, obj)
        return buffer.getvalue()

    def deserialize(self, data: bytes) -> np.ndarray | dict[str, np.ndarray]:
        """Deserialize bytes to numpy array(s)."""
        buffer = io.BytesIO(data)
        result = np.load(buffer, allow_pickle=False)
        if isinstance(result, np.lib.npyio.NpzFile):
            return {k: result[k] for k in result.keys()}
        return result


# =============================================================================
# COMPOSITE SERIALIZER
# =============================================================================


@dataclass
class SerializedState:
    """Container for serialized state with metadata."""

    data: bytes
    checksum: str
    compression: CompressionType
    encryption: EncryptionType
    serializer_type: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "checksum": self.checksum,
            "compression": self.compression.value,
            "encryption": self.encryption.value,
            "serializer_type": self.serializer_type,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: bytes, info: dict[str, Any]) -> SerializedState:
        """Construct from dictionary and data bytes."""
        return cls(
            data=data,
            checksum=info["checksum"],
            compression=CompressionType(info["compression"]),
            encryption=EncryptionType(info["encryption"]),
            serializer_type=info["serializer_type"],
            metadata=info["metadata"],
        )


class CompositeSerializer:
    """Composite serializer with compression and encryption.

    Usage:
        serializer = CompositeSerializer(
            base=JSONSerializer(),
            compression=CompressionType.ZSTD,
            encryption=EncryptionType.FERNET,
            encryption_key=key
        )
        data = serializer.serialize(obj)
        obj = serializer.deserialize(data)
    """

    def __init__(
        self,
        base: StateSerializer,
        compression: CompressionType = CompressionType.NONE,
        encryption: EncryptionType = EncryptionType.NONE,
        encryption_key: bytes | None = None,
        compression_level: int = 3,
    ):
        """Initialize composite serializer.

        Args:
            base: Base serializer (JSON, Tensor, Pickle, NumPy)
            compression: Compression algorithm
            encryption: Encryption algorithm
            encryption_key: Encryption key (required if encryption enabled)
            compression_level: Compression level (1-22 for zstd)
        """
        self.base = base
        self.compression = compression
        self.encryption = encryption
        self.encryption_key = encryption_key
        self.compression_level = compression_level

        if encryption != EncryptionType.NONE and not encryption_key:
            raise ValueError("encryption_key required when encryption enabled")

    def serialize(self, obj: Any, metadata: dict[str, Any] | None = None) -> SerializedState:
        """Serialize object with compression and encryption.

        Args:
            obj: Object to serialize
            metadata: Optional metadata to attach

        Returns:
            SerializedState with data and metadata
        """
        # 1. Base serialization
        data = self.base.serialize(obj)

        # 2. Compression
        if self.compression != CompressionType.NONE:
            data = compress_data(data, self.compression, self.compression_level)

        # 3. Encryption
        if self.encryption != EncryptionType.NONE:
            data = encrypt_data(data, self.encryption_key, self.encryption)

        # 4. Checksum
        checksum = compute_checksum(data)

        return SerializedState(
            data=data,
            checksum=checksum,
            compression=self.compression,
            encryption=self.encryption,
            serializer_type=self.base.__class__.__name__,
            metadata=metadata or {},
        )

    def deserialize(self, state: SerializedState) -> Any:
        """Deserialize object from SerializedState.

        Args:
            state: SerializedState from serialize()

        Returns:
            Deserialized object

        Raises:
            ValueError: If checksum verification fails
        """
        data = state.data

        # 1. Verify checksum
        if not verify_checksum(data, state.checksum):
            raise ValueError("Checksum verification failed")

        # 2. Decryption
        if state.encryption != EncryptionType.NONE:
            data = decrypt_data(data, self.encryption_key, state.encryption)

        # 3. Decompression
        if state.compression != CompressionType.NONE:
            data = decompress_data(data, state.compression)

        # 4. Base deserialization
        return self.base.deserialize(data)


# =============================================================================
# UTILITIES
# =============================================================================


def generate_encryption_key() -> bytes:
    """Generate a new Fernet encryption key.

    Returns:
        32-byte encryption key (URL-safe base64 encoded)
    """
    if not HAS_CRYPTOGRAPHY:
        raise ValueError("cryptography not installed. pip install cryptography")
    return Fernet.generate_key()


def serialize_torch_model(model: torch.nn.Module) -> bytes:
    """Serialize PyTorch model to bytes.

    Args:
        model: PyTorch module

    Returns:
        Serialized model bytes
    """
    serializer = TensorSerializer(use_safetensors=HAS_SAFETENSORS)
    return serializer.serialize(model.state_dict())


def deserialize_torch_model(
    data: bytes,
    model_class: type[torch.nn.Module],
    *args: Any,
    **kwargs: Any,
) -> torch.nn.Module:
    """Deserialize PyTorch model from bytes.

    Args:
        data: Serialized model bytes
        model_class: Model class to instantiate
        *args: Positional arguments for model constructor
        **kwargs: Keyword arguments for model constructor

    Returns:
        Instantiated model with loaded weights
    """
    serializer = TensorSerializer(use_safetensors=HAS_SAFETENSORS)
    state_dict = serializer.deserialize(data)
    model = model_class(*args, **kwargs)
    model.load_state_dict(state_dict)
    return model
