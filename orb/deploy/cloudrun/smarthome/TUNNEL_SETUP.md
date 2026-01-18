# Secure Tunnel: Cloud Run ↔ Home Network

End-to-end encrypted tunnel using **Tailscale** (WireGuard-based mesh VPN).

```
┌─────────────────┐         WireGuard          ┌─────────────────┐
│   Cloud Run     │◄────────encrypted────────►│   Home Network   │
│  (GCP us-west1) │         tunnel            │  (192.168.1.x)   │
├─────────────────┤                           ├─────────────────┤
│ kagami-smarthome│                           │ Control4        │
│ + tailscale     │                           │ UniFi           │
│   sidecar       │                           │ Denon           │
└─────────────────┘                           └─────────────────┘
        │                                             │
        └──────── Tailscale Mesh Network ────────────┘
                   (100.x.x.x addresses)
```

## Step 1: Create Tailscale Account

1. Go to https://login.tailscale.com
2. Sign up with Google/GitHub
3. Note your **tailnet name** (e.g., `tail1234.ts.net`)

## Step 2: Install Tailscale Subnet Router at Home

### Option A: On your Mac (easiest for testing)

```bash
# Install Tailscale
brew install tailscale

# Start and authenticate
sudo tailscaled &
tailscale up --advertise-routes=192.168.1.0/24 --accept-dns=false

# Approve subnet routes in Tailscale admin console
# https://login.tailscale.com/admin/machines
```

### Option B: On UniFi (recommended for 24/7)

UniFi Dream Machine doesn't natively support Tailscale, but you can:

1. **Use a Raspberry Pi** on your network as subnet router
2. Or run Tailscale in a **container on UniFi** (if UDM Pro)

```bash
# On Raspberry Pi
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up --advertise-routes=192.168.1.0/24 --accept-dns=false
```

### Option C: Docker on any home server

```bash
docker run -d \
  --name=tailscale \
  --hostname=kagami-home \
  --cap-add=NET_ADMIN \
  --cap-add=SYS_MODULE \
  -e TS_AUTHKEY=tskey-auth-xxx \
  -e TS_EXTRA_ARGS="--advertise-routes=192.168.1.0/24" \
  -e TS_STATE_DIR=/var/lib/tailscale \
  -v tailscale-state:/var/lib/tailscale \
  tailscale/tailscale:latest
```

## Step 3: Approve Subnet Routes

1. Go to https://login.tailscale.com/admin/machines
2. Find your home device
3. Click "..." → "Edit route settings"
4. Enable the `192.168.1.0/24` subnet route

## Step 4: Generate Auth Key for Cloud Run

1. Go to https://login.tailscale.com/admin/settings/keys
2. Click "Generate auth key"
3. Settings:
   - Reusable: Yes
   - Ephemeral: Yes (for Cloud Run instances)
   - Tags: `tag:cloudrun`
4. Copy the key (starts with `tskey-auth-`)

## Step 5: Store Auth Key in GCP Secret Manager

```bash
echo -n "tskey-auth-kXXXXXXXXXXXXXXXXX" | \
  gcloud secrets create tailscale-authkey \
    --data-file=- \
    --project=gen-lang-client-0509316009

# Or add version to existing secret
echo -n "tskey-auth-kXXXXXXXXXXXXXXXXX" | \
  gcloud secrets versions add tailscale-authkey \
    --data-file=- \
    --project=gen-lang-client-0509316009
```

## Step 6: Deploy Cloud Run with Tailscale Sidecar

The updated deployment uses a multi-container setup:
- Main container: kagami-smarthome
- Sidecar: tailscale (handles VPN)

See `cloudbuild-tailscale.yaml` for the deployment config.

## Security Notes

- All traffic is end-to-end encrypted (WireGuard)
- No ports exposed on home network
- Tailscale uses NAT traversal (no firewall changes needed)
- Auth keys can be revoked instantly from admin console
- ACLs can restrict which services Cloud Run can access

## Troubleshooting

```bash
# Check Tailscale status (home device)
tailscale status

# Check connectivity
tailscale ping 192.168.1.x

# View logs
tailscale bugreport
```

## Alternative: Cloudflare Tunnel

If you prefer Cloudflare:

```bash
# On home device
cloudflared tunnel create kagami-home
cloudflared tunnel route dns kagami-home home.yourdomain.com
cloudflared tunnel run kagami-home
```

Then configure Cloud Run to use the Cloudflare endpoint.
