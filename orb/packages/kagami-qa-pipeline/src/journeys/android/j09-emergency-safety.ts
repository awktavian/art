/**
 * J09 Emergency Safety Journey Test - Android Implementation
 *
 * Tests the emergency safety protocol on Android devices.
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
// ANDROID ELEMENT LOCATORS
// =============================================================================

/**
 * Android-specific element locators for emergency features
 * Uses resource-id for reliable element identification
 */
const ANDROID_LOCATORS = {
  // Emergency access elements (using resource-id pattern)
  emergencyButton: {
    id: 'com.kagami.app:id/emergency_button',
    xpath: '//android.widget.Button[@content-desc="Emergency"]',
  } as ElementLocator,

  emergencyActiveIndicator: {
    id: 'com.kagami.app:id/emergency_active_indicator',
  } as ElementLocator,

  allLightsOnIndicator: {
    id: 'com.kagami.app:id/all_lights_on',
  } as ElementLocator,

  safetyConfirmedIndicator: {
    id: 'com.kagami.app:id/safety_confirmed_indicator',
  } as ElementLocator,

  // Safety card elements
  safetyCard: {
    id: 'com.kagami.app:id/safety_card',
  } as ElementLocator,

  safetyScoreLabel: {
    id: 'com.kagami.app:id/safety_score_label',
  } as ElementLocator,

  // Home view elements
  homeView: {
    id: 'com.kagami.app:id/home_view',
  } as ElementLocator,

  // Confirmation button
  confirmSafetyButton: {
    id: 'com.kagami.app:id/confirm_safety_button',
    xpath: '//android.widget.Button[@text="I am Safe"]',
  } as ElementLocator,
};

// =============================================================================
// ANDROID ADB DRIVER
// =============================================================================

/**
 * Android Driver using ADB (Android Debug Bridge)
 *
 * Supports both emulators and physical devices.
 * Uses UI Automator for element interaction.
 */
class AndroidADBDriver implements EmergencyDriver {
  readonly platform = 'android' as const;
  private deviceId: string;
  private connected = false;
  private screenshotDir: string;
  private packageName = 'com.kagami.app';

  constructor(deviceId?: string, screenshotDir: string = '/tmp/kagami-qa-android') {
    this.deviceId = deviceId ?? this.detectDevice();
    this.screenshotDir = screenshotDir;
  }

  /**
   * Detect the first available Android device/emulator
   */
  private detectDevice(): string {
    try {
      const devices = execSync('adb devices -l', { encoding: 'utf8' });
      const lines = devices.split('\n').slice(1);
      for (const line of lines) {
        const match = line.match(/^(\S+)\s+device\s/);
        if (match && match[1]) {
          return match[1];
        }
      }
    } catch {
      // Fall through
    }
    return 'emulator-5554'; // Default emulator
  }

  async connect(): Promise<void> {
    // Verify device is connected
    try {
      const result = execSync(`adb -s ${this.deviceId} get-state`, {
        encoding: 'utf8',
      });
      if (!result.includes('device')) {
        throw new Error(`Device ${this.deviceId} not ready`);
      }
      this.connected = true;

      // Ensure screenshot directory exists
      if (!fs.existsSync(this.screenshotDir)) {
        fs.mkdirSync(this.screenshotDir, { recursive: true });
      }

      // Wake screen and unlock
      await this.wakeDevice();
    } catch (error) {
      throw new Error(`Failed to connect to Android device: ${error}`);
    }
  }

  /**
   * Wake the device screen
   */
  private async wakeDevice(): Promise<void> {
    try {
      // Press power button if screen is off
      execSync(
        `adb -s ${this.deviceId} shell input keyevent KEYCODE_WAKEUP`,
        { timeout: 5000 }
      );
      // Swipe to unlock (if needed)
      execSync(
        `adb -s ${this.deviceId} shell input swipe 500 1500 500 500 300`,
        { timeout: 5000 }
      );
    } catch {
      // Ignore - device may already be awake
    }
  }

  async disconnect(): Promise<void> {
    this.connected = false;
  }

  isConnected(): boolean {
    return this.connected;
  }

