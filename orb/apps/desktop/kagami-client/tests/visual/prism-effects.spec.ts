/**
 * Visual Regression Tests — Prismorphism Design System
 *
 * Tests all prismorphism effects and design token consistency.
 * Screenshots are compared against baseline images.
 *
 * Run:
 *   npx playwright test tests/visual/prism-effects.spec.ts
 *
 * Update baselines:
 *   npx playwright test tests/visual/prism-effects.spec.ts --update-snapshots
 *
 * Colony: Crystal (e₇) — Verification & Polish
 */

import { test, expect, Page } from '@playwright/test';

// =============================================================================
// TEST HELPERS
// =============================================================================

/**
 * Wait for all CSS animations to settle
 */
async function waitForAnimations(page: Page) {
  // Wait for any in-progress animations
  await page.evaluate(() => {
    return new Promise<void>((resolve) => {
      const animations = document.getAnimations();
      if (animations.length === 0) {
        resolve();
        return;
      }
      Promise.all(animations.map((a) => a.finished)).then(() => resolve());
    });
  });
  // Additional buffer for CSS transitions
  await page.waitForTimeout(100);
}

/**
 * Enable reduced motion for accessibility tests
 */
async function enableReducedMotion(page: Page) {
  await page.emulateMedia({ reducedMotion: 'reduce' });
}

// =============================================================================
// DESIGN TOKEN TESTS
// =============================================================================

test.describe('Design Tokens', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('colony colors render correctly', async ({ page }) => {
    // Create a test element with all colony colors
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'colony-test';
      container.innerHTML = `
        <div style="display: flex; gap: 8px; padding: 24px; background: var(--kagami-void);">
          <div style="width: 48px; height: 48px; border-radius: 50%; background: var(--kagami-spark);"></div>
          <div style="width: 48px; height: 48px; border-radius: 50%; background: var(--kagami-forge);"></div>
          <div style="width: 48px; height: 48px; border-radius: 50%; background: var(--kagami-flow);"></div>
          <div style="width: 48px; height: 48px; border-radius: 50%; background: var(--kagami-nexus);"></div>
          <div style="width: 48px; height: 48px; border-radius: 50%; background: var(--kagami-beacon);"></div>
          <div style="width: 48px; height: 48px; border-radius: 50%; background: var(--kagami-grove);"></div>
          <div style="width: 48px; height: 48px; border-radius: 50%; background: var(--kagami-crystal);"></div>
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#colony-test');
    await expect(element).toHaveScreenshot('colony-colors.png');
  });

  test('void palette renders correctly', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'void-test';
      container.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 8px; padding: 24px;">
          <div style="padding: 16px; background: var(--kagami-void); color: var(--kagami-text-primary);">void</div>
          <div style="padding: 16px; background: var(--kagami-voidWarm); color: var(--kagami-text-primary);">voidWarm</div>
          <div style="padding: 16px; background: var(--kagami-obsidian); color: var(--kagami-text-primary);">obsidian</div>
          <div style="padding: 16px; background: var(--kagami-voidLight); color: var(--kagami-text-primary);">voidLight</div>
          <div style="padding: 16px; background: var(--kagami-carbon); color: var(--kagami-text-primary);">carbon</div>
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#void-test');
    await expect(element).toHaveScreenshot('void-palette.png');
  });

  test('text colors have correct opacity', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'text-test';
      container.innerHTML = `
        <div style="padding: 24px; background: var(--kagami-void);">
          <p style="color: var(--kagami-text-primary); font-size: 16px; margin: 8px 0;">Primary text (100%)</p>
          <p style="color: var(--kagami-text-secondary); font-size: 16px; margin: 8px 0;">Secondary text (65%)</p>
          <p style="color: var(--kagami-text-tertiary); font-size: 16px; margin: 8px 0;">Tertiary text (35%)</p>
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#text-test');
    await expect(element).toHaveScreenshot('text-colors.png');
  });
});

// =============================================================================
// PRISMORPHISM EFFECT TESTS
// =============================================================================

