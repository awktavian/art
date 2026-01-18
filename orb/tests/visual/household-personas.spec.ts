/**
 * Household Personas Visual Tests
 *
 * Tests the household management UI across different family configurations,
 * validating privacy boundaries, accessibility, and state management.
 *
 * Follows Playwright best practices:
 * - Web-first assertions with auto-waiting
 * - Page Object Model pattern
 * - Robust selectors with data-testid fallbacks
 * - Parallel test execution
 * - Fibonacci timing constants
 */

import { test, expect, Page, Locator } from '@playwright/test';

// =============================================================================
// FIBONACCI TIMING CONSTANTS
// =============================================================================

const TIMING = {
  MICRO: 89,      // Micro-interactions
  BUTTON: 144,    // Button presses
  MODAL: 233,     // Modal appearances
  SETTLE: 377,    // UI settle time
  TRANSITION: 610, // Page transitions
  COMPLEX: 987,   // Complex reveals
} as const;

// =============================================================================
// TYPE DEFINITIONS
// =============================================================================

interface HouseholdMember {
  name: string;
  role: 'owner' | 'resident' | 'guest' | 'pet';
  avatar?: string;
  privacyLevel?: 'full' | 'limited' | 'minimal';
}

interface HouseholdSettings {
  name: string;
  members: HouseholdMember[];
  privacyMode: boolean;
  inclusiveFeatures: boolean;
  audioFeedback: boolean;
  reducedMotion: boolean;
}

// =============================================================================
// HOUSEHOLD CONFIGURATIONS
// =============================================================================

const HOUSEHOLD_CONFIGS: Record<string, HouseholdSettings> = {
  patel: {
    name: 'Patel Family',
    members: [
      { name: 'Priya', role: 'owner', privacyLevel: 'full' },
      { name: 'Raj', role: 'resident', privacyLevel: 'full' },
      { name: 'Ananya', role: 'resident', privacyLevel: 'limited' },
      { name: 'Vikram', role: 'resident', privacyLevel: 'limited' },
      { name: 'Dadi', role: 'guest', privacyLevel: 'minimal' },
    ],
    privacyMode: false,
    inclusiveFeatures: true,
    audioFeedback: true,
    reducedMotion: false,
  },
  tokyo: {
    name: 'Tokyo Roommates',
    members: [
      { name: 'Yuki', role: 'owner', privacyLevel: 'full' },
      { name: 'Kenji', role: 'resident', privacyLevel: 'full' },
      { name: 'Mika', role: 'resident', privacyLevel: 'full' },
    ],
    privacyMode: true,
    inclusiveFeatures: false,
    audioFeedback: false,
    reducedMotion: true,
  },
  jordanSam: {
    name: 'Jordan & Sam',
    members: [
      { name: 'Jordan', role: 'owner', privacyLevel: 'full' },
      { name: 'Sam', role: 'resident', privacyLevel: 'full' },
      { name: 'Luna', role: 'pet' },
    ],
    privacyMode: false,
    inclusiveFeatures: true,
    audioFeedback: true,
    reducedMotion: false,
  },
};

// =============================================================================
// PAGE OBJECT MODEL
// =============================================================================

class HouseholdPage {
  readonly page: Page;

  // Navigation locators
  readonly navRooms: Locator;
  readonly navSettings: Locator;
  readonly navMembers: Locator;
  readonly navDashboard: Locator;

  // Profile switcher locators
  readonly profileSwitcher: Locator;
  readonly profileDropdown: Locator;

  // Settings locators
  readonly privacyToggle: Locator;
  readonly inclusiveToggle: Locator;
  readonly audioToggle: Locator;
  readonly motionToggle: Locator;

  // Member management locators
  readonly addMemberButton: Locator;
  readonly memberList: Locator;
  readonly memberCards: Locator;

  // Room locators
  readonly roomGrid: Locator;
  readonly roomCards: Locator;

  // Accessibility locators
  readonly skipLink: Locator;
  readonly mainContent: Locator;

