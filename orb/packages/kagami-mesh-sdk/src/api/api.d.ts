/**
 * Kagami Mesh SDK - TypeScript Type Definitions
 *
 * These types mirror the Rust types in kagami-mesh-sdk/src/api/types.rs
 * and provide consistent typing for Desktop (Tauri) applications.
 *
 * Colony: Nexus (e4) - Integration
 *
 * Usage:
 *   import type { Light, RoomModel, HealthResponse } from 'kagami-mesh-sdk';
 *
 * h(x) >= 0. Always.
 */

// ============================================================================
// Device Models
// ============================================================================

/**
 * A light fixture in the home.
 * Represents a controllable light with brightness level (0-100).
 */
export interface Light {
  /** Unique identifier for the light */
  id: number;
  /** Human-readable name (e.g., "Living Room Main") */
  name: string;
  /** Current brightness level (0 = off, 100 = full brightness) */
  level: number;
}

/**
 * A motorized shade/blind.
 * Represents a controllable shade with position (0 = closed, 100 = fully open).
 */
export interface Shade {
  /** Unique identifier for the shade */
  id: number;
  /** Human-readable name (e.g., "Bedroom Blinds") */
  name: string;
  /** Current position (0 = closed, 100 = fully open) */
  position: number;
}

/**
 * An audio zone for whole-home audio.
 */
export interface AudioZone {
  /** Unique identifier for the audio zone */
  id: number;
  /** Human-readable name (e.g., "Kitchen Speakers") */
  name: string;
  /** Whether audio is currently playing */
  isActive: boolean;
  /** Current audio source (e.g., "Spotify", "AirPlay") */
  source: string | null;
  /** Volume level (0-100) */
  volume: number;
}

/**
 * HVAC (heating/cooling) state for a room.
 */
export interface HvacState {
  /** Current temperature in the room (Fahrenheit) */
  currentTemp: number;
  /** Target/setpoint temperature (Fahrenheit) */
  targetTemp: number;
  /** Operating mode: "heat", "cool", "auto", "off" */
  mode: 'heat' | 'cool' | 'auto' | 'off';
}

/**
 * State of a door lock.
 */
export interface LockState {
  /** Human-readable name (e.g., "Front Door") */
  name: string;
  /** Whether the lock is currently locked */
  isLocked: boolean;
  /** Door state: "open", "closed", "unknown" */
  doorState: 'open' | 'closed' | 'unknown';
}

/**
 * State of the fireplace.
 */
export interface FireplaceState {
  /** Whether the fireplace is currently on */
  isOn: boolean;
  /** Unix timestamp when fireplace was turned on (if on) */
  onSince: number | null;
  /** Minutes remaining before auto-shutoff (if applicable) */
  remainingMinutes: number | null;
}

/**
 * State of the motorized TV mount.
 */
export interface TvMountState {
  /** Current position: "up", "down", "moving" */
  position: 'up' | 'down' | 'moving';
  /** Preset position number (if applicable) */
  preset: number | null;
}

// ============================================================================
// Room Model
// ============================================================================

/**
 * A room in the home with all its devices.
 * This is the primary model for room-based control and display.
 */
export interface RoomModel {
  /** Unique identifier for the room */
  id: string;
  /** Human-readable name (e.g., "Living Room") */
  name: string;
  /** Floor designation (e.g., "Main Floor", "Upper Floor") */
  floor: string;
  /** Lights in this room */
  lights: Light[];
  /** Shades in this room */
  shades: Shade[];
  /** Audio zone for this room (if any) */
  audioZone: AudioZone | null;
  /** HVAC state for this room (if any) */
  hvac: HvacState | null;
  /** Whether the room is currently occupied */
  occupied: boolean;
}

// ============================================================================
// Home Status
// ============================================================================

/**
 * Overall home status summary.
 */
export interface HomeStatus {
  /** Whether the home system has been initialized */
  initialized: boolean;
  /** Total number of rooms */
  rooms: number;
  /** Number of currently occupied rooms */
  occupiedRooms: number;
  /** Whether movie mode is active */
  movieMode: boolean;
  /** Average temperature across all zones (Fahrenheit) */
  avgTemp: number | null;
}

/**
 * Devices response from GET /home/devices
 */
export interface DevicesResponse {
  /** All lights in the home */
  lights: Light[];
  /** All shades in the home */
  shades: Shade[];
  /** All audio zones in the home */
  audioZones: AudioZone[];
  /** All locks in the home */
  locks: LockState[];
  /** Fireplace state */
  fireplace: FireplaceState;
  /** TV mount state */
  tvMount: TvMountState;
}

/**
 * Rooms response from GET /home/rooms
 */
