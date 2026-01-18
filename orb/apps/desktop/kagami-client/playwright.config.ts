/**
 * Playwright Configuration - Kagami Visual Regression Tests
 *
 * Configures visual testing across multiple viewports, themes, browsers, and platforms.
 * Supports consistent cross-platform snapshot generation via Docker.
 *
 * Colony: Crystal (e7) - Verification & Polish
 */

import { defineConfig, devices } from '@playwright/test';

/**
 * Platform detection for snapshot paths
 * In CI with Docker, we use 'linux' as the canonical platform
 */
const isDocker = process.env.DOCKER_BASELINE === 'true';
const snapshotPlatform = isDocker ? 'docker' : process.platform;

export default defineConfig({
  testDir: './tests/visual',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'test-results/html-report' }],
    ['json', { outputFile: 'test-results/results.json' }],
  ],
  outputDir: 'test-results',

  // Global settings
  use: {
    baseURL: 'http://localhost:1420',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  // Snapshot settings with cross-platform support
  expect: {
    toHaveScreenshot: {
      // Allow 1% pixel difference for anti-aliasing variations
      maxDiffPixelRatio: 0.01,
      // Anti-aliasing threshold
      threshold: 0.2,
      // Animation handling
      animations: 'disabled',
    },
  },

  // Cross-platform snapshot path template
  // Format: __snapshots__/{testFileName}/{platform}/{projectName}/{snapshotName}
  snapshotPathTemplate: '{snapshotDir}/{testFileName}/{arg}{-projectName}{-snapshotSuffix}{ext}',

  // Project configurations
  projects: [
    // =========================================================================
    // CHROMIUM PROJECTS
    // =========================================================================

    // Desktop Dark Mode - Chromium
    {
      name: 'desktop-dark',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
      },
    },

    // Desktop Light Mode - Chromium
    {
      name: 'desktop-light',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'light',
      },
    },

    // Tablet Dark Mode - Chromium
    {
      name: 'tablet-dark',
      use: {
        ...devices['iPad Pro 11'],
        colorScheme: 'dark',
      },
    },

    // Mobile Dark Mode - Chromium
    {
      name: 'mobile-dark',
      use: {
        ...devices['iPhone 14 Pro'],
        colorScheme: 'dark',
      },
    },

    // Reduced Motion - Chromium
    {
      name: 'reduced-motion',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
        // reducedMotion is set in test file via page.emulateMedia()
      },
    },

    // =========================================================================
    // WEBKIT PROJECTS (Safari Parity)
    // =========================================================================

    // Desktop Dark Mode - WebKit (Safari)
    {
      name: 'webkit-desktop-dark',
      use: {
        ...devices['Desktop Safari'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
      },
    },

    // Desktop Light Mode - WebKit (Safari)
    {
      name: 'webkit-desktop-light',
      use: {
        ...devices['Desktop Safari'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'light',
      },
    },

    // iPad - WebKit (Safari)
    {
      name: 'webkit-ipad',
      use: {
        ...devices['iPad Pro 11'],
        colorScheme: 'dark',
      },
    },

    // iPhone - WebKit (Safari)
    {
      name: 'webkit-iphone',
      use: {
        ...devices['iPhone 14 Pro'],
        colorScheme: 'dark',
      },
    },

    // =========================================================================
    // FIREFOX PROJECTS
    // =========================================================================

    // Desktop Dark Mode - Firefox
    {
      name: 'firefox-desktop-dark',
      use: {
        ...devices['Desktop Firefox'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
      },
    },

    // =========================================================================
    // RETINA/HiDPI PROJECTS
    // =========================================================================

    // Retina Desktop Dark Mode (2x DPI)
    {
      name: 'retina-desktop-dark',
      use: {
        ...devices['Desktop Chrome HiDPI'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
        deviceScaleFactor: 2,
      },
    },

    // Retina Desktop Light Mode (2x DPI)
    {
      name: 'retina-desktop-light',
      use: {
        ...devices['Desktop Chrome HiDPI'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'light',
        deviceScaleFactor: 2,
      },
    },

    // Retina Mobile (iPhone 14 Pro already has 3x)
    {
      name: 'retina-mobile-dark',
      use: {
        ...devices['iPhone 14 Pro'],
        colorScheme: 'dark',
        // iPhone 14 Pro has deviceScaleFactor: 3 by default
      },
    },

    // =========================================================================
    // ACCESSIBILITY PROJECTS
    // =========================================================================

    // High Contrast Mode
    {
      name: 'high-contrast',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 1440, height: 900 },
        colorScheme: 'dark',
        // forcedColors: 'active' for Windows High Contrast mode
      },
    },
  ],

  // Dev server configuration for Tauri app
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:1420',
    reuseExistingServer: !process.env.CI,
    timeout: 120000,
  },
});
