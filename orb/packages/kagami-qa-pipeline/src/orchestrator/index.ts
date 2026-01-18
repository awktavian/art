/**
 * Constellation Orchestrator Module
 *
 * Exports all components needed for multi-device constellation testing.
 *
 * @example
 * ```typescript
 * import {
 *   ConstellationOrchestrator,
 *   FIBONACCI_TIMEOUTS,
 * } from '@kagami/qa-pipeline/orchestrator';
 *
 * const orchestrator = new ConstellationOrchestrator({
 *   enableSimulatedMDNS: true,
 * });
 *
 * await orchestrator.discoverDevices();
 * const result = await orchestrator.startConstellation('C01_WATCH_TO_PHONE_HANDOFF');
 * ```
 */

export {
  // Main orchestrator class
  ConstellationOrchestrator,

  // mDNS implementations
  MDNSParser,
  RealMDNS,
  SimulatedMDNS,
  MDNSParseError,

  // Device drivers
  ADBDriver,
  SimctlDriver,
  HubTCPDriver,
  DesktopWebSocketDriver,

  // Timing utilities
  FIBONACCI_TIMEOUTS,
  getFibonacciTimeout,
} from './constellation-orchestrator.js';

export type {
  // Journey types
  ConstellationJourneySpec,

  // Device types
  DeviceConnectionState,
  DiscoveredDevice,
  DeviceConnection,
  DeviceCommand,
  DeviceResponse,
  DeviceDriver,

  // Result types
  PhaseResult,
  CheckpointResult,
  ConstellationResult,

  // Configuration types
  MDNSServiceRecord,
  ConstellationOrchestratorOptions,

  // mDNS error types
  MDNSErrorCode,
} from './constellation-orchestrator.js';
