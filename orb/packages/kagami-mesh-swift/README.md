# KagamiMesh Swift Package

Cross-platform Swift wrapper for the `kagami-mesh-sdk` Rust library, providing unified cryptographic operations across all Apple platforms.

## Supported Platforms

- iOS 16+
- watchOS 9+
- tvOS 16+
- visionOS 1+
- macOS 13+

## Features

- **Ed25519 Identity** - Device signing and verification
- **XChaCha20-Poly1305** - Authenticated encryption
- **X25519 Key Exchange** - Diffie-Hellman with HKDF derivation
- **Circuit Breaker** - Connection state management (Closed/Open/HalfOpen)
- **Vector Clocks** - Causality tracking for distributed state
- **CRDTs** - Conflict-free G-Counters for offline-first sync

## Installation

Add to your `Package.swift`:

```swift
dependencies: [
    .package(path: "../../../packages/kagami-mesh-swift"),
]

targets: [
    .target(
        name: "YourApp",
        dependencies: [
            .product(name: "KagamiMesh", package: "kagami-mesh-swift"),
        ]
    ),
]
```

## Building the Rust Library

Before using this package, you must compile the Rust static library for your target platforms.

### Prerequisites

```bash
# Install Rust targets for Apple platforms
rustup target add aarch64-apple-ios
rustup target add aarch64-apple-ios-sim
rustup target add aarch64-apple-watchos
rustup target add aarch64-apple-watchos-sim
rustup target add aarch64-apple-tvos
rustup target add aarch64-apple-tvos-sim
rustup target add aarch64-apple-darwin
rustup target add x86_64-apple-darwin
```

### Build Commands

From `packages/kagami-mesh-sdk/`:

```bash
# iOS
cargo build --release --target aarch64-apple-ios
cargo build --release --target aarch64-apple-ios-sim

# watchOS
cargo build --release --target aarch64-apple-watchos
cargo build --release --target aarch64-apple-watchos-sim

# tvOS
cargo build --release --target aarch64-apple-tvos
cargo build --release --target aarch64-apple-tvos-sim

# macOS
cargo build --release --target aarch64-apple-darwin
cargo build --release --target x86_64-apple-darwin
```

### Linking

Set library search paths in Xcode Build Settings:
```
LIBRARY_SEARCH_PATHS = $(PROJECT_DIR)/../../../packages/kagami-mesh-sdk/target/$(CARGO_TARGET)/release
```

## Usage

```swift
import KagamiMesh

// Get the shared service
let mesh = await MeshService.shared

// Initialize with Keychain persistence
try await mesh.initialize()

// Get peer ID (hex-encoded Ed25519 public key)
let peerId = mesh.peerId

// Sign a message
let signature = try mesh.sign(message: "Hello, mesh!")

// Verify a signature
let isValid = try mesh.verify(message: data, signatureHex: signature)

// Generate encryption key
let key = mesh.generateEncryptionKey()

// Encrypt/decrypt
let ciphertext = try mesh.encrypt(message: "Secret", keyHex: key)
let plaintext = try mesh.decryptToString(ciphertextHex: ciphertext, keyHex: key)

// X25519 key exchange
let myPublicKey = try mesh.generateX25519KeyPair()
let sharedKey = try mesh.deriveSharedKey(peerPublicKeyHex: theirPublicKey)

// Circuit breaker
try mesh.onConnect()     // Signal connection attempt
try mesh.onConnected()   // Signal success
try mesh.onFailure(reason: "timeout")  // Signal failure

// Vector clocks
let clock = try mesh.createVectorClock()
let updated = try mesh.incrementVectorClock(clock)
let ordering = try mesh.compareVectorClocks(clock1, clock2)

// G-Counters
let counter = mesh.createGCounter()
let incremented = try mesh.incrementGCounter(counter)
let value = try mesh.getGCounterValue(incremented)
```

## Architecture

```
KagamiMesh (Swift Package)
    |
    +-- MeshService.swift          (High-level API)
    |       |
    |       +-- MeshKeychainService  (Platform keychain abstraction)
    |       +-- MeshConnectionState  (Circuit breaker states)
    |       +-- VectorClockOrdering  (Causality comparison)
    |
    +-- kagami_mesh_sdk.swift      (UniFFI-generated bindings)
            |
            +-- MeshIdentity        (Ed25519 wrapper)
            +-- MeshConnection      (State machine wrapper)
            +-- generateCipherKey()
            +-- encryptData() / decryptData()
            +-- x25519DeriveKey()
            +-- vectorClock*() / gCounter*()
```

## DRY Philosophy

> Write cryptography once in Rust. Generate bindings. Every platform gets it.

This package eliminates duplicated crypto code across iOS, watchOS, tvOS, and visionOS. All platforms share:

- Ed25519 signatures with `zeroize` on drop
- X25519 key exchange with HKDF salt `b"kagami-mesh-sdk-v1"`
- XChaCha20-Poly1305 with `OsRng` nonces
- Vector clocks with automatic merge
- CRDTs for offline-first state sync

## Custom Keychain

For testing or alternative storage, provide a custom `MeshKeychainService`:

```swift
class TestKeychain: MeshKeychainService {
    private var storage: [String: String] = [:]

    func save(key: String, value: String) -> Bool {
        storage[key] = value
        return true
    }

    func load(key: String) -> String? {
        storage[key]
    }

    func delete(key: String) -> Bool {
        storage.removeValue(forKey: key)
        return true
    }
}

let mesh = MeshService.create(keychainService: TestKeychain())
```

## Thread Safety

`MeshService` is `@MainActor` for UI integration. All cryptographic operations are performed on the Rust side, which is inherently thread-safe.

## h(x) >= 0. Always.

```
鏡
```
