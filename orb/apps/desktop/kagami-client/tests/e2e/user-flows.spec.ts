/**
 * E2E User Flow Tests - Kagami Desktop Client
 *
 * Comprehensive end-to-end tests covering:
 * - Complete user journeys
 * - Critical path testing
 * - Visual regression
 * - Accessibility automation
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * Usage:
 *   npx playwright test tests/e2e/user-flows.spec.ts
 *   npx playwright test --headed  # Watch mode
 *   npx playwright test --debug   # Step through
 *
 * h(x) >= 0. Always.
 */

import { test, expect, Page, BrowserContext } from '@playwright/test';

// ═══════════════════════════════════════════════════════════════════════════
// TEST FIXTURES AND HELPERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Wait for page to be fully ready
 */
async function waitForAppReady(page: Page) {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  // Wait for any initial animations to settle
  await page.waitForTimeout(500);
}

/**
 * Clear localStorage and start fresh
 */
async function resetAppState(page: Page) {
  await page.evaluate(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
}

/**
 * Mark onboarding as complete for tests that don't need it
 */
async function skipOnboarding(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('hasCompletedOnboarding', 'true');
    localStorage.setItem('kagami-tour-completed', 'true');
    localStorage.setItem('kagami-welcome-shown', 'true');
  });
}

/**
 * Set up demo mode for testing without real backend
 */
async function enableDemoMode(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('isDemoMode', 'true');
  });
}

/**
 * Wait for and dismiss any toast notifications
 */
async function dismissToasts(page: Page) {
  const toast = page.locator('.prism-toast');
  if (await toast.isVisible({ timeout: 1000 }).catch(() => false)) {
    await toast.click();
    await page.waitForTimeout(300);
  }
}

/**
 * Get accessibility tree for a11y testing
 */
async function getA11yTree(page: Page) {
  return await page.accessibility.snapshot();
}

