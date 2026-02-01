/* ═══════════════════════════════════════════════════════════════════════════
   Playwright Tests — Design Intelligence Scrollytelling
   
   Test coverage:
   - Responsive rendering (320px, 768px, 1440px)
   - Scroll progress updates
   - Interactive demos
   - Easter eggs
   - Accessibility (keyboard nav, reduced motion)
   
   h(x) ≥ 0
═══════════════════════════════════════════════════════════════════════════ */

import { test, expect, Page } from '@playwright/test';

// =========================================================================
// HELPERS
// =========================================================================

async function waitForLoadingScreen(page: Page) {
    // Wait for loading screen to disappear
    await page.waitForSelector('.loading-screen.hidden', { timeout: 5000 });
}

async function scrollToChapter(page: Page, chapterIndex: number) {
    await page.evaluate((index) => {
        const chapter = document.querySelector(`[data-chapter="${index}"]`);
        if (chapter) {
            chapter.scrollIntoView({ behavior: 'instant' });
        }
    }, chapterIndex);
    // Wait for scroll to settle
    await page.waitForTimeout(300);
}

// =========================================================================
// RESPONSIVE RENDERING TESTS
// =========================================================================

test.describe('Responsive Rendering', () => {
    test('renders correctly at 320px (mobile)', async ({ page }) => {
        await page.setViewportSize({ width: 320, height: 568 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Check title is visible and readable
        const title = page.locator('.overture-title');
        await expect(title).toBeVisible();
        
        // Chapter nav should be hidden on mobile
        const chapterNav = page.locator('#chapter-nav');
        await expect(chapterNav).toBeHidden();
        
        // Flow diagram should be horizontally scrollable
        const flowSection = page.locator('.flow-section');
        await expect(flowSection).toHaveCSS('overflow-x', 'auto');
    });
    
    test('renders correctly at 768px (tablet)', async ({ page }) => {
        await page.setViewportSize({ width: 768, height: 1024 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Check all major sections are visible
        const overture = page.locator('.overture');
        await expect(overture).toBeVisible();
        
        // Chapter nav should be visible
        const chapterNav = page.locator('#chapter-nav');
        await expect(chapterNav).toBeVisible();
    });
    
    test('renders correctly at 1440px (desktop)', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Check flow diagram displays horizontally
        const flowDiagram = page.locator('.flow-diagram');
        await expect(flowDiagram).toBeVisible();
        
        // Check all chapter dots are visible
        const chapterDots = page.locator('.chapter-dot');
        await expect(chapterDots).toHaveCount(6);
    });
});

// =========================================================================
// SCROLL PROGRESS TESTS
// =========================================================================

test.describe('Scroll Progress', () => {
    test('progress bar updates on scroll', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Initial progress should be 0
        const progressBar = page.locator('#progress-bar');
        const initialWidth = await progressBar.evaluate(el => el.style.width);
        expect(initialWidth).toBe('0%');
        
        // Scroll to middle
        await page.evaluate(() => {
            window.scrollTo(0, document.body.scrollHeight / 2);
        });
        await page.waitForTimeout(200);
        
        // Progress should be approximately 50%
        const midWidth = await progressBar.evaluate(el => parseFloat(el.style.width));
        expect(midWidth).toBeGreaterThan(40);
        expect(midWidth).toBeLessThan(60);
        
        // Scroll to end
        await page.evaluate(() => {
            window.scrollTo(0, document.body.scrollHeight);
        });
        await page.waitForTimeout(200);
        
        // Progress should be ~100%
        const endWidth = await progressBar.evaluate(el => parseFloat(el.style.width));
        expect(endWidth).toBeGreaterThan(95);
    });
    
    test('chapter navigation updates active state', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // First chapter dot should be active
        const firstDot = page.locator('.chapter-dot[data-chapter="0"]');
        await expect(firstDot).toHaveClass(/active/);
        
        // Scroll to chapter 3
        await scrollToChapter(page, 3);
        
        // Chapter 3 dot should be active
        const thirdDot = page.locator('.chapter-dot[data-chapter="3"]');
        await expect(thirdDot).toHaveClass(/active/);
        
        // First dot should no longer be active
        await expect(firstDot).not.toHaveClass(/active/);
    });
});

// =========================================================================
// INTERACTIVE DEMO TESTS
// =========================================================================

test.describe('Interactive Demos', () => {
    test('threshold slider updates display and actions', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Scroll to quality chapter
        await scrollToChapter(page, 3);
        await page.waitForTimeout(500);
        
        const slider = page.locator('.threshold-slider');
        const display = page.locator('.threshold-value-display');
        
        // Set slider to critical (50)
        await slider.fill('50');
        await expect(display).toHaveClass(/critical/);
        await expect(display).toContainText('50/100');
        
        // Critical action should be active
        const criticalAction = page.locator('.action-card.critical-action');
        await expect(criticalAction).toHaveClass(/active/);
        
        // Set slider to passing (90)
        await slider.fill('90');
        await expect(display).toHaveClass(/passing/);
        
        // Passing action should be active
        const passingAction = page.locator('.action-card.passing-action');
        await expect(passingAction).toHaveClass(/active/);
    });
    
    test('sync button shows feedback', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Scroll to harmony chapter
        await scrollToChapter(page, 4);
        await page.waitForTimeout(500);
        
        const syncButton = page.locator('#sync-button');
        await expect(syncButton).toBeVisible();
        await expect(syncButton).toContainText('Sync Now');
        
        // Click sync
        await syncButton.click();
        await expect(syncButton).toContainText('Syncing');
        
        // Wait for sync to complete
        await page.waitForTimeout(2000);
        await expect(syncButton).toContainText('Synced');
        
        // Toast should appear
        const toast = page.locator('.toast');
        await expect(toast).toBeVisible();
    });
    
    test('chapter dots navigate on click', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Click chapter 5 dot
        const chapter5Dot = page.locator('.chapter-dot[data-chapter="5"]');
        await chapter5Dot.click();
        
        // Wait for scroll
        await page.waitForTimeout(1000);
        
        // Chapter 5 should be in view
        const chapter5 = page.locator('[data-chapter="5"]');
        await expect(chapter5).toBeInViewport();
    });
});