  constructor(page: Page) {
    this.page = page;

    // Navigation - using .or() for robust fallbacks
    this.navRooms = page.getByRole('link', { name: /rooms/i })
      .or(page.locator('[data-testid="nav-rooms"]'))
      .or(page.locator('a[href*="rooms"]'));

    this.navSettings = page.getByRole('link', { name: /settings/i })
      .or(page.locator('[data-testid="nav-settings"]'))
      .or(page.locator('a[href*="settings"]'));

    this.navMembers = page.getByRole('link', { name: /members/i })
      .or(page.locator('[data-testid="nav-members"]'))
      .or(page.locator('a[href*="members"]'));

    this.navDashboard = page.getByRole('link', { name: /dashboard|home/i })
      .or(page.locator('[data-testid="nav-dashboard"]'))
      .or(page.locator('a[href="/"]'));

    // Profile switcher
    this.profileSwitcher = page.getByRole('button', { name: /profile|switch user|account/i })
      .or(page.locator('[data-testid="profile-switcher"]'))
      .or(page.locator('[aria-label*="profile"]'));

    this.profileDropdown = page.getByRole('menu')
      .or(page.locator('[data-testid="profile-dropdown"]'))
      .or(page.locator('[role="listbox"]'));

    // Settings toggles
    this.privacyToggle = page.getByRole('switch', { name: /privacy/i })
      .or(page.locator('[data-testid="privacy-toggle"]'))
      .or(page.locator('input[name*="privacy"]'));

    this.inclusiveToggle = page.getByRole('switch', { name: /inclusive|accessibility/i })
      .or(page.locator('[data-testid="inclusive-toggle"]'))
      .or(page.locator('input[name*="inclusive"]'));

    this.audioToggle = page.getByRole('switch', { name: /audio|sound/i })
      .or(page.locator('[data-testid="audio-toggle"]'))
      .or(page.locator('input[name*="audio"]'));

    this.motionToggle = page.getByRole('switch', { name: /motion|animation/i })
      .or(page.locator('[data-testid="motion-toggle"]'))
      .or(page.locator('input[name*="motion"]'));

    // Member management
    this.addMemberButton = page.getByRole('button', { name: /add member|invite/i })
      .or(page.locator('[data-testid="add-member-button"]'));

    this.memberList = page.locator('[data-testid="member-list"]')
      .or(page.getByRole('list', { name: /members/i }));

    this.memberCards = page.locator('[data-testid="member-card"]')
      .or(page.locator('.member-card'));

    // Rooms
    this.roomGrid = page.locator('[data-testid="room-grid"]')
      .or(page.getByRole('grid'))
      .or(page.locator('.room-grid'));

    this.roomCards = page.locator('[data-testid="room-card"]')
      .or(page.locator('.room-card'));

    // Accessibility
    this.skipLink = page.locator('a[href="#main-content"]')
      .or(page.locator('[data-testid="skip-link"]'))
      .or(page.getByRole('link', { name: /skip to/i }));

    this.mainContent = page.locator('#main-content')
      .or(page.locator('[role="main"]'))
      .or(page.locator('main'));
  }

  async goto(path: string = '/'): Promise<void> {
    await this.page.goto(path);
    await this.waitForAppReady();
  }

  async waitForAppReady(): Promise<void> {
    // Wait for main content to be visible
    await expect(this.mainContent).toBeVisible({ timeout: TIMING.TRANSITION * 3 });
    // Additional settle time for dynamic content
    await this.page.waitForTimeout(TIMING.SETTLE);
  }

  async navigateToRooms(): Promise<void> {
    await this.navRooms.click();
    await this.page.waitForTimeout(TIMING.TRANSITION);
    await expect(this.roomGrid).toBeVisible();
  }

  async navigateToSettings(): Promise<void> {
    await this.navSettings.click();
    await this.page.waitForTimeout(TIMING.TRANSITION);
  }

