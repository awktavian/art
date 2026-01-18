# ═══════════════════════════════════════════════════════════════
# KAGAMI HUB DOCKERFILE
# Colony: Forge (e₂) — Implementation
#
# Multi-stage build for Raspberry Pi (ARM64) deployment
# Supports voice wake word, LED ring, and real-time API
# ═══════════════════════════════════════════════════════════════

# Stage 1: Build stage
FROM rust:1.75-bookworm AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libasound2-dev \
    libssl-dev \
    build-essential \
    crossbuild-essential-arm64 \
    && rm -rf /var/lib/apt/lists/*

# Set up cross-compilation for ARM64 (Raspberry Pi)
ENV CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc
ENV PKG_CONFIG_SYSROOT_DIR=/usr/aarch64-linux-gnu

# Add ARM64 target
RUN rustup target add aarch64-unknown-linux-gnu

WORKDIR /app

# Copy Cargo files first for dependency caching
COPY Cargo.toml Cargo.lock ./

# Create dummy src for dependency build
RUN mkdir src && echo "fn main() {}" > src/main.rs

# Build dependencies (cached layer)
RUN cargo build --release --target aarch64-unknown-linux-gnu || \
    cargo build --release

# Remove dummy src
RUN rm -rf src

# Copy actual source code
COPY src/ src/
COPY config/ config/

# Build the actual binary
RUN touch src/main.rs && \
    cargo build --release --target aarch64-unknown-linux-gnu || \
    cargo build --release

# ═══════════════════════════════════════════════════════════════
# Stage 2: Runtime stage (minimal)
# ═══════════════════════════════════════════════════════════════

FROM debian:bookworm-slim AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    libasound2 \
    libssl3 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash kagami

WORKDIR /app

# Copy binary from builder
COPY --from=builder /app/target/*/release/kagami-hub /usr/local/bin/kagami-hub

# Copy configuration
COPY config/ /app/config/

# Set ownership
RUN chown -R kagami:kagami /app

# Switch to non-root user
USER kagami

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose ports
# 8080: Phone configuration web server + mDNS discovery
# 8765: WebSocket for real-time state sync
EXPOSE 8080 8765

# Environment variables
ENV RUST_LOG=info
ENV KAGAMI_HUB_CONFIG=/app/config/hub.toml
ENV KAGAMI_API_URL=http://kagami.local:8001
ENV HUB_WEB_PORT=8080

# Volume for configuration overrides
VOLUME ["/app/config"]

# Entry point
ENTRYPOINT ["kagami-hub"]

# ═══════════════════════════════════════════════════════════════
# RASPBERRY PI SPECIFIC BUILD
# ═══════════════════════════════════════════════════════════════

# For native Raspberry Pi build (on the device itself):
# docker build --platform linux/arm64 -t kagami-hub:latest .

# For cross-compilation from x86:
# docker buildx build --platform linux/arm64 -t kagami-hub:latest .

# ═══════════════════════════════════════════════════════════════
# DOCKER COMPOSE USAGE
# ═══════════════════════════════════════════════════════════════
#
# version: '3.8'
# services:
#   kagami-hub:
#     image: kagami-hub:latest
#     container_name: kagami-hub
#     restart: unless-stopped
#     privileged: true  # Required for GPIO/LED access
#     devices:
#       - /dev/snd:/dev/snd  # Audio access
#       - /dev/spidev0.0:/dev/spidev0.0  # SPI for LED ring
#     environment:
#       - KAGAMI_API_URL=http://kagami.local:8001
#       - RUST_LOG=info
#     volumes:
#       - ./config:/app/config
#     network_mode: host
#
# ═══════════════════════════════════════════════════════════════

# Labels
LABEL org.opencontainers.image.title="Kagami Hub"
LABEL org.opencontainers.image.description="Voice-first smart home hub for Raspberry Pi"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.authors="Kagami Team"
LABEL org.opencontainers.image.source="https://github.com/kagami/kagami-hub"

# 鏡
# The Hub listens. The Hub speaks.
# h(x) ≥ 0. Always.
