# Kagami iOS

Native iOS client for the Kagami smart home system.

## Overview

Kagami iOS provides a modern, accessibility-first interface for controlling your smart home. Built with SwiftUI, it supports iPhone, iPad, Apple Watch, and CarPlay.

## Features

- **Smart Home Control**: Lights, shades, fireplace, TV mount, and more
- **Scene Activation**: Movie mode, goodnight, welcome home, away
- **Voice Commands**: Natural language voice control with Apple Speech framework
- **Real-time Updates**: WebSocket connection for instant state sync
- **Multi-platform**: iPhone, iPad (with sidebar), watchOS, CarPlay
- **Widgets**: Home screen widgets for quick actions
- **Siri Shortcuts**: Deep integration with iOS shortcuts

## Architecture

```
KagamiIOS/
├── KagamiIOSApp.swift          # App entry point, deep linking
├── ContentView.swift           # Main UI with adaptive layout
├── DesignSystem.swift          # Colors, typography, spacing
├── Services/
│   ├── KagamiAPIService.swift  # High-level API client
│   ├── KagamiNetworkService.swift  # HTTP with retry logic
│   ├── KeychainService.swift   # Secure credential storage
│   ├── SpeechRecognizer.swift  # Voice recognition
│   ├── HealthKitService.swift  # Health data integration
│   └── NotificationService.swift  # Push notifications
├── Views/
│   ├── HomeView               # Dashboard
│   ├── RoomsView              # Room controls
│   ├── ScenesView             # Scene activation
│   ├── SettingsView           # Configuration
│   └── Onboarding/            # First-run experience
├── Hub/                       # Media center controls
├── CarPlay/                   # CarPlay interface
└── Intents/                   # Siri shortcuts
```

## API Endpoints

The app communicates with the Kagami server over HTTPS (default: `https://api.awkronos.com`).

**Security**: All connections use HTTPS to prevent MITM attacks. Local development requires self-signed certificates.

### Authentication

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/user/token` | POST | OAuth2 password grant login |
| `/api/user/register` | POST | Create new account |

### Home Control

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server health check |
| `/home/rooms` | GET | List all rooms with device states |
| `/home/lights/set` | POST | Set light levels |
| `/home/shades/{action}` | POST | Control shades (open/close) |
| `/home/tv/{action}` | POST | TV mount control (raise/lower) |
| `/home/fireplace/on` | POST | Turn on fireplace |
| `/home/fireplace/off` | POST | Turn off fireplace |

### Scenes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/home/movie-mode/enter` | POST | Enter movie mode |
| `/home/goodnight` | POST | Goodnight scene |
| `/home/welcome-home` | POST | Welcome home scene |
| `/home/away` | POST | Away mode |

### Client Registration

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/home/clients/register` | POST | Register iOS client |
| `/api/home/clients/{id}/sense` | POST | Upload sensory data |
| `/api/home/clients/{id}/heartbeat` | POST | Client heartbeat |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `wss://{server}/ws/client/{clientId}` | Real-time updates (secure WebSocket) |

## Authentication Flow

1. **Initial Login**:
   - User enters server URL (mDNS discovery available)
   - User enters username/password
   - App calls `/api/user/token` with OAuth2 password grant
   - JWT token stored in iOS Keychain

2. **Subsequent Launches**:
   - App checks Keychain for stored token
   - If available, offers Face ID/Touch ID authentication
   - On success, restores session from stored token

3. **Token Storage**:
   - Tokens stored in iOS Keychain with `kSecAttrAccessibleWhenUnlockedThisDeviceOnly`
   - Cleared on logout
   - Server URL stored in UserDefaults for convenience

## Network Layer

The app uses a two-tier network architecture:

1. **KagamiNetworkService**: Low-level HTTP with:
   - Automatic retry with exponential backoff
   - Rate limit handling (429)
   - Server error retry (5xx)
   - Analytics integration

2. **KagamiAPIService**: High-level API with:
   - Service discovery via mDNS
   - WebSocket management
   - Request caching
   - Error propagation to UI

## Error Handling

Errors are propagated to the UI through:

- `KagamiAPIError`: Unified error type wrapping API, Auth, and Network errors
- `ErrorAlertModifier`: SwiftUI modifier for alert presentation
- `ErrorBannerView`: Inline error display with retry buttons
- `ConnectionErrorView`: Full-screen connection error state

All errors include:
- Localized description
- Recovery suggestion
- Retry capability flag

## Security

- JWT tokens stored in iOS Keychain
- Biometric authentication (Face ID/Touch ID) supported
- No sensitive data in UserDefaults
- HTTPS recommended for production (HTTP allowed for local development)

## Requirements

- iOS 17.0+
- iPadOS 17.0+
- watchOS 10.0+
- Xcode 15.0+

## Building

```bash
# Clone and open in Xcode
cd apps/ios/kagami-ios
open Package.swift

# Or use Swift Package Manager
swift build
swift test
```

## Configuration

The server URL can be configured:

1. **At Login**: Enter in the server URL field
2. **mDNS Discovery**: Tap the antenna icon to scan for servers
3. **Settings**: Change server URL after login

Default: `https://api.awkronos.com` (production) or `https://kagami.local:8001` (local with self-signed cert)

## Deep Links

The app supports the `kagami://` URL scheme:

| URL | Action |
|-----|--------|
| `kagami://room/{id}` | Navigate to room |
| `kagami://scene/{name}` | Activate scene |
| `kagami://settings` | Open settings |
| `kagami://hub` | Open media hub |
| `kagami://movie_mode` | Activate movie mode |
| `kagami://goodnight` | Activate goodnight |

## Accessibility

- WCAG 2.1 AA compliant
- VoiceOver support throughout
- Dynamic Type support
- Reduced motion support
- Minimum 44pt touch targets

## License

Proprietary - Kagami Smart Home System

---

h(x) >= 0. Always.