export interface RoomsResponse {
  /** List of rooms */
  rooms: RoomModel[];
  /** Total count of rooms */
  count: number;
}

// ============================================================================
// API Request/Response Types
// ============================================================================

/**
 * Health check response from GET /health
 */
export interface HealthResponse {
  /** Status string: "healthy", "ok", etc. */
  status: string;
  /** Safety score h(x) (should always be >= 0) */
  hX: number | null;
  /** Server version */
  version: string | null;
  /** Number of rooms */
  roomsCount: number | null;
  /** Uptime in milliseconds */
  uptimeMs: number | null;
}

/**
 * Client registration request for POST /api/home/clients/register
 */
export interface ClientRegistrationRequest {
  /** Unique client identifier (e.g., "ios-uuid", "android-uuid") */
  clientId: string;
  /** Client type: "ios", "android", "visionos", "tvos", "watchos", "desktop" */
  clientType: ClientType;
  /** Human-readable device name */
  deviceName: string;
  /** List of capabilities this client supports */
  capabilities: string[];
  /** App version string */
  appVersion: string;
  /** OS version string (optional) */
  osVersion?: string;
}

/**
 * Scene information
 */
export interface SceneInfo {
  /** Scene identifier (e.g., "movie_mode", "goodnight") */
  id: string;
  /** Human-readable name */
  name: string;
  /** Description of what the scene does */
  description: string | null;
  /** Icon identifier (SF Symbol name or emoji) */
  icon: string | null;
}

/**
 * Scenes response from GET /home/scenes
 */
export interface ScenesResponse {
  /** List of available scenes */
  scenes: SceneInfo[];
}

/**
 * Lights control request for POST /home/lights
 */
export interface LightsRequest {
  /** Target brightness level (0-100) */
  level: number;
  /** Optional list of room IDs to target (all rooms if undefined) */
  rooms?: string[];
}

/**
 * Shades control request for POST /home/shades
 */
export interface ShadesRequest {
  /** Action: "open", "close", "stop" */
  action: 'open' | 'close' | 'stop';
  /** Optional list of room IDs to target (all rooms if undefined) */
  rooms?: string[];
}

/**
 * Fireplace control request for POST /home/fireplace
 */
export interface FireplaceRequest {
  /** Desired state: "on" or "off" */
  state: 'on' | 'off';
}

/**
 * Climate control request for POST /home/climate
 */
export interface ClimateRequest {
  /** Target temperature (Fahrenheit) */
  temperature: number;
  /** Optional room ID to target */
  room?: string;
  /** Optional mode: "heat", "cool", "auto", "off" */
  mode?: 'heat' | 'cool' | 'auto' | 'off';
}

/**
 * Announce request for POST /home/announce
 */
export interface AnnounceRequest {
  /** Message to announce */
  message: string;
  /** Optional list of room IDs to announce in (all rooms if undefined) */
  rooms?: string[];
}

// ============================================================================
// WebSocket Message Types
// ============================================================================

/**
 * WebSocket message type enumeration
 */
export type WebSocketMessageType =
  | 'context_update'
  | 'suggestion'
  | 'home_update'
  | 'error'
  | 'unknown';

/**
 * Context update received via WebSocket
 */
export interface ContextUpdateMessage {
  type: 'context_update';
  data: {
    /** Current wakefulness level: "alert", "drowsy", "asleep" */
    wakefulness?: string;
    /** Current situation phase */
    situationPhase?: string;
    /** Current safety score */
    safetyScore?: number;
  };
  timestamp: number;
}

/**
 * Suggested action from server
 */
export interface SuggestedAction {
  /** Icon (SF Symbol name or emoji) */
  icon: string;
  /** Human-readable label */
  label: string;
  /** Action identifier to execute */
  action: string;
}

/**
 * Suggestion message received via WebSocket
 */
export interface SuggestionMessage {
  type: 'suggestion';
  data: SuggestedAction;
  timestamp: number;
}

/**
 * Home update received via WebSocket
 */
export interface HomeUpdateMessage {
  type: 'home_update';
  data: {
    /** Whether movie mode is active */
    movieMode?: boolean;
    /** Room that changed (if applicable) */
    roomId?: string;
  };
  timestamp: number;
}

/**
 * Error message received via WebSocket
 */
export interface ErrorMessage {
  type: 'error';
  data: {
    message: string;
    code?: string;
  };
  timestamp: number;
}

/**
 * Union type for all WebSocket messages
 */
export type WebSocketMessage =
  | ContextUpdateMessage
  | SuggestionMessage
  | HomeUpdateMessage
  | ErrorMessage;

// ============================================================================
// Error Types
// ============================================================================