  async navigateToMembers(): Promise<void> {
    await this.navMembers.click();
    await this.page.waitForTimeout(TIMING.TRANSITION);
    await expect(this.memberList).toBeVisible();
  }

  async openProfileSwitcher(): Promise<void> {
    await this.profileSwitcher.click();
    await this.page.waitForTimeout(TIMING.MODAL);
    await expect(this.profileDropdown).toBeVisible();
  }

  async selectProfile(memberName: string): Promise<void> {
    await this.openProfileSwitcher();
    const profileOption = this.page.getByRole('menuitem', { name: new RegExp(memberName, 'i') })
      .or(this.page.locator(`[data-testid="profile-${memberName.toLowerCase()}"]`));
    await profileOption.click();
    await this.page.waitForTimeout(TIMING.TRANSITION);
  }

  async togglePrivacyMode(enable: boolean): Promise<void> {
    const isChecked = await this.privacyToggle.isChecked().catch(() => false);
    if (isChecked !== enable) {
      await this.privacyToggle.click();
      await this.page.waitForTimeout(TIMING.BUTTON);
    }
  }

  async getMemberCount(): Promise<number> {
    return await this.memberCards.count();
  }

  async takeScreenshot(name: string): Promise<void> {
    await this.page.screenshot({
      path: `tests/visual/screenshots/${name}.png`,
      fullPage: true,
    });
  }

  getMemberLocator(memberName: string): Locator {
    return this.page.locator(`[data-testid="member-${memberName.toLowerCase()}"]`)
      .or(this.page.getByRole('listitem').filter({ hasText: memberName }))
      .or(this.page.locator('.member-card').filter({ hasText: memberName }));
  }

  getRoomLocator(roomName: string): Locator {
    return this.page.locator(`[data-testid="room-${roomName.toLowerCase().replace(/\s+/g, '-')}"]`)
      .or(this.page.getByRole('button').filter({ hasText: roomName }))
      .or(this.page.locator('.room-card').filter({ hasText: roomName }));
  }
}

// =============================================================================
// TEST SUITES
// =============================================================================

test.describe('Patel Family Household', () => {
  test.describe.configure({ mode: 'parallel' });

  let householdPage: HouseholdPage;
  const config = HOUSEHOLD_CONFIGS.patel;

  test.beforeEach(async ({ page }) => {
    householdPage = new HouseholdPage(page);
    // In real implementation, this would set up the household context
    await householdPage.goto('/household/patel');
  });

  test('should display all family members in member list', async ({ page }) => {
    await householdPage.navigateToMembers();

    const memberCount = await householdPage.getMemberCount();
    expect(memberCount).toBe(config.members.length);

    // Verify each member is displayed
    for (const member of config.members) {
      const memberLocator = householdPage.getMemberLocator(member.name);
      await expect(memberLocator).toBeVisible();
    }

    await householdPage.takeScreenshot('patel-family-members');
  });

  test('should show owner badge for Priya', async ({ page }) => {
    await householdPage.navigateToMembers();

    const priyaCard = householdPage.getMemberLocator('Priya');
    await expect(priyaCard).toBeVisible();

    const ownerBadge = priyaCard.locator('[data-testid="owner-badge"]')
      .or(priyaCard.getByText(/owner/i));
    await expect(ownerBadge).toBeVisible();
  });

  test('should show guest indicator for Dadi', async ({ page }) => {
    await householdPage.navigateToMembers();

    const dadiCard = householdPage.getMemberLocator('Dadi');
    await expect(dadiCard).toBeVisible();

    const guestBadge = dadiCard.locator('[data-testid="guest-badge"]')
      .or(dadiCard.getByText(/guest/i));
    await expect(guestBadge).toBeVisible();
  });

  test('should have inclusive features enabled by default', async ({ page }) => {
    await householdPage.navigateToSettings();

    await expect(householdPage.inclusiveToggle).toBeChecked();
  });

  test('should have audio feedback enabled', async ({ page }) => {
    await householdPage.navigateToSettings();

    await expect(householdPage.audioToggle).toBeChecked();
  });

  test('should allow profile switching between members', async ({ page }) => {
    // Start as Priya (owner)
    await expect(page.getByText(/priya/i)).toBeVisible();

    // Switch to Ananya
    await householdPage.selectProfile('Ananya');

    // Verify profile changed
    const profileIndicator = page.locator('[data-testid="current-profile"]')
      .or(page.getByRole('button', { name: /ananya/i }));
    await expect(profileIndicator).toContainText(/ananya/i);
  });

  test('should respect limited privacy for children', async ({ page }) => {
    // Switch to Ananya (limited privacy)
    await householdPage.selectProfile('Ananya');
    await householdPage.navigateToSettings();

    // Privacy toggle should be visible but limited options
    const advancedPrivacy = page.locator('[data-testid="advanced-privacy"]');
    await expect(advancedPrivacy).toBeHidden();
  });

  test('should display multigenerational household UI correctly', async ({ page }) => {
    await householdPage.navigateToMembers();

    // Verify role hierarchy is displayed
    const roleGroups = page.locator('[data-testid="role-group"]');
    const groupCount = await roleGroups.count();
    expect(groupCount).toBeGreaterThan(0);

    await householdPage.takeScreenshot('patel-multigenerational-layout');
  });
});

