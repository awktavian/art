# Kagami Mesh SDK Native Libraries

This directory contains the compiled native libraries for the Kagami Mesh SDK.

## Building the Native Libraries

To build the native libraries for Android, run from the `packages/kagami-mesh-sdk` directory:

```bash
# Install Android NDK targets
rustup target add aarch64-linux-android armv7-linux-androideabi x86_64-linux-android

# Build for all Android ABIs
cargo ndk -t arm64-v8a -t armeabi-v7a -t x86_64 -o ../apps/android/kagami-android/app/src/main/jniLibs build --release
```

Or using the project's build script:

```bash
cd packages/kagami-mesh-sdk
./build-android.sh
```

## Directory Structure

```
jniLibs/
  arm64-v8a/
    libkagami_mesh_sdk.so      # ARM64 (most modern Android devices)
  armeabi-v7a/
    libkagami_mesh_sdk.so      # ARM32 (older devices)
  x86_64/
    libkagami_mesh_sdk.so      # x86_64 (emulators, Chromebooks)
```

## Dependencies

The build requires:
- Rust toolchain with Android targets
- Android NDK (set via `ANDROID_NDK_HOME` or install with `cargo install cargo-ndk`)

## Library Features

The native library provides:
- Ed25519 identity and signatures (via ed25519-dalek)
- XChaCha20-Poly1305 encryption (via chacha20poly1305)
- X25519 Diffie-Hellman key exchange
- CRDT primitives (vector clocks, G-counters)
- Connection state machine with circuit breaker

h(x) >= 0. Always.
