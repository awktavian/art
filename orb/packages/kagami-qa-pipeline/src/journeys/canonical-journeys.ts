/**
 * Canonical User Journey Specifications
 *
 * This file defines the SINGLE SOURCE OF TRUTH for all user journey tests
 * across ALL Kagami platforms. Every platform MUST implement these exact
 * journeys with platform-appropriate interactions.
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

import { z } from 'zod';

// =============================================================================
// PLATFORM DEFINITIONS
// =============================================================================

/**
 * All supported platforms in the Kagami ecosystem
 */
export const Platform = z.enum([
  'ios',
  'android',
  'watchos',
  'wearos',
  'tvos',
  'visionos',
  'androidxr',
  'desktop',
  'hub',
]);
export type Platform = z.infer<typeof Platform>;

/**
 * Platform capabilities determine which journeys are applicable
 */
export const PlatformCapabilities = z.object({
  hasTouch: z.boolean(),
  hasVoice: z.boolean(),
  hasSpatial: z.boolean(),
  hasHaptics: z.boolean(),
  hasWatch: z.boolean(),
  hasTV: z.boolean(),
  hasKeyboard: z.boolean(),
  hasCrown: z.boolean(),
  hasGaze: z.boolean(),
  hasHandTracking: z.boolean(),
  hasMesh: z.boolean(),
  isAmbient: z.boolean(),
});
export type PlatformCapabilities = z.infer<typeof PlatformCapabilities>;

/**
 * Platform capability matrix
 */
export const PLATFORM_CAPABILITIES: Record<Platform, PlatformCapabilities> = {
  ios: {
    hasTouch: true,
    hasVoice: true,
    hasSpatial: false,
    hasHaptics: true,
    hasWatch: false,
    hasTV: false,
    hasKeyboard: false,
    hasCrown: false,
    hasGaze: false,
    hasHandTracking: false,
    hasMesh: true,
    isAmbient: false,
  },
  android: {
    hasTouch: true,
    hasVoice: true,
    hasSpatial: false,
    hasHaptics: true,
    hasWatch: false,
    hasTV: false,
    hasKeyboard: false,
    hasCrown: false,
    hasGaze: false,
    hasHandTracking: false,
    hasMesh: true,
    isAmbient: false,
  },
  watchos: {
    hasTouch: true,
    hasVoice: true,
    hasSpatial: false,
    hasHaptics: true,
    hasWatch: true,
    hasTV: false,
    hasKeyboard: false,
    hasCrown: true,
    hasGaze: false,
    hasHandTracking: false,
    hasMesh: true,
    isAmbient: true,
  },
  wearos: {
    hasTouch: true,
    hasVoice: true,
    hasSpatial: false,
    hasHaptics: true,
    hasWatch: true,
    hasTV: false,
    hasKeyboard: false,
    hasCrown: true,
    hasGaze: false,
    hasHandTracking: false,
    hasMesh: true,
    isAmbient: true,
  },
  tvos: {
    hasTouch: false,
    hasVoice: true,
    hasSpatial: false,
    hasHaptics: false,
    hasWatch: false,
    hasTV: true,
    hasKeyboard: false,
    hasCrown: false,
    hasGaze: false,
    hasHandTracking: false,
    hasMesh: true,
    isAmbient: false,
  },
  visionos: {
    hasTouch: false,
    hasVoice: true,
    hasSpatial: true,
    hasHaptics: true,
    hasWatch: false,
    hasTV: false,
    hasKeyboard: false,
    hasCrown: true,
    hasGaze: true,
    hasHandTracking: true,
    hasMesh: true,
    isAmbient: false,
  },
  androidxr: {
    hasTouch: false,
    hasVoice: true,
    hasSpatial: true,
    hasHaptics: true,
    hasWatch: false,
    hasTV: false,
    hasKeyboard: false,
    hasCrown: false,
    hasGaze: true,
    hasHandTracking: true,
    hasMesh: true,
    isAmbient: false,
  },
  desktop: {
    hasTouch: false,
    hasVoice: true,
    hasSpatial: false,
    hasHaptics: false,
    hasWatch: false,
    hasTV: false,
    hasKeyboard: true,
    hasCrown: false,
    hasGaze: false,
    hasHandTracking: false,
    hasMesh: true,
    isAmbient: false,
  },
  hub: {
    hasTouch: false,
    hasVoice: true,
    hasSpatial: false,
    hasHaptics: false,
    hasWatch: false,
    hasTV: false,
    hasKeyboard: false,
    hasCrown: false,
    hasGaze: false,
    hasHandTracking: false,
    hasMesh: true,
    isAmbient: true,
  },
};

// =============================================================================
// JOURNEY DEFINITIONS
// =============================================================================

/**
 * Journey IDs - canonical identifiers for all journeys
 */
export const JourneyId = z.enum([
  // Single-device journeys (J01-J10)
  'J01_MORNING_ROUTINE',
  'J02_SCENE_ACTIVATION',
  'J03_ROOM_CONTROL',
  'J04_VOICE_COMMAND',
  'J05_QUICK_ACTIONS',
  'J06_GLANCEABLE_STATUS',
  'J07_SETTINGS_MANAGEMENT',
  'J08_HOUSEHOLD_MEMBER_SWITCH',
  'J09_EMERGENCY_SAFETY',
  'J10_FULL_EXPLORATION',

  // Constellation journeys (C01-C05)
  'C01_WATCH_TO_PHONE_HANDOFF',
  'C02_MULTI_ROOM_ORCHESTRATION',
  'C03_SPATIAL_TO_AMBIENT_TRANSITION',
  'C04_VOICE_COMMAND_ROUTING',
  'C05_EMERGENCY_ALL_DEVICES',
]);
export type JourneyId = z.infer<typeof JourneyId>;

/**
 * Checkpoint definition - what to verify at each step
 */
export const Checkpoint = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  /** Required UI element identifiers to verify */
  requiredElements: z.array(z.string()),
  /** Expected state after checkpoint */
  expectedState: z.record(z.string(), z.unknown()).optional(),
  /** Accessibility requirements */
  accessibility: z.object({
    minTouchTarget: z.number().default(44),
    requiresLabel: z.boolean().default(true),
    requiresHint: z.boolean().default(false),
  }).optional(),
  /** Maximum duration in ms (Fibonacci timing) */
  maxDurationMs: z.number(),
  /** Haptic feedback expected (if platform supports) */
  expectedHaptic: z.enum(['none', 'light', 'medium', 'heavy', 'success', 'error']).optional(),
});
export type Checkpoint = z.infer<typeof Checkpoint>;

