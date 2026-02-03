/**
 * Visual Regression Tests
 * =======================
 * 
 * Screenshot comparison tests for museum visuals.
 */

import { test, expect } from '@playwright/test';

test.describe('Museum Visual Regression', () => {
    
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        
        // Wait for loading screen to disappear
        await page.waitForSelector('#loading-screen.hidden', { timeout: 30000 });
        
        // Click to start (dismiss instructions)
        await page.click('#navigation-instructions');
        
        // Wait for scene to stabilize
        await page.waitForTimeout(2000);
    });
    
    test('rotunda renders correctly', async ({ page }) => {
        // Take screenshot of initial rotunda view
        await expect(page).toHaveScreenshot('rotunda-initial.png', {
            maxDiffPixelRatio: 0.05, // Allow some variance for animation
            timeout: 10000
        });
    });
    
    test('location indicator shows rotunda', async ({ page }) => {
        const indicator = page.locator('#location-indicator');
        await expect(indicator).toContainText('ROTUNDA');
    });
    
    test('minimap is visible', async ({ page }) => {
        const minimap = page.locator('#minimap');
        await expect(minimap).toBeVisible();
    });
    
    test('audio controls are visible', async ({ page }) => {
        const audioControls = page.locator('#audio-controls');
        await expect(audioControls).toBeVisible();
    });
    
    test('help button is visible and clickable', async ({ page }) => {
        const helpButton = page.locator('#help-button');
        await expect(helpButton).toBeVisible();
        await expect(helpButton).toHaveText('?');
    });
    
});

test.describe('Wing Navigation Visuals', () => {
    
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('#loading-screen.hidden', { timeout: 30000 });
        await page.click('#navigation-instructions');
        await page.waitForTimeout(2000);
    });
    
    const wings = [
        { key: 'Digit1', name: 'SPARK' },
        { key: 'Digit2', name: 'FORGE' },
        { key: 'Digit3', name: 'FLOW' },
        { key: 'Digit4', name: 'NEXUS' },
        { key: 'Digit5', name: 'BEACON' },
        { key: 'Digit6', name: 'GROVE' },
        { key: 'Digit7', name: 'CRYSTAL' }
    ];
    
    for (const wing of wings) {
        test(`teleport to ${wing.name} wing shows correct indicator`, async ({ page }) => {
            // Teleport to wing
            await page.keyboard.press(wing.key);
            await page.waitForTimeout(500); // Wait for teleport animation
            
            // Check location indicator
            const indicator = page.locator('#location-indicator');
            await expect(indicator).toContainText(wing.name);
        });
    }
    
    test('return to rotunda via Digit0', async ({ page }) => {
        // First go to a wing
        await page.keyboard.press('Digit1');
        await page.waitForTimeout(500);
        
        // Return to rotunda
        await page.keyboard.press('Digit0');
        await page.waitForTimeout(500);
        
        const indicator = page.locator('#location-indicator');
        await expect(indicator).toContainText('ROTUNDA');
    });
    
});

test.describe('Gallery Menu Visuals', () => {
    
    test.beforeEach(async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('#loading-screen.hidden', { timeout: 30000 });
        await page.click('#navigation-instructions');
        await page.waitForTimeout(2000);
    });
    
    test('Tab key opens gallery menu', async ({ page }) => {
        await page.keyboard.press('Tab');
        
        const menu = page.locator('#gallery-menu');
        await expect(menu).toHaveClass(/visible/);
    });
    
    test('gallery menu has all wing buttons', async ({ page }) => {
        await page.keyboard.press('Tab');
        
        const buttons = page.locator('.wing-button');
        await expect(buttons).toHaveCount(8); // 7 wings + rotunda
    });
    
    test('gallery menu screenshot', async ({ page }) => {
        await page.keyboard.press('Tab');
        await page.waitForTimeout(300); // Animation
        
        await expect(page).toHaveScreenshot('gallery-menu-open.png', {
            maxDiffPixelRatio: 0.02
        });
    });
    
});

test.describe('Mobile Viewport', () => {
    
    test.use({ viewport: { width: 375, height: 667 } }); // iPhone SE
    
    test('loads on mobile viewport', async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('#loading-screen.hidden', { timeout: 30000 });
        await page.click('#navigation-instructions');
        await page.waitForTimeout(2000);
        
        await expect(page).toHaveScreenshot('mobile-viewport.png', {
            maxDiffPixelRatio: 0.05
        });
    });
    
    test('touch joystick is visible on mobile', async ({ page }) => {
        await page.goto('/');
        await page.waitForSelector('#loading-screen.hidden', { timeout: 30000 });
        await page.click('#navigation-instructions');
        
        const joystick = page.locator('#touch-joystick');
        await expect(joystick).toBeVisible();
    });
    
});