// =========================================================================
// EASTER EGG TESTS
// =========================================================================

test.describe('Easter Eggs', () => {
    test('Konami code activates design mode', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Enter Konami code
        const konamiCode = [
            'ArrowUp', 'ArrowUp',
            'ArrowDown', 'ArrowDown',
            'ArrowLeft', 'ArrowRight',
            'ArrowLeft', 'ArrowRight',
            'b', 'a'
        ];
        
        for (const key of konamiCode) {
            await page.keyboard.press(key);
            await page.waitForTimeout(50);
        }
        
        // Design mode overlay should be visible
        const overlay = page.locator('#design-mode-overlay');
        await expect(overlay).toHaveClass(/active/);
        
        // Toast should appear
        const toast = page.locator('.toast');
        await expect(toast).toContainText('Design Mode');
    });
    
    test('triple-click title toggles night mode', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        const title = page.locator('.overture-title');
        
        // Triple click
        await title.click({ clickCount: 3 });
        
        // Body should have night-mode class
        await expect(page.locator('body')).toHaveClass(/night-mode/);
        
        // Toast should appear
        const toast = page.locator('.toast');
        await expect(toast).toContainText('Night mode');
    });
    
    test('hidden message appears at footer', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Scroll to bottom
        await page.evaluate(() => {
            window.scrollTo(0, document.body.scrollHeight);
        });
        await page.waitForTimeout(500);
        
        // Hidden message should be visible
        const hiddenMessage = page.locator('#hidden-message');
        await expect(hiddenMessage).toHaveClass(/visible/);
    });
    
    test('typing "figma" triggers animation', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Type "figma"
        await page.keyboard.type('figma');
        
        // Toast should appear
        const toast = page.locator('.toast');
        await expect(toast).toContainText('Figma');
        
        // Confetti should appear
        const confetti = page.locator('.confetti');
        await expect(confetti.first()).toBeVisible();
    });
});

// =========================================================================
// ACCESSIBILITY TESTS
// =========================================================================

