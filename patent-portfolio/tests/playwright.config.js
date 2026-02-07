/**
 * Playwright Configuration
 * ========================
 * 
 * Testing configuration for visual regression, interaction, and XR simulation tests.
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
    testDir: './',
    timeout: 120000,  // 2 minutes per test (WebGL 3D scenes take time)
    expect: {
        timeout: 10000,
        toHaveScreenshot: {
            maxDiffPixelRatio: 0.02
        }
    },
    fullyParallel: false,  // Run sequentially for 3D scene stability
    forbidOnly: !!process.env.CI,
    retries: 0,  // No retries for faster local testing
    workers: process.env.CI ? 1 : undefined,
    reporter: 'html',
    use: {
        baseURL: 'http://localhost:9000',  // Use free port
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
        headless: false  // Run headed for WebGL support
    },
    projects: [
        {
            name: 'chromium',
            use: { 
                ...devices['Desktop Chrome'],
                // Standard Chrome settings - no SwiftShader (too slow)
                launchOptions: {
                    args: ['--no-sandbox']
                }
            }
        },
        {
            name: 'chromium-webgl',
            // WebGL tests - slower, for manual verification
            use: { 
                ...devices['Desktop Chrome'],
                launchOptions: {
                    headless: false,  // Must be headed for WebGL
                    args: [
                        '--no-sandbox',
                        '--enable-webgl',
                        '--ignore-gpu-blocklist'
                    ]
                }
            }
        },
        {
            name: 'firefox',
            use: { ...devices['Desktop Firefox'] }
        },
        {
            name: 'webkit',
            use: { ...devices['Desktop Safari'] }
        }
    ],
    webServer: {
        command: 'python3 -m http.server 9000',
        cwd: '..',
        port: 9000,
        timeout: 60000,
        reuseExistingServer: true
    }
});