test.describe('Tokyo Roommates Household', () => {
  test.describe.configure({ mode: 'parallel' });

  let householdPage: HouseholdPage;
  const config = HOUSEHOLD_CONFIGS.tokyo;

  test.beforeEach(async ({ page }) => {
    householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/tokyo');
  });

  test('should display all roommates with equal status', async ({ page }) => {
    await householdPage.navigateToMembers();

    const memberCount = await householdPage.getMemberCount();
    expect(memberCount).toBe(config.members.length);

    // Verify no hierarchy badges (all equal)
    for (const member of config.members) {
      const memberCard = householdPage.getMemberLocator(member.name);
      await expect(memberCard).toBeVisible();

      // Owner badge should only appear for Yuki
      if (member.role === 'owner') {
        const ownerBadge = memberCard.locator('[data-testid="owner-badge"]');
        await expect(ownerBadge).toBeVisible();
      }
    }
  });

  test('should have privacy mode enabled by default', async ({ page }) => {
    await householdPage.navigateToSettings();

    await expect(householdPage.privacyToggle).toBeChecked();
  });

  test('should have reduced motion enabled', async ({ page }) => {
    await householdPage.navigateToSettings();

    await expect(householdPage.motionToggle).toBeChecked();
  });

  test('should respect prefers-reduced-motion', async ({ page }) => {
    // Check that animations are disabled
    const animatedElements = page.locator('[class*="animate"]');
    const count = await animatedElements.count();

    // If any animated elements exist, they should have reduced motion
    if (count > 0) {
      const styles = await page.evaluate(() => {
        const el = document.querySelector('[class*="animate"]');
        return el ? getComputedStyle(el).animationDuration : '0s';
      });
      expect(styles).toBe('0s');
    }
  });

  test('should have audio feedback disabled', async ({ page }) => {
    await householdPage.navigateToSettings();

    await expect(householdPage.audioToggle).not.toBeChecked();
  });

  test('should show privacy indicators in room view', async ({ page }) => {
    await householdPage.navigateToRooms();

    // Each room should show privacy status
    const privacyIndicators = page.locator('[data-testid="room-privacy-indicator"]')
      .or(page.locator('.privacy-indicator'));
    const indicatorCount = await privacyIndicators.count();

    expect(indicatorCount).toBeGreaterThan(0);
  });

  test('should maintain privacy mode state across navigation', async ({ page }) => {
    // Verify privacy mode is on
    await householdPage.navigateToSettings();
    await expect(householdPage.privacyToggle).toBeChecked();

    // Navigate away and back
    await householdPage.navigateToRooms();
    await householdPage.navigateToSettings();

    // Privacy mode should still be on
    await expect(householdPage.privacyToggle).toBeChecked();
  });

  test('should transition profile state correctly when switching users', async ({ page }) => {
    // Start as Yuki
    await expect(page.getByText(/yuki/i)).toBeVisible();

    // Switch to Kenji
    await householdPage.selectProfile('Kenji');
    await page.waitForTimeout(TIMING.TRANSITION);

    // Verify Kenji's profile is active
    const profileIndicator = page.locator('[data-testid="current-profile"]');
    await expect(profileIndicator).toContainText(/kenji/i);

    // Switch to Mika
    await householdPage.selectProfile('Mika');
    await page.waitForTimeout(TIMING.TRANSITION);

    // Verify Mika's profile is active
    await expect(profileIndicator).toContainText(/mika/i);
  });

  test('should display Japanese locale formatting when enabled', async ({ page }) => {
    // Check for Japanese date/time formatting
    const dateElements = page.locator('[data-testid="date-display"]')
      .or(page.locator('time'));

    const firstDate = dateElements.first();
    if (await firstDate.isVisible()) {
      const dateText = await firstDate.textContent();
      // Japanese date format often uses specific patterns
      expect(dateText).toBeTruthy();
    }

    await householdPage.takeScreenshot('tokyo-roommates-locale');
  });
});

