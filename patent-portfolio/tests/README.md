# Patent Museum Tests

## Test Structure

### Basic Tests (`basic.spec.js`)
- **Run in**: Headless mode (no GPU required)
- **What**: DOM structure, HTML validity, CSS loading, module syntax
- **Command**: `npx playwright test basic.spec.js --project=chromium`

### Visual/Interaction Tests
- **Run in**: Headed mode (requires GPU)
- **What**: WebGL rendering, museum navigation, artwork interactions
- **Command**: `npx playwright test --project=chromium-webgl --headed`

### XR Tests (`xr-simulation/`)
- **Run in**: Headed mode with XR polyfill
- **What**: WebXR session handling, VR/AR UI

## Known Limitations

### Headless Chrome + WebGL
Chromium's headless mode uses SwiftShader (software rendering) for WebGL. This is:
- Very slow (10-100x slower than hardware)
- Memory intensive
- Prone to crashes with complex 3D scenes

**Solution**: Run WebGL tests in headed mode with `--headed` flag.

### Running Tests

```bash
# Basic tests (headless, fast)
npm test -- basic.spec.js

# WebGL tests (headed, requires GPU)
npm test -- --project=chromium-webgl --headed

# All tests (requires GPU)
npm test -- --headed
```

## CI/CD Recommendations

For CI environments:
1. Run basic tests in headless mode
2. Skip or defer WebGL tests to manual verification
3. Use visual snapshot testing for regression detection