/**
 * Phase definition - a group of related checkpoints
 */
export const Phase = z.object({
  id: z.string(),
  name: z.string(),
  description: z.string(),
  checkpoints: z.array(Checkpoint),
  /** Platform-specific interaction type */
  interactionType: z.enum([
    'tap',
    'swipe',
    'scroll',
    'voice',
    'gaze',
    'pinch',
    'crown',
    'remote',
    'keyboard',
    'ambient',
  ]),
});
export type Phase = z.infer<typeof Phase>;

/**
 * Journey specification - complete definition of a user journey
 */
export const JourneySpec = z.object({
  id: JourneyId,
  name: z.string(),
  description: z.string(),
  /** Which platforms must implement this journey */
  requiredPlatforms: z.array(Platform),
  /** Minimum capabilities required */
  requiredCapabilities: z.array(z.string()),
  /** Phases in order */
  phases: z.array(Phase),
  /** Expected total duration in ms */
  expectedDurationMs: z.number(),
  /** Personas this journey tests */
  personas: z.array(z.string()),
  /** Byzantine quality dimensions to verify */
  qualityDimensions: z.object({
    technical: z.boolean().default(true),
    aesthetic: z.boolean().default(true),
    accessibility: z.boolean().default(true),
    emotional: z.boolean().default(true),
    polish: z.boolean().default(true),
    delight: z.boolean().default(true),
  }),
});
export type JourneySpec = z.infer<typeof JourneySpec>;

// =============================================================================
// CANONICAL JOURNEY SPECIFICATIONS
// =============================================================================

/**
 * J01: Morning Routine Journey
 *
 * User wakes up and uses Kagami to start their day.
 * Tests: App launch -> Status check -> Scene activation -> Room review
 */
export const J01_MORNING_ROUTINE: JourneySpec = {
  id: 'J01_MORNING_ROUTINE',
  name: 'Morning Routine',
  description: 'User wakes up and activates morning routine across home',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop', 'hub'],
  requiredCapabilities: [],
  personas: ['P1_AL_RASHID', 'P3_SOFIA', 'P6_OKONKWO', 'P11_VOLKOV', 'P12_OCONNOR'],
  expectedDurationMs: 30000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_LAUNCH',
      name: 'App Launch',
      description: 'Launch app and reach home screen',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP1_APP_LAUNCHED',
          name: 'App Launched',
          description: 'App has launched and is responsive',
          requiredElements: ['app_root', 'loading_indicator'],
          maxDurationMs: 3000,
          expectedHaptic: 'none',
        },
        {
          id: 'CP2_HOME_REACHED',
          name: 'Home Screen Reached',
          description: 'Home screen is displayed with status',
          requiredElements: ['home_view', 'safety_card', 'connection_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'light',
          accessibility: {
            minTouchTarget: 44,
            requiresLabel: true,
            requiresHint: false,
          },
        },
      ],
    },
    {
      id: 'P2_STATUS_CHECK',
      name: 'Home Status Check',
      description: 'Verify home status is visible and correct',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP3_SAFETY_VISIBLE',
          name: 'Safety Status Visible',
          description: 'Safety card shows current home status',
          requiredElements: ['safety_card', 'safety_status_text'],
          maxDurationMs: 1000,
          expectedHaptic: 'none',
        },
        {
          id: 'CP4_CONNECTION_STATUS',
          name: 'Connection Status',
          description: 'Connection indicator shows hub connectivity',
          requiredElements: ['connection_indicator'],
          expectedState: { connected: true },
          maxDurationMs: 1000,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P3_SCENE_ACTIVATION',
      name: 'Morning Scene Activation',
      description: 'Navigate to scenes and activate morning scene',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP5_SCENES_NAVIGATED',
          name: 'Scenes Screen',
          description: 'Navigated to scenes tab/screen',
          requiredElements: ['scenes_view', 'scenes_list'],
          maxDurationMs: 1000,
          expectedHaptic: 'light',
        },
        {
          id: 'CP6_MORNING_FOUND',
          name: 'Morning Scene Found',
          description: 'Morning/wake up scene is visible',
          requiredElements: ['scene_card_morning'],
          maxDurationMs: 1000,
          expectedHaptic: 'none',
        },
        {
          id: 'CP7_SCENE_ACTIVATED',
          name: 'Scene Activated',
          description: 'Morning scene has been activated',
          requiredElements: ['scene_active_indicator'],
          expectedState: { activeScene: 'morning' },
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
    },
    {
      id: 'P4_ROOM_REVIEW',
      name: 'Room Status Review',
      description: 'Review room status after scene activation',
      interactionType: 'scroll',
      checkpoints: [
        {
          id: 'CP8_ROOMS_NAVIGATED',
          name: 'Rooms Screen',
          description: 'Navigated to rooms tab/screen',
          requiredElements: ['rooms_view', 'rooms_list'],
          maxDurationMs: 1000,
          expectedHaptic: 'light',
        },
        {
          id: 'CP9_ROOMS_SCROLLED',
          name: 'Rooms Reviewed',
          description: 'Scrolled through room list',
          requiredElements: ['rooms_list'],
          maxDurationMs: 2000,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P5_RETURN_HOME',
      name: 'Return to Home',
      description: 'Return to home screen to complete journey',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP10_JOURNEY_COMPLETE',
          name: 'Journey Complete',
          description: 'Returned to home screen, journey complete',
          requiredElements: ['home_view'],
          maxDurationMs: 1000,
          expectedHaptic: 'success',
        },
      ],
    },
  ],
};

/**
 * J02: Scene Activation Journey
 *
 * User activates multiple scenes with haptic feedback.
 * Tests: Scene navigation -> Multiple activations -> Rapid switching
 */