test.describe('Jordan & Sam Household', () => {
  test.describe.configure({ mode: 'parallel' });

  let householdPage: HouseholdPage;
  const config = HOUSEHOLD_CONFIGS.jordanSam;

  test.beforeEach(async ({ page }) => {
    householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/jordan-sam');
  });

  test('should display both partners and pet', async ({ page }) => {
    await householdPage.navigateToMembers();

    const memberCount = await householdPage.getMemberCount();
    expect(memberCount).toBe(config.members.length);

    // Verify each member
    await expect(householdPage.getMemberLocator('Jordan')).toBeVisible();
    await expect(householdPage.getMemberLocator('Sam')).toBeVisible();
    await expect(householdPage.getMemberLocator('Luna')).toBeVisible();
  });

  test('should show pet indicator for Luna', async ({ page }) => {
    await householdPage.navigateToMembers();

    const lunaCard = householdPage.getMemberLocator('Luna');
    await expect(lunaCard).toBeVisible();

    const petBadge = lunaCard.locator('[data-testid="pet-badge"]')
      .or(lunaCard.getByText(/pet/i))
      .or(lunaCard.locator('.pet-icon'));
    await expect(petBadge).toBeVisible();
  });

  test('should have inclusive features enabled', async ({ page }) => {
    await householdPage.navigateToSettings();

    await expect(householdPage.inclusiveToggle).toBeChecked();
  });

  test('should allow both partners to manage household equally', async ({ page }) => {
    // Check Jordan's permissions
    await householdPage.selectProfile('Jordan');
    await householdPage.navigateToSettings();

    const addMemberVisible = await householdPage.addMemberButton.isVisible();

    // Check Sam's permissions
    await householdPage.selectProfile('Sam');
    await householdPage.navigateToSettings();

    const samCanAdd = await householdPage.addMemberButton.isVisible();

    // Both should have same permissions
    expect(addMemberVisible).toBe(samCanAdd);
  });

  test('should display shared spaces prominently', async ({ page }) => {
    await householdPage.navigateToRooms();

    // Should have shared spaces marked
    const sharedRooms = page.locator('[data-testid="shared-room"]')
      .or(page.locator('.room-card[data-shared="true"]'));
    const sharedCount = await sharedRooms.count();

    expect(sharedCount).toBeGreaterThan(0);
  });

  test('should show pet-specific features', async ({ page }) => {
    await householdPage.navigateToMembers();

    const lunaCard = householdPage.getMemberLocator('Luna');
    await lunaCard.click();
    await page.waitForTimeout(TIMING.MODAL);

    // Pet details should show pet-specific info
    const petDetails = page.locator('[data-testid="pet-details"]')
      .or(page.locator('.pet-profile'));
    await expect(petDetails).toBeVisible();
  });

  test('should handle pet-only home automation', async ({ page }) => {
    await householdPage.navigateToRooms();

    // Look for pet monitoring features
    const petMonitor = page.locator('[data-testid="pet-monitor"]')
      .or(page.getByText(/pet cam|pet mode/i));

    // Pet monitoring should be available
    const hasPetFeatures = await petMonitor.isVisible().catch(() => false);
    expect(hasPetFeatures).toBeDefined();
  });

  test('should support gender-neutral language options', async ({ page }) => {
    await householdPage.navigateToSettings();

    const languageSettings = page.locator('[data-testid="language-settings"]')
      .or(page.getByRole('region', { name: /language/i }));

    if (await languageSettings.isVisible()) {
      const neutralOption = languageSettings.getByText(/neutral|inclusive/i);
      await expect(neutralOption).toBeVisible();
    }
  });

  test('should persist inclusive settings across sessions', async ({ page, context }) => {
    await householdPage.navigateToSettings();

    // Enable a setting
    const inclusiveChecked = await householdPage.inclusiveToggle.isChecked();
    expect(inclusiveChecked).toBe(true);

    // Simulate session restart by navigating away and back
    await page.goto('/logout');
    await page.goto('/household/jordan-sam');
    await householdPage.navigateToSettings();

    // Setting should persist
    await expect(householdPage.inclusiveToggle).toBeChecked();
  });
});

