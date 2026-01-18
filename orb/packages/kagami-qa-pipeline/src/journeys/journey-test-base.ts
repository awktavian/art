/**
 * Base Types and Utilities for Platform-Specific Journey Tests
 *
 * This module provides the foundation for implementing journey tests
 * across all Kagami platforms. Each platform extends these base types
 * with platform-specific interaction methods.
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

import { EventEmitter } from 'events';
import {
  JourneySpec,
  Checkpoint,
  Phase,
  Platform,
  JourneyId,
} from './canonical-journeys.js';

// =============================================================================
// TIMING CONSTANTS (Fibonacci-based)
// =============================================================================

/**
 * Fibonacci timing values for UI interactions
 * Used for natural-feeling animations and timeouts
 */
export const FIBONACCI_MS = {
  F1: 1,
  F2: 1,
  F3: 2,
  F4: 3,
  F5: 5,
  F6: 8,
  F7: 13,
  F8: 21,
  F9: 34,
  F10: 55,
  F11: 89,
  F12: 144,
  F13: 233,
  F14: 377,
  F15: 610,
  F16: 987,
  F17: 1597,
  F18: 2584,
  F19: 4181,
  F20: 6765,
} as const;

/**
 * Standard timing for emergency tests
 * Emergency response MUST be FAST
 */
export const EMERGENCY_TIMING = {
  /** Maximum time to access emergency button (2 taps max) */
  accessTimeMs: FIBONACCI_MS.F18, // 2584ms (~2.5s)
  /** Maximum time for emergency to activate after trigger */
  activationTimeMs: FIBONACCI_MS.F16, // 987ms (~1s)
  /** Maximum time for confirmation after safety confirmed */
  confirmationTimeMs: FIBONACCI_MS.F18, // 2584ms (~2.5s)
  /** Polling interval for state checks */
  pollIntervalMs: FIBONACCI_MS.F11, // 89ms
} as const;

// =============================================================================
// SAFETY TYPES
// =============================================================================

/**
 * Safety score type for h(x) >= 0 verification
 *
 * The safety score represents the system's safety state:
 * - Positive values indicate safe operation
 * - Zero indicates boundary (still safe but at limit)
 * - Negative values indicate unsafe state (MUST NEVER HAPPEN)
 */
export interface SafetyScore {
  /** Current h(x) value - MUST be >= 0 */
  value: number;
  /** Components contributing to safety score */
  components: {
    /** Door lock status contribution */
    doorLocks: number;
    /** Light status contribution */
    lights: number;
    /** Alert system contribution */
    alerts: number;
    /** Emergency contacts contribution */
    emergencyContacts: number;
  };
  /** Timestamp of score calculation */
  timestamp: number;
  /** Human-readable status */
  status: 'safe' | 'boundary' | 'unsafe';
}

/**
 * Emergency state enum
 */
export type EmergencyState =
  | 'idle'
  | 'triggered'
  | 'activating'
  | 'active'
  | 'confirming'
  | 'confirmed'
  | 'error';

/**
 * Emergency system state snapshot
 */
export interface EmergencySystemState {
  /** Current emergency state */
  emergencyState: EmergencyState;
  /** Safety score (h(x)) */
  safetyScore: SafetyScore;
  /** All doors locked */
  allDoorsLocked: boolean;
  /** All lights on maximum */
  allLightsOn: boolean;
  /** Emergency alerts sent */
  alertsSent: boolean;
  /** Emergency contacts notified */
  contactsNotified: boolean;
  /** Timestamp of state capture */
  capturedAt: number;
}

// =============================================================================
// TEST RESULT TYPES
// =============================================================================

/**
 * Individual assertion result
 */
export interface AssertionResult {
  /** Assertion name */
  name: string;
  /** Whether assertion passed */
  passed: boolean;
  /** Expected value (for debugging) */
  expected: unknown;
  /** Actual value (for debugging) */
  actual: unknown;
  /** Error message if failed - use empty string for no error instead of undefined */
  error?: string | undefined;
  /** Duration to complete assertion */
  durationMs: number;
}

/**
 * Checkpoint test result with video markers
 */
export interface CheckpointTestResult {
  /** Checkpoint ID from canonical spec */
  checkpointId: string;
  /** Checkpoint name */
  checkpointName: string;
  /** Whether checkpoint passed */
  passed: boolean;
  /** All assertions for this checkpoint */
  assertions: AssertionResult[];
  /** Duration in milliseconds */
  durationMs: number;
  /** Maximum duration allowed */
  maxDurationMs: number;
  /** Video timestamp for start of checkpoint */
  videoStartMs?: number;
  /** Video timestamp for end of checkpoint */
  videoEndMs?: number;
  /** Screenshot paths captured during checkpoint */
  screenshots: string[];
  /** Error if checkpoint failed */
  error?: string | undefined;
}

/**
 * Phase test result
 */
export interface PhaseTestResult {
  /** Phase ID from canonical spec */
  phaseId: string;
  /** Phase name */
  phaseName: string;
  /** Whether phase passed */
  passed: boolean;
  /** Checkpoint results */
  checkpoints: CheckpointTestResult[];
  /** Total duration */
  durationMs: number;
  /** Errors encountered */
  errors: string[];
}

