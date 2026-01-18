# 鏡 Kagami Instance

Your federated smart home, powered by GitHub.

## Quick Start

1. **Fork this repository**
2. **Enable GitHub Pages** (Settings → Pages → Source: `main` branch)
3. **Done!** Your instance is live at `https://YOUR_USERNAME.github.io/kagami-instance`

## What You Get

- 🏠 **Smart Home Dashboard** — Control lights, presence, automations
- 🌐 **Federation** — Connect with other Kagami instances
- 🔐 **End-to-End Encryption** — Your data, your keys
- 📱 **Works Everywhere** — Desktop, mobile, tablet
- 💰 **Free** — Public repos are free forever

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR GITHUB REPO                          │
│                                                              │
│  index.html          ← Dashboard UI (served via Pages)      │
│  .well-known/        ← Federation discovery                  │
│    kagami.json       ← Your instance's identity              │
│  data/               ← Encrypted config & state              │
│    config.enc        ← AES-256 encrypted                     │
│    state.enc         ← Your home state (encrypted)           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
           │
           │ HTTPS
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    GITHUB PAGES                              │
│                                                              │
│  Static hosting, global CDN, automatic HTTPS                │
│  Cost: $0 (public) or $4/mo (private with GitHub Pro)       │
│                                                              │
└─────────────────────────────────────────────────────────────┘
           │
           │ WebSocket (optional)
           ▼
┌─────────────────────────────────────────────────────────────┐
│                    KAGAMI RELAY                              │
│                    (relay.kagami.io)                         │
│                                                              │
│  Real-time sync between instances                           │
│  PBFT consensus for shared state                            │
│  Can self-host for full privacy                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Federation

Other Kagami instances can discover you by fetching:

```
https://YOUR_USERNAME.github.io/kagami-instance/.well-known/kagami.json
```

To federate with another instance, go to Dashboard → Federation → Add Instance.

## Consensus (via GitHub Issues)

State changes that affect federated instances use GitHub Issues for consensus:

1. Create issue with `[CONSENSUS]` prefix
2. Other instances vote by commenting
3. When quorum reached, change is applied
4. Issue is closed and labeled

This works even if the relay is offline!

## Privacy Options

| Option | Visibility | Cost | Federation |
|--------|------------|------|------------|
| **Public Repo** | Anyone can see code | Free | ✅ Full |
| **Private Repo** | Only you | $4/mo (Pro) | ✅ Full |
| **Self-Hosted** | Your server | Infrastructure | ✅ Full |

All data in `data/` is always encrypted regardless of repo visibility.

## Local Control (Kagami Hub)

For real-time smart home control (<100ms), get a Kagami Hub:

- **Raspberry Pi** — $35-75
- **Docker** — Any Linux/Mac/Windows machine
- **Syncs to GitHub** — Your hub backs up to this repo

[Get Started with Kagami Hub →](https://kagami.io/hub)

## Security

- 🔐 **AES-256-GCM** encryption for all stored data
- 🔑 **WebCrypto API** — Keys never leave your browser
- 🛡️ **Quantum-Safe Ready** — Kyber + X25519 hybrid available
- ✅ **No Server Access** — We can't read your data

## Customization

Edit `.well-known/kagami.json` to customize your instance:

```json
{
  "version": "kfp1",
  "owner": "your-username",
  "relay_url": "wss://relay.kagami.io",
  "capabilities": ["presence", "automation", "federation"]
}
```

## Support

- 📚 [Documentation](https://kagami.io/docs)
- 💬 [Discord Community](https://discord.gg/kagami)
- 🐛 [Report Issues](https://github.com/kagami-io/kagami/issues)

---

Built with ❤️ by the Kagami community.

鏡 — The mirror reflects the best of who you are.