/**
 * API error types
 */
export type ApiErrorKind =
  | 'invalid_url'
  | 'network_error'
  | 'request_failed'
  | 'decoding_failed'
  | 'not_connected'
  | 'circuit_open'
  | 'auth_required'
  | 'invalid_credentials'
  | 'server_version_incompatible';

/**
 * API error with details
 */
export interface ApiError {
  kind: ApiErrorKind;
  message: string;
  isRetryable: boolean;
  recoverySuggestion: string;
}

// ============================================================================
// Client Types
// ============================================================================

/**
 * Supported client platform types
 */
export type ClientType =
  | 'ios'
  | 'android'
  | 'visionos'
  | 'tvos'
  | 'watchos'
  | 'wearos'
  | 'desktop'
  | 'hub';

/**
 * Default capabilities for each client type
 */
export const DEFAULT_CAPABILITIES: Record<ClientType, string[]> = {
  ios: ['healthkit', 'location', 'notifications', 'quick_actions', 'widgets'],
  android: ['health_connect', 'location', 'notifications', 'quick_actions'],
  visionos: ['healthkit', 'spatial', 'immersive', 'gaze', 'hand_tracking', 'quick_actions'],
  tvos: ['tv_controls', 'siri_remote', 'quick_actions'],
  watchos: ['healthkit', 'complications', 'quick_actions'],
  wearos: ['health_connect', 'quick_actions'],
  desktop: ['notifications', 'keyboard_shortcuts', 'system_tray'],
  hub: ['local_processing', 'device_control', 'automation'],
};

// ============================================================================
// Connection State
// ============================================================================

/**
 * Connection state of the API client
 */
export type ApiConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'circuit_open'
  | 'failed';

/**
 * API client configuration
 */
export interface ApiClientConfig {
  /** Base URL for the API (default: production API) */
  baseUrl?: string;
  /** Request timeout in milliseconds (default: 10000) */
  timeoutMs?: number;
  /** Cache validity in seconds (default: 5) */
  cacheValiditySeconds?: number;
  /** Poll interval in seconds (default: 15) */
  pollIntervalSeconds?: number;
  /** Maximum retry attempts for transient failures (default: 3) */
  maxRetries?: number;
}

// ============================================================================
// Scene Icons (Unified)
// ============================================================================

/**
 * Scene icon constants for consistent UI across platforms.
 * Uses SF Symbol names for Apple platforms, with emoji fallbacks for others.
 */
export const SCENE_ICONS = {
  MOVIE_MODE: 'film.fill',
  GOODNIGHT: 'moon.fill',
  WELCOME_HOME: 'house.fill',
  AWAY: 'lock.fill',
  FIREPLACE: 'flame.fill',
  LIGHTS: 'lightbulb.fill',
  SHADES: 'blinds.vertical.open',
  TV: 'tv.fill',
} as const;

// ============================================================================
// Colony Colors (Unified Design System)
// ============================================================================

/**
 * Colony color definition
 */
export interface ColonyColor {
  /** Red component (0-255) */
  r: number;
  /** Green component (0-255) */
  g: number;
  /** Blue component (0-255) */
  b: number;
}

/**
 * Colony color palette - based on octonion basis e1-e7
 */
export const COLONY_COLORS = {
  /** e1 - Spark (Ideation) - Orange */
  SPARK: { r: 0xff, g: 0x6b, b: 0x35 },
  /** e2 - Forge (Implementation) - Gold */
  FORGE: { r: 0xd4, g: 0xaf, b: 0x37 },
  /** e3 - Flow (Adaptation) - Teal */
  FLOW: { r: 0x4e, g: 0xcd, b: 0xc4 },
  /** e4 - Nexus (Integration) - Purple */
  NEXUS: { r: 0x9b, g: 0x7e, b: 0xbd },
  /** e5 - Beacon (Planning) - Amber */
  BEACON: { r: 0xf5, g: 0x9e, b: 0x0b },
  /** e6 - Grove (Research) - Green */
  GROVE: { r: 0x7e, g: 0xb7, b: 0x7f },
  /** e7 - Crystal (Verification) - Cyan */
  CRYSTAL: { r: 0x67, g: 0xd4, b: 0xe4 },
  /** Void background (dark) */
  VOID: { r: 0x0a, g: 0x0a, b: 0x0f },
  /** Void light background */
  VOID_LIGHT: { r: 0x1c, g: 0x1c, b: 0x24 },
  /** Safety OK (green) */
  SAFETY_OK: { r: 0x32, g: 0xd7, b: 0x4b },
  /** Safety Caution (yellow) */
  SAFETY_CAUTION: { r: 0xff, g: 0xd6, b: 0x0a },
  /** Safety Violation (red) */
  SAFETY_VIOLATION: { r: 0xff, g: 0x3b, b: 0x30 },
} as const;

