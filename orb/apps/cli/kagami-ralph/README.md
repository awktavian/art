# Ralph AI Monitor

Real-time visualization of parallel Ralph AI training with Byzantine consensus voting.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (TypeScript + Vite)                               │
│  • Real-time WebSocket connection                           │
│  • Animated agent cards with physics                        │
│  • Byzantine consensus visualization                        │
│  • QR code Stripe payments                                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ WebSocket (/ws/ralph)
                   │
┌──────────────────▼──────────────────────────────────────────┐
│  Backend (Python FastAPI)                                   │
│  • WebSocket server for agent streams                       │
│  • Connects to ralph_tui.py output                          │
│  • Stripe payment integration                               │
│  • Byzantine consensus aggregation                          │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   │ Parses logs
                   │
┌──────────────────▼──────────────────────────────────────────┐
│  tools/ralph_tui.py                                         │
│  • Real training visualization                              │
│  • 7 agent windows with physics                             │
│  • Byzantine voting logic                                   │
└─────────────────────────────────────────────────────────────┘
```

## Development

```bash
# Install dependencies
npm install

# Start dev server
npm run dev

# Run tests
npm test

# Type check
npm run typecheck

# Lint
npm run lint

# Build for production
npm run build
```

## Testing

- **Unit tests**: `npm test` (Vitest)
- **E2E tests**: `npm run test:e2e` (Playwright)
- **Type safety**: `npm run typecheck` (TypeScript)

## Deployment

```bash
# Build
npm run build

# Serve dist/ with any static server
# Or use kagami API to serve
```

## Features

### ✅ Implemented
- TypeScript + Vite build system
- WebSocket connection to real backend
- Error handling with retry logic
- Comprehensive test coverage
- QR code Stripe payments
- Byzantine consensus visualization

### 🚧 In Progress (Phase 1 → 70/100)
- Real-time agent data streaming
- Performance optimization
- Accessibility audit (WCAG 2.1 AA)
- Security hardening (CSP, XSS protection)

### 📋 Planned (Phase 2 → 100/100)
- Analytics integration
- A/B testing framework
- Progressive Web App (PWA)
- Offline support
- Multi-language support

### ✨ Future (Phase 3 → 125/100)
- AI-powered personalized onboarding
- Generative UI per persona
- Real-time collaboration (multi-user)
- Particle effects on consensus
- Predictive error prevention

## Byzantine Consensus Score

**Current**: 42.1/100 (REJECTED)  
**Target Phase 1**: 70/100 (APPROVED)  
**Target Phase 2**: 100/100 (EXCELLENT)  
**Target Phase 3**: 125/100 (TRANSCENDENT)

See `AUDIT.md` for detailed scoring breakdown.
