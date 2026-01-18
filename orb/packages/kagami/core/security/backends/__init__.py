"""Secret backend implementations for multiple providers.

Use the unified API instead of importing backends directly:

    from kagami.core.security import get_secret, set_secret

    value = get_secret("my_key")
    set_secret("my_key", "my_value")
"""

from kagami.core.security.backends.aws_secrets_manager import AWSSecretsManagerBackend
from kagami.core.security.backends.azure_key_vault import AzureKeyVaultBackend
from kagami.core.security.backends.environment_backend import EnvironmentBackend
from kagami.core.security.backends.gcp_secret_manager import GCPSecretManagerBackend
from kagami.core.security.backends.keychain_backend import (
    HalKeychain,
    KeychainBackend,
)
from kagami.core.security.backends.local_backend import LocalEncryptedBackend
from kagami.core.security.backends.unified_backend import (
    UnifiedSecretsBackend,
    get_sync_backend,
    get_unified_backend,
)
from kagami.core.security.backends.vault_backend import HashiCorpVaultBackend

__all__ = [
    "AWSSecretsManagerBackend",
    "AzureKeyVaultBackend",
    "EnvironmentBackend",
    "GCPSecretManagerBackend",
    "HalKeychain",
    "HashiCorpVaultBackend",
    "KeychainBackend",
    "LocalEncryptedBackend",
    "UnifiedSecretsBackend",
    "get_sync_backend",
    "get_unified_backend",
]
