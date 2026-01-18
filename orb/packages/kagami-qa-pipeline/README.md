# Kagami QA Pipeline

A Gemini-powered video analysis pipeline for automated QA testing of mobile and desktop applications.

## Features

- **Video Processing**: Extract frames and segments from test recordings
- **AI Analysis**: Use Gemini Pro Vision to detect UI issues
- **Issue Tracking**: SQLite-based storage with regression detection
- **REST API**: HTTP endpoints for dashboard integration
- **WebSocket**: Real-time analysis progress updates
- **CLI Tool**: Command-line interface for local testing

## Quick Start

### Installation

```bash
# Install dependencies
npm install

# Copy environment config
cp .env.example .env

# Add your Gemini API key
# Edit .env and set GEMINI_API_KEY
```

### CLI Usage

```bash
# Analyze a single video
npm run cli -- ./test-video.mp4 --platform ios --test-name "Login Flow"

# Batch analyze a directory
npm run cli -- batch ./test-videos --platform android --parallel 2

# Generate a report
npm run cli -- report --format json --output report.json

# Check pipeline health
npm run cli -- health
```

### API Server

```bash
# Start the API server
npm run dev

# The server will start at http://localhost:3847
```

### Programmatic Usage

```typescript
import {
  getRunner,
  loadConfig,
  setConfig
} from '@kagami/qa-pipeline';

// Configure
const config = loadConfig();
setConfig(config);

// Run analysis
const runner = getRunner();
await runner.start();

const result = await runner.runAnalysis({
  videoPath: './test-recording.mp4',
  config: {
    platform: 'ios',
    testName: 'Login Flow'
  }
});

console.log(`Quality Score: ${result.qualityScore}/100`);
console.log(`Issues Found: ${result.issues.length}`);

for (const issue of result.issues) {
  console.log(`  [${issue.severity}] ${issue.description}`);
}

await runner.stop();
```

## API Endpoints

### Analysis

- `GET /api/analyses` - List all analyses
- `GET /api/analyses/:id` - Get specific analysis
- `POST /api/analyze` - Queue video for analysis

### Issues

- `GET /api/issues` - List all issues
- `GET /api/issues/stats` - Get issue statistics
- `POST /api/issues/:fingerprint/resolve` - Mark issue as resolved

### Pipeline

- `GET /api/health` - Pipeline health check
- `GET /api/queue` - Get queue status
- `DELETE /api/queue/:id` - Cancel queued job
- `POST /api/pipeline/pause` - Pause processing
- `POST /api/pipeline/resume` - Resume processing

## WebSocket Events

Connect to `ws://localhost:3847/ws` for real-time updates:

```typescript
const ws = new WebSocket('ws://localhost:3847/ws');

ws.onmessage = (event) => {
  const { type, payload, timestamp } = JSON.parse(event.data);

  switch (type) {
    case 'analysis:started':
      console.log('Analysis started:', payload.job.id);
      break;
    case 'analysis:progress':
      console.log(`Progress: ${payload.progress}%`);
      break;
    case 'analysis:completed':
      console.log('Complete!', payload.result.qualityScore);
      break;
  }
};

// Subscribe to specific events
ws.send(JSON.stringify({
  type: 'subscribe',
  events: ['analysis:progress', 'issue:detected']
}));
```

## Issue Categories

The analyzer checks for these issue types:

| Category | Description |
|----------|-------------|
| `ui_consistency` | Design system violations, color mismatches |
| `accessibility` | WCAG violations, contrast issues, touch targets |
| `animation` | Janky transitions, frame drops |
| `layout` | Overlapping elements, truncated text |
| `state` | Incorrect UI state, loading issues |
| `error` | Error messages, unhandled exceptions |
| `performance` | Slow responses, memory warnings |

## Severity Levels

- **critical**: Blocks user, crashes, data loss, major a11y violation
- **warning**: Degrades experience, minor issues
- **info**: Polish suggestions, minor improvements

## Configuration

All configuration can be set via environment variables or programmatically:

```typescript
const config = loadConfig({
  server: { port: 4000 },
  processing: { maxConcurrentJobs: 4 },
  gemini: { model: 'gemini-2.0-flash' }
});
```

See `.env.example` for all available options.

## Development

```bash
# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Type check
npm run typecheck

# Lint
npm run lint

# Build
npm run build
```

## Requirements

- Node.js 20+
- FFmpeg (for video processing)
- Gemini API key

## License

MIT
