# WireGuard VPN Sidecar for Cloud Run
#
# Connects to UniFi WireGuard VPN server to access home network.
# Uses userspace WireGuard (wireguard-go) since Cloud Run doesn't allow kernel modules.

FROM golang:1.21-alpine AS builder

# Build wireguard-go (userspace implementation)
RUN apk add --no-cache git make
RUN git clone https://git.zx2c4.com/wireguard-go /wireguard-go
WORKDIR /wireguard-go
RUN make

FROM alpine:3.19

# Install dependencies
RUN apk add --no-cache \
    wireguard-tools \
    iptables \
    iproute2 \
    curl \
    bash

# Copy wireguard-go binary
COPY --from=builder /wireguard-go/wireguard-go /usr/bin/

# Create config directory
RUN mkdir -p /etc/wireguard

# Healthcheck script
COPY healthcheck.sh /healthcheck.sh
RUN chmod +x /healthcheck.sh

# Entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV WG_INTERFACE=wg0
ENV WG_USERSPACE=1

HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD /healthcheck.sh

ENTRYPOINT ["/entrypoint.sh"]
