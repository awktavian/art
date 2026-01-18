# Privacy and Telemetry Settings

This document describes the privacy settings and telemetry options for the Kagami Desktop application.

## Data Collection Overview

Kagami collects minimal data necessary for operation. All data collection is opt-in and can be disabled.

### What We Collect (when enabled)

| Data Type | Purpose | Retention | Can Disable |
|-----------|---------|-----------|-------------|
| Crash reports | Fix bugs, improve stability | 90 days | Yes |
| Usage analytics | Understand feature usage | 30 days | Yes |
| Performance metrics | Optimize response times | 7 days | Yes |
| Error logs | Debug issues | 30 days | Yes |

### What We Never Collect

- Voice recordings (processed locally)
- Smart home device states (processed locally)
- Personal calendar data
- Location data beyond presence (home/away)
- Keystrokes or typed commands
- Screen content

## Telemetry Settings

### Opting Out

All telemetry can be disabled in Settings or via environment variables:

```bash
# Disable all telemetry
export KAGAMI_TELEMETRY_ENABLED=false

# Disable specific categories
export KAGAMI_CRASH_REPORTS=false
export KAGAMI_USAGE_ANALYTICS=false
export KAGAMI_PERFORMANCE_METRICS=false
```

### Settings UI

In the Kagami Desktop app:

1. Click the tray icon
2. Select "Settings..."
3. Navigate to "Privacy"
4. Toggle telemetry options as desired

### Available Options

```json
{
  "privacy": {
    "telemetry_enabled": true,
    "crash_reports": true,
    "usage_analytics": false,
    "performance_metrics": true,
    "send_device_info": false
  }
}
```

## Crash Reporting (Sentry)

Crash reports are sent to Sentry when:
- `KAGAMI_SENTRY_DSN` environment variable is set
- Crash reports are not disabled

### What's Included in Crash Reports

- Stack trace
- OS version and architecture
- Kagami version
- Error message
- Device model (if enabled)

### What's NOT Included

- User identity
- IP address (anonymized)
- Smart home data
- API tokens or secrets
- Voice or audio data

### Disabling Crash Reports

```bash
# Unset the Sentry DSN
unset KAGAMI_SENTRY_DSN

# Or disable via environment
export KAGAMI_CRASH_REPORTS=false
```

## Local Data Storage

Kagami stores data locally on your device:

| Location | Purpose | Contains |
|----------|---------|----------|
| `~/.kagami/config.json` | Settings | Preferences, API URL |
| `~/.kagami/cache/` | Performance | Cached API responses |
| `~/.kagami/logs/` | Debugging | Local-only logs |
| macOS Keychain | Security | API tokens (encrypted) |

### Clearing Local Data

```bash
# Clear all local data
rm -rf ~/.kagami/

# Clear only cache
rm -rf ~/.kagami/cache/

# Clear logs
rm -rf ~/.kagami/logs/
```

## Network Connections

Kagami makes network connections to:

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `kagami.local:8001` | Smart home API | Continuous |
| `releases.awkronos.com` | Update checks | On launch |
| `sentry.io` | Crash reports | On crash (if enabled) |
| `fonts.googleapis.com` | UI fonts | On launch |

### Blocking Telemetry at Network Level

You can block telemetry endpoints in your firewall:

```
# Block Sentry
sentry.io

# Keep these for functionality:
# kagami.local - Required for smart home
# releases.awkronos.com - Optional for updates
```

## Third-Party Services

### Sentry (Crash Reporting)
- Only used if DSN is configured
- Privacy policy: https://sentry.io/privacy/
- Data center: US (can be changed with self-hosted)

### Google Fonts
- Used for UI typography
- No tracking or analytics
- Privacy policy: https://policies.google.com/privacy

## Compliance

### GDPR
- All data collection is opt-in
- Data can be deleted on request
- No cross-device tracking
- No third-party data sharing

### CCPA
- No sale of personal information
- Deletion requests supported
- Disclosure of data collection (this document)

### Children's Privacy
- Kagami is not intended for children under 13
- No age-gated content
- Parental consent required for minors

## Contact

For privacy questions or data deletion requests:
- Email: privacy@awkronos.com
- GitHub: https://github.com/awktavian/kagami/issues

## Changelog

| Date | Change |
|------|--------|
| 2025-01-02 | Initial privacy documentation |

---

h(x) >= 0. Always.
