# Vercel Deployment Rules

## Constants
- **Team ID**: `team_LRfTyFRIUR6SN3FFcYjqqBij`
- **Team Slug**: `timothyjacoby-9338s-projects`
- **Project Name**: `kagami-art`
- **Framework**: Static (no build step)

## Deployment Protocol

### Before Every Deploy
1. Validate changed files render correctly in browser
2. Check WCAG 2.1 AA compliance on modified pages
3. Ensure `prefers-reduced-motion` is respected
4. Verify no hardcoded localhost URLs in production code
5. Confirm `vercel.json` cache headers are appropriate for changed file types

### Deploy Command
Use `deploy_to_vercel` MCP tool — DO NOT use CLI `vercel deploy`.
The MCP tool handles auth, project linking, and team context automatically.

### Post-Deploy Verification (MANDATORY)
```
get_deployment(idOrUrl, teamId) → confirm state === "READY"
get_deployment_build_logs(idOrUrl, teamId) → scan for warnings/errors
web_fetch_vercel_url(url) → smoke test at least the changed pages
```

### Monitoring After Deploy
- `get_runtime_logs(projectId, teamId, level=["error","warning"], since="1h")` — check for runtime issues
- `list_toolbar_threads(teamId, status="unresolved")` — check for new feedback
- Resolve toolbar threads after addressing feedback

### Rollback
If a deployment breaks production:
1. `list_deployments(projectId, teamId)` → find last known good deployment
2. Redeploy from that commit or use Vercel dashboard rollback

## Cache Header Rules

When adding NEW file types or changing asset paths:
- HTML files → `max-age=0, must-revalidate` (always fresh)
- Shared libs (`/lib/*.js`) → `max-age=31536000, immutable` (versioned)
- Project JS/CSS → `max-age=86400` (1 day)
- Binary assets (images, fonts, audio) → `max-age=31536000, immutable`
- Design system CSS → `max-age=0, must-revalidate` (evolves with Kagami)

## What NOT to Deploy via Vercel
- `medverify/` → Deployed separately to Fly.io
- `realtime-proxy/` → Deployed separately to Fly.io
- The `ignoreCommand` in vercel.json handles this automatically

## Domain Management
Use `check_domain_availability_and_price(names[])` before purchasing.
Max 10 domains per check. Returns availability + pricing.

## Vercel Documentation
When unsure about platform features, use `search_vercel_documentation(topic)`.
Covers: routing, caching, CDN, edge functions, image optimization, security, pricing.