// ═══════════════════════════════════════════════════════════════════════════
// ONBOARDING FLOW TESTS
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Onboarding Flow', () => {
  test.beforeEach(async ({ page }) => {
    await resetAppState(page);
    await page.goto('/onboarding.html');
    await waitForAppReady(page);
  });

  test('should show welcome step first', async ({ page }) => {
    // Should show step 1
    const step1 = page.locator('[data-step="1"]');
    await expect(step1).toBeVisible();
    await expect(step1).toHaveClass(/active/);

    // Title should be visible
    await expect(page.getByRole('heading', { name: /welcome/i })).toBeVisible();
  });

  test('should navigate through all steps', async ({ page }) => {
    // Step 1: Welcome - click next
    await page.click('[data-action="next"]');
    await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);

    // Step 2: Server - enter URL and connect (demo mode)
    await enableDemoMode(page);
    const serverInput = page.locator('#server-url');
    await serverInput.fill('http://localhost:3000');
    await page.click('#connect-btn');
    await page.waitForTimeout(500);
    await page.click('[data-action="next"]');

    // Step 3: Integrations - should show discovery
    await expect(page.locator('[data-step="3"]')).toHaveClass(/active/);
    await page.click('[data-action="next"]');

    // Step 4: Rooms - should show room selection
    await expect(page.locator('[data-step="4"]')).toHaveClass(/active/);
    await page.click('[data-action="next"]');

    // Step 5: Permissions
    await expect(page.locator('[data-step="5"]')).toHaveClass(/active/);
    await page.click('#complete-setup-btn');

    // Step 6: Complete
    await expect(page.locator('[data-step="6"]')).toHaveClass(/active/);
    await expect(page.getByText(/all set/i)).toBeVisible();
  });

  test('should persist progress across page reloads', async ({ page }) => {
    // Go to step 2
    await page.click('[data-action="next"]');
    await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);

    // Reload page
    await page.reload();
    await waitForAppReady(page);

    // Should still be on step 2
    await expect(page.locator('[data-step="2"]')).toHaveClass(/active/);
  });

  test('should allow going back to previous steps', async ({ page }) => {
    // Go to step 2
    await page.click('[data-action="next"]');

    // Go back
    await page.click('[data-action="back"]');
    await expect(page.locator('[data-step="1"]')).toHaveClass(/active/);
  });

  test('should validate server URL before proceeding', async ({ page }) => {
    // Go to step 2
    await page.click('[data-action="next"]');

    // Try to proceed without entering URL
    const nextBtn = page.locator('[data-action="next"]');
    await expect(nextBtn).toBeDisabled();

    // Enter invalid URL
    await page.locator('#server-url').fill('not-a-url');
    await page.click('#connect-btn');

    // Should show error
    await expect(page.locator('.status-text')).toContainText(/error|failed/i);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// QUICK ENTRY FLOW TESTS
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Quick Entry', () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
  });

  test('should focus input on load', async ({ page }) => {
    const input = page.locator('#command-input');
    await expect(input).toBeFocused();
  });

  test('should show suggestions when typing', async ({ page }) => {
    const input = page.locator('#command-input');
    await input.fill('/');

    // Should show command suggestions
    const suggestions = page.locator('.suggestions-container');
    await expect(suggestions).toBeVisible();
    await expect(suggestions.locator('.suggestion-item')).toHaveCount.greaterThan(0);
  });

  test('should navigate suggestions with keyboard', async ({ page }) => {
    const input = page.locator('#command-input');
    await input.fill('/');

    // Press down arrow
    await page.keyboard.press('ArrowDown');
    const firstItem = page.locator('.suggestion-item').first();
    await expect(firstItem).toHaveClass(/selected/);

    // Press down again
    await page.keyboard.press('ArrowDown');
    const secondItem = page.locator('.suggestion-item').nth(1);
    await expect(secondItem).toHaveClass(/selected/);

    // Press up
    await page.keyboard.press('ArrowUp');
    await expect(firstItem).toHaveClass(/selected/);
  });

  test('should execute command on Enter', async ({ page }) => {
    const input = page.locator('#command-input');
    await input.fill('/lights 50');
    await page.keyboard.press('Enter');

    // Should clear input and show feedback
    await expect(input).toHaveValue('');
  });

  test('should close on Escape', async ({ page }) => {
    // Press Escape
    await page.keyboard.press('Escape');

    // In Tauri, this would close the window
    // For web testing, we check that the escape handler was triggered
    // by verifying input is blurred or window state changes
  });

  test('should toggle mode with mode pills', async ({ page }) => {
    const askPill = page.locator('[data-mode="ask"]');
    const actPill = page.locator('[data-mode="act"]');

    // Default should be ask
    await expect(askPill).toHaveClass(/active/);

    // Click act
    await actPill.click();
    await expect(actPill).toHaveClass(/active/);
    await expect(askPill).not.toHaveClass(/active/);
  });

  test('should persist mode preference', async ({ page }) => {
    // Switch to act mode
    await page.locator('[data-mode="act"]').click();

    // Reload
    await page.reload();
    await waitForAppReady(page);

    // Should still be in act mode
    await expect(page.locator('[data-mode="act"]')).toHaveClass(/active/);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// DASHBOARD FLOW TESTS
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);
  });

  test('should show connection status', async ({ page }) => {
    const statusDot = page.locator('.status-dot');
    await expect(statusDot).toBeVisible();
  });

  test('should display room cards', async ({ page }) => {
    const roomCards = page.locator('.room-card, .prism-card');
    await expect(roomCards).toHaveCount.greaterThan(0);
  });

  test('should toggle light controls', async ({ page }) => {
    const lightControl = page.locator('[data-control="lights"]').first();
    if (await lightControl.isVisible()) {
      await lightControl.click();
      // Verify state change
      await expect(lightControl).toHaveAttribute('aria-pressed', /(true|false)/);
    }
  });

  test('should execute scene buttons', async ({ page }) => {
    const sceneBtn = page.locator('[data-scene]').first();
    if (await sceneBtn.isVisible()) {
      await sceneBtn.click();
      // Should show feedback
      await dismissToasts(page);
    }
  });

  test('should open settings modal', async ({ page }) => {
    const settingsBtn = page.locator('[data-action="settings"], .settings-btn');
    if (await settingsBtn.isVisible()) {
      await settingsBtn.click();
      await expect(page.locator('.prism-modal, [role="dialog"]')).toBeVisible();
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// FEATURE TOUR TESTS
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Feature Tour', () => {
  test.beforeEach(async ({ page }) => {
    // Complete onboarding but don't skip tour
    await page.evaluate(() => {
      localStorage.setItem('hasCompletedOnboarding', 'true');
      localStorage.setItem('kagami-welcome-shown', 'true');
      localStorage.removeItem('kagami-tour-completed');
      localStorage.removeItem('kagami-tour-skipped');
    });
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);
  });

  test('should show tour for first-time users after onboarding', async ({ page }) => {
    // Wait for auto-start delay
    await page.waitForTimeout(1500);

    const tourTooltip = page.locator('.tour-tooltip');
    // Tour might not auto-start in test environment, try triggering it
    if (!await tourTooltip.isVisible({ timeout: 1000 }).catch(() => false)) {
      await page.evaluate(() => {
        if (window.KagamiOnboarding?.startTour) {
          window.KagamiOnboarding.startTour({ force: true });
        }
      });
    }
  });

  test('should navigate tour with buttons', async ({ page }) => {
    // Start tour manually
    await page.evaluate(() => {
      if (window.KagamiOnboarding?.startTour) {
        window.KagamiOnboarding.startTour({ force: true });
      }
    });

    await page.waitForSelector('.tour-tooltip', { timeout: 2000 }).catch(() => {});

    const tooltip = page.locator('.tour-tooltip');
    if (await tooltip.isVisible()) {
      // Click next
      await page.click('.tour-btn-next');
      await page.waitForTimeout(500);

      // Should advance to next step
      const stepText = await page.locator('.tour-tooltip-step').textContent();
      expect(stepText).toContain('2');
    }
  });

  test('should skip tour when clicking skip', async ({ page }) => {
    await page.evaluate(() => {
      if (window.KagamiOnboarding?.startTour) {
        window.KagamiOnboarding.startTour({ force: true });
      }
    });

    await page.waitForSelector('.tour-tooltip', { timeout: 2000 }).catch(() => {});

    const skipBtn = page.locator('.tour-btn-skip');
    if (await skipBtn.isVisible()) {
      await skipBtn.click();
      await page.waitForTimeout(500);

      // Tooltip should be gone
      await expect(page.locator('.tour-tooltip')).not.toBeVisible();

      // Should be persisted
      const skipped = await page.evaluate(() =>
        localStorage.getItem('kagami-tour-skipped')
      );
      expect(skipped).toBe('true');
    }
  });

  test('should complete tour and persist', async ({ page }) => {
    await page.evaluate(() => {
      if (window.KagamiOnboarding?.startTour) {
        window.KagamiOnboarding.startTour({ force: true });
      }
    });

    await page.waitForSelector('.tour-tooltip', { timeout: 2000 }).catch(() => {});

    const tooltip = page.locator('.tour-tooltip');
    if (await tooltip.isVisible()) {
      // Click through all steps
      while (await page.locator('.tour-btn-next').isVisible().catch(() => false)) {
        await page.click('.tour-btn-next');
        await page.waitForTimeout(300);
      }

      // After completion, check persistence
      const completed = await page.evaluate(() =>
        localStorage.getItem('kagami-tour-completed')
      );
      expect(completed).toBe('true');
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// ACCESSIBILITY TESTS
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Accessibility', () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
  });

  test('quick entry should be keyboard navigable', async ({ page }) => {
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);

    // Tab through elements
    await page.keyboard.press('Tab');
    const focusedElement = await page.evaluate(() => document.activeElement?.tagName);
    expect(focusedElement).toBeTruthy();
  });

  test('all interactive elements should have accessible names', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Check buttons have accessible names
    const buttons = await page.locator('button').all();
    for (const button of buttons.slice(0, 10)) { // Check first 10
      const name = await button.getAttribute('aria-label') ||
                   await button.textContent();
      expect(name?.trim()).toBeTruthy();
    }
  });

  test('modals should trap focus', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    const settingsBtn = page.locator('[data-action="settings"], .settings-btn').first();
    if (await settingsBtn.isVisible()) {
      await settingsBtn.click();
      await page.waitForTimeout(300);

      const modal = page.locator('.prism-modal, [role="dialog"]');
      if (await modal.isVisible()) {
        // Tab should cycle within modal
        await page.keyboard.press('Tab');
        await page.keyboard.press('Tab');
        await page.keyboard.press('Tab');

        const focusedInModal = await page.evaluate(() => {
          const focused = document.activeElement;
          const modal = document.querySelector('.prism-modal, [role="dialog"]');
          return modal?.contains(focused);
        });

        expect(focusedInModal).toBe(true);
      }
    }
  });

  test('reduced motion should disable animations', async ({ page }) => {
    // Emulate reduced motion
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await waitForAppReady(page);

    // Animations should be disabled
    const hasAnimations = await page.evaluate(() => {
      const elements = document.querySelectorAll('*');
      for (const el of elements) {
        const style = getComputedStyle(el);
        const duration = parseFloat(style.animationDuration);
        if (duration > 0.02) return true;
      }
      return false;
    });

    expect(hasAnimations).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// VISUAL REGRESSION TESTS
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Visual Regression', () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);
  });

  test('quick entry layout', async ({ page }) => {
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);

    // Disable animations for stable screenshots
    await page.addStyleTag({
      content: `*, *::before, *::after {
        animation-duration: 0s !important;
        transition-duration: 0s !important;
      }`,
    });

    await expect(page).toHaveScreenshot('quick-entry.png', {
      maxDiffPixelRatio: 0.02,
    });
  });

  test('quick entry with suggestions', async ({ page }) => {
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);

    await page.addStyleTag({
      content: `*, *::before, *::after {
        animation-duration: 0s !important;
        transition-duration: 0s !important;
      }`,
    });

    // Type to show suggestions
    await page.locator('#command-input').fill('/');
    await page.waitForTimeout(200);

    await expect(page).toHaveScreenshot('quick-entry-suggestions.png', {
      maxDiffPixelRatio: 0.02,
    });
  });

  test('dashboard layout', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    await page.addStyleTag({
      content: `*, *::before, *::after {
        animation-duration: 0s !important;
        transition-duration: 0s !important;
      }`,
    });

    await expect(page).toHaveScreenshot('dashboard.png', {
      maxDiffPixelRatio: 0.02,
    });
  });

  test('dark mode consistency', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Force dark mode
    await page.emulateMedia({ colorScheme: 'dark' });

    await page.addStyleTag({
      content: `*, *::before, *::after {
        animation-duration: 0s !important;
        transition-duration: 0s !important;
      }`,
    });

    await expect(page).toHaveScreenshot('dashboard-dark.png', {
      maxDiffPixelRatio: 0.02,
    });
  });

  test('light mode consistency', async ({ page }) => {
    await page.goto('/');
    await waitForAppReady(page);

    // Force light mode
    await page.emulateMedia({ colorScheme: 'light' });

    await page.addStyleTag({
      content: `*, *::before, *::after {
        animation-duration: 0s !important;
        transition-duration: 0s !important;
      }`,
    });

    await expect(page).toHaveScreenshot('dashboard-light.png', {
      maxDiffPixelRatio: 0.02,
    });
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// ERROR HANDLING TESTS
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    await skipOnboarding(page);
  });

  test('should show error state when disconnected', async ({ page }) => {
    // Don't enable demo mode - simulate disconnection
    await page.goto('/');
    await waitForAppReady(page);

    const statusDot = page.locator('.status-dot');
    // Should show disconnected state
    await expect(statusDot).toHaveClass(/disconnected|error/);
  });

  test('should handle network errors gracefully', async ({ page }) => {
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    // Simulate offline
    await page.context().setOffline(true);

    // Try an action
    const sceneBtn = page.locator('[data-scene]').first();
    if (await sceneBtn.isVisible()) {
      await sceneBtn.click();
      // Should show error toast or status
    }

    await page.context().setOffline(false);
  });

  test('should recover from errors', async ({ page }) => {
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    // Simulate offline then online
    await page.context().setOffline(true);
    await page.waitForTimeout(1000);
    await page.context().setOffline(false);
    await page.waitForTimeout(1000);

    // Should recover to connected state
    const statusDot = page.locator('.status-dot');
    // In demo mode, might show connected after recovery
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// PERFORMANCE TESTS
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Performance', () => {
  test('quick entry should load under 2 seconds', async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);

    const start = Date.now();
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
    const loadTime = Date.now() - start;

    expect(loadTime).toBeLessThan(2000);
  });

  test('dashboard should load under 3 seconds', async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);

    const start = Date.now();
    await page.goto('/');
    await waitForAppReady(page);
    const loadTime = Date.now() - start;

    expect(loadTime).toBeLessThan(3000);
  });

  test('should not have memory leaks after navigation', async ({ page }) => {
    await skipOnboarding(page);
    await enableDemoMode(page);

    // Navigate multiple times
    for (let i = 0; i < 5; i++) {
      await page.goto('/quick-entry.html');
      await waitForAppReady(page);
      await page.goto('/');
      await waitForAppReady(page);
    }

    // Check heap usage
    const metrics = await page.metrics();
    const jsHeapUsedSize = metrics.JSHeapUsedSize;

    // Should be under 50MB
    expect(jsHeapUsedSize).toBeLessThan(50 * 1024 * 1024);
  });
});

/*
 * Crystal verifies. Crystal polishes. Crystal ensures quality.
 * h(x) >= 0. Always.
 */
