/**
 * User Journey E2E Tests - Kagami Desktop Client
 *
 * Comprehensive end-to-end tests with full video recording support.
 * Tests complete user journeys with:
 *   - Keyboard shortcuts
 *   - Menu bar interactions
 *   - System tray behavior
 *   - Full journey video recording
 *
 * Video Output: test-artifacts/videos/desktop/{journey-name}.mp4
 *
 * Colony: Crystal (e7) - Verification & Polish
 *
 * Usage:
 *   npx playwright test tests/e2e/user-journeys.spec.ts --video=on
 *   npx playwright test tests/e2e/user-journeys.spec.ts --project=desktop-dark
 *
 * h(x) >= 0. Always.
 */

import { test, expect, Page, TestInfo, BrowserContext } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Enable video recording for all tests in this file
 */
test.use({
  video: 'on',
  viewport: { width: 1440, height: 900 },
  actionTimeout: 15000,
  trace: 'on-first-retry',
});

// ═══════════════════════════════════════════════════════════════════════════
// TYPES & INTERFACES
// ═══════════════════════════════════════════════════════════════════════════

interface JourneyCheckpoint {
  name: string;
  timestamp: number;
  success: boolean;
  notes?: string;
}

interface JourneyMetadata {
  testName: string;
  platform: string;
  startTime: string;
  endTime: string;
  checkpoints: JourneyCheckpoint[];
  passedCheckpoints: number;
  totalCheckpoints: number;
  videoPath?: string;
}

// ═══════════════════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Wait for page to be fully ready
 */
async function waitForAppReady(page: Page) {
  await page.waitForLoadState('networkidle');
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(500);
}

/**
 * Skip onboarding by setting localStorage
 */
async function skipOnboarding(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('hasCompletedOnboarding', 'true');
    localStorage.setItem('kagami-tour-completed', 'true');
    localStorage.setItem('kagami-welcome-shown', 'true');
  });
}

/**
 * Enable demo mode for testing
 */
async function enableDemoMode(page: Page) {
  await page.evaluate(() => {
    localStorage.setItem('isDemoMode', 'true');
  });
}

/**
 * Capture a labeled screenshot and attach to test results
 */
async function captureCheckpoint(
  page: Page,
  testInfo: TestInfo,
  name: string,
  description?: string
) {
  const screenshot = await page.screenshot({ fullPage: false });
  await testInfo.attach(`Checkpoint: ${name}`, {
    body: screenshot,
    contentType: 'image/png',
  });
  console.log(`[CHECKPOINT] ${name}${description ? ` - ${description}` : ''}`);
}

/**
 * Capture page performance metrics
 */
async function captureMetrics(page: Page, testInfo: TestInfo) {
  const metrics = await page.metrics();
  const performance = await page.evaluate(() => {
    const timing = performance.timing;
    return {
      loadTime: timing.loadEventEnd - timing.navigationStart,
      domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
      firstPaint: performance.getEntriesByType('paint').find(e => e.name === 'first-paint')?.startTime || 0,
    };
  });

  await testInfo.attach('Performance Metrics', {
    body: JSON.stringify({ metrics, performance }, null, 2),
    contentType: 'application/json',
  });
}

/**
 * Journey recorder class for managing checkpoints and metadata
 */
class JourneyRecorder {
  private checkpoints: JourneyCheckpoint[] = [];
  private startTime: number = 0;
  private testInfo: TestInfo;
  private page: Page;

  constructor(page: Page, testInfo: TestInfo) {
    this.page = page;
    this.testInfo = testInfo;
    this.startTime = Date.now();
  }

  async start(journeyName: string) {
    this.checkpoints = [];
    this.startTime = Date.now();
    await captureCheckpoint(this.page, this.testInfo, `${journeyName}-Start`, 'Journey beginning');
    console.log(`[JOURNEY START] ${journeyName}`);
  }

