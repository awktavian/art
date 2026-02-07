/**
 * Basic Tests
 * ===========
 * 
 * Fast tests for DOM structure and basic functionality.
 * These run WITHOUT JavaScript to avoid WebGL crashes in headless mode.
 */

import { test, expect } from '@playwright/test';

// Disable JavaScript to avoid WebGL crashes in headless mode
test.use({ javaScriptEnabled: false });

test.describe('Basic DOM Tests', () => {
    
    test('HTML page loads with correct structure', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        // Check title
        await expect(page).toHaveTitle(/Patent Museum|Kagami/);
        
        // Check essential elements exist
        await expect(page.locator('#loading-screen')).toBeAttached();
        await expect(page.locator('body')).toBeVisible();
    });
    
    test('meta tags are present', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        // Check viewport meta
        const viewport = page.locator('meta[name="viewport"]');
        await expect(viewport).toBeAttached();
        
        // Check description
        const desc = page.locator('meta[name="description"]');
        await expect(desc).toBeAttached();
    });
    
    test('import map is present', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        const hasImportMap = await page.evaluate(() => {
            const scripts = document.querySelectorAll('script[type="importmap"]');
            return scripts.length > 0;
        });
        
        expect(hasImportMap).toBe(true);
    });
    
    test('CSS styles are loaded', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        // Check loading screen has background color (CSS loaded)
        const bgColor = await page.evaluate(() => {
            const ls = document.getElementById('loading-screen');
            return getComputedStyle(ls).backgroundColor;
        });
        
        // Should not be transparent
        expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
    });
    
    test('fonts are loaded', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        // Check fonts link tags
        const fontLinks = page.locator('link[href*="fonts.googleapis.com"]');
        const count = await fontLinks.count();
        expect(count).toBeGreaterThan(0);
    });
    
});

test.describe('Script Tags', () => {
    
    test('main.js script tag exists', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        // Check main.js script tag (src includes ./main.js)
        const mainScript = page.locator('script[src="./main.js"]');
        await expect(mainScript).toBeAttached();
    });
    
    test('script is module type', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        const mainScript = page.locator('script[src="./main.js"]');
        await expect(mainScript).toHaveAttribute('type', 'module');
    });
    
});

test.describe('Accessibility', () => {
    
    test('loading screen has ARIA attributes', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        const ls = page.locator('#loading-screen');
        await expect(ls).toHaveAttribute('role', 'status');
    });
    
    test('document has lang attribute', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 10000 });
        
        const html = page.locator('html');
        await expect(html).toHaveAttribute('lang', 'en');
    });
    
});
