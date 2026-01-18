/**
 * E2E Video Recording Tests - Kagami Desktop Client
 *
 * Comprehensive end-to-end tests with full video recording support.
 * Records complete user journeys for visual documentation and debugging.
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * Usage:
 *   npx playwright test tests/e2e/video-recording.spec.ts --video=on
 *   npx playwright test tests/e2e/video-recording.spec.ts --project=desktop-dark --video=retain-on-failure
 *
 * h(x) >= 0. Always.
 */

import { test, expect, Page, TestInfo } from '@playwright/test';

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Enable video recording for all tests in this file
 */
test.use({
  video: 'on',
  viewport: { width: 1440, height: 900 },
  actionTimeout: 15000,
});

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Wait for page to be fully ready
 */
async function waitForAppReady(page: Page) {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
}

/**
 * Skip onboarding by setting localStorage
 */
async function skipOnboarding(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('hasCompletedOnboarding', 'true');
    localStorage.setItem('kagami-tour-completed', 'true');
    localStorage.setItem('kagami-welcome-shown', 'true');
  });
}

/**
 * Enable demo mode for testing
 */
async function enableDemoMode(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('isDemoMode', 'true');
  });
}

/**
 * Capture a labeled screenshot and attach to test results
 */
async function captureCheckpoint(
  page: Page,
  testInfo: TestInfo,
  name: string,
  description?: string
) {
  const screenshot = await page.screenshot({ fullPage: false });
  await testInfo.attach(`Checkpoint: ${name}`, {
    body: screenshot,
    contentType: 'image/png',
  });

  // Log checkpoint for video annotation reference
  console.log(`[CHECKPOINT] ${name}${description ? ` - ${description}` : ''}`);
}

/**
 * Capture page performance metrics
 */
async function captureMetrics(page: Page, testInfo: TestInfo) {
  const metrics = await page.metrics();
  const performance = await page.evaluate(() => {
    const timing = performance.timing;
    return {
      loadTime: timing.loadEventEnd - timing.navigationStart,
      domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
      firstPaint: performance.getEntriesByType('paint').find(e => e.name === 'first-paint')?.startTime || 0,
    };
  });

  await testInfo.attach('Performance Metrics', {
    body: JSON.stringify({ metrics, performance }, null, 2),
    contentType: 'application/json',
  });
}

