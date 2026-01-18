# Code Signing Setup for Kagami Desktop

This document describes the requirements and setup for code signing the Kagami Desktop application for macOS and Windows distribution.

## macOS Code Signing

### Requirements

1. **Apple Developer Account** - Required for distribution outside Mac App Store
2. **Developer ID Application Certificate** - For signing the app
3. **Developer ID Installer Certificate** - For signing the .pkg installer (optional)
4. **Notarization** - Required for macOS 10.15+ (Catalina and later)

### Setup Steps

#### 1. Create Certificates

1. Log in to [Apple Developer Portal](https://developer.apple.com/account)
2. Go to Certificates, Identifiers & Profiles
3. Create a new certificate:
   - Type: "Developer ID Application"
   - Follow the CSR creation process
4. Download and install the certificate in Keychain Access

#### 2. Configure tauri.conf.json

Update `src-tauri/tauri.conf.json`:

```json
{
  "bundle": {
    "macOS": {
      "signingIdentity": "Developer ID Application: Your Name (TEAM_ID)",
      "providerShortName": "TEAM_ID",
      "entitlements": "entitlements.plist",
      "minimumSystemVersion": "10.15"
    }
  }
}
```

#### 3. Create Entitlements

Create `src-tauri/entitlements.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <!-- Required for hardened runtime -->
    <key>com.apple.security.app-sandbox</key>
    <false/>

    <!-- Network access for API communication -->
    <key>com.apple.security.network.client</key>
    <true/>

    <!-- Local network access for mDNS discovery -->
    <key>com.apple.security.network.server</key>
    <true/>

    <!-- Microphone for voice commands (optional) -->
    <key>com.apple.security.device.audio-input</key>
    <true/>

    <!-- Accessibility for global hotkeys -->
    <key>com.apple.security.automation.apple-events</key>
    <true/>
</dict>
</plist>
```

#### 4. Environment Variables for CI/CD

Set these environment variables:

```bash
# Certificate identity
export APPLE_SIGNING_IDENTITY="Developer ID Application: Your Name (TEAM_ID)"

# Notarization credentials
export APPLE_ID="your-apple-id@email.com"
export APPLE_TEAM_ID="TEAM_ID"
export APPLE_PASSWORD="app-specific-password"
```

#### 5. Notarization

After building, notarize the app:

```bash
# Submit for notarization
xcrun notarytool submit target/release/bundle/macos/Kagami.app.zip \
  --apple-id "$APPLE_ID" \
  --team-id "$APPLE_TEAM_ID" \
  --password "$APPLE_PASSWORD" \
  --wait

# Staple the ticket
xcrun stapler staple target/release/bundle/macos/Kagami.app
```

### Entitlements Required for Kagami

| Entitlement | Purpose | Required |
|-------------|---------|----------|
| `network.client` | API communication | Yes |
| `network.server` | mDNS discovery | Yes |
| `device.audio-input` | Voice commands | Optional |
| `automation.apple-events` | Global hotkeys | Yes |
| `files.user-selected.read-write` | File access | Optional |

---

## Windows Code Signing

### Requirements

1. **Code Signing Certificate** - EV certificate recommended for SmartScreen reputation
2. **SignTool** - Included with Windows SDK
3. **Timestamp server** - For long-term validity

### Certificate Options

| Type | Cost | SmartScreen | Notes |
|------|------|-------------|-------|
| Standard Code Signing | ~$80/year | Builds reputation slowly | Good for internal |
| EV Code Signing | ~$300/year | Immediate trust | Recommended for public release |
| Azure Code Signing | Per-signature | Immediate trust | Good for CI/CD |

### Setup Steps

#### 1. Obtain Certificate

Purchase from a trusted CA:
- DigiCert
- Sectigo (Comodo)
- GlobalSign

#### 2. Configure tauri.conf.json

```json
{
  "bundle": {
    "windows": {
      "certificateThumbprint": "YOUR_CERT_THUMBPRINT",
      "digestAlgorithm": "sha256",
      "timestampUrl": "http://timestamp.digicert.com"
    }
  }
}
```

#### 3. Environment Variables for CI/CD

```powershell
# Certificate thumbprint
$env:TAURI_SIGNING_IDENTITY = "YOUR_CERT_THUMBPRINT"

# For PFX file signing
$env:TAURI_PRIVATE_KEY = "base64-encoded-pfx"
$env:TAURI_PRIVATE_KEY_PASSWORD = "pfx-password"
```

#### 4. Manual Signing (if needed)

```powershell
signtool sign /sha1 "THUMBPRINT" /fd sha256 /tr http://timestamp.digicert.com /td sha256 "Kagami.exe"
```

### Timestamp Servers

Use one of these for long-term validity:

- `http://timestamp.digicert.com`
- `http://timestamp.sectigo.com`
- `http://timestamp.globalsign.com`

---

## GitHub Actions CI/CD

Example workflow for automated signing:

```yaml
name: Build and Sign

on:
  push:
    tags: ['v*']

jobs:
  build-macos:
    runs-on: macos-latest
    steps:
      - uses: actions/checkout@v4

      - name: Import Certificate
        env:
          CERTIFICATE: ${{ secrets.APPLE_CERTIFICATE }}
          CERTIFICATE_PASSWORD: ${{ secrets.APPLE_CERTIFICATE_PASSWORD }}
        run: |
          echo $CERTIFICATE | base64 --decode > certificate.p12
          security create-keychain -p "" build.keychain
          security import certificate.p12 -k build.keychain -P "$CERTIFICATE_PASSWORD" -T /usr/bin/codesign
          security set-key-partition-list -S apple-tool:,apple: -s -k "" build.keychain

      - name: Build and Sign
        env:
          APPLE_SIGNING_IDENTITY: ${{ secrets.APPLE_SIGNING_IDENTITY }}
        run: |
          cd apps/desktop/kagami-client
          npm run tauri build

      - name: Notarize
        env:
          APPLE_ID: ${{ secrets.APPLE_ID }}
          APPLE_TEAM_ID: ${{ secrets.APPLE_TEAM_ID }}
          APPLE_PASSWORD: ${{ secrets.APPLE_PASSWORD }}
        run: |
          xcrun notarytool submit target/release/bundle/macos/*.dmg \
            --apple-id "$APPLE_ID" \
            --team-id "$APPLE_TEAM_ID" \
            --password "$APPLE_PASSWORD" \
            --wait

  build-windows:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4

      - name: Import Certificate
        env:
          CERTIFICATE: ${{ secrets.WINDOWS_CERTIFICATE }}
          CERTIFICATE_PASSWORD: ${{ secrets.WINDOWS_CERTIFICATE_PASSWORD }}
        run: |
          $bytes = [Convert]::FromBase64String("$env:CERTIFICATE")
          [IO.File]::WriteAllBytes("certificate.pfx", $bytes)
          certutil -f -p "$env:CERTIFICATE_PASSWORD" -importpfx certificate.pfx

      - name: Build and Sign
        env:
          TAURI_SIGNING_IDENTITY: ${{ secrets.WINDOWS_CERT_THUMBPRINT }}
        run: |
          cd apps/desktop/kagami-client
          npm run tauri build
```

---

## Troubleshooting

### macOS

**"app is damaged and can't be opened"**
- App wasn't notarized or stapled correctly
- Run: `xattr -cr /Applications/Kagami.app`

**"Developer cannot be verified"**
- Certificate not trusted or expired
- Check in Keychain Access

### Windows

**SmartScreen warning**
- Use EV certificate for immediate trust
- Otherwise, build reputation over time with downloads

**"Windows protected your PC"**
- Certificate not trusted
- Ensure timestamp was applied

---

## Security Best Practices

1. **Never commit certificates or private keys** to version control
2. **Use CI/CD secrets** for all signing credentials
3. **Rotate certificates** before expiration
4. **Enable 2FA** on all developer accounts
5. **Use hardware tokens** for EV certificates (required)
6. **Audit signing logs** regularly

---

h(x) >= 0. Always.