test.describe('Prismorphism Effects', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('spectral border animation', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'spectral-border-test';
      container.innerHTML = `
        <div style="padding: 48px; background: var(--kagami-void);">
          <div class="spectral-border" style="width: 200px; height: 100px; background: var(--kagami-obsidian); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
            <span style="color: var(--kagami-text-primary);">Spectral Border</span>
          </div>
        </div>
      `;
      document.body.appendChild(container);
    });

    // Wait for animation to reach a stable point
    await page.waitForTimeout(500);
    const element = page.locator('#spectral-border-test');
    await expect(element).toHaveScreenshot('spectral-border.png', {
      animations: 'disabled',
    });
  });

  test('caustic background animation', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'caustic-test';
      container.innerHTML = `
        <div class="caustic-bg" style="width: 300px; height: 200px; border-radius: 16px; display: flex; align-items: center; justify-content: center; position: relative; overflow: hidden;">
          <span style="color: var(--kagami-text-primary); position: relative; z-index: 1;">Caustic Background</span>
        </div>
      `;
      document.body.appendChild(container);
    });

    await page.waitForTimeout(500);
    const element = page.locator('#caustic-test');
    await expect(element).toHaveScreenshot('caustic-background.png', {
      animations: 'disabled',
    });
  });

  test('shimmer text effect', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'shimmer-test';
      container.innerHTML = `
        <div style="padding: 48px; background: var(--kagami-void);">
          <h1 class="shimmer-text" style="font-size: 48px; font-weight: bold;">KAGAMI</h1>
        </div>
      `;
      document.body.appendChild(container);
    });

    await page.waitForTimeout(500);
    const element = page.locator('#shimmer-test');
    await expect(element).toHaveScreenshot('shimmer-text.png', {
      animations: 'disabled',
    });
  });

  test('prism glass card', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'glass-card-test';
      container.innerHTML = `
        <div style="padding: 48px; background: linear-gradient(135deg, var(--kagami-spark), var(--kagami-crystal));">
          <div class="prism-card" style="padding: 24px; backdrop-filter: blur(20px); background: rgba(18, 16, 26, 0.7); border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.1);">
            <h2 style="color: var(--kagami-text-primary); margin: 0 0 8px 0;">Glass Card</h2>
            <p style="color: var(--kagami-text-secondary); margin: 0;">With glassmorphism and spectral shimmer</p>
          </div>
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#glass-card-test');
    await expect(element).toHaveScreenshot('glass-card.png');
  });

  test('chromatic aberration effect', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'chromatic-test';
      container.innerHTML = `
        <div style="padding: 48px; background: var(--kagami-void); text-align: center;">
          <div class="chromatic-text" style="font-size: 64px; position: relative; display: inline-block;">
            <span style="position: absolute; left: -2px; color: var(--kagami-spark); opacity: 0.5;">鏡</span>
            <span style="position: absolute; left: 2px; color: var(--kagami-crystal); opacity: 0.5;">鏡</span>
            <span style="color: var(--kagami-text-primary); position: relative;">鏡</span>
          </div>
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#chromatic-test');
    await expect(element).toHaveScreenshot('chromatic-aberration.png');
  });
});

// =============================================================================
// COMPONENT STATE TESTS
// =============================================================================

