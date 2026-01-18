/**
 * Kagami QA Pipeline - Journey Tests
 *
 * This module exports all journey test specifications and implementations.
 *
 * Journey tests verify user flows across all Kagami platforms using
 * Byzantine quality scoring and the h(x) >= 0 safety invariant.
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

// =============================================================================
// CANONICAL JOURNEY SPECIFICATIONS
// =============================================================================

export {
  // Platform definitions
  Platform,
  PlatformCapabilities,
  PLATFORM_CAPABILITIES,

  // Journey identifiers
  JourneyId,

  // Journey structure types
  Checkpoint,
  Phase,
  JourneySpec,

  // Constellation types
  ConstellationRole,
  ConstellationDevice,
  ConstellationJourneySpec,

  // Single-device journeys
  J01_MORNING_ROUTINE,
  J02_SCENE_ACTIVATION,
  J03_ROOM_CONTROL,
  J04_VOICE_COMMAND,
  J05_QUICK_ACTIONS,
  J06_GLANCEABLE_STATUS,
  J07_SETTINGS_MANAGEMENT,
  J08_HOUSEHOLD_MEMBER_SWITCH,
  J09_EMERGENCY_SAFETY,
  J10_FULL_EXPLORATION,

  // Constellation journeys
  C01_WATCH_TO_PHONE_HANDOFF,
  C02_MULTI_ROOM_ORCHESTRATION,
  C03_SPATIAL_TO_AMBIENT_TRANSITION,
  C04_VOICE_COMMAND_ROUTING,
  C05_EMERGENCY_ALL_DEVICES,

  // Journey collections
  SINGLE_DEVICE_JOURNEYS,
  CONSTELLATION_JOURNEYS,

  // Utility functions
  getJourneysForPlatform,
  getConstellationJourneysForPlatform,
  validateJourneyResult,
} from './canonical-journeys.js';

// =============================================================================
// JOURNEY TEST BASE
// =============================================================================

export {
  // Timing constants
  FIBONACCI_MS,
  EMERGENCY_TIMING,

  // Safety types
  SafetyScore,
  EmergencyState,
  EmergencySystemState,

  // Test result types
  AssertionResult,
  CheckpointTestResult,
  PhaseTestResult,
  JourneyTestResult,

  // Driver interfaces
  ElementLocator,
  ElementState,
  PlatformDriver,
  EmergencyDriver,

  // Base test class
  JourneyTestBase,
} from './journey-test-base.js';

// =============================================================================
// PLATFORM-SPECIFIC J09 EMERGENCY SAFETY TESTS
// =============================================================================

// iOS
export {
  J09EmergencySafetyTest as J09EmergencySafetyTestiOS,
  runJ09EmergencySafetyiOS,
} from './ios/index.js';

// Android
export {
  J09EmergencySafetyTest as J09EmergencySafetyTestAndroid,
  runJ09EmergencySafetyAndroid,
} from './android/index.js';

// Desktop
export {
  J09EmergencySafetyTest as J09EmergencySafetyTestDesktop,
  runJ09EmergencySafetyDesktop,
} from './desktop/index.js';

// Hub
export {
  J09EmergencySafetyTest as J09EmergencySafetyTestHub,
  runJ09EmergencySafetyHub,
} from './hub/index.js';

// =============================================================================
// CONVENIENCE: RUN ALL J09 TESTS
// =============================================================================

import { runJ09EmergencySafetyiOS } from './ios/index.js';
import { runJ09EmergencySafetyAndroid } from './android/index.js';
import { runJ09EmergencySafetyDesktop } from './desktop/index.js';
import { runJ09EmergencySafetyHub } from './hub/index.js';
import type { JourneyTestResult } from './journey-test-base.js';

/**
 * Run J09 Emergency Safety tests on all platforms
 *
 * This is a convenience function to verify the emergency safety protocol
 * across the entire Kagami ecosystem.
 *
 * h(x) >= 0. Always.
 *
 * @returns Results for all platforms
 */