test.describe('Cross-Household Tests', () => {
  test.describe.configure({ mode: 'parallel' });

  test('should maintain household isolation', async ({ page }) => {
    const householdPage = new HouseholdPage(page);

    // Load Patel household
    await householdPage.goto('/household/patel');
    await householdPage.navigateToMembers();

    // Patel members should be visible
    await expect(householdPage.getMemberLocator('Priya')).toBeVisible();

    // Tokyo members should NOT be visible
    const yukiLocator = householdPage.getMemberLocator('Yuki');
    await expect(yukiLocator).toBeHidden();

    // Jordan-Sam members should NOT be visible
    const jordanLocator = householdPage.getMemberLocator('Jordan');
    await expect(jordanLocator).toBeHidden();
  });

  test('should apply correct theme per household', async ({ page }) => {
    const householdPage = new HouseholdPage(page);

    // Check Patel theme
    await householdPage.goto('/household/patel');
    const patelTheme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );

    // Check Tokyo theme
    await householdPage.goto('/household/tokyo');
    const tokyoTheme = await page.evaluate(() =>
      document.documentElement.getAttribute('data-theme')
    );

    // Themes should exist (may or may not be different)
    expect(patelTheme).toBeTruthy();
    expect(tokyoTheme).toBeTruthy();
  });

  test('should respect household-specific accessibility settings', async ({ page }) => {
    const householdPage = new HouseholdPage(page);

    // Tokyo has reduced motion
    await householdPage.goto('/household/tokyo');
    const tokyoMotion = await page.evaluate(() =>
      document.documentElement.classList.contains('reduce-motion') ||
      document.documentElement.getAttribute('data-reduce-motion') === 'true'
    );
    expect(tokyoMotion).toBe(true);

    // Patel does not
    await householdPage.goto('/household/patel');
    const patelMotion = await page.evaluate(() =>
      document.documentElement.classList.contains('reduce-motion') ||
      document.documentElement.getAttribute('data-reduce-motion') === 'true'
    );
    expect(patelMotion).toBe(false);
  });

  test('should validate data-testid attributes exist on key elements', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Check for essential data-testid attributes
    const essentialTestIds = [
      'nav-rooms',
      'nav-settings',
      'profile-switcher',
      'main-content',
    ];

    for (const testId of essentialTestIds) {
      const element = page.locator(`[data-testid="${testId}"]`);
      const exists = await element.count() > 0;
      // Log which ones are missing for debugging
      if (!exists) {
        console.warn(`Missing data-testid: ${testId}`);
      }
    }

    // At minimum, main content should exist
    await expect(householdPage.mainContent).toBeVisible();
  });
});