// ═══════════════════════════════════════════════════════════════════════════
// ONBOARDING USER JOURNEY - VIDEO RECORDED
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Onboarding User Journey (Video)', () => {
  test('complete onboarding flow with video', async ({ page }, testInfo) => {
    // Clear state for fresh onboarding
    await page.goto('/onboarding.html');
    await page.evaluate(() => {
      localStorage.clear();
      sessionStorage.clear();
    });
    await page.reload();
    await waitForAppReady(page);

    // Step 1: Welcome Screen
    await captureCheckpoint(page, testInfo, 'Step1-Welcome', 'Initial welcome screen');
    await expect(page.locator('[data-step="1"]')).toHaveClass(/active/);
    await page.waitForTimeout(1000); // Pause for video clarity

    // Step 2: Navigate to Server Setup
    await page.click('[data-action="next"]');
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'Step2-Server', 'Server configuration screen');

    // Step 3: Enable Demo Mode
    await enableDemoMode(page);
    const serverInput = page.locator('#server-url');
    if (await serverInput.isVisible()) {
      await serverInput.fill('http://localhost:3000');
      await page.click('#connect-btn');
      await page.waitForTimeout(1000);
    }
    await captureCheckpoint(page, testInfo, 'Step2-DemoMode', 'Demo mode activated');

    // Step 4: Continue through screens
    await page.click('[data-action="next"]');
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'Step3-Integrations', 'Integration selection');

    await page.click('[data-action="next"]');
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'Step4-Rooms', 'Room configuration');

    await page.click('[data-action="next"]');
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'Step5-Permissions', 'Permissions screen');

    // Step 5: Complete setup
    const completeBtn = page.locator('#complete-setup-btn');
    if (await completeBtn.isVisible()) {
      await completeBtn.click();
      await page.waitForTimeout(500);
    }
    await captureCheckpoint(page, testInfo, 'Step6-Complete', 'Onboarding complete');

    // Capture final metrics
    await captureMetrics(page, testInfo);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// QUICK ENTRY USER JOURNEY - VIDEO RECORDED
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Quick Entry User Journey (Video)', () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
  });

  test('command execution flow with video', async ({ page }, testInfo) => {
    // Checkpoint: Initial state
    await captureCheckpoint(page, testInfo, 'QuickEntry-Start', 'Quick entry initial state');

    // Type a command
    const input = page.locator('#command-input');
    await input.fill('/');
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'QuickEntry-Slash', 'Command suggestions shown');

    // Select a suggestion
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(300);
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(300);
    await captureCheckpoint(page, testInfo, 'QuickEntry-Selection', 'Navigating suggestions');

    // Execute command
    await page.keyboard.press('Enter');
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'QuickEntry-Executed', 'Command executed');

    // Type a full command
    await input.fill('/lights 50');
    await page.waitForTimeout(300);
    await page.keyboard.press('Enter');
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'QuickEntry-LightsCommand', 'Lights command executed');

    // Capture metrics
    await captureMetrics(page, testInfo);
  });

  test('mode switching with video', async ({ page }, testInfo) => {
    await captureCheckpoint(page, testInfo, 'ModeSwitching-Start', 'Initial ask mode');

    // Click act mode
    const actPill = page.locator('[data-mode="act"]');
    await actPill.click();
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'ModeSwitching-ActMode', 'Switched to act mode');

    // Click ask mode
    const askPill = page.locator('[data-mode="ask"]');
    await askPill.click();
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'ModeSwitching-AskMode', 'Switched back to ask mode');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DASHBOARD USER JOURNEY - VIDEO RECORDED
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Dashboard User Journey (Video)', () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);
  });

  test('dashboard exploration with video', async ({ page }, testInfo) => {
    await captureCheckpoint(page, testInfo, 'Dashboard-Start', 'Dashboard initial state');

    // Explore room cards
    const roomCards = page.locator('.room-card, .prism-card');
    const cardCount = await roomCards.count();

    if (cardCount > 0) {
      // Hover over first card
      await roomCards.first().hover();
      await page.waitForTimeout(500);
      await captureCheckpoint(page, testInfo, 'Dashboard-CardHover', 'Hovering over room card');

      // Click card
      await roomCards.first().click();
      await page.waitForTimeout(500);
      await captureCheckpoint(page, testInfo, 'Dashboard-CardClick', 'Room card clicked');
    }

    // Try light control
    const lightControl = page.locator('[data-control="lights"]').first();
    if (await lightControl.isVisible()) {
      await lightControl.click();
      await page.waitForTimeout(500);
      await captureCheckpoint(page, testInfo, 'Dashboard-LightToggle', 'Light control toggled');
    }

    // Try scene button
    const sceneBtn = page.locator('[data-scene]').first();
    if (await sceneBtn.isVisible()) {
      await sceneBtn.click();
      await page.waitForTimeout(500);
      await captureCheckpoint(page, testInfo, 'Dashboard-SceneActivated', 'Scene activated');
    }

    await captureMetrics(page, testInfo);
  });

  test('settings modal with video', async ({ page }, testInfo) => {
    await captureCheckpoint(page, testInfo, 'Settings-Start', 'Before opening settings');

    const settingsBtn = page.locator('[data-action="settings"], .settings-btn').first();
    if (await settingsBtn.isVisible()) {
      await settingsBtn.click();
      await page.waitForTimeout(500);
      await captureCheckpoint(page, testInfo, 'Settings-ModalOpen', 'Settings modal open');

      // Close modal
      const closeBtn = page.locator('.prism-modal .close-btn, [data-action="close"]').first();
      if (await closeBtn.isVisible()) {
        await closeBtn.click();
        await page.waitForTimeout(500);
        await captureCheckpoint(page, testInfo, 'Settings-ModalClosed', 'Settings modal closed');
      }
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// ACCESSIBILITY USER JOURNEY - VIDEO RECORDED
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Accessibility User Journey (Video)', () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
  });

  test('keyboard navigation with video', async ({ page }, testInfo) => {
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);

    await captureCheckpoint(page, testInfo, 'Keyboard-Start', 'Starting keyboard navigation');

    // Tab through elements
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press('Tab');
      await page.waitForTimeout(300);
      await captureCheckpoint(page, testInfo, `Keyboard-Tab${i + 1}`, `Tab press ${i + 1}`);
    }

    // Shift-Tab back
    await page.keyboard.press('Shift+Tab');
    await page.waitForTimeout(300);
    await captureCheckpoint(page, testInfo, 'Keyboard-ShiftTab', 'Shift+Tab navigation');
  });

  test('reduced motion mode with video', async ({ page }, testInfo) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await waitForAppReady(page);

    await captureCheckpoint(page, testInfo, 'ReducedMotion-Dashboard', 'Dashboard with reduced motion');

    // Interact with elements
    const button = page.locator('.prism-btn').first();
    if (await button.isVisible()) {
      await button.hover();
      await page.waitForTimeout(300);
      await captureCheckpoint(page, testInfo, 'ReducedMotion-Hover', 'Button hover with reduced motion');
    }
  });

  test('high contrast mode with video', async ({ page }, testInfo) => {
    // Force high contrast via CSS
    await page.goto('/');
    await page.addStyleTag({
      content: `
        :root {
          --prism-contrast: 1.5;
          filter: contrast(1.2);
        }
      `,
    });
    await waitForAppReady(page);

    await captureCheckpoint(page, testInfo, 'HighContrast-Dashboard', 'Dashboard with high contrast');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// ERROR HANDLING USER JOURNEY - VIDEO RECORDED
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Error Handling User Journey (Video)', () => {
  test('network error recovery with video', async ({ page }, testInfo) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    await captureCheckpoint(page, testInfo, 'Error-NormalState', 'Normal connected state');

    // Simulate offline
    await page.context().setOffline(true);
    await page.waitForTimeout(1000);
    await captureCheckpoint(page, testInfo, 'Error-Offline', 'Offline state');

    // Try to interact
    const button = page.locator('.prism-btn').first();
    if (await button.isVisible()) {
      await button.click();
      await page.waitForTimeout(500);
      await captureCheckpoint(page, testInfo, 'Error-OfflineAction', 'Action while offline');
    }

    // Restore connection
    await page.context().setOffline(false);
    await page.waitForTimeout(1000);
    await captureCheckpoint(page, testInfo, 'Error-Recovered', 'Connection recovered');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// THEME SWITCHING USER JOURNEY - VIDEO RECORDED
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Theme Switching User Journey (Video)', () => {
  test('dark to light mode switch with video', async ({ page }, testInfo) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');

    // Start in dark mode
    await page.emulateMedia({ colorScheme: 'dark' });
    await waitForAppReady(page);
    await captureCheckpoint(page, testInfo, 'Theme-DarkMode', 'Dashboard in dark mode');

    // Switch to light mode
    await page.emulateMedia({ colorScheme: 'light' });
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'Theme-LightMode', 'Dashboard in light mode');

    // Switch back
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.waitForTimeout(500);
    await captureCheckpoint(page, testInfo, 'Theme-BackToDark', 'Dashboard back to dark mode');
  });
});

/*
 * Crystal verifies. Crystal polishes. Crystal ensures quality.
 * h(x) >= 0. Always.
 */
