#!/bin/bash
# Kagami Mesh SDK - Unified Build Script
#
# Builds the SDK and generates bindings for all platforms:
#   - Swift (iOS/visionOS/watchOS)
#   - Kotlin (Android)
#   - Rust (Desktop - native)
#
# Usage:
#   ./build.sh           # Build all
#   ./build.sh swift     # Swift only
#   ./build.sh kotlin    # Kotlin only
#   ./build.sh test      # Run tests only
#   ./build.sh clean     # Clean build artifacts

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Detect platform
detect_platform() {
    case "$(uname -s)" in
        Darwin*)
            PLATFORM="macos"
            LIB_EXT="dylib"
            LIB_PREFIX="lib"
            ;;
        Linux*)
            PLATFORM="linux"
            LIB_EXT="so"
            LIB_PREFIX="lib"
            ;;
        *)
            log_error "Unsupported platform: $(uname -s)"
            exit 1
            ;;
    esac
}

# Build the Rust library
build_lib() {
    log_info "Building kagami-mesh-sdk (release)..."
    cargo build --release
    log_success "Library built: target/release/${LIB_PREFIX}kagami_mesh_sdk.${LIB_EXT}"
}

# Run tests
run_tests() {
    log_info "Running SDK tests..."
    cargo test
    log_success "All tests passed!"
}

# Generate Swift bindings
generate_swift() {
    log_info "Generating Swift bindings..."
    cargo run --release --features bindgen --bin uniffi-bindgen -- swift

    # CANONICAL LOCATION: ../kagami-mesh-swift/Sources/
    # This is the ONLY place FFI files should exist
    SWIFT_PKG_DIR="$SCRIPT_DIR/../kagami-mesh-swift"
    
    log_info "Copying Swift bindings to canonical location: kagami-mesh-swift..."
    mkdir -p "$SWIFT_PKG_DIR/Sources/KagamiMesh"
    mkdir -p "$SWIFT_PKG_DIR/Sources/FFI"
    
    # Copy generated Swift bindings
    cp bindings/swift/kagami_mesh_sdk.swift "$SWIFT_PKG_DIR/Sources/KagamiMesh/"
    
    # Copy FFI headers and modulemap
    cp bindings/swift/kagami_mesh_sdkFFI.h "$SWIFT_PKG_DIR/Sources/FFI/"
    cp bindings/swift/kagami_mesh_sdkFFI.modulemap "$SWIFT_PKG_DIR/Sources/FFI/module.modulemap" 2>/dev/null || \
        echo "module kagami_mesh_sdkFFI { header \"kagami_mesh_sdkFFI.h\" export * }" > "$SWIFT_PKG_DIR/Sources/FFI/module.modulemap"

    # Clean up intermediate files (source is in kagami-mesh-swift now)
    rm -rf bindings/swift/Sources 2>/dev/null || true
    
    log_success "Swift bindings generated at: $SWIFT_PKG_DIR/Sources/"
}

# Generate Kotlin bindings
generate_kotlin() {
    log_info "Generating Kotlin bindings..."
    cargo run --release --features bindgen --bin uniffi-bindgen -- kotlin

    log_success "Kotlin bindings generated at: bindings/kotlin/"
}

# Clean build artifacts
clean() {
    log_info "Cleaning build artifacts..."
    cargo clean
    rm -rf bindings/
    log_success "Clean complete"
}

# Print usage
usage() {
    echo "Kagami Mesh SDK Build Script"
    echo ""
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  (none)    Build library and generate all bindings"
    echo "  swift     Generate Swift bindings only"
    echo "  kotlin    Generate Kotlin bindings only"
    echo "  test      Run tests only"
    echo "  clean     Clean build artifacts"
    echo "  help      Show this help"
    echo ""
    echo "Examples:"
    echo "  ./build.sh          # Full build + all bindings"
    echo "  ./build.sh swift    # Swift bindings only (requires prior build)"
    echo "  ./build.sh test     # Run test suite"
}

# Main
main() {
    detect_platform

    case "${1:-all}" in
        all)
            build_lib
            run_tests
            generate_swift
            generate_kotlin
            log_success "Build complete! Bindings ready for iOS/Android integration."
            ;;
        swift)
            if [ ! -f "target/release/${LIB_PREFIX}kagami_mesh_sdk.${LIB_EXT}" ]; then
                build_lib
            fi
            generate_swift
            ;;
        kotlin)
            if [ ! -f "target/release/${LIB_PREFIX}kagami_mesh_sdk.${LIB_EXT}" ]; then
                build_lib
            fi
            generate_kotlin
            ;;
        test)
            run_tests
            ;;
        clean)
            clean
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            log_error "Unknown command: $1"
            usage
            exit 1
            ;;
    esac
}

main "$@"
