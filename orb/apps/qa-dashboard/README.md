# Kagami QA Dashboard

High-craft QA dashboard for monitoring and analyzing user journey test videos across all Kagami platforms.

## Overview

The QA Dashboard provides real-time visibility into test health across iOS, Android, Desktop, Hub, watchOS, tvOS, and visionOS platforms. It integrates with the Gemini-powered video analysis pipeline to provide AI-driven insights into test failures.

## Features

- **Platform Health Monitoring** - Real-time status of all test platforms
- **Video Analysis** - AI-powered analysis of test recordings using Gemini
- **Trend Visualization** - Pass rate trends over time
- **Issue Tracking** - Categorized issue detection with severity levels
- **Real-time Updates** - WebSocket-based live test status updates
- **Responsive Design** - Works on desktop and mobile devices

## Design Philosophy

Built with the Kagami design system:

- **Colony Colors** - Semantic colors mapped to test states (Grove for pass, Spark for fail, etc.)
- **Fibonacci Timing** - All animations use Fibonacci-based durations (89ms, 144ms, 233ms, 377ms, 610ms, 987ms)
- **Accessibility First** - WCAG AAA compliance, supports reduced motion and high contrast modes
- **Dark Mode Default** - Void background with luminous Colony accents

## Getting Started

### Prerequisites

- Node.js 18+
- npm or pnpm

### Installation

```bash
# Install dependencies
npm install --legacy-peer-deps

# Start development server
npm run dev
```

The dashboard will be available at `http://localhost:3000`.

### Environment Variables

Create a `.env.local` file:

```bash
# QA Pipeline API (optional - uses mock data if not set)
NEXT_PUBLIC_API_URL=http://localhost:3001
NEXT_PUBLIC_WS_URL=ws://localhost:3001

# API Authentication (for protected endpoints)
NEXT_PUBLIC_API_KEY=your-api-key
```

## Architecture

```
src/
├── app/                    # Next.js App Router pages
│   ├── page.tsx           # Dashboard home
│   ├── analysis/          # Analysis view
│   ├── reports/           # Reports view
│   ├── journey/[id]/      # Journey detail
│   └── platform/[platform]/ # Platform detail
├── components/
│   ├── ui/                # Design system components
│   │   ├── button.tsx     # Button variants
│   │   ├── card.tsx       # Card component
│   │   ├── progress.tsx   # Progress indicators
│   │   ├── celebration.tsx # Delight animations
│   │   └── live-region.tsx # Accessibility
│   ├── layout/            # Layout components
│   │   ├── header.tsx     # App header
│   │   ├── sidebar.tsx    # Platform sidebar
│   │   └── ambient-canvas.tsx # Background animation
│   ├── video/             # Video components
│   └── charts/            # Data visualization
├── hooks/                 # React hooks
│   ├── use-theme.tsx      # Theme management
│   └── use-websocket.tsx  # WebSocket connection
├── lib/                   # Utilities
│   ├── utils.ts          # Helper functions
│   └── mock-data.ts      # Development mock data
├── styles/
│   └── globals.css       # Global styles & tokens
└── types/
    └── index.ts          # TypeScript types
```

## Accessibility

The dashboard is designed with accessibility as a first-class concern:

- **Keyboard Navigation** - Full keyboard support with visible focus indicators
- **Screen Reader Support** - ARIA labels, roles, and live regions for dynamic content
- **Reduced Motion** - Respects `prefers-reduced-motion` preference
- **High Contrast** - Enhanced contrast in high contrast mode
- **Touch Targets** - Minimum 44px touch targets for interactive elements
- **Skip Links** - Skip to main content link for keyboard users

## Scripts

```bash
npm run dev      # Start development server
npm run build    # Production build
npm run start    # Start production server
npm run lint     # Run ESLint
npm run type-check # TypeScript type checking
```

## Integration with QA Pipeline

The dashboard connects to the `@kagami/qa-pipeline` package for:

- Fetching analysis results
- Receiving real-time test updates via WebSocket
- Triggering new video analyses

See the `packages/kagami-qa-pipeline` README for pipeline setup.

## Security

- **CORS** - Configurable origin allowlist via `CORS_ALLOWED_ORIGINS`
- **API Authentication** - Protected routes require `X-API-Key` header
- **Content Security** - Security headers (X-Content-Type-Options, X-Frame-Options, X-XSS-Protection)

## License

MIT
