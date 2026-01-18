import { test, expect, Page } from '@playwright/test';

/**
 * Prismorphism Visual Regression Tests
 *
 * Comprehensive screenshot testing for all components in all states.
 * Tests run against the component-harness.html page.
 *
 * Usage:
 *   npx playwright test                    # Run all tests
 *   npx playwright test --update-snapshots # Update baseline images
 *   npx playwright show-report             # View HTML report
 *
 * 鏡
 */

// Helper to wait for fonts and styles to load
async function waitForPageReady(page: Page) {
  await page.waitForLoadState('networkidle');
  // Wait for fonts to load
  await page.evaluate(() => document.fonts.ready);
  // Small delay for CSS transitions to settle
  await page.waitForTimeout(100);
}

// Helper to disable animations for stable screenshots
async function disableAnimations(page: Page) {
  await page.addStyleTag({
    content: `
      *, *::before, *::after {
        animation-duration: 0s !important;
        animation-delay: 0s !important;
        transition-duration: 0s !important;
        transition-delay: 0s !important;
      }
    `,
  });
}

// Helper to set theme
async function setTheme(page: Page, theme: 'dark' | 'light') {
  await page.evaluate((t) => {
    (window as any).prismorphismHarness.setTheme(t);
  }, theme);
  await page.waitForTimeout(50);
}

