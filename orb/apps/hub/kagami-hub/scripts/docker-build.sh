#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════
# KAGAMI HUB — Docker Build Script
# ═══════════════════════════════════════════════════════════════════════════
#
# Build and tag Docker images with proper versioning for Docker Hub.
#
# Usage:
#   ./scripts/docker-build.sh              # Build for local arch
#   ./scripts/docker-build.sh --push       # Build and push to Docker Hub
#   ./scripts/docker-build.sh --multiarch  # Build for all architectures
#   ./scripts/docker-build.sh --release    # Build release with all tags
#
# Tags generated:
#   - kagami/kagami-hub:latest
#   - kagami/kagami-hub:stable
#   - kagami/kagami-hub:v1.0.0
#   - kagami/kagami-hub:v1.0
#   - kagami/kagami-hub:v1
#   - kagami/kagami-hub:sha-abc1234
#
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ───────────────────────────────────────────────────────────────────────────
# Configuration
# ───────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Docker Hub repository
DOCKER_REPO="${DOCKER_REPO:-kagami/kagami-hub}"

# Version from VERSION file
VERSION=$(cat "$PROJECT_DIR/VERSION" | tr -d '[:space:]')

# Git information
COMMIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
COMMIT_SHA_FULL=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Parse version components
MAJOR=$(echo "$VERSION" | cut -d. -f1)
MINOR=$(echo "$VERSION" | cut -d. -f2)
PATCH=$(echo "$VERSION" | cut -d. -f3)

# ───────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ───────────────────────────────────────────────────────────────────────────

PUSH=false
MULTIARCH=false
RELEASE=false
LATEST=false
PLATFORMS="linux/arm64"  # Default to Raspberry Pi

while [[ $# -gt 0 ]]; do
    case $1 in
        --push)
            PUSH=true
            shift
            ;;
        --multiarch)
            MULTIARCH=true
            PLATFORMS="linux/arm64,linux/amd64"
            shift
            ;;
        --release)
            RELEASE=true
            LATEST=true
            MULTIARCH=true
            PLATFORMS="linux/arm64,linux/amd64"
            shift
            ;;
        --latest)
            LATEST=true
            shift
            ;;
        --platform)
            PLATFORMS="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --push       Push to Docker Hub after building"
            echo "  --multiarch  Build for linux/arm64 and linux/amd64"
            echo "  --release    Full release build with all tags"
            echo "  --latest     Also tag as 'latest'"
            echo "  --platform   Specify platforms (default: linux/arm64)"
            echo "  --version    Override version (default: from VERSION file)"
            echo "  -h, --help   Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ───────────────────────────────────────────────────────────────────────────
# Print Build Info
# ───────────────────────────────────────────────────────────────────────────

echo "═══════════════════════════════════════════════════════════════════════════"
echo "  KAGAMI HUB — Docker Build"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""
echo "  Repository:  $DOCKER_REPO"
echo "  Version:     $VERSION"
echo "  Commit:      $COMMIT_SHA ($BRANCH)"
echo "  Date:        $BUILD_DATE"
echo "  Platforms:   $PLATFORMS"
echo "  Push:        $PUSH"
echo "  Release:     $RELEASE"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

# ───────────────────────────────────────────────────────────────────────────
# Build Tags
# ───────────────────────────────────────────────────────────────────────────

TAGS=()

# Always include version and SHA tags
TAGS+=("--tag" "$DOCKER_REPO:v$VERSION")
TAGS+=("--tag" "$DOCKER_REPO:v$MAJOR.$MINOR")
TAGS+=("--tag" "$DOCKER_REPO:v$MAJOR")
TAGS+=("--tag" "$DOCKER_REPO:sha-$COMMIT_SHA")

# Branch tags
if [[ "$BRANCH" == "main" ]]; then
    TAGS+=("--tag" "$DOCKER_REPO:main")
elif [[ "$BRANCH" == "develop" ]]; then
    TAGS+=("--tag" "$DOCKER_REPO:develop")
fi

# Latest/stable tags for releases
if [[ "$LATEST" == true ]] || [[ "$RELEASE" == true ]]; then
    TAGS+=("--tag" "$DOCKER_REPO:latest")
    TAGS+=("--tag" "$DOCKER_REPO:stable")
fi

echo "Tags to build:"
for tag in "${TAGS[@]}"; do
    if [[ "$tag" != "--tag" ]]; then
        echo "  - $tag"
    fi
done
echo ""

# ───────────────────────────────────────────────────────────────────────────
# Ensure buildx is available
# ───────────────────────────────────────────────────────────────────────────

if ! docker buildx version &>/dev/null; then
    echo "❌ docker buildx not available. Please install Docker Desktop or buildx plugin."
    exit 1
fi

# Create/use builder
BUILDER_NAME="kagami-builder"
if ! docker buildx inspect "$BUILDER_NAME" &>/dev/null; then
    echo "Creating buildx builder: $BUILDER_NAME"
    docker buildx create --name "$BUILDER_NAME" --driver docker-container --bootstrap
fi
docker buildx use "$BUILDER_NAME"

# ───────────────────────────────────────────────────────────────────────────
# Build
# ───────────────────────────────────────────────────────────────────────────

cd "$PROJECT_DIR"

BUILD_ARGS=(
    "--file" "Dockerfile.production"
    "--platform" "$PLATFORMS"
    "--build-arg" "VERSION=$VERSION"
    "--build-arg" "COMMIT_SHA=$COMMIT_SHA_FULL"
    "--build-arg" "BUILD_DATE=$BUILD_DATE"
    "${TAGS[@]}"
)

if [[ "$PUSH" == true ]]; then
    BUILD_ARGS+=("--push")
    echo "🚀 Building and pushing to Docker Hub..."
else
    # Load into local docker (only works for single platform)
    if [[ "$MULTIARCH" == false ]]; then
        BUILD_ARGS+=("--load")
    fi
    echo "🔨 Building locally..."
fi

echo ""
echo "Running: docker buildx build ${BUILD_ARGS[*]} ."
echo ""

docker buildx build "${BUILD_ARGS[@]}" .

# ───────────────────────────────────────────────────────────────────────────
# Success
# ───────────────────────────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════════════════════════════════════════"
echo "  ✅ Build complete!"
echo "═══════════════════════════════════════════════════════════════════════════"
echo ""

if [[ "$PUSH" == true ]]; then
    echo "  Images pushed to Docker Hub:"
    for tag in "${TAGS[@]}"; do
        if [[ "$tag" != "--tag" ]]; then
            echo "    docker pull $tag"
        fi
    done
else
    echo "  To push to Docker Hub, run:"
    echo "    $0 --push"
fi

echo ""
echo "  To run locally:"
echo "    docker run -d -p 8080:8080 -p 8765:8765 $DOCKER_REPO:v$VERSION"
echo ""
echo "═══════════════════════════════════════════════════════════════════════════"

# 鏡
