# KagamiCore

Shared Swift components for all Kagami Apple platforms.

## Supported Platforms

- iOS 16+
- watchOS 9+
- visionOS 1+
- tvOS 16+
- macOS 13+

## Components

### CircuitBreaker

Graceful network degradation pattern for resilient API clients.

```swift
import KagamiCore

// Check if request is allowed
if CircuitBreaker.shared.allowRequest() {
    do {
        let result = try await makeRequest()
        CircuitBreaker.shared.recordSuccess()
    } catch {
        CircuitBreaker.shared.recordFailure()
    }
} else {
    // Circuit is open - fail fast
}
```

**State Machine:**
```
Closed → (failures >= 3) → Open → (30s timeout) → HalfOpen → (success) → Closed
                                                           ↓
                                                     (failure) → Open
```

### KeychainService

Secure credential storage using iOS Keychain.

```swift
import KagamiCore

// Save token
KeychainService.shared.saveToken("jwt-token")

// Retrieve token
if let token = KeychainService.shared.getToken() {
    // Use token
}

// Clear on logout
KeychainService.shared.clearAll()
```

**Features:**
- Auth token management
- Refresh token storage
- Username/server URL convenience storage
- Custom key-value pairs
- Thread-safe access

## Installation

### Swift Package Manager

Add to your `Package.swift`:

```swift
dependencies: [
    .package(path: "../packages/kagami-core-swift")
]
```

Or in Xcode:
1. File → Add Packages...
2. Add local package: `packages/kagami-core-swift`

## Migration from Duplicate Code

If your app has its own `CircuitBreaker.swift` or `KeychainService.swift`:

1. Add KagamiCore dependency
2. Remove local copies
3. Update imports to use `KagamiCore`

```swift
// Before
import Foundation
// Uses local CircuitBreaker.swift

// After
import KagamiCore
// Uses shared CircuitBreaker
```

## h(x) >= 0. Always.