export const J02_SCENE_ACTIVATION: JourneySpec = {
  id: 'J02_SCENE_ACTIVATION',
  name: 'Scene Activation with Haptics',
  description: 'User activates multiple scenes and experiences haptic feedback',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop'],
  requiredCapabilities: [],
  personas: ['P1_AL_RASHID', 'P2_CHEN_WILLIAMS', 'P4_RIVERA', 'P5_JACKSON', 'P10_HAVEN'],
  expectedDurationMs: 25000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_NAVIGATE_SCENES',
      name: 'Navigate to Scenes',
      description: 'Navigate from home to scenes screen',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP1_SCENES_SCREEN',
          name: 'Scenes Screen',
          description: 'Scenes screen is displayed',
          requiredElements: ['scenes_view', 'scenes_list'],
          maxDurationMs: 2000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P2_MOVIE_MODE',
      name: 'Activate Movie Mode',
      description: 'Activate the Movie Mode scene',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP2_MOVIE_FOUND',
          name: 'Movie Mode Found',
          description: 'Movie Mode scene card is visible',
          requiredElements: ['scene_card_movie'],
          maxDurationMs: 1000,
          expectedHaptic: 'none',
        },
        {
          id: 'CP3_MOVIE_ACTIVATED',
          name: 'Movie Mode Activated',
          description: 'Movie Mode scene is now active',
          requiredElements: ['scene_active_indicator'],
          expectedState: { activeScene: 'movie' },
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
    },
    {
      id: 'P3_RELAX_MODE',
      name: 'Activate Relax Mode',
      description: 'Switch to Relax scene',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP4_RELAX_ACTIVATED',
          name: 'Relax Mode Activated',
          description: 'Relax scene is now active',
          requiredElements: ['scene_active_indicator'],
          expectedState: { activeScene: 'relax' },
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
    },
    {
      id: 'P4_GOODNIGHT',
      name: 'Activate Goodnight',
      description: 'Activate Goodnight scene',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP5_GOODNIGHT_ACTIVATED',
          name: 'Goodnight Activated',
          description: 'Goodnight scene is now active',
          requiredElements: ['scene_active_indicator'],
          expectedState: { activeScene: 'goodnight' },
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
    },
    {
      id: 'P5_RAPID_SWITCH',
      name: 'Rapid Scene Switching',
      description: 'Rapidly switch between scenes to stress test',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP6_RAPID_COMPLETE',
          name: 'Rapid Switching Complete',
          description: 'Successfully rapid-switched 3 scenes',
          requiredElements: ['scenes_list'],
          maxDurationMs: 3000,
          expectedHaptic: 'medium',
        },
      ],
    },
  ],
};

/**
 * J03: Room Control Journey
 *
 * User controls devices in a specific room.
 * Tests: Room selection -> Light control -> Return
 */
export const J03_ROOM_CONTROL: JourneySpec = {
  id: 'J03_ROOM_CONTROL',
  name: 'Room Control Flow',
  description: 'User selects a room and controls devices within it',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop'],
  requiredCapabilities: [],
  personas: ['P1_AL_RASHID', 'P3_SOFIA', 'P6_OKONKWO', 'P9_NGUYEN', 'P11_VOLKOV'],
  expectedDurationMs: 20000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_NAVIGATE_ROOMS',
      name: 'Navigate to Rooms',
      description: 'Navigate to rooms screen',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP1_ROOMS_SCREEN',
          name: 'Rooms Screen',
          description: 'Rooms screen is displayed',
          requiredElements: ['rooms_view', 'rooms_list'],
          maxDurationMs: 2000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P2_SELECT_ROOM',
      name: 'Select Room',
      description: 'Select a room from the list',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP2_ROOM_SELECTED',
          name: 'Room Selected',
          description: 'Room detail view is displayed',
          requiredElements: ['room_detail_view', 'room_name'],
          maxDurationMs: 1500,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P3_CONTROL_LIGHTS',
      name: 'Control Lights',
      description: 'Adjust light levels in the room',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP3_LIGHTS_ADJUSTED',
          name: 'Lights Adjusted',
          description: 'Light level has been changed',
          requiredElements: ['light_control', 'light_level_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'medium',
        },
      ],
    },
    {
      id: 'P4_RETURN',
      name: 'Return to Rooms',
      description: 'Navigate back to rooms list',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP4_RETURNED',
          name: 'Returned to Rooms',
          description: 'Back at rooms list',
          requiredElements: ['rooms_view', 'rooms_list'],
          maxDurationMs: 1000,
          expectedHaptic: 'light',
        },
      ],
    },
  ],
};

/**
 * J04: Voice Command Journey
 *
 * User issues voice commands to control home.
 * Tests: Voice interface -> Command -> Response verification
 */
export const J04_VOICE_COMMAND: JourneySpec = {
  id: 'J04_VOICE_COMMAND',
  name: 'Voice Command',
  description: 'User controls home via voice commands',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'visionos', 'androidxr', 'desktop', 'hub'],
  requiredCapabilities: ['hasVoice'],
  personas: ['P2_CHEN_WILLIAMS', 'P3_SOFIA', 'P6_OKONKWO', 'P11_VOLKOV', 'P12_OCONNOR'],
  expectedDurationMs: 15000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_ACCESS_VOICE',
      name: 'Access Voice Interface',
      description: 'Open voice command interface',
      interactionType: 'voice',
      checkpoints: [
        {
          id: 'CP1_VOICE_READY',
          name: 'Voice Ready',
          description: 'Voice interface is listening',
          requiredElements: ['voice_indicator', 'listening_animation'],
          maxDurationMs: 2000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P2_ISSUE_COMMAND',
      name: 'Issue Command',
      description: 'Speak a command to the system',
      interactionType: 'voice',
      checkpoints: [
        {
          id: 'CP2_COMMAND_RECOGNIZED',
          name: 'Command Recognized',
          description: 'System has recognized the command',
          requiredElements: ['command_text', 'processing_indicator'],
          maxDurationMs: 3000,
          expectedHaptic: 'medium',
        },
      ],
    },
    {
      id: 'P3_VERIFY_RESPONSE',
      name: 'Verify Response',
      description: 'Verify the command was executed',
      interactionType: 'voice',
      checkpoints: [
        {
          id: 'CP3_COMMAND_EXECUTED',
          name: 'Command Executed',
          description: 'Command has been executed successfully',
          requiredElements: ['success_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
    },
  ],
};

/**
 * J05: Quick Actions Journey
 *
 * User triggers quick actions from home screen.
 * Tests: Quick action location -> Multiple activations
 */
export const J05_QUICK_ACTIONS: JourneySpec = {
  id: 'J05_QUICK_ACTIONS',
  name: 'Quick Actions',
  description: 'User triggers quick actions for immediate control',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop'],
  requiredCapabilities: [],
  personas: ['P1_AL_RASHID', 'P5_JACKSON', 'P8_REYES', 'P10_HAVEN', 'P13_RECOVERY'],
  expectedDurationMs: 15000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_LOCATE_ACTIONS',
      name: 'Locate Quick Actions',
      description: 'Find quick actions on home screen',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP1_ACTIONS_FOUND',
          name: 'Quick Actions Found',
          description: 'Quick actions section is visible',
          requiredElements: ['quick_actions_container'],
          maxDurationMs: 2000,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P2_LIGHTS_ON',
      name: 'Lights On',
      description: 'Activate lights on quick action',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP2_LIGHTS_ON',
          name: 'Lights On Activated',
          description: 'All lights turned on',
          requiredElements: ['quick_action_lights_on'],
          maxDurationMs: 1500,
          expectedHaptic: 'success',
        },
      ],
    },
    {
      id: 'P3_LIGHTS_OFF',
      name: 'Lights Off',
      description: 'Activate lights off quick action',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP3_LIGHTS_OFF',
          name: 'Lights Off Activated',
          description: 'All lights turned off',
          requiredElements: ['quick_action_lights_off'],
          maxDurationMs: 1500,
          expectedHaptic: 'success',
        },
      ],
    },
  ],
};