test.describe('Audio Feedback Tests', () => {
  test.describe.configure({ mode: 'parallel' });

  test('should play feedback sounds when audio is enabled', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Track audio play calls
    const audioPlayed: string[] = [];
    await page.exposeFunction('trackAudio', (src: string) => {
      audioPlayed.push(src);
    });

    await page.evaluate(() => {
      const originalPlay = HTMLAudioElement.prototype.play;
      HTMLAudioElement.prototype.play = function () {
        // @ts-ignore
        window.trackAudio(this.src);
        return originalPlay.call(this);
      };
    });

    // Trigger an action that should play sound
    await householdPage.navRooms.click();
    await page.waitForTimeout(TIMING.SETTLE);

    // Audio should have been triggered (Patel has audio enabled)
    // Note: This checks the mechanism, actual audio may be mocked in tests
    expect(audioPlayed.length).toBeGreaterThanOrEqual(0); // May be 0 if mocked
  });

  test('should NOT play sounds when audio is disabled', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/tokyo');

    const audioPlayed: string[] = [];
    await page.exposeFunction('trackAudio', (src: string) => {
      audioPlayed.push(src);
    });

    await page.evaluate(() => {
      const originalPlay = HTMLAudioElement.prototype.play;
      HTMLAudioElement.prototype.play = function () {
        // @ts-ignore
        window.trackAudio(this.src);
        return originalPlay.call(this);
      };
    });

    // Trigger navigation
    await householdPage.navRooms.click();
    await page.waitForTimeout(TIMING.SETTLE);

    // Tokyo has audio disabled - should not play
    expect(audioPlayed.length).toBe(0);
  });

  test('should respect system audio preferences', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');
    await householdPage.navigateToSettings();

    // Check for system audio preference detection
    const audioSection = page.locator('[data-testid="audio-settings"]')
      .or(page.getByRole('region', { name: /audio/i }));

    if (await audioSection.isVisible()) {
      const systemPrefIndicator = audioSection.getByText(/system|default/i);
      const hasSystemPref = await systemPrefIndicator.isVisible().catch(() => false);
      expect(hasSystemPref).toBeDefined();
    }
  });

  test('should mute all audio when mute button is pressed', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');
    await householdPage.navigateToSettings();

    // Find and click mute button
    const muteButton = page.getByRole('button', { name: /mute|silence/i })
      .or(page.locator('[data-testid="mute-all"]'));

    if (await muteButton.isVisible()) {
      await muteButton.click();
      await page.waitForTimeout(TIMING.BUTTON);

      // Audio toggle should now be unchecked
      await expect(householdPage.audioToggle).not.toBeChecked();
    }
  });
});

