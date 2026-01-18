# Kagami Design Tokens

Unified design tokens for all Kagami platforms.

## Overview

This package contains the canonical `tokens.json` that serves as the single source of truth for all design tokens across:

- **Swift** (iOS, watchOS, tvOS, visionOS)
- **Kotlin** (Android, Wear OS)
- **CSS** (Desktop/Web)
- **Rust** (Hub)

## Token Categories

| Category | Description |
|----------|-------------|
| Colors | Void palette, colony colors (e1-e7), status, safety, text |
| Typography | Font sizes, weights, line heights, semantic styles |
| Spacing | 8pt grid system (xxs to 6xl) |
| Radius | Corner radius tokens (none to full) |
| Motion | Fibonacci durations (89-2584ms), catastrophe-inspired easings |
| Shadows | Elevation system (none to xl, glow, chromatic) |
| Breakpoints | Responsive breakpoints (xs to 2xl) |
| Effects | Glass morphism, spectral shimmer, caustics |
| Accessibility | Touch targets, contrast ratios, focus states |

## Colony Colors (Octonion Basis)

| Colony | Hex | Basis | Function |
|--------|-----|-------|----------|
| Spark | #FF6B35 | e1 | Ideation |
| Forge | #D4AF37 | e2 | Implementation |
| Flow | #4ECDC4 | e3 | Adaptation |
| Nexus | #9B7EBD | e4 | Integration |
| Beacon | #F59E0B | e5 | Planning |
| Grove | #7EB77F | e6 | Research |
| Crystal | #67D4E4 | e7 | Verification |

## Fibonacci Motion Timing

| Token | Duration | Usage |
|-------|----------|-------|
| instant | 89ms | Micro-interactions |
| fast | 144ms | Quick transitions |
| normal | 233ms | Standard transitions |
| slow | 377ms | Modal presentations |
| slower | 610ms | Complex reveals |
| slowest | 987ms | Ambient motion |
| glacial | 1597ms | Very slow transitions |
| breathing | 2584ms | Breathing effects |

## Usage

### Generate All Platforms

```bash
python packages/kagami-design-tokens/generate.py
```

### Generate Specific Platform

```bash
python packages/kagami-design-tokens/generate.py --platform swift
python packages/kagami-design-tokens/generate.py --platform kotlin
python packages/kagami-design-tokens/generate.py --platform css
python packages/kagami-design-tokens/generate.py --platform rust
```

### Preview Without Writing

```bash
python packages/kagami-design-tokens/generate.py --dry-run
```

## Output Locations

| Platform | Output Path |
|----------|-------------|
| Swift | `packages/kagami-design-swift/Sources/KagamiDesign/DesignTokens.generated.swift` |
| Kotlin | `apps/android/kagami-android/app/src/main/java/com/kagami/android/ui/theme/DesignTokens.generated.kt` |
| CSS | `apps/desktop/kagami-client/src/css/design-tokens.generated.css` |
| Rust | `apps/hub/kagami-hub/src/design_tokens.generated.rs` |

## CI Integration

The design tokens are automatically regenerated on:
- Push to `main` or `session/*` branches when `packages/kagami-design-tokens/**` changes
- Pull requests affecting token files
- Manual workflow dispatch

See `.github/workflows/design-tokens.yml` for details.

## Editing Tokens

1. Edit `packages/kagami-design-tokens/tokens.json`
2. Run `make generate-tokens` or the generate.py script
3. Commit both the tokens.json and generated files

---

h(x) >= 0. Always.