/**
 * J06: Glanceable Status Journey
 *
 * User quickly checks home status with minimal interaction.
 * Tests: Status at a glance -> Minimal interaction
 */
export const J06_GLANCEABLE_STATUS: JourneySpec = {
  id: 'J06_GLANCEABLE_STATUS',
  name: 'Glanceable Status Check',
  description: 'User quickly glances at home status',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop'],
  requiredCapabilities: [],
  personas: ['P1_AL_RASHID', 'P3_SOFIA', 'P6_OKONKWO', 'P8_REYES', 'P11_VOLKOV'],
  expectedDurationMs: 5000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_VIEW_STATUS',
      name: 'View Status',
      description: 'View home status on launch',
      interactionType: 'ambient',
      checkpoints: [
        {
          id: 'CP1_STATUS_VISIBLE',
          name: 'Status Visible',
          description: 'Home status is immediately visible',
          requiredElements: ['home_view', 'safety_card', 'connection_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'none',
        },
        {
          id: 'CP2_STATUS_READABLE',
          name: 'Status Readable',
          description: 'Status information is readable at a glance',
          requiredElements: ['safety_status_text'],
          maxDurationMs: 1000,
          expectedHaptic: 'none',
          accessibility: {
            minTouchTarget: 44,
            requiresLabel: true,
            requiresHint: false,
          },
        },
      ],
    },
  ],
};

/**
 * J07: Settings Management Journey
 *
 * User manages app settings.
 * Tests: Settings navigation -> Preference changes
 */
export const J07_SETTINGS_MANAGEMENT: JourneySpec = {
  id: 'J07_SETTINGS_MANAGEMENT',
  name: 'Settings Management',
  description: 'User manages app and home settings',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop'],
  requiredCapabilities: [],
  personas: ['P1_AL_RASHID', 'P4_RIVERA', 'P7_MENDEZ', 'P9_NGUYEN', 'P10_HAVEN'],
  expectedDurationMs: 20000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_NAVIGATE_SETTINGS',
      name: 'Navigate to Settings',
      description: 'Navigate to settings screen',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP1_SETTINGS_SCREEN',
          name: 'Settings Screen',
          description: 'Settings screen is displayed',
          requiredElements: ['settings_view'],
          maxDurationMs: 2000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P2_VIEW_OPTIONS',
      name: 'View Options',
      description: 'Browse available settings',
      interactionType: 'scroll',
      checkpoints: [
        {
          id: 'CP2_OPTIONS_VISIBLE',
          name: 'Options Visible',
          description: 'Settings options are listed',
          requiredElements: ['settings_list'],
          maxDurationMs: 1500,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P3_RETURN_HOME',
      name: 'Return Home',
      description: 'Navigate back to home',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP3_HOME_RETURNED',
          name: 'Home Returned',
          description: 'Back at home screen',
          requiredElements: ['home_view'],
          maxDurationMs: 1000,
          expectedHaptic: 'light',
        },
      ],
    },
  ],
};

/**
 * J08: Household Member Switch Journey
 *
 * User switches between household members.
 * Tests: Household access -> Member selection -> Context switch
 */
export const J08_HOUSEHOLD_MEMBER_SWITCH: JourneySpec = {
  id: 'J08_HOUSEHOLD_MEMBER_SWITCH',
  name: 'Household Member Switch',
  description: 'User switches between household member contexts',
  requiredPlatforms: ['ios', 'android', 'tvos', 'visionos', 'androidxr', 'desktop'],
  requiredCapabilities: [],
  personas: ['P1_AL_RASHID', 'P4_RIVERA', 'P7_MENDEZ', 'P10_HAVEN', 'P11_VOLKOV'],
  expectedDurationMs: 25000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_ACCESS_HOUSEHOLD',
      name: 'Access Household',
      description: 'Navigate to household settings',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP1_HOUSEHOLD_SCREEN',
          name: 'Household Screen',
          description: 'Household management screen is displayed',
          requiredElements: ['household_view', 'household_members_list'],
          maxDurationMs: 2000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P2_SELECT_MEMBER',
      name: 'Select Member',
      description: 'Select a different household member',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP2_MEMBER_SELECTED',
          name: 'Member Selected',
          description: 'New household member is selected',
          requiredElements: ['member_selected_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
    },
    {
      id: 'P3_VERIFY_SWITCH',
      name: 'Verify Context Switch',
      description: 'Verify the context has switched',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP3_CONTEXT_VERIFIED',
          name: 'Context Verified',
          description: 'Home screen reflects new member context',
          requiredElements: ['home_view', 'member_name_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'none',
        },
      ],
    },
  ],
};

/**
 * J09: Emergency Safety Journey
 *
 * User triggers emergency/safety features.
 * Tests: Emergency access -> Activation -> Confirmation
 *
 * h(x) >= 0. Always. This journey MUST always work.
 */
export const J09_EMERGENCY_SAFETY: JourneySpec = {
  id: 'J09_EMERGENCY_SAFETY',
  name: 'Emergency Safety',
  description: 'User triggers emergency safety features - MUST ALWAYS WORK',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop', 'hub'],
  requiredCapabilities: [],
  personas: ['P2_CHEN_WILLIAMS', 'P6_OKONKWO', 'P11_VOLKOV', 'P12_OCONNOR', 'P13_RECOVERY'],
  expectedDurationMs: 10000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_ACCESS_EMERGENCY',
      name: 'Access Emergency',
      description: 'Access emergency features (max 2 taps)',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP1_EMERGENCY_ACCESSIBLE',
          name: 'Emergency Accessible',
          description: 'Emergency feature is accessible within 2 taps',
          requiredElements: ['emergency_button'],
          maxDurationMs: 2000,
          expectedHaptic: 'heavy',
          accessibility: {
            minTouchTarget: 60, // Larger for emergency
            requiresLabel: true,
            requiresHint: true,
          },
        },
      ],
    },
    {
      id: 'P2_ACTIVATE',
      name: 'Activate Emergency',
      description: 'Activate emergency mode',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP2_EMERGENCY_ACTIVE',
          name: 'Emergency Active',
          description: 'Emergency mode is now active',
          requiredElements: ['emergency_active_indicator', 'all_lights_on'],
          maxDurationMs: 1000,
          expectedHaptic: 'heavy',
        },
      ],
    },
    {
      id: 'P3_CONFIRM',
      name: 'Confirm Safety',
      description: 'Confirm emergency was handled',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP3_SAFETY_CONFIRMED',
          name: 'Safety Confirmed',
          description: 'User confirms they are safe, emergency deactivated',
          requiredElements: ['safety_confirmed_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
    },
  ],
};

