# Kagami Secrets Configuration

## Overview

Kagami uses secrets from three sources:
1. **macOS Keychain** — Local development and on-premise deployment
2. **GitHub Actions Secrets** — CI/CD pipelines
3. **Google Cloud Secret Manager** — Production Cloud Run deployments

## Required GitHub Actions Secrets

### Currently Configured ✓

| Secret | Purpose | Last Updated |
|--------|---------|--------------|
| `ANTHROPIC_API_KEY` | Claude API access | Jan 2026 |
| `CANVAS_API_TOKEN` | Canvas LMS integration | Jan 2026 |
| `COMPOSIO_API_KEY` | Digital integrations | Jan 2026 |
| `ELEVENLABS_API_KEY` | Voice synthesis | Jan 2026 |
| `GEMINI_API_KEY` | Google AI access | Jan 2026 |
| `HF_TOKEN` | Hugging Face access | Jan 2026 |
| `OPENAI_API_KEY` | OpenAI API access | Jan 2026 |

### Needs Configuration ⚠️

| Secret | Purpose | Workflow | Priority |
|--------|---------|----------|----------|
| `STRIPE_API_KEY` | Payment processing | API deployment | P0 |
| `STRIPE_ACCOUNT_ID` | Stripe account | API deployment | P0 |
| `STRIPE_WEBHOOK_SECRET` | Webhook validation | API deployment | P0 |
| `GCP_WORKLOAD_IDENTITY_PROVIDER` | GCP auth | smarthome-deploy | P0 |
| `GCP_SERVICE_ACCOUNT` | GCP auth | smarthome-deploy | P0 |
| `CODECOV_TOKEN` | Coverage reporting | ci, coverage-tracking | P1 |
| `DOCKERHUB_USERNAME` | Docker registry | docker-hub-publish | P1 |
| `DOCKERHUB_TOKEN` | Docker registry | docker-hub-publish | P1 |
| `SLACK_WEBHOOK_URL` | Notifications | nightly-stress, ci | P2 |

### Optional (Feature-Specific)

| Secret | Purpose | Workflow |
|--------|---------|----------|
| `QA_DASHBOARD_URL` | QA metrics | gemini-video-analysis |
| `QA_DASHBOARD_TOKEN` | QA metrics | gemini-video-analysis |
| `CLOUD_STORAGE_BUCKET` | Media storage | gemini-video-analysis |

## macOS Keychain Secrets

All local secrets stored under service name `kagami`:

```bash
# List all Kagami secrets
security dump-keychain | grep -A2 "kagami" | grep "acct"

# Get a specific secret
security find-generic-password -s "kagami" -a "<key_name>" -w
```

### Core API Keys

| Key | Purpose |
|-----|---------|
| `stripe_api_key` | Stripe org API key |
| `stripe_account_id` | Stripe account ID |
| `openai_api_key` | OpenAI API |
| `gemini_api_key` | Google Gemini |
| `elevenlabs_api_key` | Voice synthesis |
| `COMPOSIO_API_KEY` | Digital integrations |

### Smart Home Integrations

| Key | Purpose |
|-----|---------|
| `control4_*` | Control4 home automation |
| `august_*` | August smart locks |
| `tesla_*` | Tesla vehicle integration |
| `eight_sleep_*` | Sleep tracking |
| `unifi_*` | UniFi network |
| `denon_host` | AV receiver |
| `dsc_*` | Security system |
| `kumo_*` | Mini-split HVAC |
| `oelo_*` | Outdoor lighting |

### Stripe Price IDs

| Key | Value |
|-----|-------|
| `stripe_price_personal` | price_1SoxoBAuWFOnOuV55OHa3O4z |
| `stripe_price_personal_annual` | price_1SoxoBAuWFOnOuV5NUM44Cqn |
| `stripe_price_family` | price_1SoxoBAuWFOnOuV5Iq4XP9hS |
| `stripe_price_family_annual` | price_1SoxoBAuWFOnOuV5QxAUFQ0R |
| `stripe_price_power` | price_1SoxoCAuWFOnOuV5nko3FZOl |
| `stripe_price_power_annual` | price_1SoxoCAuWFOnOuV5wpw96Opr |
| `stripe_price_usage` | price_1SoxoKAuWFOnOuV5dEw0XSQm |

## Environment Variables

### Required for Stripe

```bash
# .env (gitignored)
STRIPE_ENABLED=1
STRIPE_ACCOUNT_ID=acct_1SoxfKAuWFOnOuV5
STRIPE_PRICE_PERSONAL=price_1SoxoBAuWFOnOuV55OHa3O4z
STRIPE_PRICE_PERSONAL_ANNUAL=price_1SoxoBAuWFOnOuV5NUM44Cqn
STRIPE_PRICE_FAMILY=price_1SoxoBAuWFOnOuV5Iq4XP9hS
STRIPE_PRICE_FAMILY_ANNUAL=price_1SoxoBAuWFOnOuV5QxAUFQ0R
STRIPE_PRICE_POWER=price_1SoxoCAuWFOnOuV5nko3FZOl
STRIPE_PRICE_POWER_ANNUAL=price_1SoxoCAuWFOnOuV5wpw96Opr
STRIPE_PRICE_USAGE=price_1SoxoKAuWFOnOuV5dEw0XSQm
STRIPE_PORTAL_RETURN_URL=https://kagami.ai/account
```

### Required for Cloud Run

```bash
# Set via gcloud or terraform
GCP_PROJECT_ID=gen-lang-client-0509316009
GCP_REGION=us-west1
```

## Setting Up GitHub Secrets

### Via CLI

```bash
# Stripe
gh secret set STRIPE_API_KEY
gh secret set STRIPE_ACCOUNT_ID --body "acct_1SoxfKAuWFOnOuV5"
gh secret set STRIPE_WEBHOOK_SECRET

# GCP (get from terraform or console)
gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER
gh secret set GCP_SERVICE_ACCOUNT

# Docker Hub
gh secret set DOCKERHUB_USERNAME
gh secret set DOCKERHUB_TOKEN

# Optional
gh secret set CODECOV_TOKEN
gh secret set SLACK_WEBHOOK_URL
```

### Via GitHub UI

1. Go to Repository → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add each required secret

## Cloud Run Secrets

For production Cloud Run deployments, secrets should be:
1. Stored in Google Cloud Secret Manager
2. Mounted as environment variables in Cloud Run service

```bash
# Create secret in GCP
gcloud secrets create stripe-api-key --data-file=-
echo "sk_live_xxx" | gcloud secrets versions add stripe-api-key --data-file=-

# Reference in Cloud Run
gcloud run services update kagami-api \
  --set-secrets="STRIPE_API_KEY=stripe-api-key:latest"
```

## Secret Rotation

### Stripe
- API keys can be rolled in Stripe Dashboard
- Update keychain, .env, and GitHub secrets
- Webhook secrets auto-rotate on endpoint update

### API Keys
- Rotate quarterly for security
- Update all three locations: keychain, .env, GitHub

## Verification

```bash
# Verify local secrets
PYTHONPATH=packages python3 -c "
from kagami_integrations.stripe_billing import stripe_enabled, _stripe_request
print(f'Stripe enabled: {stripe_enabled()}')
result = _stripe_request('GET', 'products', {'limit': '1'})
print(f'API connection: {result.get(\"ok\", False)}')
"

# Verify GitHub secrets (check workflow runs)
gh run list --workflow=ci.yml --limit=1
```