test.describe('Component States', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');
  });

  test('button states - default, hover, active, disabled', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'button-states-test';
      container.innerHTML = `
        <div style="display: flex; gap: 16px; padding: 24px; background: var(--kagami-void);">
          <button class="prism-button" style="padding: 12px 24px; background: var(--kagami-crystal); color: var(--kagami-void); border: none; border-radius: 8px; font-weight: 600;">Default</button>
          <button class="prism-button hover" style="padding: 12px 24px; background: var(--kagami-crystal); color: var(--kagami-void); border: none; border-radius: 8px; font-weight: 600; transform: translateY(-2px); box-shadow: 0 4px 20px rgba(103, 212, 228, 0.4);">Hover</button>
          <button class="prism-button active" style="padding: 12px 24px; background: var(--kagami-crystal); color: var(--kagami-void); border: none; border-radius: 8px; font-weight: 600; transform: scale(0.97);">Active</button>
          <button class="prism-button" disabled style="padding: 12px 24px; background: var(--kagami-carbon); color: var(--kagami-text-tertiary); border: none; border-radius: 8px; font-weight: 600; opacity: 0.5;">Disabled</button>
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#button-states-test');
    await expect(element).toHaveScreenshot('button-states.png');
  });

  test('input states - default, focus, error, disabled', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'input-states-test';
      container.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 16px; padding: 24px; background: var(--kagami-void); width: 300px;">
          <input type="text" placeholder="Default" style="padding: 12px 16px; background: var(--kagami-obsidian); border: 1px solid rgba(255,255,255,0.1); border-radius: 8px; color: var(--kagami-text-primary);">
          <input type="text" placeholder="Focus" style="padding: 12px 16px; background: var(--kagami-obsidian); border: 1px solid var(--kagami-crystal); border-radius: 8px; color: var(--kagami-text-primary); box-shadow: 0 0 0 2px rgba(103, 212, 228, 0.2);">
          <input type="text" placeholder="Error" style="padding: 12px 16px; background: var(--kagami-obsidian); border: 1px solid var(--kagami-status-error); border-radius: 8px; color: var(--kagami-text-primary);">
          <input type="text" placeholder="Disabled" disabled style="padding: 12px 16px; background: var(--kagami-carbon); border: 1px solid rgba(255,255,255,0.05); border-radius: 8px; color: var(--kagami-text-tertiary); opacity: 0.5;">
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#input-states-test');
    await expect(element).toHaveScreenshot('input-states.png');
  });

  test('status indicators', async ({ page }) => {
    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'status-test';
      container.innerHTML = `
        <div style="display: flex; gap: 24px; padding: 24px; background: var(--kagami-void);">
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 12px; height: 12px; border-radius: 50%; background: var(--kagami-status-success); box-shadow: 0 0 8px var(--kagami-status-success);"></div>
            <span style="color: var(--kagami-text-primary);">Success</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 12px; height: 12px; border-radius: 50%; background: var(--kagami-status-warning); box-shadow: 0 0 8px var(--kagami-status-warning);"></div>
            <span style="color: var(--kagami-text-primary);">Warning</span>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 12px; height: 12px; border-radius: 50%; background: var(--kagami-status-error); box-shadow: 0 0 8px var(--kagami-status-error);"></div>
            <span style="color: var(--kagami-text-primary);">Error</span>
          </div>
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#status-test');
    await expect(element).toHaveScreenshot('status-indicators.png');
  });
});

// =============================================================================
// ACCESSIBILITY TESTS
// =============================================================================

test.describe('Accessibility', () => {
  test('reduced motion - animations disabled', async ({ page }) => {
    await enableReducedMotion(page);
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await page.evaluate(() => {
      const container = document.createElement('div');
      container.id = 'reduced-motion-test';
      container.innerHTML = `
        <div style="padding: 24px; background: var(--kagami-void);">
          <div class="spectral-border" style="width: 200px; height: 100px; background: var(--kagami-obsidian); border-radius: 12px; display: flex; align-items: center; justify-content: center;">
            <span style="color: var(--kagami-text-primary);">Reduced Motion</span>
          </div>
        </div>
      `;
      document.body.appendChild(container);
    });

    // In reduced motion mode, spectral border should be static
    const element = page.locator('#reduced-motion-test');
    await expect(element).toHaveScreenshot('reduced-motion.png');
  });

  test('high contrast mode colors', async ({ page }) => {
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    // Simulate high contrast by adding a class
    await page.evaluate(() => {
      document.documentElement.classList.add('high-contrast');
      const container = document.createElement('div');
      container.id = 'high-contrast-test';
      container.innerHTML = `
        <style>
          .high-contrast #high-contrast-test {
            --kagami-text-primary: #FFFFFF;
            --kagami-void: #000000;
            --kagami-obsidian: #121212;
            --kagami-crystal: #00FFFF;
          }
        </style>
        <div style="padding: 24px; background: var(--kagami-void);">
          <button style="padding: 12px 24px; background: var(--kagami-crystal); color: var(--kagami-void); border: 2px solid white; border-radius: 8px; font-weight: bold;">High Contrast Button</button>
        </div>
      `;
      document.body.appendChild(container);
    });

    const element = page.locator('#high-contrast-test');
    await expect(element).toHaveScreenshot('high-contrast.png');
  });
});

// =============================================================================
// RESPONSIVE TESTS
// =============================================================================

test.describe('Responsive', () => {
  test('mobile viewport', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveScreenshot('responsive-mobile.png', {
      fullPage: false,
    });
  });

  test('tablet viewport', async ({ page }) => {
    await page.setViewportSize({ width: 834, height: 1194 });
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    await expect(page).toHaveScreenshot('responsive-tablet.png', {
      fullPage: false,
    });
  });
});
