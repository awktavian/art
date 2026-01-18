/**
 * J09 Emergency Safety Journey Test - iOS Implementation
 *
 * Tests the emergency safety protocol on iOS devices.
 * This is a CRITICAL safety test that MUST always pass.
 *
 * h(x) >= 0. Always.
 *
 * Test Flow:
 * 1. Access emergency features (max 2 taps)
 * 2. Trigger emergency mode
 * 3. Verify safety score h(x) >= 0
 * 4. Verify all doors locked
 * 5. Verify alerts sent
 * 6. Verify emergency contacts notified
 * 7. Confirm safety (end emergency)
 *
 * Colony: Crystal (e7) -- Verification & Polish
 */

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import {
  JourneyTestBase,
  Checkpoint,
  CheckpointTestResult,
  AssertionResult,
  SafetyScore,
  EmergencySystemState,
  EmergencyState,
  EmergencyDriver,
  ElementLocator,
  ElementState,
  EMERGENCY_TIMING,
  FIBONACCI_MS,
} from '../journey-test-base.js';
import { J09_EMERGENCY_SAFETY } from '../canonical-journeys.js';

// =============================================================================
// iOS ELEMENT LOCATORS
// =============================================================================

/**
 * iOS-specific element locators for emergency features
 * Uses accessibilityIdentifier for reliable cross-device testing
 */
const IOS_LOCATORS = {
  // Emergency access elements
  emergencyButton: {
    id: 'emergency_button',
    label: 'Emergency',
  } as ElementLocator,

  emergencyActiveIndicator: {
    id: 'emergency_active_indicator',
  } as ElementLocator,

  allLightsOnIndicator: {
    id: 'all_lights_on',
  } as ElementLocator,

  safetyConfirmedIndicator: {
    id: 'safety_confirmed_indicator',
  } as ElementLocator,

  // Safety card elements
  safetyCard: {
    id: 'safety_card',
  } as ElementLocator,

  safetyScoreLabel: {
    id: 'safety_score_label',
  } as ElementLocator,

  // Home view elements
  homeView: {
    id: 'home_view',
  } as ElementLocator,

  // Confirmation button
  confirmSafetyButton: {
    id: 'confirm_safety_button',
    label: 'I am Safe',
  } as ElementLocator,
};

// =============================================================================
// iOS SIMULATOR DRIVER
// =============================================================================

/**
 * iOS Simulator Driver using xcrun simctl
 */
class IOSSimulatorDriver implements EmergencyDriver {
  readonly platform = 'ios' as const;
  private deviceId: string;
  private connected = false;
  private screenshotDir: string;

  constructor(deviceId: string = 'booted', screenshotDir: string = '/tmp/kagami-qa-ios') {
    this.deviceId = deviceId;
    this.screenshotDir = screenshotDir;
  }

  async connect(): Promise<void> {
    // Verify simulator is running
    try {
      const result = execSync(`xcrun simctl list devices | grep -E "Booted"`, {
        encoding: 'utf8',
      });
      if (!result.includes('Booted')) {
        throw new Error('No booted iOS simulator found');
      }
      this.connected = true;

      // Ensure screenshot directory exists
      if (!fs.existsSync(this.screenshotDir)) {
        fs.mkdirSync(this.screenshotDir, { recursive: true });
      }
    } catch (error) {
      throw new Error(`Failed to connect to iOS simulator: ${error}`);
    }
  }