/**
 * Convert a ColonyColor to a hex string
 */
export function colonyColorToHex(color: ColonyColor): string {
  return `#${color.r.toString(16).padStart(2, '0')}${color.g.toString(16).padStart(2, '0')}${color.b.toString(16).padStart(2, '0')}`;
}

/**
 * Get the appropriate safety color for a given score.
 *
 * @param score - Safety score h(x). Should always be >= 0 in normal operation.
 * @returns The appropriate color based on the safety score
 */
export function getSafetyColor(score: number | null): ColonyColor {
  if (score === null) {
    return { r: 0x80, g: 0x80, b: 0x80 }; // Gray for unknown
  }
  if (score >= 0.5) {
    return COLONY_COLORS.SAFETY_OK;
  }
  if (score >= 0.0) {
    return COLONY_COLORS.SAFETY_CAUTION;
  }
  return COLONY_COLORS.SAFETY_VIOLATION;
}

// ============================================================================
// Validation Helpers
// ============================================================================

/**
 * Validate a light level (must be 0-100)
 */
export function validateLightLevel(level: number): number {
  if (level < 0 || level > 100) {
    throw new Error(`Light level must be 0-100, got ${level}`);
  }
  return level;
}

/**
 * Validate a shade position (must be 0-100)
 */
export function validateShadePosition(position: number): number {
  if (position < 0 || position > 100) {
    throw new Error(`Shade position must be 0-100, got ${position}`);
  }
  return position;
}

/**
 * Validate a volume level (must be 0-100)
 */
export function validateVolume(volume: number): number {
  if (volume < 0 || volume > 100) {
    throw new Error(`Volume must be 0-100, got ${volume}`);
  }
  return volume;
}

/**
 * Validate a temperature (must be reasonable: 40-100F)
 */
export function validateTemperature(temp: number): number {
  if (temp < 40 || temp > 100) {
    throw new Error(`Temperature must be 40-100F, got ${temp}`);
  }
  return temp;
}

// ============================================================================
// API Endpoints
// ============================================================================

/**
 * API endpoint constants
 */
export const ENDPOINTS = {
  HEALTH: '/health',
  REGISTER_CLIENT: '/api/home/clients/register',
  ROOMS: '/home/rooms',
  DEVICES: '/home/devices',
  SCENES: '/home/scenes',
  LIGHTS: '/home/lights',
  SHADES: '/home/shades',
  FIREPLACE: '/home/fireplace',
  CLIMATE: '/home/climate/set',
  ANNOUNCE: '/home/announce',
  LOCKS: '/home/locks',
  TV: '/home/tv',
} as const;

/**
 * Default API URL
 */
export const DEFAULT_API_URL = 'https://api.awkronos.com';

/**
 * Local mDNS URL for home network
 */
export const LOCAL_MDNS_URL = 'http://kagami.local:8001';

/**
 * Discovery candidate URLs
 */
export const DISCOVERY_CANDIDATES = [
  'https://api.awkronos.com',
  'http://kagami.local:8001',
] as const;

// ============================================================================
// Helper Functions
// ============================================================================

/**
 * Calculate average light level for a room
 */
export function calculateAvgLightLevel(lights: Light[]): number {
  if (lights.length === 0) return 0;
  const sum = lights.reduce((acc, light) => acc + light.level, 0);
  return Math.round(sum / lights.length);
}

/**
 * Get light state description for a room
 */
export function getLightState(avgLevel: number): 'Off' | 'Dim' | 'On' {
  if (avgLevel === 0) return 'Off';
  if (avgLevel < 50) return 'Dim';
  return 'On';
}

/**
 * Check if a light is on
 */
export function isLightOn(light: Light): boolean {
  return light.level > 0;
}

/**
 * Check if a shade is open
 */
export function isShadeOpen(shade: Shade): boolean {
  return shade.position > 0;
}

/**
 * Build a scene execution endpoint URL
 */
export function sceneEndpoint(sceneId: string): string {
  return `${ENDPOINTS.SCENES}/${sceneId}`;
}

/**
 * Build a TV control endpoint URL
 */
export function tvEndpoint(action: string): string {
  return `${ENDPOINTS.TV}/${action}`;
}

/**
 * Build a locks action endpoint URL
 */
export function locksEndpoint(action: string): string {
  return `${ENDPOINTS.LOCKS}/${action}`;
}

/*
 * 鏡
 * Unified TypeScript Types: Type safety for Desktop.
 * h(x) >= 0. Always.
 */