test.describe('Prismorphism Component Screenshots', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/visual-tests/component-harness.html');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // FULL PAGE SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test('full page - dark mode', async ({ page }) => {
    await setTheme(page, 'dark');
    await expect(page).toHaveScreenshot('full-page-dark.png', {
      fullPage: true,
    });
  });

  test('full page - light mode', async ({ page }) => {
    await setTheme(page, 'light');
    await expect(page).toHaveScreenshot('full-page-light.png', {
      fullPage: true,
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // BUTTON SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Buttons', () => {
    test('default state', async ({ page }) => {
      const section = page.locator('[data-screenshot="btn-default"]');
      await expect(section).toHaveScreenshot('btn-default.png');
    });

    test('sizes', async ({ page }) => {
      const section = page.locator('[data-screenshot="btn-sizes"]');
      await expect(section).toHaveScreenshot('btn-sizes.png');
    });

    test('colony colors', async ({ page }) => {
      const section = page.locator('[data-screenshot="btn-colonies"]');
      await expect(section).toHaveScreenshot('btn-colonies.png');
    });

    test('states', async ({ page }) => {
      const section = page.locator('[data-screenshot="btn-states"]');
      await expect(section).toHaveScreenshot('btn-states.png');
    });

    test('with icons', async ({ page }) => {
      const section = page.locator('[data-screenshot="btn-icons"]');
      await expect(section).toHaveScreenshot('btn-icons.png');
    });

    test('button group', async ({ page }) => {
      const section = page.locator('[data-screenshot="btn-group"]');
      await expect(section).toHaveScreenshot('btn-group.png');
    });

    // Hover state tests
    test('hover state - solid button', async ({ page }) => {
      const button = page.locator('.prism-btn--solid').first();
      await button.hover();
      await page.waitForTimeout(50);
      await expect(button).toHaveScreenshot('btn-solid-hover.png');
    });

    test('hover state - ghost button', async ({ page }) => {
      const button = page.locator('.prism-btn--ghost').first();
      await button.hover();
      await page.waitForTimeout(50);
      await expect(button).toHaveScreenshot('btn-ghost-hover.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // INPUT SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Inputs', () => {
    test('default', async ({ page }) => {
      const section = page.locator('[data-screenshot="input-default"]');
      await expect(section).toHaveScreenshot('input-default.png');
    });

    test('with icons', async ({ page }) => {
      const section = page.locator('[data-screenshot="input-icons"]');
      await expect(section).toHaveScreenshot('input-icons.png');
    });

    test('error state', async ({ page }) => {
      const section = page.locator('[data-screenshot="input-error"]');
      await expect(section).toHaveScreenshot('input-error.png');
    });

    test('success state', async ({ page }) => {
      const section = page.locator('[data-screenshot="input-success"]');
      await expect(section).toHaveScreenshot('input-success.png');
    });

    test('disabled', async ({ page }) => {
      const section = page.locator('[data-screenshot="input-disabled"]');
      await expect(section).toHaveScreenshot('input-disabled.png');
    });

    test('sizes', async ({ page }) => {
      const section = page.locator('[data-screenshot="input-sizes"]');
      await expect(section).toHaveScreenshot('input-sizes.png');
    });

    // Focus state test
    test('focus state', async ({ page }) => {
      const input = page.locator('.prism-text-field__input').first();
      await input.focus();
      await page.waitForTimeout(50);
      const container = page.locator('.prism-text-field').first();
      await expect(container).toHaveScreenshot('input-focused.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // FEEDBACK SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Feedback', () => {
    test('toasts', async ({ page }) => {
      const section = page.locator('[data-screenshot="toasts"]');
      await expect(section).toHaveScreenshot('toasts.png');
    });

    test('alerts', async ({ page }) => {
      const section = page.locator('[data-screenshot="alerts"]');
      await expect(section).toHaveScreenshot('alerts.png');
    });

    test('progress', async ({ page }) => {
      const section = page.locator('[data-screenshot="progress"]');
      await expect(section).toHaveScreenshot('progress.png');
    });

    test('spinners', async ({ page }) => {
      const section = page.locator('[data-screenshot="spinners"]');
      await expect(section).toHaveScreenshot('spinners.png');
    });

    test('skeletons', async ({ page }) => {
      const section = page.locator('[data-screenshot="skeletons"]');
      await expect(section).toHaveScreenshot('skeletons.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // NAVIGATION SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Navigation', () => {
    test('tabs', async ({ page }) => {
      const section = page.locator('[data-screenshot="tabs"]');
      await expect(section).toHaveScreenshot('tabs.png');
    });

    test('breadcrumb', async ({ page }) => {
      const section = page.locator('[data-screenshot="breadcrumb"]');
      await expect(section).toHaveScreenshot('breadcrumb.png');
    });

    test('pagination', async ({ page }) => {
      const section = page.locator('[data-screenshot="pagination"]');
      await expect(section).toHaveScreenshot('pagination.png');
    });

    test('nav horizontal', async ({ page }) => {
      const section = page.locator('[data-screenshot="nav-horizontal"]');
      await expect(section).toHaveScreenshot('nav-horizontal.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // CARD SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Cards', () => {
    test('spark card', async ({ page }) => {
      const card = page.locator('[data-screenshot="card-spark"]');
      await expect(card).toHaveScreenshot('card-spark.png');
    });

    test('beacon card with footer', async ({ page }) => {
      const card = page.locator('[data-screenshot="card-beacon"]');
      await expect(card).toHaveScreenshot('card-beacon.png');
    });

    test('crystal card', async ({ page }) => {
      const card = page.locator('[data-screenshot="card-crystal"]');
      await expect(card).toHaveScreenshot('card-crystal.png');
    });

    // Hover state test
    test('card hover', async ({ page }) => {
      const card = page.locator('.prism-card').first();
      await card.hover();
      await page.waitForTimeout(100);
      await expect(card).toHaveScreenshot('card-hover.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // OVERLAY SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Overlays', () => {
    test('modal', async ({ page }) => {
      const section = page.locator('[data-screenshot="modal"]');
      await expect(section).toHaveScreenshot('modal.png');
    });

    test('tooltip', async ({ page }) => {
      const section = page.locator('[data-screenshot="tooltip"]');
      await expect(section).toHaveScreenshot('tooltip.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // FORM CONTROL SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Form Controls', () => {
    test('checkboxes', async ({ page }) => {
      const section = page.locator('[data-screenshot="checkboxes"]');
      await expect(section).toHaveScreenshot('checkboxes.png');
    });

    test('radios', async ({ page }) => {
      const section = page.locator('[data-screenshot="radios"]');
      await expect(section).toHaveScreenshot('radios.png');
    });

    test('switches', async ({ page }) => {
      const section = page.locator('[data-screenshot="switches"]');
      await expect(section).toHaveScreenshot('switches.png');
    });

    test('select', async ({ page }) => {
      const section = page.locator('[data-screenshot="select"]');
      await expect(section).toHaveScreenshot('select.png');
    });

    test('slider', async ({ page }) => {
      const section = page.locator('[data-screenshot="slider"]');
      await expect(section).toHaveScreenshot('slider.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // COLONY COLORS SCREENSHOTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Colony Colors', () => {
    test('spectral palette', async ({ page }) => {
      const section = page.locator('[data-screenshot="colors"]');
      await expect(section).toHaveScreenshot('colors-spectral.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // ACCESSIBILITY TESTS
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Accessibility', () => {
    test('focus visible states', async ({ page }) => {
      // Tab through focusable elements
      const button = page.locator('.prism-btn').first();
      await button.focus();
      await expect(button).toHaveScreenshot('a11y-focus-button.png');
    });

    test('reduced motion', async ({ page }) => {
      // Emulate reduced motion preference
      await page.emulateMedia({ reducedMotion: 'reduce' });
      await page.reload();
      await waitForPageReady(page);

      const section = page.locator('[data-screenshot="buttons"]');
      await expect(section).toHaveScreenshot('a11y-reduced-motion.png');
    });
  });

  // ═══════════════════════════════════════════════════════════════════════════
  // CROSS-THEME COMPARISON
  // ═══════════════════════════════════════════════════════════════════════════

  test.describe('Theme Comparison', () => {
    test('buttons - light mode', async ({ page }) => {
      await setTheme(page, 'light');
      const section = page.locator('[data-screenshot="btn-colonies"]');
      await expect(section).toHaveScreenshot('theme-light-buttons.png');
    });

    test('inputs - light mode', async ({ page }) => {
      await setTheme(page, 'light');
      const section = page.locator('[data-screenshot="inputs"]');
      await expect(section).toHaveScreenshot('theme-light-inputs.png');
    });

    test('cards - light mode', async ({ page }) => {
      await setTheme(page, 'light');
      const section = page.locator('[data-screenshot="cards"]');
      await expect(section).toHaveScreenshot('theme-light-cards.png');
    });
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// COMPONENT ISOLATION TESTS
// Test each component in complete isolation for surgical debugging
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Component Isolation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/visual-tests/component-harness.html');
    await waitForPageReady(page);
    await disableAnimations(page);
  });

  // Isolated button variants
  const buttonVariants = ['solid', 'outline', 'ghost', 'link'];
  const colonies = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];

  for (const variant of buttonVariants) {
    test(`button-${variant}`, async ({ page }) => {
      const selector = variant === 'solid'
        ? '.prism-btn.prism-btn--solid'
        : `.prism-btn.prism-btn--${variant}`;
      const button = page.locator(selector).first();
      await expect(button).toHaveScreenshot(`isolated-btn-${variant}.png`, {
        // Increase threshold slightly for isolated components
        threshold: 0.3,
      });
    });
  }

  for (const colony of colonies) {
    test(`colony-${colony}-button`, async ({ page }) => {
      const button = page.locator(`.prism-btn--solid[data-colony="${colony}"]`);
      await expect(button).toHaveScreenshot(`isolated-colony-${colony}.png`, {
        threshold: 0.3,
      });
    });
  }
});