/**
 * Complete journey test result
 */
export interface JourneyTestResult {
  /** Journey ID */
  journeyId: JourneyId;
  /** Journey name */
  journeyName: string;
  /** Platform tested */
  platform: Platform;
  /** Whether journey passed */
  passed: boolean;
  /** All phase results */
  phases: PhaseTestResult[];
  /** Total duration */
  totalDurationMs: number;
  /** Safety score at end (for emergency tests) */
  finalSafetyScore?: SafetyScore;
  /** Video recording path */
  videoPath?: string;
  /** Test execution timestamp */
  executedAt: string;
  /** Errors encountered */
  errors: string[];
}

// =============================================================================
// DRIVER INTERFACES
// =============================================================================

/**
 * Element locator for platform-specific element identification
 */
export interface ElementLocator {
  /** Platform-native identifier (accessibilityIdentifier on iOS, resource-id on Android, etc.) */
  id?: string;
  /** Accessibility label */
  label?: string;
  /** XPath expression (cross-platform) */
  xpath?: string;
  /** CSS selector (web/desktop) */
  css?: string;
  /** Text content match */
  text?: string;
  /** Partial text match */
  textContains?: string;
  /** Class name */
  className?: string;
}

/**
 * Element state after interaction or query
 */
export interface ElementState {
  /** Element was found */
  exists: boolean;
  /** Element is visible */
  visible: boolean;
  /** Element is enabled/interactive */
  enabled: boolean;
  /** Element bounds (for tap target verification) */
  bounds?: {
    x: number;
    y: number;
    width: number;
    height: number;
  } | undefined;
  /** Element text content */
  text?: string | undefined;
  /** Element value (for inputs) */
  value?: string | undefined;
}

/**
 * Base driver interface that all platform drivers must implement
 */
export interface PlatformDriver {
  /** Platform this driver controls */
  readonly platform: Platform;

  /** Connect to the device/simulator */
  connect(): Promise<void>;

  /** Disconnect from the device */
  disconnect(): Promise<void>;

  /** Check if connected */
  isConnected(): boolean;

  /** Find an element by locator */
  findElement(locator: ElementLocator): Promise<ElementState>;

  /** Wait for element to appear */
  waitForElement(
    locator: ElementLocator,
    timeoutMs: number
  ): Promise<ElementState>;

  /** Tap on an element */
  tap(locator: ElementLocator): Promise<void>;

  /** Long press on an element */
  longPress(locator: ElementLocator, durationMs?: number): Promise<void>;

  /** Type text into an element */
  typeText(locator: ElementLocator, text: string): Promise<void>;

  /** Swipe gesture */
  swipe(
    startX: number,
    startY: number,
    endX: number,
    endY: number,
    durationMs?: number
  ): Promise<void>;

  /** Take a screenshot */
  screenshot(): Promise<Buffer>;

  /** Get current application state */
  getAppState(): Promise<Record<string, unknown>>;

  /** Execute platform-specific command */
  executeCommand(command: string, args?: unknown[]): Promise<unknown>;
}

/**
 * Emergency-specific driver interface with safety-critical operations
 */
export interface EmergencyDriver extends PlatformDriver {
  /** Get current emergency system state */
  getEmergencyState(): Promise<EmergencySystemState>;

  /** Trigger emergency mode */
  triggerEmergency(): Promise<void>;

  /** Confirm safety (end emergency) */
  confirmSafety(): Promise<void>;

  /** Get safety score (h(x)) */
  getSafetyScore(): Promise<SafetyScore>;

  /** Verify all doors are locked */
  verifyDoorsLocked(): Promise<boolean>;

  /** Verify all lights are at maximum */
  verifyLightsOn(): Promise<boolean>;

  /** Verify alerts were sent */
  verifyAlertsSent(): Promise<boolean>;

  /** Verify emergency contacts notified */
  verifyContactsNotified(): Promise<boolean>;
}

// =============================================================================
// BASE TEST CLASS
// =============================================================================

/**
 * Base class for journey tests
 *
 * Platform-specific implementations extend this class and provide
 * concrete driver implementations.
 */
export abstract class JourneyTestBase extends EventEmitter {
  protected journeySpec: JourneySpec;
  protected platform: Platform;
  protected driver: PlatformDriver;
  protected results: JourneyTestResult;
  protected startTime: number = 0;
  protected videoRecording: boolean = false;
  protected videoStartTime: number = 0;

  constructor(journeySpec: JourneySpec, platform: Platform, driver: PlatformDriver) {
    super();
    this.journeySpec = journeySpec;
    this.platform = platform;
    this.driver = driver;
    this.results = this.initializeResults();
  }

  /**
   * Initialize empty results structure
   */
  private initializeResults(): JourneyTestResult {
    return {
      journeyId: this.journeySpec.id,
      journeyName: this.journeySpec.name,
      platform: this.platform,
      passed: false,
      phases: [],
      totalDurationMs: 0,
      executedAt: new Date().toISOString(),
      errors: [],
    };
  }