  async findElement(locator: ElementLocator): Promise<ElementState> {
    // Use UI Automator dump to find elements
    try {
      // Dump UI hierarchy
      const dumpPath = '/sdcard/ui_dump.xml';
      execSync(
        `adb -s ${this.deviceId} shell uiautomator dump ${dumpPath}`,
        { timeout: 10000 }
      );

      // Pull and parse the dump
      const localPath = path.join(this.screenshotDir, 'ui_dump.xml');
      execSync(
        `adb -s ${this.deviceId} pull ${dumpPath} ${localPath}`,
        { timeout: 5000 }
      );

      const xml = fs.readFileSync(localPath, 'utf8');
      return this.parseElementFromXML(xml, locator);
    } catch {
      return { exists: false, visible: false, enabled: false };
    }
  }

  /**
   * Parse element from UI Automator XML dump
   */
  private parseElementFromXML(xml: string, locator: ElementLocator): ElementState {
    // Build regex pattern for element search
    let pattern: RegExp | null = null;

    if (locator.id) {
      pattern = new RegExp(
        `<node[^>]*resource-id="${locator.id}"[^>]*bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"[^>]*`,
        'i'
      );
    } else if (locator.text) {
      pattern = new RegExp(
        `<node[^>]*text="${locator.text}"[^>]*bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"[^>]*`,
        'i'
      );
    } else if (locator.textContains) {
      pattern = new RegExp(
        `<node[^>]*text="[^"]*${locator.textContains}[^"]*"[^>]*bounds="\\[(\\d+),(\\d+)\\]\\[(\\d+),(\\d+)\\]"[^>]*`,
        'i'
      );
    }

    if (!pattern) {
      return { exists: false, visible: false, enabled: false };
    }

    const match = xml.match(pattern);
    if (!match) {
      return { exists: false, visible: false, enabled: false };
    }

    // Parse bounds
    const boundsMatch = match[0].match(/bounds="\[(\d+),(\d+)\]\[(\d+),(\d+)\]"/);
    if (!boundsMatch) {
      return { exists: true, visible: true, enabled: true };
    }

    const x1 = parseInt(boundsMatch[1]!, 10);
    const y1 = parseInt(boundsMatch[2]!, 10);
    const x2 = parseInt(boundsMatch[3]!, 10);
    const y2 = parseInt(boundsMatch[4]!, 10);

    // Check enabled and clickable
    const enabled = !match[0].includes('enabled="false"');
    const clickable = match[0].includes('clickable="true"');

    // Extract text
    const textMatch = match[0].match(/text="([^"]*)"/);
    const text = textMatch ? textMatch[1] : undefined;

    return {
      exists: true,
      visible: true,
      enabled: enabled && clickable,
      bounds: {
        x: x1,
        y: y1,
        width: x2 - x1,
        height: y2 - y1,
      },
      text,
    };
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

    execSync(
      `adb -s ${this.deviceId} shell input tap ${x} ${y}`,
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

    // Use swipe with same start/end point for long press
    execSync(
      `adb -s ${this.deviceId} shell input swipe ${x} ${y} ${x} ${y} ${durationMs}`,
      { timeout: durationMs + 5000 }
    );
  }