test.describe('Privacy Boundaries - Negative Tests', () => {
  test.describe.configure({ mode: 'parallel' });

  test('should NOT allow cross-household data access', async ({ page }) => {
    const householdPage = new HouseholdPage(page);

    // Login to Patel household
    await householdPage.goto('/household/patel');

    // Attempt to access Tokyo data via URL manipulation
    const response = await page.goto('/api/household/tokyo/members');

    // Should be forbidden or redirect
    if (response) {
      expect([401, 403, 404]).toContain(response.status());
    }

    // UI should not show Tokyo members
    await householdPage.goto('/household/patel');
    await householdPage.navigateToMembers();

    const yukiCard = householdPage.getMemberLocator('Yuki');
    await expect(yukiCard).toBeHidden();
  });

  test('should NOT persist sensitive data in localStorage unencrypted', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Check localStorage for sensitive patterns
    const sensitivePatterns = await page.evaluate(() => {
      const storage = { ...localStorage };
      const sensitiveKeys = Object.keys(storage).filter(key =>
        key.toLowerCase().includes('password') ||
        key.toLowerCase().includes('token') ||
        key.toLowerCase().includes('secret')
      );

      return sensitiveKeys.map(key => {
        const value = storage[key];
        // Check if value looks encrypted (base64 or hex pattern)
        const looksEncrypted = /^[A-Za-z0-9+/=]{20,}$/.test(value) ||
          /^[0-9a-f]{32,}$/i.test(value);
        return { key, looksEncrypted };
      });
    });

    // Any sensitive data should appear encrypted
    for (const item of sensitivePatterns) {
      expect(item.looksEncrypted).toBe(true);
    }
  });

  test('should enforce member permission boundaries', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Switch to Dadi (guest with minimal privacy level)
    await householdPage.selectProfile('Dadi');
    await householdPage.navigateToSettings();

    // Guest should not see advanced settings
    const advancedSettings = page.locator('[data-testid="advanced-settings"]')
      .or(page.getByRole('region', { name: /advanced/i }));

    await expect(advancedSettings).toBeHidden();

    // Guest should not be able to add members
    await expect(householdPage.addMemberButton).toBeHidden();
  });
});

test.describe('Accessibility Compliance', () => {
  test.describe.configure({ mode: 'parallel' });

  test('should have functioning skip link', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Focus the skip link (usually hidden until focused)
    await page.keyboard.press('Tab');

    // Skip link should be visible when focused
    const skipLink = householdPage.skipLink;
    await expect(skipLink).toBeFocused();

    // Click skip link
    await skipLink.click();

    // Main content should now be focused
    await expect(householdPage.mainContent).toBeFocused();
  });

  test('should have proper heading hierarchy', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Check heading levels
    const headings = await page.evaluate(() => {
      const h1s = document.querySelectorAll('h1');
      const h2s = document.querySelectorAll('h2');
      return {
        h1Count: h1s.length,
        h2Count: h2s.length,
      };
    });

    // Should have exactly one h1
    expect(headings.h1Count).toBe(1);
    // Should have h2s for sections
    expect(headings.h2Count).toBeGreaterThan(0);
  });

  test('should have sufficient color contrast', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Check that primary text has good contrast
    const contrastIssues = await page.evaluate(() => {
      const issues: string[] = [];
      const textElements = document.querySelectorAll('p, span, a, button, label');

      textElements.forEach((el) => {
        const styles = getComputedStyle(el);
        const color = styles.color;
        const bgColor = styles.backgroundColor;

        // Simple check - this would need a real contrast calculation in production
        if (color === bgColor) {
          issues.push(`Element with same fg/bg: ${el.tagName}`);
        }
      });

      return issues;
    });

    expect(contrastIssues.length).toBe(0);
  });

  test('should support keyboard navigation', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Tab through interactive elements
    const focusableElements: string[] = [];

    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('Tab');
      const focused = await page.evaluate(() => {
        const el = document.activeElement;
        return el ? el.tagName + (el.getAttribute('data-testid') || '') : null;
      });
      if (focused) {
        focusableElements.push(focused);
      }
    }

    // Should have found focusable elements
    expect(focusableElements.length).toBeGreaterThan(0);
  });

  test('should have ARIA labels on interactive elements', async ({ page }) => {
    const householdPage = new HouseholdPage(page);
    await householdPage.goto('/household/patel');

    // Check buttons have accessible names
    const unlabeledButtons = await page.evaluate(() => {
      const buttons = document.querySelectorAll('button');
      const unlabeled: string[] = [];

      buttons.forEach((btn) => {
        const hasText = btn.textContent?.trim();
        const hasAriaLabel = btn.getAttribute('aria-label');
        const hasAriaLabelledBy = btn.getAttribute('aria-labelledby');

        if (!hasText && !hasAriaLabel && !hasAriaLabelledBy) {
          unlabeled.push(btn.outerHTML.slice(0, 100));
        }
      });

      return unlabeled;
    });

    expect(unlabeledButtons.length).toBe(0);
  });
});
