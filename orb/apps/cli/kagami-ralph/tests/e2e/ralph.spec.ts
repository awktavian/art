/**
 * E2E tests for Ralph AI Monitor
 */

import { test, expect } from '@playwright/test';

test.describe('Ralph AI Monitor', () => {
  test('should load successfully', async ({ page }) => {
    await page.goto('/');
    
    // Check title
    await expect(page).toHaveTitle(/Ralph AI Monitor/);
    
    // Check main container exists
    const app = page.locator('#app');
    await expect(app).toBeVisible();
  });

  test('should display agent cards', async ({ page }) => {
    await page.goto('/');
    
    // Wait for agents to load
    await page.waitForSelector('.agent-card', { timeout: 5000 });
    
    // Should have 7 agent cards
    const agents = page.locator('.agent-card');
    await expect(agents).toHaveCount(7);
  });

  test('should show connection status', async ({ page }) => {
    await page.goto('/');
    
    // Connection status badge should exist
    const status = page.locator('#connection-status');
    await expect(status).toBeVisible();
  });

  test('should display consensus panel', async ({ page }) => {
    await page.goto('/');
    
    // Vote display should exist
    const votes = page.locator('#vote-display');
    await expect(votes).toBeVisible();
  });

  test('should display metrics', async ({ page }) => {
    await page.goto('/');
    
    // Metrics should exist
    await expect(page.locator('#metric-step')).toBeVisible();
    await expect(page.locator('#metric-loss')).toBeVisible();
    await expect(page.locator('#metric-phase')).toBeVisible();
  });

  test('should handle disconnection gracefully', async ({ page }) => {
    await page.goto('/');
    
    // Initially should attempt connection
    await page.waitForTimeout(1000);
    
    // Should not crash on failed connection
    const app = page.locator('#app');
    await expect(app).toBeVisible();
  });
});