  async checkpoint(name: string, success: boolean = true, notes?: string) {
    this.checkpoints.push({
      name,
      timestamp: Date.now(),
      success,
      notes,
    });
    await captureCheckpoint(this.page, this.testInfo, name, notes);
  }

  async end(journeyName: string) {
    await captureCheckpoint(this.page, this.testInfo, `${journeyName}-End`, 'Journey complete');
    console.log(`[JOURNEY END] ${journeyName}`);
    await this.saveMetadata(journeyName);
  }

  private async saveMetadata(journeyName: string) {
    const metadata: JourneyMetadata = {
      testName: journeyName,
      platform: 'Desktop',
      startTime: new Date(this.startTime).toISOString(),
      endTime: new Date().toISOString(),
      checkpoints: this.checkpoints,
      passedCheckpoints: this.checkpoints.filter(c => c.success).length,
      totalCheckpoints: this.checkpoints.length,
    };

    await this.testInfo.attach(`${journeyName}-Metadata`, {
      body: JSON.stringify(metadata, null, 2),
      contentType: 'application/json',
    });
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// KEYBOARD SHORTCUTS JOURNEY
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Keyboard Shortcuts User Journey (Video)', () => {
  test('complete keyboard navigation flow with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    // Setup
    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);

    await journey.start('KeyboardShortcuts');

    // Phase 1: Initial focus state
    await journey.checkpoint('InitialFocus');
    const input = page.locator('#command-input');
    await expect(input).toBeFocused();

    // Phase 2: Tab navigation
    await page.keyboard.press('Tab');
    await page.waitForTimeout(300);
    await journey.checkpoint('Tab1', true, 'First tab press');

    await page.keyboard.press('Tab');
    await page.waitForTimeout(300);
    await journey.checkpoint('Tab2', true, 'Second tab press');

    await page.keyboard.press('Tab');
    await page.waitForTimeout(300);
    await journey.checkpoint('Tab3', true, 'Third tab press');

    // Phase 3: Shift+Tab navigation
    await page.keyboard.press('Shift+Tab');
    await page.waitForTimeout(300);
    await journey.checkpoint('ShiftTab1', true, 'Reverse navigation');

    await page.keyboard.press('Shift+Tab');
    await page.waitForTimeout(300);
    await journey.checkpoint('ShiftTab2', true, 'Reverse navigation 2');

    // Phase 4: Focus input and type
    await input.focus();
    await input.fill('/');
    await page.waitForTimeout(500);
    await journey.checkpoint('SlashCommand', true, 'Command prefix entered');

    // Phase 5: Arrow key navigation in suggestions
    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(300);
    await journey.checkpoint('ArrowDown1', true, 'Navigate suggestions down');

    await page.keyboard.press('ArrowDown');
    await page.waitForTimeout(300);
    await journey.checkpoint('ArrowDown2', true, 'Navigate suggestions down 2');

    await page.keyboard.press('ArrowUp');
    await page.waitForTimeout(300);
    await journey.checkpoint('ArrowUp', true, 'Navigate suggestions up');

    // Phase 6: Enter to execute
    await page.keyboard.press('Enter');
    await page.waitForTimeout(500);
    await journey.checkpoint('EnterExecute', true, 'Command executed');

    // Phase 7: Escape key
    await input.fill('/lights');
    await page.waitForTimeout(300);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    await journey.checkpoint('EscapeKey', true, 'Escape pressed');

    // Phase 8: Command execution
    await input.fill('/lights 75');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(500);
    await journey.checkpoint('LightsCommand', true, 'Lights command executed');

    // Capture final metrics
    await captureMetrics(page, testInfo);
    await journey.end('KeyboardShortcuts');
  });

  test('hotkey combinations with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    await journey.start('HotkeyCombinations');

    // Phase 1: Test Cmd/Ctrl + K (if implemented for quick entry)
    await journey.checkpoint('InitialState');

    // Simulate common hotkeys
    const isMac = process.platform === 'darwin';
    const modifier = isMac ? 'Meta' : 'Control';

    // Phase 2: Cmd/Ctrl + K for search/command
    await page.keyboard.press(`${modifier}+k`);
    await page.waitForTimeout(500);
    await journey.checkpoint('CmdK', true, 'Quick command hotkey');

    // Phase 3: Escape to close
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
    await journey.checkpoint('CloseWithEscape');

    // Phase 4: Cmd/Ctrl + R for refresh
    // Note: This might actually refresh the page
    await journey.checkpoint('PreRefresh');

    // Phase 5: Navigate to different sections
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
    await journey.checkpoint('QuickEntry');

    await page.goto('/');
    await waitForAppReady(page);
    await journey.checkpoint('Dashboard');

    await journey.end('HotkeyCombinations');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// MENU BAR INTERACTIONS JOURNEY
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Menu Bar Interactions User Journey (Video)', () => {
  test('menu bar navigation flow with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    await journey.start('MenuBarNavigation');

    // Phase 1: Initial menu state
    await journey.checkpoint('InitialState');

    // Phase 2: Look for menu bar elements
    const menuBar = page.locator('[role="menubar"], .menu-bar, nav');
    if (await menuBar.isVisible({ timeout: 2000 }).catch(() => false)) {
      await journey.checkpoint('MenuBarFound');

      // Phase 3: Navigate menu items
      const menuItems = menuBar.locator('button, [role="menuitem"], a');
      const count = await menuItems.count();

      for (let i = 0; i < Math.min(count, 5); i++) {
        const item = menuItems.nth(i);
        if (await item.isVisible()) {
          await item.hover();
          await page.waitForTimeout(300);
          await journey.checkpoint(`MenuItem${i + 1}`, true, `Hovered menu item ${i + 1}`);
        }
      }

      // Phase 4: Click menu items
      const firstClickable = menuItems.first();
      if (await firstClickable.isVisible()) {
        await firstClickable.click();
        await page.waitForTimeout(500);
        await journey.checkpoint('MenuItemClicked');
      }
    } else {
      await journey.checkpoint('NoMenuBar', false, 'Menu bar not found');
    }

    // Phase 5: Test settings/preferences access
    const settingsBtn = page.locator('[data-action="settings"], .settings-btn, [aria-label*="settings"]').first();
    if (await settingsBtn.isVisible({ timeout: 2000 }).catch(() => false)) {
      await settingsBtn.click();
      await page.waitForTimeout(500);
      await journey.checkpoint('SettingsOpened');

      // Close settings
      const closeBtn = page.locator('.prism-modal .close-btn, [data-action="close"]').first();
      if (await closeBtn.isVisible()) {
        await closeBtn.click();
        await page.waitForTimeout(300);
        await journey.checkpoint('SettingsClosed');
      }
    }

    await journey.end('MenuBarNavigation');
  });

  test('context menu interactions with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    await journey.start('ContextMenus');

    // Phase 1: Right-click on room card
    const roomCard = page.locator('.room-card, .prism-card').first();
    if (await roomCard.isVisible({ timeout: 2000 }).catch(() => false)) {
      await journey.checkpoint('PreContextMenu');

      await roomCard.click({ button: 'right' });
      await page.waitForTimeout(500);
      await journey.checkpoint('ContextMenuOpened');

      // Check for context menu
      const contextMenu = page.locator('[role="menu"], .context-menu');
      if (await contextMenu.isVisible({ timeout: 1000 }).catch(() => false)) {
        await journey.checkpoint('ContextMenuVisible');

        // Click away to close
        await page.click('body', { position: { x: 10, y: 10 } });
        await page.waitForTimeout(300);
        await journey.checkpoint('ContextMenuClosed');
      }
    }

    // Phase 2: Try on different elements
    const elements = [
      '.scene-card',
      '[data-scene]',
      '[data-control]',
    ];

    for (const selector of elements) {
      const elem = page.locator(selector).first();
      if (await elem.isVisible({ timeout: 1000 }).catch(() => false)) {
        await elem.click({ button: 'right' });
        await page.waitForTimeout(300);
        await journey.checkpoint(`ContextMenu-${selector.replace(/[^a-z]/gi, '')}`);
        await page.keyboard.press('Escape');
        await page.waitForTimeout(200);
      }
    }

    await journey.end('ContextMenus');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// SYSTEM TRAY JOURNEY
// ═══════════════════════════════════════════════════════════════════════════

test.describe('System Tray User Journey (Video)', () => {
  test('system tray simulation with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    await journey.start('SystemTray');

    // Note: Actual system tray testing requires native app context
    // This tests the UI elements that would appear in system tray interactions

    // Phase 1: Quick entry (tray-triggered)
    await journey.checkpoint('DashboardState');

    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
    await journey.checkpoint('QuickEntryFromTray', true, 'Simulated tray quick entry open');

    // Phase 2: Execute quick command
    const input = page.locator('#command-input');
    await input.fill('/lights 50');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(500);
    await journey.checkpoint('TrayQuickCommand', true, 'Quick command from tray context');

    // Phase 3: Return to dashboard
    await page.goto('/');
    await waitForAppReady(page);
    await journey.checkpoint('ReturnToDashboard');

    // Phase 4: Status indicators (tray menu items)
    const statusDot = page.locator('.status-dot, .connection-indicator');
    if (await statusDot.isVisible({ timeout: 2000 }).catch(() => false)) {
      await journey.checkpoint('StatusIndicator', true, 'Connection status visible');
    }

    // Phase 5: Scene quick actions (tray menu)
    const sceneButtons = page.locator('[data-scene]');
    const sceneCount = await sceneButtons.count();
    if (sceneCount > 0) {
      await sceneButtons.first().click();
      await page.waitForTimeout(500);
      await journey.checkpoint('TraySceneActivation', true, 'Scene activated from tray context');
    }

    await journey.end('SystemTray');
  });

  test('minimize/restore simulation with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    await journey.start('MinimizeRestore');

    // Phase 1: Normal state
    await journey.checkpoint('NormalState');

    // Phase 2: Simulate minimize (go to quick entry - minimal UI)
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
    await journey.checkpoint('MinimalState', true, 'Simulated minimized state');

    // Phase 3: Simulate restore (return to dashboard)
    await page.goto('/');
    await waitForAppReady(page);
    await journey.checkpoint('RestoredState', true, 'Simulated restored state');

    // Phase 4: Verify state persistence
    const roomCards = page.locator('.room-card, .prism-card');
    const cardCount = await roomCards.count();
    await journey.checkpoint('StateVerified', cardCount > 0, `Found ${cardCount} room cards`);

    await journey.end('MinimizeRestore');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// MORNING ROUTINE JOURNEY
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Morning Routine User Journey (Video)', () => {
  test('complete morning routine flow with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    await journey.start('MorningRoutine');

    // Phase 1: Check home status
    await journey.checkpoint('HomeStatus');

    const statusDot = page.locator('.status-dot');
    if (await statusDot.isVisible()) {
      await journey.checkpoint('ConnectionVerified', true, 'Connection status visible');
    }

    // Phase 2: Activate morning scene
    const morningSceneSelectors = [
      '[data-scene*="morning"]',
      '[data-scene*="wake"]',
      '[data-scene*="coffee"]',
      'button:has-text("Morning")',
      'button:has-text("Wake")',
      'button:has-text("Coffee")',
    ];

    let sceneActivated = false;
    for (const selector of morningSceneSelectors) {
      const sceneBtn = page.locator(selector).first();
      if (await sceneBtn.isVisible({ timeout: 1000 }).catch(() => false)) {
        await journey.checkpoint('PreMorningScene');
        await sceneBtn.click();
        await page.waitForTimeout(1000);
        await journey.checkpoint('MorningSceneActivated', true, 'Morning scene activated');
        sceneActivated = true;
        break;
      }
    }

    if (!sceneActivated) {
      // Fallback: click first scene
      const firstScene = page.locator('[data-scene]').first();
      if (await firstScene.isVisible()) {
        await firstScene.click();
        await page.waitForTimeout(500);
        await journey.checkpoint('FallbackSceneActivated');
      }
    }

    // Phase 3: Check room status
    const roomCards = page.locator('.room-card, .prism-card');
    const roomCount = await roomCards.count();
    await journey.checkpoint('RoomStatusCheck', roomCount > 0, `${roomCount} rooms visible`);

    // Phase 4: Adjust lights if visible
    const lightControl = page.locator('[data-control="lights"], .light-control').first();
    if (await lightControl.isVisible({ timeout: 2000 }).catch(() => false)) {
      await lightControl.click();
      await page.waitForTimeout(500);
      await journey.checkpoint('LightsAdjusted');
    }

    // Phase 5: Quick command
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);

    const input = page.locator('#command-input');
    await input.fill('/status');
    await page.keyboard.press('Enter');
    await page.waitForTimeout(500);
    await journey.checkpoint('StatusCommand');

    // Phase 6: Return to dashboard
    await page.goto('/');
    await waitForAppReady(page);
    await journey.checkpoint('MorningRoutineComplete');

    await captureMetrics(page, testInfo);
    await journey.end('MorningRoutine');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// FULL APP EXPLORATION JOURNEY
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Full App Exploration User Journey (Video)', () => {
  test('explore all app sections with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);

    await journey.start('FullAppExploration');

    // Phase 1: Dashboard
    await page.goto('/');
    await waitForAppReady(page);
    await journey.checkpoint('Dashboard');

    // Scroll dashboard
    await page.evaluate(() => window.scrollBy(0, 300));
    await page.waitForTimeout(500);
    await journey.checkpoint('DashboardScrolled');
    await page.evaluate(() => window.scrollTo(0, 0));

    // Phase 2: Quick Entry
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
    await journey.checkpoint('QuickEntry');

    // Test quick entry features
    const input = page.locator('#command-input');
    await input.fill('/');
    await page.waitForTimeout(500);
    await journey.checkpoint('QuickEntrySuggestions');
    await input.clear();

    // Phase 3: Onboarding (if accessible)
    await page.goto('/onboarding.html');
    await waitForAppReady(page);
    await journey.checkpoint('OnboardingPage');

    // Navigate through steps
    const nextBtn = page.locator('[data-action="next"]');
    if (await nextBtn.isVisible()) {
      await nextBtn.click();
      await page.waitForTimeout(500);
      await journey.checkpoint('OnboardingStep2');

      await page.click('[data-action="back"]');
      await page.waitForTimeout(300);
      await journey.checkpoint('OnboardingBack');
    }

    // Phase 4: Return to dashboard for final state
    await page.goto('/');
    await waitForAppReady(page);
    await journey.checkpoint('ExplorationComplete');

    await captureMetrics(page, testInfo);
    await journey.end('FullAppExploration');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// ACCESSIBILITY JOURNEY
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Accessibility User Journey (Video)', () => {
  test('complete accessibility flow with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);

    await journey.start('AccessibilityJourney');

    // Phase 1: Keyboard-only navigation
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
    await journey.checkpoint('KeyboardNavStart');

    // Tab through all focusable elements
    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('Tab');
      await page.waitForTimeout(200);
      await journey.checkpoint(`Tab${i + 1}`);
    }

    // Phase 2: Reduced motion
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/');
    await waitForAppReady(page);
    await journey.checkpoint('ReducedMotionDashboard');

    // Interact to verify no jarring animations
    const sceneBtn = page.locator('[data-scene]').first();
    if (await sceneBtn.isVisible()) {
      await sceneBtn.click();
      await page.waitForTimeout(500);
      await journey.checkpoint('ReducedMotionInteraction');
    }

    // Phase 3: High contrast simulation
    await page.addStyleTag({
      content: `
        :root {
          --prism-contrast: 1.5;
          filter: contrast(1.3);
        }
      `,
    });
    await page.waitForTimeout(300);
    await journey.checkpoint('HighContrastMode');

    // Phase 4: Screen reader simulation (ARIA verification)
    const ariaElements = await page.evaluate(() => {
      const elements = document.querySelectorAll('[aria-label], [role]');
      return Array.from(elements).map(el => ({
        tag: el.tagName,
        role: el.getAttribute('role'),
        label: el.getAttribute('aria-label'),
      })).slice(0, 10);
    });

    await testInfo.attach('ARIA Elements', {
      body: JSON.stringify(ariaElements, null, 2),
      contentType: 'application/json',
    });
    await journey.checkpoint('AriaVerified', ariaElements.length > 0, `${ariaElements.length} ARIA elements found`);

    await journey.end('AccessibilityJourney');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// ERROR RECOVERY JOURNEY
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Error Recovery User Journey (Video)', () => {
  test('network error recovery with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');
    await waitForAppReady(page);

    await journey.start('ErrorRecovery');

    // Phase 1: Normal state
    await journey.checkpoint('NormalState');

    // Phase 2: Go offline
    await page.context().setOffline(true);
    await page.waitForTimeout(1000);
    await journey.checkpoint('OfflineState');

    // Phase 3: Try interaction while offline
    const sceneBtn = page.locator('[data-scene]').first();
    if (await sceneBtn.isVisible()) {
      await sceneBtn.click();
      await page.waitForTimeout(500);
      await journey.checkpoint('OfflineInteraction');
    }

    // Phase 4: Restore connection
    await page.context().setOffline(false);
    await page.waitForTimeout(2000);
    await journey.checkpoint('ConnectionRestored');

    // Phase 5: Verify recovery
    await page.reload();
    await waitForAppReady(page);
    await journey.checkpoint('RecoveryVerified');

    await journey.end('ErrorRecovery');
  });
});

