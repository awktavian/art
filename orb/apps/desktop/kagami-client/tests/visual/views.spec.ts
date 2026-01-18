/**
 * Visual Regression Tests - Major Views
 *
 * Comprehensive screenshot testing for all major application views.
 * Covers: Dashboard, Login, Settings, Onboarding, Quick Entry, and Documentation.
 *
 * Usage:
 *   npx playwright test tests/visual/views.spec.ts
 *   npx playwright test tests/visual/views.spec.ts --update-snapshots
 *
 * Colony: Crystal (e7) - Verification & Polish
 */

import { test, expect, Page } from '@playwright/test';

// =============================================================================
// TEST HELPERS
// =============================================================================

/**
 * Wait for page to be fully loaded and stable
 */
async function waitForPageReady(page: Page) {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  // Wait for CSS animations to settle
  await page.waitForTimeout(200);
}

/**
 * Disable all animations for stable screenshots
 */
async function disableAnimations(page: Page) {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
      }
      .breath-layer, .particle, #particles {
        display: none !important;
      }
    `,
  });
}

/**
 * Mock network requests to prevent flaky tests
 */
async function mockNetworkRequests(page: Page) {
  await page.route('**/api/**', (route) => {
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ status: 'ok', data: {} }),
    });
  });
}

// =============================================================================
// DASHBOARD VIEW TESTS
// =============================================================================

test.describe('Dashboard View', () => {
  test.beforeEach(async ({ page }) => {
    await mockNetworkRequests(page);
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  test('full page - initial state', async ({ page }) => {
    await expect(page).toHaveScreenshot('dashboard-full.png', {
      fullPage: true,
    });
  });

  test('hero section', async ({ page }) => {
    const hero = page.locator('.hero').first();
    await expect(hero).toHaveScreenshot('dashboard-hero.png');
  });

  test('status grid', async ({ page }) => {
    const statusGrid = page.locator('.status-grid').first();
    await expect(statusGrid).toHaveScreenshot('dashboard-status-grid.png');
  });

  test('stat card - hover state', async ({ page }) => {
    const statCard = page.locator('.stat-card').first();
    await statCard.hover();
    await page.waitForTimeout(100);
    await expect(statCard).toHaveScreenshot('dashboard-stat-card-hover.png');
  });

  test('hero action button', async ({ page }) => {
    const heroButton = page.locator('.hero-action-btn');
    await expect(heroButton).toHaveScreenshot('dashboard-hero-action.png');
  });

  test('hero action button - hover', async ({ page }) => {
    const heroButton = page.locator('.hero-action-btn');
    await heroButton.hover();
    await page.waitForTimeout(100);
    await expect(heroButton).toHaveScreenshot('dashboard-hero-action-hover.png');
  });

  test('offline banner', async ({ page }) => {
    // Show the offline banner
    await page.evaluate(() => {
      const banner = document.getElementById('offline-banner');
      if (banner) banner.style.display = 'flex';
    });
    const banner = page.locator('#offline-banner');
    await expect(banner).toHaveScreenshot('dashboard-offline-banner.png');
  });
});

// =============================================================================
// LOGIN VIEW TESTS
// =============================================================================

test.describe('Login View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login.html');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  test('full page', async ({ page }) => {
    await expect(page).toHaveScreenshot('login-full.png', {
      fullPage: true,
    });
  });

  test('login card', async ({ page }) => {
    const loginCard = page.locator('.login-card');
    await expect(loginCard).toHaveScreenshot('login-card.png');
  });

  test('input field - empty', async ({ page }) => {
    const input = page.locator('input[type="text"], input[type="email"]').first();
    const container = input.locator('..').locator('..');
    await expect(container).toHaveScreenshot('login-input-empty.png');
  });

  test('input field - focused', async ({ page }) => {
    const input = page.locator('input[type="text"], input[type="email"]').first();
    await input.focus();
    await page.waitForTimeout(100);
    const container = input.locator('..').locator('..');
    await expect(container).toHaveScreenshot('login-input-focused.png');
  });

  test('input field - with value', async ({ page }) => {
    const input = page.locator('input[type="text"], input[type="email"]').first();
    await input.fill('tim@example.com');
    const container = input.locator('..').locator('..');
    await expect(container).toHaveScreenshot('login-input-filled.png');
  });

  test('submit button', async ({ page }) => {
    const button = page.locator('button[type="submit"], .login-btn, .prism-btn').first();
    await expect(button).toHaveScreenshot('login-button.png');
  });

  test('submit button - hover', async ({ page }) => {
    const button = page.locator('button[type="submit"], .login-btn, .prism-btn').first();
    await button.hover();
    await page.waitForTimeout(100);
    await expect(button).toHaveScreenshot('login-button-hover.png');
  });
});

// =============================================================================
// SETTINGS VIEW TESTS
// =============================================================================

test.describe('Settings View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings.html');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  test('full page', async ({ page }) => {
    await expect(page).toHaveScreenshot('settings-full.png', {
      fullPage: true,
    });
  });

  test('header', async ({ page }) => {
    const header = page.locator('.header, .settings-header').first();
    await expect(header).toHaveScreenshot('settings-header.png');
  });

  test('section', async ({ page }) => {
    const section = page.locator('.section').first();
    await expect(section).toHaveScreenshot('settings-section.png');
  });

  test('toggle switch', async ({ page }) => {
    const toggle = page.locator('.toggle, .switch, input[type="checkbox"]').first();
    if (await toggle.count() > 0) {
      const container = toggle.locator('..');
      await expect(container).toHaveScreenshot('settings-toggle.png');
    }
  });

  test('select dropdown', async ({ page }) => {
    const select = page.locator('select, .select').first();
    if (await select.count() > 0) {
      await expect(select).toHaveScreenshot('settings-select.png');
    }
  });
});

// =============================================================================
// ONBOARDING VIEW TESTS
// =============================================================================

test.describe('Onboarding View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/onboarding.html');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  test('full page - step 1', async ({ page }) => {
    await expect(page).toHaveScreenshot('onboarding-full.png', {
      fullPage: true,
    });
  });

  test('welcome content', async ({ page }) => {
    const content = page.locator('.onboarding-content, .welcome-content, main').first();
    await expect(content).toHaveScreenshot('onboarding-content.png');
  });

  test('progress indicator', async ({ page }) => {
    const progress = page.locator('.progress, .steps, .pagination').first();
    if (await progress.count() > 0) {
      await expect(progress).toHaveScreenshot('onboarding-progress.png');
    }
  });

  test('navigation buttons', async ({ page }) => {
    const nav = page.locator('.onboarding-nav, .button-group, .actions').first();
    if (await nav.count() > 0) {
      await expect(nav).toHaveScreenshot('onboarding-nav.png');
    }
  });
});

// =============================================================================
// QUICK ENTRY VIEW TESTS
// =============================================================================

test.describe('Quick Entry View', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/quick-entry.html');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  test('full page', async ({ page }) => {
    await expect(page).toHaveScreenshot('quick-entry-full.png', {
      fullPage: true,
    });
  });

  test('command input', async ({ page }) => {
    const input = page.locator('input, textarea, .command-input').first();
    if (await input.count() > 0) {
      await expect(input).toHaveScreenshot('quick-entry-input.png');
    }
  });

  test('command input - focused', async ({ page }) => {
    const input = page.locator('input, textarea, .command-input').first();
    if (await input.count() > 0) {
      await input.focus();
      await page.waitForTimeout(100);
      await expect(input).toHaveScreenshot('quick-entry-input-focused.png');
    }
  });

  test('suggestions list', async ({ page }) => {
    const suggestions = page.locator('.suggestions, .autocomplete, .dropdown').first();
    if (await suggestions.count() > 0) {
      await expect(suggestions).toHaveScreenshot('quick-entry-suggestions.png');
    }
  });
});

// =============================================================================
// DOCUMENTATION SHOWCASE TESTS
// =============================================================================

test.describe('Documentation Showcase', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/docs/showcase.html');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  test('full page', async ({ page }) => {
    await expect(page).toHaveScreenshot('docs-showcase-full.png', {
      fullPage: true,
    });
  });

  test('component grid', async ({ page }) => {
    const grid = page.locator('.component-grid, .showcase-grid, .grid').first();
    if (await grid.count() > 0) {
      await expect(grid).toHaveScreenshot('docs-component-grid.png');
    }
  });
});

// =============================================================================
// COMPONENT DOCUMENTATION TESTS
// =============================================================================

test.describe('Component Documentation', () => {
  test('buttons page', async ({ page }) => {
    await page.goto('/docs/components/button.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('docs-buttons.png', {
      fullPage: true,
    });
  });

  test('cards page', async ({ page }) => {
    await page.goto('/docs/components/card.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('docs-cards.png', {
      fullPage: true,
    });
  });

  test('inputs page', async ({ page }) => {
    await page.goto('/docs/components/input.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('docs-inputs.png', {
      fullPage: true,
    });
  });

  test('dialogs page', async ({ page }) => {
    await page.goto('/docs/components/dialog.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('docs-dialogs.png', {
      fullPage: true,
    });
  });

  test('colors page', async ({ page }) => {
    await page.goto('/docs/foundations/colors.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('docs-colors.png', {
      fullPage: true,
    });
  });
});

// =============================================================================
// PRISMORPHISM DEMO TESTS
// =============================================================================

test.describe('Prismorphism Demo', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/prismorphism-demo.html');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  test('full page', async ({ page }) => {
    await expect(page).toHaveScreenshot('prismorphism-demo-full.png', {
      fullPage: true,
    });
  });

  test('glass effects section', async ({ page }) => {
    const section = page.locator('[data-section="glass"], .glass-section').first();
    if (await section.count() > 0) {
      await expect(section).toHaveScreenshot('prismorphism-glass.png');
    }
  });

  test('spectral effects section', async ({ page }) => {
    const section = page.locator('[data-section="spectral"], .spectral-section').first();
    if (await section.count() > 0) {
      await expect(section).toHaveScreenshot('prismorphism-spectral.png');
    }
  });
});

// =============================================================================
// RESPONSIVE VIEW TESTS
// =============================================================================

test.describe('Responsive Views', () => {
  test('dashboard - mobile portrait', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('responsive-dashboard-mobile.png', {
      fullPage: true,
    });
  });

  test('dashboard - mobile landscape', async ({ page }) => {
    await page.setViewportSize({ width: 812, height: 375 });
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('responsive-dashboard-mobile-landscape.png', {
      fullPage: false,
    });
  });

  test('dashboard - tablet portrait', async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('responsive-dashboard-tablet.png', {
      fullPage: true,
    });
  });

  test('login - mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/login.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('responsive-login-mobile.png', {
      fullPage: true,
    });
  });

  test('settings - mobile', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/settings.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('responsive-settings-mobile.png', {
      fullPage: true,
    });
  });
});

// =============================================================================
// THEME VARIATION TESTS
// =============================================================================

test.describe('Theme Variations', () => {
  test('dashboard - light mode', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('theme-dashboard-light.png', {
      fullPage: true,
    });
  });

  test('login - light mode', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/login.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('theme-login-light.png', {
      fullPage: true,
    });
  });

  test('settings - light mode', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/settings.html');
    await waitForPageReady(page);
    await disableAnimations(page);
    await expect(page).toHaveScreenshot('theme-settings-light.png', {
      fullPage: true,
    });
  });
});

// =============================================================================
// ACCESSIBILITY VISUAL TESTS
// =============================================================================

test.describe('Accessibility Visuals', () => {
  test('reduced motion - dashboard', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await waitForPageReady(page);
    await expect(page).toHaveScreenshot('a11y-reduced-motion-dashboard.png', {
      fullPage: true,
    });
  });

  test('keyboard focus - dashboard buttons', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);

    // Tab to first focusable element
    await page.keyboard.press('Tab');
    await page.keyboard.press('Tab');
    await page.waitForTimeout(100);

    // Screenshot with focus ring visible
    await expect(page).toHaveScreenshot('a11y-focus-visible.png', {
      fullPage: false,
    });
  });

  test('high contrast - dashboard', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);

    // Add high contrast styles
    await page.addStyleTag({
      content: `
        :root {
          --void: #000000 !important;
          --text: #ffffff !important;
          --crystal: #00ffff !important;
          --grove: #00ff00 !important;
          --beacon: #ffff00 !important;
          --spark: #ff0000 !important;
        }
        * {
          border-color: currentColor !important;
        }
      `,
    });

    await expect(page).toHaveScreenshot('a11y-high-contrast.png', {
      fullPage: true,
    });
  });
});

// =============================================================================
// ERROR STATE TESTS
// =============================================================================

test.describe('Error States', () => {
  test('login - validation error', async ({ page }) => {
    await page.goto('/login.html');
    await waitForPageReady(page);
    await disableAnimations(page);

    // Add error state to input
    await page.evaluate(() => {
      const input = document.querySelector('input');
      if (input) {
        input.classList.add('error', 'prism-text-field--error');
        input.setAttribute('aria-invalid', 'true');
        const error = document.createElement('div');
        error.className = 'error-message prism-text-field__error';
        error.textContent = 'Invalid email address';
        input.parentElement?.appendChild(error);
      }
    });

    const loginCard = page.locator('.login-card');
    await expect(loginCard).toHaveScreenshot('error-login-validation.png');
  });

  test('dashboard - api error', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);

    // Simulate API error state
    await page.evaluate(() => {
      const apiStatus = document.getElementById('api-status');
      if (apiStatus) {
        apiStatus.textContent = 'Error';
        apiStatus.style.color = 'var(--fail, #ff4444)';
      }
      const apiHealth = document.getElementById('api-health');
      if (apiHealth) {
        apiHealth.textContent = 'Connection failed';
      }
    });

    const statusGrid = page.locator('.status-grid').first();
    await expect(statusGrid).toHaveScreenshot('error-api-status.png');
  });
});

// =============================================================================
// LOADING STATE TESTS
// =============================================================================

test.describe('Loading States', () => {
  test('dashboard - loading state', async ({ page }) => {
    await page.goto('/');
    await waitForPageReady(page);
    await disableAnimations(page);

    // Add loading skeleton states
    await page.evaluate(() => {
      const statValues = document.querySelectorAll('.stat-value');
      statValues.forEach((el) => {
        el.innerHTML = '<span class="skeleton" style="display:inline-block;width:60px;height:1em;background:rgba(255,255,255,0.1);border-radius:4px;"></span>';
      });
    });

    const statusGrid = page.locator('.status-grid').first();
    await expect(statusGrid).toHaveScreenshot('loading-status-grid.png');
  });
});
