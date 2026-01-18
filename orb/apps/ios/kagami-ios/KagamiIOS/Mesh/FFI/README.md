# Kagami Mesh SDK FFI — Canonical Source

**FFI bindings have been deduplicated.**

## New Architecture

The UniFFI-generated Swift bindings now live in a **single canonical location**:

```
packages/kagami-mesh-swift/Sources/
├── FFI/                          # C headers and modulemap
│   ├── kagami_mesh_sdkFFI.h
│   └── module.modulemap
└── KagamiMesh/
    ├── kagami_mesh_sdk.swift     # UniFFI-generated Swift bindings
    └── MeshService.swift         # Cross-platform Swift wrapper
```

## Integration

This iOS app depends on the `KagamiMesh` package via Swift Package Manager:

```swift
// Package.swift
.package(name: "KagamiMesh", path: "../../../packages/kagami-mesh-swift"),
```

## Building the Rust Library

See `packages/kagami-mesh-sdk/README.md` for build instructions.

Quick build:
```bash
cd packages/kagami-mesh-sdk
./build.sh swift
```

This generates bindings directly into `packages/kagami-mesh-swift/Sources/`.

## Local Files

This directory is intentionally empty (except for this README). The iOS app imports `KagamiMesh` from the package instead of bundling duplicate FFI files.

The iOS-specific `MeshService.swift` and `MeshCommandRouter.swift` in `../` extend the cross-platform functionality with iOS features like Keychain persistence and Combine integration.

## h(x) >= 0. Always.