export async function runJ09EmergencySafetyAllPlatforms(): Promise<{
  ios: JourneyTestResult | { error: string };
  android: JourneyTestResult | { error: string };
  desktop: JourneyTestResult | { error: string };
  hub: JourneyTestResult | { error: string };
  allPassed: boolean;
  summary: {
    totalPlatforms: number;
    passedPlatforms: number;
    failedPlatforms: string[];
    safetyInvariantMaintained: boolean;
  };
}> {
  console.log('========================================');
  console.log('J09 EMERGENCY SAFETY - ALL PLATFORMS');
  console.log('h(x) >= 0. Always.');
  console.log('========================================\n');

  const results = {
    ios: null as JourneyTestResult | { error: string } | null,
    android: null as JourneyTestResult | { error: string } | null,
    desktop: null as JourneyTestResult | { error: string } | null,
    hub: null as JourneyTestResult | { error: string } | null,
  };

  // Run tests in sequence to avoid resource conflicts
  // Hub should run first as it's the coordinator

  console.log('\n--- Hub (Coordinator) ---');
  try {
    results.hub = await runJ09EmergencySafetyHub();
  } catch (error) {
    results.hub = { error: error instanceof Error ? error.message : String(error) };
  }

  console.log('\n--- iOS ---');
  try {
    results.ios = await runJ09EmergencySafetyiOS();
  } catch (error) {
    results.ios = { error: error instanceof Error ? error.message : String(error) };
  }

  console.log('\n--- Android ---');
  try {
    results.android = await runJ09EmergencySafetyAndroid();
  } catch (error) {
    results.android = { error: error instanceof Error ? error.message : String(error) };
  }

  console.log('\n--- Desktop ---');
  try {
    results.desktop = await runJ09EmergencySafetyDesktop();
  } catch (error) {
    results.desktop = { error: error instanceof Error ? error.message : String(error) };
  }

  // Calculate summary
  const platforms = ['ios', 'android', 'desktop', 'hub'] as const;
  const failedPlatforms: string[] = [];
  let safetyInvariantMaintained = true;

  for (const platform of platforms) {
    const result = results[platform];
    if (!result) {
      failedPlatforms.push(platform);
      continue;
    }

    if ('error' in result) {
      failedPlatforms.push(platform);
    } else if (!result.passed) {
      failedPlatforms.push(platform);

      // Check if safety invariant was violated
      if (result.finalSafetyScore && result.finalSafetyScore.value < 0) {
        safetyInvariantMaintained = false;
      }
    }
  }

  const allPassed = failedPlatforms.length === 0;

  // Print summary
  console.log('\n========================================');
  console.log('J09 EMERGENCY SAFETY - SUMMARY');
  console.log('========================================');
  console.log(`Platforms Tested: ${platforms.length}`);
  console.log(`Passed: ${platforms.length - failedPlatforms.length}`);
  console.log(`Failed: ${failedPlatforms.length}`);
  if (failedPlatforms.length > 0) {
    console.log(`Failed Platforms: ${failedPlatforms.join(', ')}`);
  }
  console.log(`Safety Invariant h(x) >= 0: ${safetyInvariantMaintained ? 'MAINTAINED' : 'VIOLATED!'}`);
  console.log(`Overall: ${allPassed ? 'PASSED' : 'FAILED'}`);
  console.log('========================================\n');

  if (!safetyInvariantMaintained) {
    console.error('CRITICAL: Safety invariant h(x) >= 0 was VIOLATED!');
    console.error('This is a critical safety failure requiring immediate attention.');
  }

  return {
    ios: results.ios!,
    android: results.android!,
    desktop: results.desktop!,
    hub: results.hub!,
    allPassed,
    summary: {
      totalPlatforms: platforms.length,
      passedPlatforms: platforms.length - failedPlatforms.length,
      failedPlatforms,
      safetyInvariantMaintained,
    },
  };
}