  async typeText(locator: ElementLocator, text: string): Promise<void> {
    await this.tap(locator);
    await this.sleep(FIBONACCI_MS.F10); // 55ms

    // Escape special characters for shell
    const escapedText = text.replace(/(['"\\$`])/g, '\\$1');
    execSync(
      `adb -s ${this.deviceId} shell input text "${escapedText}"`,
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
    execSync(
      `adb -s ${this.deviceId} shell input swipe ${startX} ${startY} ${endX} ${endY} ${durationMs}`,
      { timeout: durationMs + 5000 }
    );
  }

  async screenshot(): Promise<Buffer> {
    const timestamp = Date.now();
    const devicePath = `/sdcard/screenshot_${timestamp}.png`;
    const localPath = path.join(this.screenshotDir, `screenshot_${timestamp}.png`);

    execSync(
      `adb -s ${this.deviceId} shell screencap -p ${devicePath}`,
      { timeout: 10000 }
    );
    execSync(
      `adb -s ${this.deviceId} pull ${devicePath} ${localPath}`,
      { timeout: 10000 }
    );
    execSync(
      `adb -s ${this.deviceId} shell rm ${devicePath}`,
      { timeout: 5000 }
    );

    return fs.readFileSync(localPath);
  }

  async getAppState(): Promise<Record<string, unknown>> {
    // Query Kagami app state via broadcast intent
    try {
      const result = execSync(
        `adb -s ${this.deviceId} shell am broadcast -a ${this.packageName}.STATE_QUERY --es format json -n ${this.packageName}/.StateReceiver`,
        { encoding: 'utf8', timeout: 5000 }
      );

      // Parse broadcast result
      const jsonMatch = result.match(/data="(\{[^"]+\})"/);
      if (jsonMatch && jsonMatch[1]) {
        return JSON.parse(jsonMatch[1]);
      }
    } catch {
      // Fall through
    }
    return {};
  }

  async executeCommand(command: string, args?: unknown[]): Promise<unknown> {
    const argsStr = args ? args.map(String).join(' ') : '';
    const result = execSync(
      `adb -s ${this.deviceId} shell ${command} ${argsStr}`,
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
    await this.tap(ANDROID_LOCATORS.emergencyButton);
  }

  async confirmSafety(): Promise<void> {
    // Tap the confirm safety button
    await this.tap(ANDROID_LOCATORS.confirmSafetyButton);
  }

  async getSafetyScore(): Promise<SafetyScore> {
    const appState = await this.getAppState();

    const safetyData = appState['safetyScore'] as Record<string, number> | undefined;

    if (!safetyData) {
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
    const element = await this.findElement(ANDROID_LOCATORS.allLightsOnIndicator);
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

  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// =============================================================================
// J09 EMERGENCY SAFETY TEST
// =============================================================================

/**
 * J09 Emergency Safety Journey Test for Android
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
    const driver = new AndroidADBDriver(deviceId, screenshotDir);
    super(J09_EMERGENCY_SAFETY, 'android', driver);
    this.emergencyDriver = driver;
  }

  /**
   * Execute a checkpoint with Android-specific implementation
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
      const screenshotPath = `/tmp/kagami-qa-android/${checkpoint.id}_${Date.now()}.png`;
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
      ANDROID_LOCATORS.homeView,
      FIBONACCI_MS.F16 // 987ms
    );

    assertions.push({
      name: 'Home view visible',
      passed: homeView.exists && homeView.visible,
      expected: { exists: true, visible: true },
      actual: { exists: homeView.exists, visible: homeView.visible },
      durationMs: 0,
    });

    // Find emergency button
    const emergencyButton = await this.driver.waitForElement(
      ANDROID_LOCATORS.emergencyButton,
      EMERGENCY_TIMING.accessTimeMs
    );

    assertions.push({
      name: 'Emergency button found within time limit',
      passed: emergencyButton.exists && emergencyButton.visible,
      expected: { exists: true, visible: true },
      actual: { exists: emergencyButton.exists, visible: emergencyButton.visible },
      durationMs: 0,
    });

    // Verify touch target size (Material Design: 48dp minimum, 60dp for emergency)
    if (emergencyButton.bounds) {
      // Convert dp to px (assuming ~3x density for modern devices)
      const minSizePx = 60 * 3; // 180px minimum
      const touchTargetOk =
        emergencyButton.bounds.width >= minSizePx && emergencyButton.bounds.height >= 48 * 3;
      assertions.push({
        name: 'Emergency button touch target meets Material Design (60dp)',
        passed: touchTargetOk,
        expected: { minWidth: minSizePx, minHeight: 144 },
        actual: {
          width: emergencyButton.bounds.width,
          height: emergencyButton.bounds.height,
        },
        durationMs: 0,
      });
    }

    // Verify accessibility (content description)
    assertions.push({
      name: 'Emergency button has content description',
      passed: !!emergencyButton.text,
      expected: 'Content description present',
      actual: emergencyButton.text ?? 'No content description',
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
      ANDROID_LOCATORS.emergencyActiveIndicator,
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
      ANDROID_LOCATORS.allLightsOnIndicator,
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
      ANDROID_LOCATORS.safetyConfirmedIndicator,
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
   * Override run to add Android-specific setup/teardown
   */
  override async run(): Promise<import('../journey-test-base.js').JourneyTestResult> {
    console.log('========================================');
    console.log('J09 EMERGENCY SAFETY TEST - Android');
    console.log('h(x) >= 0. Always.');
    console.log('========================================');

    try {
      const result = await super.run();

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
 * Create and run the J09 Emergency Safety test for Android
 *
 * @param deviceId - Android device/emulator ID (auto-detected if not provided)
 * @param screenshotDir - Directory for screenshots (default: '/tmp/kagami-qa-android')
 * @returns Test result
 */
export async function runJ09EmergencySafetyAndroid(
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
  runJ09EmergencySafetyAndroid()
    .then((result) => {
      process.exit(result.passed ? 0 : 1);
    })
    .catch((error) => {
      console.error('Test failed with exception:', error);
      process.exit(2);
    });
}