/**
 * J10: Full App Exploration Journey
 *
 * User explores all major areas of the app.
 * Tests: All tabs -> All major screens
 */
export const J10_FULL_EXPLORATION: JourneySpec = {
  id: 'J10_FULL_EXPLORATION',
  name: 'Full App Exploration',
  description: 'User explores all major areas of the app',
  requiredPlatforms: ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop'],
  requiredCapabilities: [],
  personas: ['P1_AL_RASHID', 'P3_SOFIA', 'P5_JACKSON', 'P9_NGUYEN', 'P12_OCONNOR'],
  expectedDurationMs: 45000,
  qualityDimensions: {
    technical: true,
    aesthetic: true,
    accessibility: true,
    emotional: true,
    polish: true,
    delight: true,
  },
  phases: [
    {
      id: 'P1_HOME',
      name: 'Home Tab',
      description: 'Explore home tab',
      interactionType: 'scroll',
      checkpoints: [
        {
          id: 'CP1_HOME_EXPLORED',
          name: 'Home Explored',
          description: 'Home tab fully explored',
          requiredElements: ['home_view'],
          maxDurationMs: 5000,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P2_ROOMS',
      name: 'Rooms Tab',
      description: 'Explore rooms tab',
      interactionType: 'scroll',
      checkpoints: [
        {
          id: 'CP2_ROOMS_EXPLORED',
          name: 'Rooms Explored',
          description: 'Rooms tab fully explored',
          requiredElements: ['rooms_view', 'rooms_list'],
          maxDurationMs: 5000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P3_SCENES',
      name: 'Scenes Tab',
      description: 'Explore scenes tab',
      interactionType: 'scroll',
      checkpoints: [
        {
          id: 'CP3_SCENES_EXPLORED',
          name: 'Scenes Explored',
          description: 'Scenes tab fully explored',
          requiredElements: ['scenes_view', 'scenes_list'],
          maxDurationMs: 5000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P4_HUB',
      name: 'Hub Tab',
      description: 'Explore hub tab',
      interactionType: 'scroll',
      checkpoints: [
        {
          id: 'CP4_HUB_EXPLORED',
          name: 'Hub Explored',
          description: 'Hub tab fully explored',
          requiredElements: ['hub_view'],
          maxDurationMs: 5000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P5_SETTINGS',
      name: 'Settings Tab',
      description: 'Explore settings tab',
      interactionType: 'scroll',
      checkpoints: [
        {
          id: 'CP5_SETTINGS_EXPLORED',
          name: 'Settings Explored',
          description: 'Settings tab fully explored',
          requiredElements: ['settings_view'],
          maxDurationMs: 5000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P6_RETURN',
      name: 'Return Home',
      description: 'Return to home to complete journey',
      interactionType: 'tap',
      checkpoints: [
        {
          id: 'CP6_EXPLORATION_COMPLETE',
          name: 'Exploration Complete',
          description: 'Full exploration journey complete',
          requiredElements: ['home_view'],
          maxDurationMs: 1000,
          expectedHaptic: 'success',
        },
      ],
    },
  ],
};

// =============================================================================
// CONSTELLATION JOURNEY SPECIFICATIONS
// =============================================================================

/**
 * Constellation device role
 */
export const ConstellationRole = z.enum([
  'initiator',    // Device that starts the journey
  'receiver',     // Device that receives handoff
  'observer',     // Device that reflects state changes
  'coordinator',  // Hub that coordinates all devices
  'ambient',      // Ambient device (always listening)
]);
export type ConstellationRole = z.infer<typeof ConstellationRole>;

/**
 * Device in a constellation
 */
export const ConstellationDevice = z.object({
  platform: Platform,
  role: ConstellationRole,
  /** mDNS service name for discovery */
  mdnsServiceName: z.string(),
  /** Expected mesh network latency in ms */
  expectedLatencyMs: z.number(),
});
export type ConstellationDevice = z.infer<typeof ConstellationDevice>;

/**
 * Constellation journey spec - tests multiple devices working together
 */
export const ConstellationJourneySpec = z.object({
  id: JourneyId,
  name: z.string(),
  description: z.string(),
  /** Devices participating in this constellation */
  devices: z.array(ConstellationDevice),
  /** Phases with multi-device coordination */
  phases: z.array(Phase.extend({
    /** Which device is active in this phase */
    activeDevice: Platform,
    /** Expected state sync across devices */
    expectedSync: z.record(Platform, z.record(z.string(), z.unknown())).optional(),
  })),
  /** Total expected duration */
  expectedDurationMs: z.number(),
  /** mDNS discovery timeout */
  mdnsDiscoveryTimeoutMs: z.number(),
  /** Mesh sync verification timeout */
  meshSyncTimeoutMs: z.number(),
});
export type ConstellationJourneySpec = z.infer<typeof ConstellationJourneySpec>;

/**
 * C01: Watch to Phone Handoff
 *
 * User starts action on watch, continues on phone.
 * Tests: Watch initiate -> mDNS discovery -> Phone continue -> State sync
 */
export const C01_WATCH_TO_PHONE_HANDOFF: ConstellationJourneySpec = {
  id: 'C01_WATCH_TO_PHONE_HANDOFF',
  name: 'Watch to Phone Handoff',
  description: 'User starts on watch, hands off to phone for complex task',
  devices: [
    {
      platform: 'watchos',
      role: 'initiator',
      mdnsServiceName: '_kagami-watch._tcp.local',
      expectedLatencyMs: 50,
    },
    {
      platform: 'ios',
      role: 'receiver',
      mdnsServiceName: '_kagami-ios._tcp.local',
      expectedLatencyMs: 30,
    },
    {
      platform: 'hub',
      role: 'coordinator',
      mdnsServiceName: '_kagami-hub._tcp.local',
      expectedLatencyMs: 20,
    },
  ],
  expectedDurationMs: 30000,
  mdnsDiscoveryTimeoutMs: 5000,
  meshSyncTimeoutMs: 2000,
  phases: [
    {
      id: 'P1_WATCH_INITIATE',
      name: 'Watch Initiates',
      description: 'User starts action on watch',
      interactionType: 'tap',
      activeDevice: 'watchos',
      checkpoints: [
        {
          id: 'CP1_WATCH_ACTION',
          name: 'Watch Action Started',
          description: 'Action started on watch',
          requiredElements: ['handoff_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'light',
        },
      ],
      expectedSync: {
        ios: { pendingHandoff: true },
        hub: { activeSession: 'watchos' },
      },
    },
    {
      id: 'P2_MDNS_DISCOVERY',
      name: 'mDNS Discovery',
      description: 'Watch discovers phone via mDNS',
      interactionType: 'ambient',
      activeDevice: 'watchos',
      checkpoints: [
        {
          id: 'CP2_PHONE_DISCOVERED',
          name: 'Phone Discovered',
          description: 'Phone discovered via mDNS',
          requiredElements: ['device_discovered_indicator'],
          maxDurationMs: 5000,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P3_HANDOFF_TRIGGER',
      name: 'Trigger Handoff',
      description: 'User triggers handoff to phone',
      interactionType: 'tap',
      activeDevice: 'watchos',
      checkpoints: [
        {
          id: 'CP3_HANDOFF_TRIGGERED',
          name: 'Handoff Triggered',
          description: 'Handoff has been triggered',
          requiredElements: ['handoff_in_progress'],
          maxDurationMs: 1000,
          expectedHaptic: 'medium',
        },
      ],
    },
    {
      id: 'P4_PHONE_CONTINUE',
      name: 'Phone Continues',
      description: 'Phone receives and continues action',
      interactionType: 'tap',
      activeDevice: 'ios',
      checkpoints: [
        {
          id: 'CP4_PHONE_RECEIVED',
          name: 'Phone Received Handoff',
          description: 'Phone has received the handoff',
          requiredElements: ['handoff_received_banner', 'continue_action_button'],
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
        {
          id: 'CP5_ACTION_CONTINUED',
          name: 'Action Continued',
          description: 'Action is now continuing on phone',
          requiredElements: ['action_in_progress'],
          maxDurationMs: 2000,
          expectedHaptic: 'none',
        },
      ],
      expectedSync: {
        watchos: { handoffComplete: true },
        hub: { activeSession: 'ios' },
      },
    },
    {
      id: 'P5_VERIFY_SYNC',
      name: 'Verify State Sync',
      description: 'Verify all devices have synced state',
      interactionType: 'ambient',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP6_STATE_SYNCED',
          name: 'State Synced',
          description: 'All devices have synchronized state',
          requiredElements: ['mesh_sync_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'none',
        },
      ],
    },
  ],
};

/**
 * C02: Multi-Room Orchestration
 *
 * User controls multiple rooms from different devices simultaneously.
 * Tests: Multi-device control -> State sync -> Conflict resolution
 */
export const C02_MULTI_ROOM_ORCHESTRATION: ConstellationJourneySpec = {
  id: 'C02_MULTI_ROOM_ORCHESTRATION',
  name: 'Multi-Room Orchestration',
  description: 'Multiple devices controlling different rooms simultaneously',
  devices: [
    {
      platform: 'ios',
      role: 'initiator',
      mdnsServiceName: '_kagami-ios._tcp.local',
      expectedLatencyMs: 30,
    },
    {
      platform: 'android',
      role: 'initiator',
      mdnsServiceName: '_kagami-android._tcp.local',
      expectedLatencyMs: 30,
    },
    {
      platform: 'desktop',
      role: 'observer',
      mdnsServiceName: '_kagami-desktop._tcp.local',
      expectedLatencyMs: 20,
    },
    {
      platform: 'hub',
      role: 'coordinator',
      mdnsServiceName: '_kagami-hub._tcp.local',
      expectedLatencyMs: 20,
    },
  ],
  expectedDurationMs: 45000,
  mdnsDiscoveryTimeoutMs: 5000,
  meshSyncTimeoutMs: 3000,
  phases: [
    {
      id: 'P1_DISCOVER_DEVICES',
      name: 'Discover Devices',
      description: 'All devices discover each other via mDNS',
      interactionType: 'ambient',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP1_ALL_DISCOVERED',
          name: 'All Devices Discovered',
          description: 'All 4 devices discovered on mesh',
          requiredElements: ['mesh_device_count_4'],
          maxDurationMs: 5000,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P2_IOS_CONTROLS_LIVING',
      name: 'iOS Controls Living Room',
      description: 'iOS device controls living room',
      interactionType: 'tap',
      activeDevice: 'ios',
      checkpoints: [
        {
          id: 'CP2_LIVING_CONTROLLED',
          name: 'Living Room Controlled',
          description: 'iOS has sent living room command',
          requiredElements: ['room_control_sent'],
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
      expectedSync: {
        android: { livingRoomLights: 75 },
        desktop: { livingRoomLights: 75 },
        hub: { livingRoomLights: 75 },
      },
    },
    {
      id: 'P3_ANDROID_CONTROLS_BEDROOM',
      name: 'Android Controls Bedroom',
      description: 'Android device controls bedroom simultaneously',
      interactionType: 'tap',
      activeDevice: 'android',
      checkpoints: [
        {
          id: 'CP3_BEDROOM_CONTROLLED',
          name: 'Bedroom Controlled',
          description: 'Android has sent bedroom command',
          requiredElements: ['room_control_sent'],
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
      expectedSync: {
        ios: { bedroomLights: 50 },
        desktop: { bedroomLights: 50 },
        hub: { bedroomLights: 50 },
      },
    },
    {
      id: 'P4_VERIFY_DESKTOP',
      name: 'Desktop Observes',
      description: 'Desktop reflects all state changes',
      interactionType: 'ambient',
      activeDevice: 'desktop',
      checkpoints: [
        {
          id: 'CP4_DESKTOP_SYNCED',
          name: 'Desktop Synced',
          description: 'Desktop shows both room changes',
          requiredElements: ['living_room_75', 'bedroom_50'],
          maxDurationMs: 3000,
          expectedHaptic: 'none',
        },
      ],
    },
  ],
};

/**
 * C03: Spatial to Ambient Transition
 *
 * User moves from spatial XR environment to ambient hub control.
 * Tests: XR session -> Transition -> Hub ambient
 */
export const C03_SPATIAL_TO_AMBIENT_TRANSITION: ConstellationJourneySpec = {
  id: 'C03_SPATIAL_TO_AMBIENT_TRANSITION',
  name: 'Spatial to Ambient Transition',
  description: 'User transitions from XR spatial control to ambient hub',
  devices: [
    {
      platform: 'visionos',
      role: 'initiator',
      mdnsServiceName: '_kagami-vision._tcp.local',
      expectedLatencyMs: 40,
    },
    {
      platform: 'hub',
      role: 'receiver',
      mdnsServiceName: '_kagami-hub._tcp.local',
      expectedLatencyMs: 20,
    },
    {
      platform: 'ios',
      role: 'observer',
      mdnsServiceName: '_kagami-ios._tcp.local',
      expectedLatencyMs: 30,
    },
  ],
  expectedDurationMs: 35000,
  mdnsDiscoveryTimeoutMs: 5000,
  meshSyncTimeoutMs: 2000,
  phases: [
    {
      id: 'P1_XR_SESSION',
      name: 'XR Spatial Session',
      description: 'User controls home in XR spatial view',
      interactionType: 'pinch',
      activeDevice: 'visionos',
      checkpoints: [
        {
          id: 'CP1_SPATIAL_ACTIVE',
          name: 'Spatial Session Active',
          description: 'XR spatial home control is active',
          requiredElements: ['spatial_home_view', 'room_panels'],
          maxDurationMs: 3000,
          expectedHaptic: 'light',
        },
      ],
    },
    {
      id: 'P2_REMOVE_HEADSET',
      name: 'Remove Headset',
      description: 'User removes XR headset',
      interactionType: 'ambient',
      activeDevice: 'visionos',
      checkpoints: [
        {
          id: 'CP2_SESSION_ENDING',
          name: 'Session Ending',
          description: 'XR session is ending',
          requiredElements: ['session_ending_indicator'],
          maxDurationMs: 2000,
          expectedHaptic: 'none',
        },
      ],
      expectedSync: {
        hub: { incomingSession: 'visionos' },
      },
    },
    {
      id: 'P3_HUB_AMBIENT',
      name: 'Hub Ambient Takeover',
      description: 'Hub takes over with ambient control',
      interactionType: 'voice',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP3_HUB_ACTIVE',
          name: 'Hub Ambient Active',
          description: 'Hub is now the active control interface',
          requiredElements: ['ambient_mode_indicator', 'voice_ready'],
          maxDurationMs: 3000,
          expectedHaptic: 'none',
        },
        {
          id: 'CP4_STATE_PRESERVED',
          name: 'State Preserved',
          description: 'Home state from XR session is preserved',
          requiredElements: ['state_indicator'],
          maxDurationMs: 1000,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P4_VOICE_CONTINUE',
      name: 'Voice Control',
      description: 'User continues via voice on hub',
      interactionType: 'voice',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP5_VOICE_COMMAND',
          name: 'Voice Command Issued',
          description: 'User issues voice command on hub',
          requiredElements: ['voice_processing'],
          maxDurationMs: 3000,
          expectedHaptic: 'none',
        },
      ],
      expectedSync: {
        ios: { lastCommand: 'voice' },
      },
    },
  ],
};

/**
 * C04: Voice Command Routing
 *
 * Voice command is routed to the most appropriate device.
 * Tests: Voice on multiple devices -> Routing -> Single execution
 */
export const C04_VOICE_COMMAND_ROUTING: ConstellationJourneySpec = {
  id: 'C04_VOICE_COMMAND_ROUTING',
  name: 'Voice Command Routing',
  description: 'Voice command is intelligently routed to best device',
  devices: [
    {
      platform: 'hub',
      role: 'coordinator',
      mdnsServiceName: '_kagami-hub._tcp.local',
      expectedLatencyMs: 20,
    },
    {
      platform: 'ios',
      role: 'observer',
      mdnsServiceName: '_kagami-ios._tcp.local',
      expectedLatencyMs: 30,
    },
    {
      platform: 'watchos',
      role: 'observer',
      mdnsServiceName: '_kagami-watch._tcp.local',
      expectedLatencyMs: 50,
    },
    {
      platform: 'desktop',
      role: 'observer',
      mdnsServiceName: '_kagami-desktop._tcp.local',
      expectedLatencyMs: 20,
    },
  ],
  expectedDurationMs: 20000,
  mdnsDiscoveryTimeoutMs: 5000,
  meshSyncTimeoutMs: 2000,
  phases: [
    {
      id: 'P1_ALL_LISTENING',
      name: 'All Devices Listening',
      description: 'Multiple devices detect wake word',
      interactionType: 'voice',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP1_WAKE_DETECTED',
          name: 'Wake Word Detected',
          description: 'Multiple devices detected wake word',
          requiredElements: ['wake_detected_indicator'],
          maxDurationMs: 1000,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P2_ROUTING_DECISION',
      name: 'Routing Decision',
      description: 'Hub coordinates routing decision',
      interactionType: 'ambient',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP2_ROUTE_SELECTED',
          name: 'Route Selected',
          description: 'Best device selected for command',
          requiredElements: ['routing_indicator'],
          maxDurationMs: 500,
          expectedHaptic: 'none',
        },
      ],
      expectedSync: {
        ios: { listeningDeferred: true },
        watchos: { listeningDeferred: true },
        desktop: { listeningDeferred: true },
      },
    },
    {
      id: 'P3_COMMAND_EXECUTION',
      name: 'Command Execution',
      description: 'Selected device executes command',
      interactionType: 'voice',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP3_COMMAND_EXECUTED',
          name: 'Command Executed',
          description: 'Command executed by single device',
          requiredElements: ['command_success'],
          maxDurationMs: 3000,
          expectedHaptic: 'success',
        },
      ],
    },
    {
      id: 'P4_STATE_BROADCAST',
      name: 'State Broadcast',
      description: 'State change broadcast to all devices',
      interactionType: 'ambient',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP4_ALL_SYNCED',
          name: 'All Devices Synced',
          description: 'All devices reflect the state change',
          requiredElements: ['mesh_sync_complete'],
          maxDurationMs: 2000,
          expectedHaptic: 'none',
        },
      ],
      expectedSync: {
        ios: { stateUpdated: true },
        watchos: { stateUpdated: true },
        desktop: { stateUpdated: true },
      },
    },
  ],
};

/**
 * C05: Emergency All Devices
 *
 * Emergency triggered on one device activates ALL devices.
 * Tests: Single trigger -> Global broadcast -> All activate
 *
 * h(x) >= 0. Always. This is the MOST CRITICAL constellation journey.
 */
export const C05_EMERGENCY_ALL_DEVICES: ConstellationJourneySpec = {
  id: 'C05_EMERGENCY_ALL_DEVICES',
  name: 'Emergency All Devices',
  description: 'Emergency on any device activates entire constellation - CRITICAL',
  devices: [
    {
      platform: 'watchos',
      role: 'initiator',
      mdnsServiceName: '_kagami-watch._tcp.local',
      expectedLatencyMs: 50,
    },
    {
      platform: 'ios',
      role: 'receiver',
      mdnsServiceName: '_kagami-ios._tcp.local',
      expectedLatencyMs: 30,
    },
    {
      platform: 'android',
      role: 'receiver',
      mdnsServiceName: '_kagami-android._tcp.local',
      expectedLatencyMs: 30,
    },
    {
      platform: 'hub',
      role: 'coordinator',
      mdnsServiceName: '_kagami-hub._tcp.local',
      expectedLatencyMs: 20,
    },
    {
      platform: 'desktop',
      role: 'receiver',
      mdnsServiceName: '_kagami-desktop._tcp.local',
      expectedLatencyMs: 20,
    },
  ],
  expectedDurationMs: 15000,
  mdnsDiscoveryTimeoutMs: 3000, // Faster for emergency
  meshSyncTimeoutMs: 1000, // Must be fast for emergency
  phases: [
    {
      id: 'P1_EMERGENCY_TRIGGER',
      name: 'Emergency Triggered',
      description: 'User triggers emergency on watch',
      interactionType: 'tap',
      activeDevice: 'watchos',
      checkpoints: [
        {
          id: 'CP1_EMERGENCY_SENT',
          name: 'Emergency Sent',
          description: 'Emergency signal sent to mesh',
          requiredElements: ['emergency_broadcast_indicator'],
          maxDurationMs: 500, // Must be FAST
          expectedHaptic: 'heavy',
        },
      ],
    },
    {
      id: 'P2_HUB_BROADCAST',
      name: 'Hub Broadcasts',
      description: 'Hub broadcasts emergency to all devices',
      interactionType: 'ambient',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP2_BROADCAST_SENT',
          name: 'Broadcast Sent',
          description: 'Emergency broadcast to all devices',
          requiredElements: ['emergency_mode_active', 'all_lights_max'],
          maxDurationMs: 500,
          expectedHaptic: 'none',
        },
      ],
    },
    {
      id: 'P3_ALL_ACTIVATE',
      name: 'All Devices Activate',
      description: 'All devices show emergency state',
      interactionType: 'ambient',
      activeDevice: 'hub',
      checkpoints: [
        {
          id: 'CP3_IOS_EMERGENCY',
          name: 'iOS Emergency',
          description: 'iOS shows emergency state',
          requiredElements: ['emergency_banner'],
          maxDurationMs: 1000,
          expectedHaptic: 'heavy',
        },
        {
          id: 'CP4_ANDROID_EMERGENCY',
          name: 'Android Emergency',
          description: 'Android shows emergency state',
          requiredElements: ['emergency_banner'],
          maxDurationMs: 1000,
          expectedHaptic: 'heavy',
        },
        {
          id: 'CP5_DESKTOP_EMERGENCY',
          name: 'Desktop Emergency',
          description: 'Desktop shows emergency state',
          requiredElements: ['emergency_banner'],
          maxDurationMs: 1000,
          expectedHaptic: 'none',
        },
      ],
      expectedSync: {
        ios: { emergencyMode: true },
        android: { emergencyMode: true },
        desktop: { emergencyMode: true },
        watchos: { emergencyMode: true },
      },
    },
    {
      id: 'P4_SAFETY_CONFIRM',
      name: 'Confirm Safety',
      description: 'Any device can confirm safety',
      interactionType: 'tap',
      activeDevice: 'ios',
      checkpoints: [
        {
          id: 'CP6_SAFETY_CONFIRMED',
          name: 'Safety Confirmed',
          description: 'User confirmed safety, emergency ended',
          requiredElements: ['safety_confirmed', 'normal_mode'],
          maxDurationMs: 2000,
          expectedHaptic: 'success',
        },
      ],
      expectedSync: {
        ios: { emergencyMode: false },
        android: { emergencyMode: false },
        desktop: { emergencyMode: false },
        watchos: { emergencyMode: false },
        hub: { emergencyMode: false },
      },
    },
  ],
};

// =============================================================================
// EXPORTS
// =============================================================================

/**
 * All single-device journeys
 */
export const SINGLE_DEVICE_JOURNEYS: JourneySpec[] = [
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
];

/**
 * All constellation journeys
 */
export const CONSTELLATION_JOURNEYS: ConstellationJourneySpec[] = [
  C01_WATCH_TO_PHONE_HANDOFF,
  C02_MULTI_ROOM_ORCHESTRATION,
  C03_SPATIAL_TO_AMBIENT_TRANSITION,
  C04_VOICE_COMMAND_ROUTING,
  C05_EMERGENCY_ALL_DEVICES,
];

/**
 * Get journeys applicable to a platform
 */
export function getJourneysForPlatform(platform: Platform): JourneySpec[] {
  return SINGLE_DEVICE_JOURNEYS.filter((j) =>
    j.requiredPlatforms.includes(platform)
  );
}

/**
 * Get constellation journeys involving a platform
 */
export function getConstellationJourneysForPlatform(
  platform: Platform
): ConstellationJourneySpec[] {
  return CONSTELLATION_JOURNEYS.filter((j) =>
    j.devices.some((d) => d.platform === platform)
  );
}

/**
 * Validate a journey result against its spec
 */
export function validateJourneyResult(
  spec: JourneySpec,
  result: {
    checkpointsPassed: string[];
    totalDurationMs: number;
    errors: string[];
  }
): { valid: boolean; score: number; issues: string[] } {
  const issues: string[] = [];
  let score = 100;

  // Check all checkpoints passed
  const expectedCheckpoints = spec.phases.flatMap((p) =>
    p.checkpoints.map((c) => c.id)
  );
  const missingCheckpoints = expectedCheckpoints.filter(
    (cp) => !result.checkpointsPassed.includes(cp)
  );

  if (missingCheckpoints.length > 0) {
    issues.push(`Missing checkpoints: ${missingCheckpoints.join(', ')}`);
    score -= missingCheckpoints.length * 10;
  }

  // Check duration
  if (result.totalDurationMs > spec.expectedDurationMs * 1.5) {
    issues.push(
      `Duration ${result.totalDurationMs}ms exceeds expected ${spec.expectedDurationMs}ms by >50%`
    );
    score -= 20;
  }

  // Check errors
  if (result.errors.length > 0) {
    issues.push(`Errors: ${result.errors.join(', ')}`);
    score -= result.errors.length * 15;
  }

  return {
    valid: score >= 70 && missingCheckpoints.length === 0,
    score: Math.max(0, score),
    issues,
  };
}