test.describe('Accessibility', () => {
    test('keyboard navigation works', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Press j to go to next chapter
        await page.keyboard.press('j');
        await page.waitForTimeout(1000);
        
        // Should have scrolled down
        const scrollY = await page.evaluate(() => window.scrollY);
        expect(scrollY).toBeGreaterThan(0);
        
        // Press k to go back
        await page.keyboard.press('k');
        await page.waitForTimeout(1000);
        
        // Should have scrolled back up
        const newScrollY = await page.evaluate(() => window.scrollY);
        expect(newScrollY).toBeLessThan(scrollY);
    });
    
    test('reduced motion disables animations', async ({ page }) => {
        // Emulate reduced motion preference
        await page.emulateMedia({ reducedMotion: 'reduce' });
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        
        // Loading screen should still work but fast
        await page.waitForTimeout(500);
        
        // Particles should be hidden or static
        const canvas = page.locator('#design-canvas');
        await expect(canvas).toBeVisible();
        
        // Magic sparks should be hidden
        const sparks = page.locator('.magic-spark');
        await expect(sparks.first()).toBeHidden();
    });
    
    test('skip link works', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Focus skip link
        await page.keyboard.press('Tab');
        
        // Skip link should be visible
        const skipLink = page.locator('.skip-link');
        await expect(skipLink).toBeFocused();
        
        // Press enter to skip to content
        await page.keyboard.press('Enter');
        await page.waitForTimeout(500);
        
        // Should have scrolled to chapter 1
        const chapter1 = page.locator('#chapter-1');
        await expect(chapter1).toBeInViewport();
    });
    
    test('interactive elements have focus states', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Scroll to flow diagram
        await scrollToChapter(page, 1);
        await page.waitForTimeout(500);
        
        // Tab to a flow node
        const flowNode = page.locator('.flow-node[tabindex="0"]').first();
        await flowNode.focus();
        
        // Should have visible focus outline
        const outline = await flowNode.evaluate((el) => {
            const style = window.getComputedStyle(el);
            return style.outline || style.outlineColor;
        });
        
        expect(outline).not.toBe('none');
    });
});

// =========================================================================
// PWA TESTS
// =========================================================================

test.describe('PWA', () => {
    test('manifest is accessible', async ({ page }) => {
        const response = await page.goto('/manifest.webmanifest');
        expect(response?.status()).toBe(200);
        
        const manifest = await response?.json();
        expect(manifest.name).toContain('Design Intelligence');
        expect(manifest.theme_color).toBe('#A259FF');
    });
    
    test('service worker is registered', async ({ page }) => {
        await page.goto('/');
        await waitForLoadingScreen(page);
        
        // Wait for SW to register
        await page.waitForTimeout(1000);
        
        // Check SW is registered
        const swRegistered = await page.evaluate(async () => {
            if ('serviceWorker' in navigator) {
                const registration = await navigator.serviceWorker.getRegistration();
                return !!registration;
            }
            return false;
        });
        
        expect(swRegistered).toBe(true);
    });
});

// =========================================================================
// LOADING SCREEN TESTS
// =========================================================================

test.describe('Loading Screen', () => {
    test('loading screen displays and hides', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        
        // Loading screen should initially be visible
        const loadingScreen = page.locator('.loading-screen');
        await expect(loadingScreen).toBeVisible();
        
        // Progress bar should animate
        const progressBar = page.locator('#loading-progress-bar');
        await expect(progressBar).toBeVisible();
        
        // Wait for loading to complete
        await waitForLoadingScreen(page);
        
        // Loading screen should be hidden
        await expect(loadingScreen).toHaveClass(/hidden/);
        
        // Body should no longer have loading class
        await expect(page.locator('body')).not.toHaveClass(/loading/);
    });
    
    test('Figma logo assembles', async ({ page }) => {
        await page.setViewportSize({ width: 1440, height: 900 });
        await page.goto('/');
        
        // Logo pieces should exist
        const logoPieces = page.locator('.logo-piece');
        await expect(logoPieces).toHaveCount(5);
        
        // Wait for animation to start
        await page.waitForTimeout(100);
        
        // First piece should have animation
        const firstPiece = logoPieces.first();
        const hasAnimation = await firstPiece.evaluate((el) => {
            const style = window.getComputedStyle(el);
            return style.animationName !== 'none';
        });
        
        expect(hasAnimation).toBe(true);
    });
});
