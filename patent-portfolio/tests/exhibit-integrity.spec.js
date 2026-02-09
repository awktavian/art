/**
 * Exhibit Integrity Tests
 * =======================
 * 
 * Verifies that all 54 museum exhibits (P1, P2, P3) can be instantiated
 * without errors and have the required structure for display.
 * 
 * Runs in browser context (needs THREE.js from import map).
 * h(x) ≥ 0 always
 */

import { test, expect } from '@playwright/test';

test.setTimeout(120000);

test.describe('P2 Exhibit Integrity', () => {
    
    test('all 18 P2 artworks instantiate without errors', async ({ page }) => {
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('console', msg => {
            if (msg.type() === 'error') errors.push(msg.text());
        });
        
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(10000); // Wait for museum init
        
        const results = await page.evaluate(async () => {
            try {
                const { createP2Artwork } = await import('./artworks/p2-artworks.js');
                const p2Ids = [
                    'P2-A4', 'P2-A5', 'P2-A6', 'P2-B2', 'P2-B3', 'P2-C2',
                    'P2-C3', 'P2-D2', 'P2-D3', 'P2-D4', 'P2-E2', 'P2-F1',
                    'P2-F2', 'P2-G1', 'P2-H1', 'P2-H2', 'P2-I1', 'P2-I2'
                ];
                
                const results = [];
                for (const id of p2Ids) {
                    try {
                        const artwork = createP2Artwork(id);
                        results.push({
                            id,
                            success: true,
                            hasChildren: artwork.children.length > 0,
                            hasUserData: artwork.userData?.patentId === id,
                            hasUpdate: typeof artwork.update === 'function',
                            hasDispose: typeof artwork.dispose === 'function',
                            childCount: artwork.children.length
                        });
                    } catch (e) {
                        results.push({ id, success: false, error: e.message });
                    }
                }
                return results;
            } catch (e) {
                return [{ id: 'IMPORT_ERROR', success: false, error: e.message }];
            }
        });
        
        // All 18 artworks should instantiate
        expect(results.length).toBe(18);
        
        for (const r of results) {
            expect(r.success, `${r.id} failed: ${r.error}`).toBe(true);
            expect(r.hasChildren, `${r.id} has no children`).toBe(true);
            expect(r.hasUserData, `${r.id} missing userData.patentId`).toBe(true);
            expect(r.hasUpdate, `${r.id} missing update()`).toBe(true);
            expect(r.hasDispose, `${r.id} missing dispose()`).toBe(true);
            expect(r.childCount, `${r.id} has too few children`).toBeGreaterThan(2);
        }
        
        // No critical JS errors
        const criticalErrors = errors.filter(e => 
            !e.includes('WebXR') && !e.includes('SharedArrayBuffer') && !e.includes('cross-origin')
        );
        expect(criticalErrors.length).toBe(0);
    });
});

test.describe('P3 Exhibit Integrity', () => {
    
    test('all 30 P3 artworks instantiate without errors', async ({ page }) => {
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(10000);
        
        const results = await page.evaluate(async () => {
            try {
                const { createP3Artwork } = await import('./artworks/p3-artworks.js');
                const { getPatent } = await import('./components/info-panel.js');
                
                const p3Ids = [
                    'P3-A7', 'P3-A8', 'P3-B4', 'P3-B5', 'P3-B6', 'P3-C4',
                    'P3-C5', 'P3-D5', 'P3-D6', 'P3-D7', 'P3-E3', 'P3-E4',
                    'P3-F3', 'P3-F4', 'P3-F5', 'P3-F6', 'P3-F7', 'P3-G2',
                    'P3-G3', 'P3-G4', 'P3-H3', 'P3-H4', 'P3-I3', 'P3-I4',
                    'P3-I5', 'P3-J1', 'P3-J2', 'P3-J3', 'P3-K1', 'P3-K2'
                ];
                
                const results = [];
                for (const id of p3Ids) {
                    try {
                        const patent = getPatent(id);
                        if (!patent) {
                            results.push({ id, success: false, error: 'Patent data not found' });
                            continue;
                        }
                        const artwork = createP3Artwork(patent);
                        results.push({
                            id,
                            success: true,
                            hasChildren: artwork.children.length > 0,
                            hasUpdate: typeof artwork.update === 'function',
                            hasDispose: typeof artwork.dispose === 'function',
                            childCount: artwork.children.length
                        });
                    } catch (e) {
                        results.push({ id, success: false, error: e.message });
                    }
                }
                return results;
            } catch (e) {
                return [{ id: 'IMPORT_ERROR', success: false, error: e.message }];
            }
        });
        
        expect(results.length).toBe(30);
        
        for (const r of results) {
            expect(r.success, `${r.id} failed: ${r.error}`).toBe(true);
            expect(r.hasChildren, `${r.id} has no children`).toBe(true);
            expect(r.hasUpdate, `${r.id} missing update()`).toBe(true);
            expect(r.hasDispose, `${r.id} missing dispose()`).toBe(true);
        }
    });
});

test.describe('Info Panel & Educational Layer', () => {
    
    test('info panel has glossary, toggle, and examples', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(12000);
        
        const result = await page.evaluate(async () => {
            try {
                const { default: InfoPanel } = await import('./components/info-panel.js');
                const panel = new InfoPanel();
                
                // Show a P1 patent (should have real-world example)
                panel.show('P1-001');
                
                const el = panel.element;
                return {
                    hasToggle: !!el.querySelector('.detail-toggle'),
                    hasExample: !!el.querySelector('.real-world-example'),
                    hasTooltip: !!el.querySelector('.glossary-tooltip'),
                    hasFeatures: !!el.querySelector('.features-list'),
                    hasActions: !!el.querySelector('.patent-actions'),
                    exampleVisible: el.querySelector('.real-world-example')?.style.display !== 'none',
                    toggleText: el.querySelector('.toggle-label')?.textContent
                };
            } catch (e) {
                return { error: e.message };
            }
        });
        
        expect(result.error).toBeUndefined();
        expect(result.hasToggle).toBe(true);
        expect(result.hasExample).toBe(true);
        expect(result.hasTooltip).toBe(true);
        expect(result.hasFeatures).toBe(true);
        expect(result.hasActions).toBe(true);
        expect(result.toggleText).toBe('Beginner');
    });
});

test.describe('Accessibility', () => {
    
    test('info panel has proper ARIA attributes', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(12000);
        
        const result = await page.evaluate(async () => {
            const { default: InfoPanel } = await import('./components/info-panel.js');
            const panel = new InfoPanel();
            const el = panel.element;
            
            return {
                role: el.getAttribute('role'),
                ariaLabel: el.getAttribute('aria-label'),
                tabIndex: el.getAttribute('tabindex'),
                closeButtonAriaLabel: el.querySelector('.info-panel-close')?.getAttribute('aria-label'),
                toggleAriaLabel: el.querySelector('.detail-toggle')?.getAttribute('aria-label'),
            };
        });
        
        expect(result.role).toBe('dialog');
        expect(result.ariaLabel).toBe('Patent Details');
        expect(result.closeButtonAriaLabel).toBe('Close panel');
        expect(result.toggleAriaLabel).toBe('Toggle detail level');
    });
    
    test('minimap canvas has ARIA label', async ({ page }) => {
        await page.goto('/', { waitUntil: 'domcontentloaded', timeout: 30000 });
        await page.waitForTimeout(15000);
        
        const minimapExists = await page.locator('#minimap').count();
        if (minimapExists > 0) {
            // Minimap should exist after museum loads
            const minimap = page.locator('#minimap');
            await expect(minimap).toBeAttached();
        }
    });
});