  /**
   * Start video recording marker
   */
  protected startVideoMarker(): void {
    this.videoRecording = true;
    this.videoStartTime = Date.now();
  }

  /**
   * Get current video timestamp
   */
  protected getVideoTimestamp(): number {
    if (!this.videoRecording) return 0;
    return Date.now() - this.videoStartTime;
  }

  /**
   * Run the complete journey test
   */
  async run(): Promise<JourneyTestResult> {
    this.startTime = Date.now();
    this.results = this.initializeResults();

    this.emit('journey:started', {
      journeyId: this.journeySpec.id,
      platform: this.platform,
    });

    try {
      // Connect to driver
      await this.driver.connect();

      // Execute each phase
      for (const phase of this.journeySpec.phases) {
        const phaseResult = await this.executePhase(phase);
        this.results.phases.push(phaseResult);

        this.emit('phase:completed', {
          phaseId: phase.id,
          passed: phaseResult.passed,
        });

        // Stop on first failure for critical journeys
        if (!phaseResult.passed && this.isCriticalJourney()) {
          this.results.errors.push(`Critical phase ${phase.id} failed`);
          break;
        }
      }

      // Calculate final results
      this.results.totalDurationMs = Date.now() - this.startTime;
      this.results.passed = this.results.phases.every((p) => p.passed);

    } catch (error) {
      this.results.errors.push(
        error instanceof Error ? error.message : String(error)
      );
      this.results.passed = false;
    } finally {
      await this.driver.disconnect();
    }

    this.emit('journey:completed', this.results);
    return this.results;
  }

  /**
   * Execute a single phase
   */
  protected async executePhase(phase: Phase): Promise<PhaseTestResult> {
    const phaseStart = Date.now();
    const checkpointResults: CheckpointTestResult[] = [];
    const errors: string[] = [];

    this.emit('phase:started', { phaseId: phase.id });

    for (const checkpoint of phase.checkpoints) {
      try {
        const result = await this.executeCheckpoint(checkpoint);
        checkpointResults.push(result);

        this.emit('checkpoint:completed', {
          checkpointId: checkpoint.id,
          passed: result.passed,
        });

        if (!result.passed) {
          errors.push(`Checkpoint ${checkpoint.id} failed: ${result.error}`);
        }
      } catch (error) {
        const errorMsg = error instanceof Error ? error.message : String(error);
        errors.push(`Checkpoint ${checkpoint.id} error: ${errorMsg}`);

        checkpointResults.push({
          checkpointId: checkpoint.id,
          checkpointName: checkpoint.name,
          passed: false,
          assertions: [],
          durationMs: Date.now() - phaseStart,
          maxDurationMs: checkpoint.maxDurationMs,
          screenshots: [],
          error: errorMsg,
        });
      }
    }

    return {
      phaseId: phase.id,
      phaseName: phase.name,
      passed: errors.length === 0,
      checkpoints: checkpointResults,
      durationMs: Date.now() - phaseStart,
      errors,
    };
  }

  /**
   * Execute a single checkpoint - must be implemented by platform-specific class
   */
  protected abstract executeCheckpoint(
    checkpoint: Checkpoint
  ): Promise<CheckpointTestResult>;

  /**
   * Check if this is a critical journey that should stop on first failure
   */
  protected isCriticalJourney(): boolean {
    // Emergency safety is always critical
    return this.journeySpec.id === 'J09_EMERGENCY_SAFETY';
  }

  /**
   * Assert a condition with timing
   */
  protected async assert(
    name: string,
    condition: () => Promise<boolean>,
    expected: unknown,
    actual: () => Promise<unknown>
  ): Promise<AssertionResult> {
    const start = Date.now();
    try {
      const passed = await condition();
      const actualValue = await actual();
      return {
        name,
        passed,
        expected,
        actual: actualValue,
        durationMs: Date.now() - start,
      };
    } catch (error) {
      return {
        name,
        passed: false,
        expected,
        actual: undefined,
        error: error instanceof Error ? error.message : String(error),
        durationMs: Date.now() - start,
      };
    }
  }

  /**
   * Assert safety score h(x) >= 0
   *
   * This is the CRITICAL safety assertion that MUST NEVER fail
   */
  protected assertSafetyScore(score: SafetyScore): AssertionResult {
    const passed = score.value >= 0;
    return {
      name: 'h(x) >= 0 (Safety Invariant)',
      passed,
      expected: '>= 0',
      actual: score.value,
      error: passed ? undefined : `CRITICAL: Safety violation h(x) = ${score.value} < 0`,
      durationMs: 0,
    };
  }

  /**
   * Wait with timeout
   */
  protected async wait(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Poll for condition with timeout
   */
  protected async pollUntil(
    condition: () => Promise<boolean>,
    timeoutMs: number,
    intervalMs: number = EMERGENCY_TIMING.pollIntervalMs
  ): Promise<boolean> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      if (await condition()) {
        return true;
      }
      await this.wait(intervalMs);
    }
    return false;
  }
}

// =============================================================================
// EXPORTS
// =============================================================================

export {
  JourneySpec,
  Checkpoint,
  Phase,
  Platform,
  JourneyId,
};