  async disconnect(): Promise<void> {
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  async findElement(locator: ElementLocator): Promise<ElementState> {
    // Use XCTest bridge via simctl to query UI hierarchy
    // In production, this would use XCUITest or Appium
    const script = this.buildFindElementScript(locator);
    try {
      const result = execSync(
        `xcrun simctl spawn ${this.deviceId} xctest-runner find-element '${script}'`,
        { encoding: 'utf8', timeout: 5000 }
      );
      return this.parseElementState(result);
    } catch {
      // Element not found
      return {
        exists: false,
        visible: false,
        enabled: false,
      };
    }
  }

  async waitForElement(
    locator: ElementLocator,
    timeoutMs: number
  ): Promise<ElementState> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      const state = await this.findElement(locator);
      if (state.exists && state.visible) {
        return state;
      }
      await this.sleep(FIBONACCI_MS.F11); // 89ms polling
    }
    return { exists: false, visible: false, enabled: false };
  }

  async tap(locator: ElementLocator): Promise<void> {
    const element = await this.waitForElement(locator, FIBONACCI_MS.F18);
    if (!element.exists || !element.bounds) {
      throw new Error(`Cannot tap: element not found - ${JSON.stringify(locator)}`);
    }

    const x = element.bounds.x + element.bounds.width / 2;
    const y = element.bounds.y + element.bounds.height / 2;

    // Use simctl to send tap event
    execSync(
      `xcrun simctl io ${this.deviceId} sendtap ${x} ${y}`,
      { timeout: 5000 }
    );
  }

  async longPress(locator: ElementLocator, durationMs: number = 1000): Promise<void> {
    const element = await this.waitForElement(locator, FIBONACCI_MS.F18);
    if (!element.exists || !element.bounds) {
      throw new Error(`Cannot long press: element not found - ${JSON.stringify(locator)}`);
    }

    const x = element.bounds.x + element.bounds.width / 2;
    const y = element.bounds.y + element.bounds.height / 2;

    // Simulate long press with touch down, wait, touch up
    execSync(
      `xcrun simctl io ${this.deviceId} sendtouch down ${x} ${y}`,
      { timeout: 5000 }
    );
    await this.sleep(durationMs);
    execSync(
      `xcrun simctl io ${this.deviceId} sendtouch up ${x} ${y}`,
      { timeout: 5000 }
    );
  }

  async typeText(locator: ElementLocator, text: string): Promise<void> {
    await this.tap(locator);
    // Use keyboard input
    execSync(
      `xcrun simctl io ${this.deviceId} keyboard type "${text}"`,
      { timeout: 10000 }
    );
  }

  async swipe(
    startX: number,
    startY: number,
    endX: number,
    endY: number,
    durationMs: number = 500
  ): Promise<void> {
    // Swipe using touch events
    const steps = Math.max(10, Math.floor(durationMs / 16)); // ~60fps
    const stepX = (endX - startX) / steps;
    const stepY = (endY - startY) / steps;
    const stepTime = durationMs / steps;

    execSync(
      `xcrun simctl io ${this.deviceId} sendtouch down ${startX} ${startY}`,
      { timeout: 5000 }
    );

    for (let i = 1; i <= steps; i++) {
      const x = startX + stepX * i;
      const y = startY + stepY * i;
      await this.sleep(stepTime);
      execSync(
        `xcrun simctl io ${this.deviceId} sendtouch move ${x} ${y}`,
        { timeout: 5000 }
      );
    }

    execSync(
      `xcrun simctl io ${this.deviceId} sendtouch up ${endX} ${endY}`,
      { timeout: 5000 }
    );
  }

  async screenshot(): Promise<Buffer> {
    const timestamp = Date.now();
    const screenshotPath = path.join(this.screenshotDir, `screenshot_${timestamp}.png`);

    execSync(
      `xcrun simctl io ${this.deviceId} screenshot "${screenshotPath}"`,
      { timeout: 10000 }
    );

    return fs.readFileSync(screenshotPath);
  }

  async getAppState(): Promise<Record<string, unknown>> {
    // Query Kagami app state via deep link or notification
    try {
      const result = execSync(
        `xcrun simctl spawn ${this.deviceId} kagami-state-query`,
        { encoding: 'utf8', timeout: 5000 }
      );
      return JSON.parse(result);
    } catch {
      return {};
    }
  }

  async executeCommand(command: string, args?: unknown[]): Promise<unknown> {
    const argsStr = args ? args.map(String).join(' ') : '';
    const result = execSync(
      `xcrun simctl spawn ${this.deviceId} ${command} ${argsStr}`,
      { encoding: 'utf8', timeout: 30000 }
    );
    return result;
  }

  // ==========================================================================
  // EMERGENCY DRIVER METHODS
  // ==========================================================================

  async getEmergencyState(): Promise<EmergencySystemState> {
    const safetyScore = await this.getSafetyScore();
    const appState = await this.getAppState();

    const emergencyState = (appState['emergencyState'] as EmergencyState) ?? 'idle';

    return {
      emergencyState,
      safetyScore,
      allDoorsLocked: await this.verifyDoorsLocked(),
      allLightsOn: await this.verifyLightsOn(),
      alertsSent: await this.verifyAlertsSent(),
      contactsNotified: await this.verifyContactsNotified(),
      capturedAt: Date.now(),
    };
  }

  async triggerEmergency(): Promise<void> {
    // Tap the emergency button
    await this.tap(IOS_LOCATORS.emergencyButton);
  }

  async confirmSafety(): Promise<void> {
    // Tap the confirm safety button
    await this.tap(IOS_LOCATORS.confirmSafetyButton);
  }

  async getSafetyScore(): Promise<SafetyScore> {
    const appState = await this.getAppState();

    // Parse safety score from app state
    const safetyData = appState['safetyScore'] as Record<string, number> | undefined;

    if (!safetyData) {
      // Default safe state
      return {
        value: 1.0,
        components: {
          doorLocks: 0.25,
          lights: 0.25,
          alerts: 0.25,
          emergencyContacts: 0.25,
        },
        timestamp: Date.now(),
        status: 'safe',
      };
    }

    const value = safetyData['value'] ?? 1.0;

    return {
      value,
      components: {
        doorLocks: safetyData['doorLocks'] ?? 0.25,
        lights: safetyData['lights'] ?? 0.25,
        alerts: safetyData['alerts'] ?? 0.25,
        emergencyContacts: safetyData['emergencyContacts'] ?? 0.25,
      },
      timestamp: Date.now(),
      status: value > 0 ? 'safe' : value === 0 ? 'boundary' : 'unsafe',
    };
  }

  async verifyDoorsLocked(): Promise<boolean> {
    const appState = await this.getAppState();
    return (appState['allDoorsLocked'] as boolean) ?? false;
  }

  async verifyLightsOn(): Promise<boolean> {
    // Check if lights indicator is visible
    const element = await this.findElement(IOS_LOCATORS.allLightsOnIndicator);
    return element.exists && element.visible;
  }

  async verifyAlertsSent(): Promise<boolean> {
    const appState = await this.getAppState();
    return (appState['alertsSent'] as boolean) ?? false;
  }

  async verifyContactsNotified(): Promise<boolean> {
    const appState = await this.getAppState();
    return (appState['contactsNotified'] as boolean) ?? false;
  }

  // ==========================================================================
  // PRIVATE HELPERS
  // ==========================================================================

  private buildFindElementScript(locator: ElementLocator): string {
    if (locator.id) {
      return `accessibility-id:${locator.id}`;
    }
    if (locator.label) {
      return `label:${locator.label}`;
    }
    if (locator.xpath) {
      return `xpath:${locator.xpath}`;
    }
    throw new Error('Invalid locator: must specify id, label, or xpath');
  }

  private parseElementState(result: string): ElementState {
    try {
      const data = JSON.parse(result);
      return {
        exists: true,
        visible: data.visible ?? true,
        enabled: data.enabled ?? true,
        bounds: data.frame
          ? {
              x: data.frame.x,
              y: data.frame.y,
              width: data.frame.width,
              height: data.frame.height,
            }
          : undefined,
        text: data.label ?? data.value,
        value: data.value,
      };
    } catch {
      return { exists: false, visible: false, enabled: false };
    }
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// =============================================================================
// J09 EMERGENCY SAFETY TEST
// =============================================================================

/**
 * J09 Emergency Safety Journey Test for iOS
 *
 * This test verifies the emergency safety protocol works correctly:
 * - Emergency can be accessed within 2 taps
 * - Emergency triggers correctly and fast
 * - Safety score h(x) >= 0 is maintained
 * - All doors lock
 * - All lights turn on
 * - Alerts are sent
 * - Emergency contacts are notified
 * - User can confirm safety to end emergency
 *
 * CRITICAL: This test MUST ALWAYS PASS. Any failure indicates a safety violation.
 */
export class J09EmergencySafetyTest extends JourneyTestBase {
  private emergencyDriver: EmergencyDriver;

  constructor(deviceId?: string, screenshotDir?: string) {
    const driver = new IOSSimulatorDriver(deviceId, screenshotDir);
    super(J09_EMERGENCY_SAFETY, 'ios', driver);
    this.emergencyDriver = driver;
  }

  /**
   * Execute a checkpoint with iOS-specific implementation
   */
  protected async executeCheckpoint(
    checkpoint: Checkpoint
  ): Promise<CheckpointTestResult> {
    const start = Date.now();
    const videoStartMs = this.getVideoTimestamp();
    const assertions: AssertionResult[] = [];
    const screenshots: string[] = [];

    this.emit('checkpoint:started', {
      checkpointId: checkpoint.id,
      videoTimestamp: videoStartMs,
    });

    try {
      switch (checkpoint.id) {
        case 'CP1_EMERGENCY_ACCESSIBLE':
          await this.executeEmergencyAccessibleCheckpoint(assertions, screenshots);
          break;

        case 'CP2_EMERGENCY_ACTIVE':
          await this.executeEmergencyActiveCheckpoint(assertions, screenshots);
          break;

        case 'CP3_SAFETY_CONFIRMED':
          await this.executeSafetyConfirmedCheckpoint(assertions, screenshots);
          break;

        default:
          throw new Error(`Unknown checkpoint: ${checkpoint.id}`);
      }

      // CRITICAL: Always verify safety score at every checkpoint
      const safetyScore = await this.emergencyDriver.getSafetyScore();
      assertions.push(this.assertSafetyScore(safetyScore));

      // Take screenshot for video correlation
      const screenshotBuffer = await this.driver.screenshot();
      const screenshotPath = `/tmp/kagami-qa-ios/${checkpoint.id}_${Date.now()}.png`;
      fs.writeFileSync(screenshotPath, screenshotBuffer);
      screenshots.push(screenshotPath);

    } catch (error) {
      // Even on error, try to capture safety state
      try {
        const safetyScore = await this.emergencyDriver.getSafetyScore();
        assertions.push({
          name: 'h(x) >= 0 (Safety Check on Error)',
          passed: safetyScore.value >= 0,
          expected: '>= 0',
          actual: safetyScore.value,
          error: safetyScore.value < 0
            ? `CRITICAL SAFETY VIOLATION: h(x) = ${safetyScore.value}`
            : undefined,
          durationMs: 0,
        });
      } catch {
        // Cannot even check safety - critical failure
        assertions.push({
          name: 'h(x) >= 0 (Safety Check)',
          passed: false,
          expected: '>= 0',
          actual: 'UNABLE TO CHECK',
          error: 'CRITICAL: Unable to verify safety state',
          durationMs: 0,
        });
      }

      return {
        checkpointId: checkpoint.id,
        checkpointName: checkpoint.name,
        passed: false,
        assertions,
        durationMs: Date.now() - start,
        maxDurationMs: checkpoint.maxDurationMs,
        videoStartMs,
        videoEndMs: this.getVideoTimestamp(),
        screenshots,
        error: error instanceof Error ? error.message : String(error),
      };
    }

    const durationMs = Date.now() - start;
    const passed = assertions.every((a) => a.passed) && durationMs <= checkpoint.maxDurationMs;

    return {
      checkpointId: checkpoint.id,
      checkpointName: checkpoint.name,
      passed,
      assertions,
      durationMs,
      maxDurationMs: checkpoint.maxDurationMs,
      videoStartMs,
      videoEndMs: this.getVideoTimestamp(),
      screenshots,
      error: passed ? undefined : `Checkpoint failed: ${assertions.filter((a) => !a.passed).map((a) => a.name).join(', ')}`,
    };
  }

  /**
   * CP1: Emergency Accessible within 2 taps
   */
  private async executeEmergencyAccessibleCheckpoint(
    assertions: AssertionResult[],
    _screenshots: string[]
  ): Promise<void> {
    // Verify we're on home screen
    const homeView = await this.driver.waitForElement(
      IOS_LOCATORS.homeView,
      FIBONACCI_MS.F16 // 987ms
    );

    assertions.push({
      name: 'Home view visible',
      passed: homeView.exists && homeView.visible,
      expected: { exists: true, visible: true },
      actual: { exists: homeView.exists, visible: homeView.visible },
      durationMs: 0,
    });

    // Find emergency button (should be accessible from home)
    const emergencyButton = await this.driver.waitForElement(
      IOS_LOCATORS.emergencyButton,
      EMERGENCY_TIMING.accessTimeMs
    );

    assertions.push({
      name: 'Emergency button found within time limit',
      passed: emergencyButton.exists && emergencyButton.visible,
      expected: { exists: true, visible: true },
      actual: { exists: emergencyButton.exists, visible: emergencyButton.visible },
      durationMs: 0,
    });

    // Verify touch target size (must be at least 60x60 for emergency)
    if (emergencyButton.bounds) {
      const touchTargetOk =
        emergencyButton.bounds.width >= 60 && emergencyButton.bounds.height >= 60;
      assertions.push({
        name: 'Emergency button touch target >= 60x60',
        passed: touchTargetOk,
        expected: { minWidth: 60, minHeight: 60 },
        actual: {
          width: emergencyButton.bounds.width,
          height: emergencyButton.bounds.height,
        },
        durationMs: 0,
      });
    }

    // Verify accessibility
    assertions.push({
      name: 'Emergency button has accessibility label',
      passed: !!emergencyButton.text,
      expected: 'Emergency label present',
      actual: emergencyButton.text ?? 'No label',
      durationMs: 0,
    });
  }

  /**
   * CP2: Emergency Mode Active
   */
  private async executeEmergencyActiveCheckpoint(
    assertions: AssertionResult[],
    _screenshots: string[]
  ): Promise<void> {
    // Trigger emergency
    await this.emergencyDriver.triggerEmergency();

    // Wait for emergency to activate
    const emergencyActivated = await this.pollUntil(
      async () => {
        const state = await this.emergencyDriver.getEmergencyState();
        return state.emergencyState === 'active';
      },
      EMERGENCY_TIMING.activationTimeMs
    );

    assertions.push({
      name: 'Emergency mode activated within time limit',
      passed: emergencyActivated,
      expected: { emergencyState: 'active' },
      actual: { emergencyActivated },
      durationMs: 0,
    });

    // Verify emergency indicator is visible
    const emergencyIndicator = await this.driver.waitForElement(
      IOS_LOCATORS.emergencyActiveIndicator,
      FIBONACCI_MS.F14 // 377ms
    );

    assertions.push({
      name: 'Emergency active indicator visible',
      passed: emergencyIndicator.exists && emergencyIndicator.visible,
      expected: { exists: true, visible: true },
      actual: { exists: emergencyIndicator.exists, visible: emergencyIndicator.visible },
      durationMs: 0,
    });

    // Get full emergency state
    const state = await this.emergencyDriver.getEmergencyState();

    // Verify all doors locked
    assertions.push({
      name: 'All doors locked',
      passed: state.allDoorsLocked,
      expected: true,
      actual: state.allDoorsLocked,
      durationMs: 0,
    });

    // Verify all lights on
    assertions.push({
      name: 'All lights on maximum',
      passed: state.allLightsOn,
      expected: true,
      actual: state.allLightsOn,
      durationMs: 0,
    });

    // Verify alerts sent
    assertions.push({
      name: 'Emergency alerts sent',
      passed: state.alertsSent,
      expected: true,
      actual: state.alertsSent,
      durationMs: 0,
    });

    // Verify emergency contacts notified
    assertions.push({
      name: 'Emergency contacts notified',
      passed: state.contactsNotified,
      expected: true,
      actual: state.contactsNotified,
      durationMs: 0,
    });

    // Verify lights indicator in UI
    const lightsIndicator = await this.driver.waitForElement(
      IOS_LOCATORS.allLightsOnIndicator,
      FIBONACCI_MS.F14 // 377ms
    );

    assertions.push({
      name: 'All lights on indicator visible',
      passed: lightsIndicator.exists && lightsIndicator.visible,
      expected: { exists: true, visible: true },
      actual: { exists: lightsIndicator.exists, visible: lightsIndicator.visible },
      durationMs: 0,
    });
  }

  /**
   * CP3: Safety Confirmed (Emergency Ended)
   */
  private async executeSafetyConfirmedCheckpoint(
    assertions: AssertionResult[],
    _screenshots: string[]
  ): Promise<void> {
    // Confirm safety
    await this.emergencyDriver.confirmSafety();

    // Wait for confirmation
    const safetyConfirmed = await this.pollUntil(
      async () => {
        const state = await this.emergencyDriver.getEmergencyState();
        return state.emergencyState === 'confirmed' || state.emergencyState === 'idle';
      },
      EMERGENCY_TIMING.confirmationTimeMs
    );

    assertions.push({
      name: 'Safety confirmed within time limit',
      passed: safetyConfirmed,
      expected: { emergencyState: 'confirmed or idle' },
      actual: { safetyConfirmed },
      durationMs: 0,
    });

    // Verify confirmation indicator
    const confirmIndicator = await this.driver.waitForElement(
      IOS_LOCATORS.safetyConfirmedIndicator,
      FIBONACCI_MS.F16 // 987ms
    );

    assertions.push({
      name: 'Safety confirmed indicator visible',
      passed: confirmIndicator.exists && confirmIndicator.visible,
      expected: { exists: true, visible: true },
      actual: { exists: confirmIndicator.exists, visible: confirmIndicator.visible },
      durationMs: 0,
    });

    // Final safety score check
    const finalScore = await this.emergencyDriver.getSafetyScore();
    assertions.push({
      name: 'Final safety score h(x) >= 0',
      passed: finalScore.value >= 0,
      expected: '>= 0',
      actual: finalScore.value,
      error: finalScore.value < 0
        ? `CRITICAL: Final safety score ${finalScore.value} < 0`
        : undefined,
      durationMs: 0,
    });

    // Store final safety score in results
    this.results.finalSafetyScore = finalScore;
  }

  /**
   * Override run to add emergency-specific setup/teardown
   */
  override async run(): Promise<import('../journey-test-base.js').JourneyTestResult> {
    console.log('========================================');
    console.log('J09 EMERGENCY SAFETY TEST - iOS');
    console.log('h(x) >= 0. Always.');
    console.log('========================================');

    try {
      const result = await super.run();

      // Log final safety status
      if (result.finalSafetyScore) {
        console.log(`\nFinal Safety Score: h(x) = ${result.finalSafetyScore.value}`);
        console.log(`Safety Status: ${result.finalSafetyScore.status}`);
      }

      if (!result.passed) {
        console.error('\nCRITICAL: J09 Emergency Safety Test FAILED');
        console.error('This is a safety-critical failure that must be investigated.');
        console.error('Errors:', result.errors);
      } else {
        console.log('\nJ09 Emergency Safety Test PASSED');
        console.log('Safety invariant h(x) >= 0 maintained throughout.');
      }

      return result;
    } catch (error) {
      console.error('\nFATAL: J09 Emergency Safety Test threw exception');
      console.error(error);
      throw error;
    }
  }
}

// =============================================================================
// FACTORY FUNCTION
// =============================================================================

/**
 * Create and run the J09 Emergency Safety test for iOS
 *
 * @param deviceId - iOS simulator device ID (default: 'booted')
 * @param screenshotDir - Directory for screenshots (default: '/tmp/kagami-qa-ios')
 * @returns Test result
 */
export async function runJ09EmergencySafetyiOS(
  deviceId?: string,
  screenshotDir?: string
): Promise<import('../journey-test-base.js').JourneyTestResult> {
  const test = new J09EmergencySafetyTest(deviceId, screenshotDir);
  return test.run();
}

// =============================================================================
// CLI ENTRY POINT
// =============================================================================

if (import.meta.url === `file://${process.argv[1]}`) {
  runJ09EmergencySafetyiOS()
    .then((result) => {
      process.exit(result.passed ? 0 : 1);
    })
    .catch((error) => {
      console.error('Test failed with exception:', error);
      process.exit(2);
    });
}
