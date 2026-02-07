/**
 * Smoke Tests
 * ===========
 * 
 * Basic tests to verify the museum loads without critical errors.
 * WebGL 3D scenes require longer load times.
 */

import { test, expect } from '@playwright/test';

// Increase timeout for WebGL tests
test.setTimeout(180000);  // 3 minutes

test.describe('Smoke Tests', () => {
    
    test('museum initializes without critical errors', async ({ page }) => {
        const errors = [];
        const logs = [];
        
        page.on('console', msg => {
            if (msg.type() === 'error') {
                errors.push(msg.text());
            }
            logs.push(msg.text());
        });
        
        page.on('pageerror', error => {
            errors.push(`Page error: ${error.message}`);
        });
        
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        
        // Check essential HTML elements exist
        await expect(page.locator('#loading-screen')).toBeAttached();
        await expect(page.locator('body')).toBeVisible();
        
        // Wait for museum to initialize (WebGL takes time)
        await page.waitForTimeout(15000);
        
        // Check if museum initialized successfully
        const museumInitialized = logs.some(l => l.includes('Patent Museum initialized'));
        expect(museumInitialized).toBe(true);
        
        // Filter out expected/non-critical errors
        const criticalErrors = errors.filter(e => 
            !e.includes('WebXR') && 
            !e.includes('XR not available') &&
            !e.includes('THREE.PropertyBinding') &&
            !e.includes('DeprecationWarning') &&
            !e.includes('SharedArrayBuffer') &&
            !e.includes('cross-origin') &&
            !e.includes('GL Driver Message') &&
            !e.includes('computeBoundingSphere')  // Allow geometry warnings
        );
        
        expect(criticalErrors.length).toBe(0);
    });
    
    test('canvas is created for WebGL rendering', async ({ page }) => {
        const logs = [];
        page.on('console', msg => logs.push(msg.text()));
        
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        
        // Wait for WebGL initialization
        await page.waitForTimeout(15000);
        
        // Check canvas exists
        const canvasCount = await page.locator('canvas').count();
        expect(canvasCount).toBeGreaterThan(0);
        
        // Check renderer initialized
        const rendererInitialized = logs.some(l => 
            l.includes('Renderer:') || l.includes('pixelRatio')
        );
        expect(rendererInitialized).toBe(true);
    });
    
    test('loading screen transitions to exploring state', async ({ page }) => {
        const logs = [];
        page.on('console', msg => logs.push(msg.text()));
        
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        
        // Wait for state transitions
        await page.waitForTimeout(20000);
        
        // Check state machine went to ready/exploring
        const reachedExploring = logs.some(l => l.includes('exploring'));
        expect(reachedExploring).toBe(true);
    });
    
    test('artworks are loaded', async ({ page }) => {
        const logs = [];
        page.on('console', msg => logs.push(msg.text()));
        
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(15000);
        
        // Check artworks were loaded
        const artworksLoaded = logs.some(l => l.includes('Loaded') && l.includes('artworks'));
        expect(artworksLoaded).toBe(true);
    });
    
});