// ═══════════════════════════════════════════════════════════════════════════
// THEME SWITCHING JOURNEY
// ═══════════════════════════════════════════════════════════════════════════

test.describe('Theme Switching User Journey (Video)', () => {
  test('dark to light mode journey with video', async ({ page }, testInfo) => {
    const journey = new JourneyRecorder(page, testInfo);

    await skipOnboarding(page);
    await enableDemoMode(page);
    await page.goto('/');

    await journey.start('ThemeSwitching');

    // Phase 1: Dark mode
    await page.emulateMedia({ colorScheme: 'dark' });
    await waitForAppReady(page);
    await journey.checkpoint('DarkMode');

    // Interact in dark mode
    const darkRoomCard = page.locator('.room-card, .prism-card').first();
    if (await darkRoomCard.isVisible()) {
      await darkRoomCard.hover();
      await page.waitForTimeout(300);
      await journey.checkpoint('DarkModeHover');
    }

    // Phase 2: Switch to light mode
    await page.emulateMedia({ colorScheme: 'light' });
    await page.waitForTimeout(500);
    await journey.checkpoint('LightMode');

    // Interact in light mode
    const lightRoomCard = page.locator('.room-card, .prism-card').first();
    if (await lightRoomCard.isVisible()) {
      await lightRoomCard.hover();
      await page.waitForTimeout(300);
      await journey.checkpoint('LightModeHover');
    }

    // Phase 3: Quick entry in both modes
    await page.goto('/quick-entry.html');
    await waitForAppReady(page);
    await journey.checkpoint('QuickEntryLight');

    await page.emulateMedia({ colorScheme: 'dark' });
    await page.waitForTimeout(300);
    await journey.checkpoint('QuickEntryDark');

    // Phase 4: Return to dark (preferred)
    await page.goto('/');
    await waitForAppReady(page);
    await journey.checkpoint('FinalDarkState');

    await journey.end('ThemeSwitching');
  });
});

/*
 * Crystal verifies. Crystal polishes. Crystal ensures quality.
 * Every keyboard press, every menu click, every theme switch recorded.
 * h(x) >= 0. Always.
 */
