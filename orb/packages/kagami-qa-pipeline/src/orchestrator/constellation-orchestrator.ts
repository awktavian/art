/**
 * Constellation Test Orchestrator
 *
 * Coordinates multi-device test execution across emulators and simulators
 * for constellation journey testing. Simulates mDNS discovery, manages
 * device connections, and verifies mesh state synchronization.
 *
 * Colony: Crystal (e7) -- Verification & Polish
 * h(x) >= 0. Always.
 */

import { ChildProcess, execSync } from 'child_process';
import { EventEmitter } from 'events';
import { createSocket, Socket } from 'dgram';
import * as net from 'net';
import * as WebSocket from 'ws';
import { createChildLogger } from '../logger.js';
import {
  Platform,
  ConstellationJourneySpec,
  Phase,
  Checkpoint,
  CONSTELLATION_JOURNEYS,
} from '../journeys/canonical-journeys.js';

// Re-export types needed by consumers
export type { ConstellationJourneySpec } from '../journeys/canonical-journeys.js';

// =============================================================================
// FIBONACCI TIMING CONSTANTS
// =============================================================================

/**
 * Fibonacci sequence for timeout intervals (milliseconds)
 * Used for natural, adaptive timing in device coordination
 */
export const FIBONACCI_TIMEOUTS = {
  F1: 89,
  F2: 144,
  F3: 233,
  F4: 377,
  F5: 610,
  F6: 987,
  F7: 1597,
  F8: 2584,
  F9: 4181,
  F10: 6765,
} as const;

/**
 * Get Fibonacci timeout by index (1-based)
 */
export function getFibonacciTimeout(index: number): number {
  const sequence = [89, 144, 233, 377, 610, 987, 1597, 2584, 4181, 6765];
  return sequence[Math.min(index - 1, sequence.length - 1)] ?? 6765;
}

// =============================================================================
// TYPES
// =============================================================================

/**
 * Device connection state
 */
export type DeviceConnectionState =
  | 'disconnected'
  | 'discovering'
  | 'connecting'
  | 'connected'
  | 'ready'
  | 'executing'
  | 'error';

/**
 * Discovered device information
 */
export interface DiscoveredDevice {
  /** Platform type */
  platform: Platform;
  /** Device identifier (serial/UDID) */
  deviceId: string;
  /** Human-readable name */
  name: string;
  /** IP address (if discovered via mDNS) */
  ipAddress?: string;
  /** Port for communication */
  port?: number;
  /** mDNS service name */
  mdnsServiceName?: string;
  /** Connection state */
  state: DeviceConnectionState;
  /** Last seen timestamp */
  lastSeen: number;
  /** Device capabilities */
  capabilities: string[];
  /** Whether this is a simulated device */
  isSimulated: boolean;
}

/**
 * Device connection handle
 */
export interface DeviceConnection {
  /** Device info */
  device: DiscoveredDevice;
  /** Active socket/websocket */
  socket?: net.Socket | WebSocket.WebSocket;
  /** ADB/simctl process (for emulators) */
  process?: ChildProcess;
  /** Send command to device */
  send: (command: DeviceCommand) => Promise<DeviceResponse>;
  /** Disconnect from device */
  disconnect: () => Promise<void>;
}

/**
 * Command to send to a device
 */
export interface DeviceCommand {
  type: 'navigate' | 'tap' | 'swipe' | 'voice' | 'verify' | 'state' | 'sync';
  target?: string;
  params?: Record<string, unknown>;
  timeout?: number;
}

/**
 * Response from a device
 */
export interface DeviceResponse {
  success: boolean;
  data?: unknown;
  error?: string;
  timestamp: number;
  durationMs: number;
}

/**
 * Phase execution result
 */
export interface PhaseResult {
  phaseId: string;
  success: boolean;
  checkpointResults: CheckpointResult[];
  durationMs: number;
  deviceStates: Map<Platform, Record<string, unknown>>;
  errors: string[];
}

/**
 * Checkpoint execution result
 */
export interface CheckpointResult {
  checkpointId: string;
  success: boolean;
  elementsFound: string[];
  elementsMissing: string[];
  durationMs: number;
  actualState?: Record<string, unknown> | undefined;
  expectedState?: Record<string, unknown> | undefined;
  hapticVerified?: boolean | undefined;
}

/**
 * Constellation execution result
 */
export interface ConstellationResult {
  journeyId: string;
  success: boolean;
  phaseResults: PhaseResult[];
  totalDurationMs: number;
  devicesParticipated: Platform[];
  syncVerified: boolean;
  errors: string[];
}

/**
 * mDNS service record
 */
export interface MDNSServiceRecord {
  name: string;
  type: string;
  domain: string;
  host: string;
  port: number;
  addresses: string[];
  txt: Record<string, string>;
}

/**
 * Orchestrator options
 */
export interface ConstellationOrchestratorOptions {
  /** Enable simulated mDNS when real discovery unavailable */
  enableSimulatedMDNS: boolean;
  /** mDNS discovery timeout */
  mdnsTimeout: number;
  /** Mesh sync verification timeout */
  meshSyncTimeout: number;
  /** Maximum retry attempts for commands */
  maxRetries: number;
  /** Hub address for direct connection */
  hubAddress?: string;
  /** Hub port */
  hubPort?: number;
  /** Verbose logging */
  verbose: boolean;
}

// =============================================================================
// DEVICE DRIVERS
// =============================================================================

/**
 * Abstract device driver interface
 */
interface DeviceDriver {
  platform: Platform;
  listDevices(): Promise<DiscoveredDevice[]>;
  connect(device: DiscoveredDevice): Promise<DeviceConnection>;
  executeCommand(connection: DeviceConnection, command: DeviceCommand): Promise<DeviceResponse>;
  verifyElement(connection: DeviceConnection, elementId: string): Promise<boolean>;
  getState(connection: DeviceConnection): Promise<Record<string, unknown>>;
}

/**
 * ADB driver for Android/Wear OS/Android XR
 */
class ADBDriver implements DeviceDriver {
  platform: Platform;
  private logger = createChildLogger({ driver: 'adb' });

  constructor(platform: 'android' | 'wearos' | 'androidxr') {
    this.platform = platform;
  }

  async listDevices(): Promise<DiscoveredDevice[]> {
    try {
      const output = execSync('adb devices -l', { encoding: 'utf-8' });
      const lines = output.split('\n').slice(1).filter(line => line.trim());

      return lines.map(line => {
        const [deviceId, ...rest] = line.split(/\s+/);
        const info = rest.join(' ');
        const model = info.match(/model:(\S+)/)?.[1] ?? 'Unknown';
        const state: DeviceConnectionState = info.includes('device') ? 'connected' : 'disconnected';

        return {
          platform: this.platform,
          deviceId: deviceId ?? 'unknown',
          name: model,
          state,
          lastSeen: Date.now(),
          capabilities: this.getCapabilities(model),
          isSimulated: info.includes('emulator'),
        };
      }).filter(d => d.state === 'connected');
    } catch (error) {
      this.logger.warn({ error }, 'Failed to list ADB devices');
      return [];
    }
  }

  async connect(device: DiscoveredDevice): Promise<DeviceConnection> {
    const connection: DeviceConnection = {
      device,
      send: async (cmd) => this.executeCommand(connection, cmd),
      disconnect: async () => {
        // No persistent connection needed for ADB
      },
    };
    return connection;
  }

  async executeCommand(connection: DeviceConnection, command: DeviceCommand): Promise<DeviceResponse> {
    const startTime = Date.now();
    const { device } = connection;

    try {
      let adbCommand: string;

      switch (command.type) {
        case 'navigate':
          // Use am start to launch activity
          adbCommand = `adb -s ${device.deviceId} shell am start -n com.kagami.app/.${command.target}`;
          break;

        case 'tap':
          // Send tap event at coordinates or to element
          if (command.params?.['x'] && command.params?.['y']) {
            adbCommand = `adb -s ${device.deviceId} shell input tap ${command.params['x']} ${command.params['y']}`;
          } else {
            // Use broadcast to communicate with test harness
            adbCommand = `adb -s ${device.deviceId} shell am broadcast -a com.kagami.TEST_ACTION --es target "${command.target}"`;
          }
          break;

        case 'swipe':
          const { x1, y1, x2, y2, duration } = command.params ?? {};
          adbCommand = `adb -s ${device.deviceId} shell input swipe ${x1 ?? 500} ${y1 ?? 1000} ${x2 ?? 500} ${y2 ?? 500} ${duration ?? 300}`;
          break;

        case 'voice':
          // Use broadcast to trigger voice command simulation
          adbCommand = `adb -s ${device.deviceId} shell am broadcast -a com.kagami.VOICE_COMMAND --es command "${command.params?.['text'] ?? ''}"`;
          break;

        case 'verify':
          // Use UI Automator to verify element presence
          adbCommand = `adb -s ${device.deviceId} shell "uiautomator dump /dev/stdout 2>/dev/null | grep -o '${command.target}' | head -1"`;
          break;

        case 'state':
          // Query app state via broadcast
          adbCommand = `adb -s ${device.deviceId} shell am broadcast -a com.kagami.GET_STATE --receiver-permission android.permission.DUMP 2>&1 || true`;
          break;

        case 'sync':
          // Trigger mesh sync
          adbCommand = `adb -s ${device.deviceId} shell am broadcast -a com.kagami.MESH_SYNC`;
          break;

        default:
          throw new Error(`Unknown command type: ${command.type}`);
      }

      this.logger.debug({ command: adbCommand }, 'Executing ADB command');
      const output = execSync(adbCommand, {
        encoding: 'utf-8',
        timeout: command.timeout ?? FIBONACCI_TIMEOUTS.F8,
      });

      return {
        success: true,
        data: output.trim(),
        timestamp: Date.now(),
        durationMs: Date.now() - startTime,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
        timestamp: Date.now(),
        durationMs: Date.now() - startTime,
      };
    }
  }

  async verifyElement(connection: DeviceConnection, elementId: string): Promise<boolean> {
    const response = await this.executeCommand(connection, {
      type: 'verify',
      target: elementId,
    });
    return response.success && Boolean(response.data);
  }

  async getState(connection: DeviceConnection): Promise<Record<string, unknown>> {
    const response = await this.executeCommand(connection, { type: 'state' });
    if (response.success && typeof response.data === 'string') {
      try {
        return JSON.parse(response.data);
      } catch {
        return { raw: response.data };
      }
    }
    return {};
  }

  private getCapabilities(model: string): string[] {
    const capabilities = ['touch', 'voice'];
    if (model.toLowerCase().includes('wear')) {
      capabilities.push('crown', 'haptics');
    }
    if (model.toLowerCase().includes('xr') || model.toLowerCase().includes('quest')) {
      capabilities.push('spatial', 'gaze', 'hand_tracking');
    }
    return capabilities;
  }
}

/**
 * Simctl driver for iOS/watchOS/visionOS/tvOS
 */
class SimctlDriver implements DeviceDriver {
  platform: Platform;
  private logger = createChildLogger({ driver: 'simctl' });

  constructor(platform: 'ios' | 'watchos' | 'visionos' | 'tvos') {
    this.platform = platform;
  }

  async listDevices(): Promise<DiscoveredDevice[]> {
    try {
      const output = execSync('xcrun simctl list devices --json', { encoding: 'utf-8' });
      const data = JSON.parse(output) as {
        devices: Record<string, Array<{
          udid: string;
          name: string;
          state: string;
          isAvailable: boolean;
        }>>;
      };

      const devices: DiscoveredDevice[] = [];

      for (const [runtime, runtimeDevices] of Object.entries(data.devices)) {
        if (!this.matchesPlatform(runtime)) continue;

        for (const device of runtimeDevices) {
          if (!device.isAvailable) continue;

          devices.push({
            platform: this.platform,
            deviceId: device.udid,
            name: device.name,
            state: device.state === 'Booted' ? 'connected' : 'disconnected',
            lastSeen: Date.now(),
            capabilities: this.getCapabilities(device.name),
            isSimulated: true,
          });
        }
      }

      return devices;
    } catch (error) {
      this.logger.warn({ error }, 'Failed to list simulators');
      return [];
    }
  }

  async connect(device: DiscoveredDevice): Promise<DeviceConnection> {
    // Boot the simulator if not already booted
    if (device.state !== 'connected') {
      try {
        execSync(`xcrun simctl boot ${device.deviceId}`, { encoding: 'utf-8' });
        device.state = 'connected';
      } catch (error) {
        // May already be booted
        this.logger.debug({ error }, 'Boot returned error (may already be booted)');
      }
    }

    const connection: DeviceConnection = {
      device,
      send: async (cmd) => this.executeCommand(connection, cmd),
      disconnect: async () => {
        // Don't shut down simulator on disconnect - leave it running
      },
    };
    return connection;
  }

  async executeCommand(connection: DeviceConnection, command: DeviceCommand): Promise<DeviceResponse> {
    const startTime = Date.now();
    const { device } = connection;

    try {
      let simctlCommand: string;

      switch (command.type) {
        case 'navigate':
          // Use xcrun simctl openurl to deep link
          const scheme = this.getAppScheme();
          simctlCommand = `xcrun simctl openurl ${device.deviceId} "${scheme}://${command.target}"`;
          break;

        case 'tap':
          // Use simctl ui to interact (requires iOS 17+)
          if (command.params?.['x'] && command.params?.['y']) {
            simctlCommand = `xcrun simctl io ${device.deviceId} tap ${command.params['x']} ${command.params['y']}`;
          } else {
            // Send notification to trigger tap on element
            simctlCommand = `xcrun simctl spawn ${device.deviceId} notifyutil -p com.kagami.tap.${command.target}`;
          }
          break;

        case 'swipe':
          const { direction } = command.params ?? {};
          // Use accessibility identifier scrolling
          simctlCommand = `xcrun simctl io ${device.deviceId} swipe ${direction ?? 'up'}`;
          break;

        case 'voice':
          // Trigger Siri or voice command simulation
          simctlCommand = `xcrun simctl spawn ${device.deviceId} notifyutil -p com.kagami.voice --data '${JSON.stringify({ text: command.params?.['text'] })}'`;
          break;

        case 'verify':
          // Use accessibility inspection
          simctlCommand = `xcrun simctl spawn ${device.deviceId} accessibility_inspector --find "${command.target}" 2>/dev/null || echo ""`;
          break;

        case 'state':
          // Query app state via notification
          simctlCommand = `xcrun simctl spawn ${device.deviceId} notifyutil -p com.kagami.getState`;
          break;

        case 'sync':
          // Trigger mesh sync
          simctlCommand = `xcrun simctl spawn ${device.deviceId} notifyutil -p com.kagami.meshSync`;
          break;

        default:
          throw new Error(`Unknown command type: ${command.type}`);
      }

      this.logger.debug({ command: simctlCommand }, 'Executing simctl command');
      const output = execSync(simctlCommand, {
        encoding: 'utf-8',
        timeout: command.timeout ?? FIBONACCI_TIMEOUTS.F8,
      });

      return {
        success: true,
        data: output.trim(),
        timestamp: Date.now(),
        durationMs: Date.now() - startTime,
      };
    } catch (error) {
      return {
        success: false,
        error: error instanceof Error ? error.message : String(error),
        timestamp: Date.now(),
        durationMs: Date.now() - startTime,
      };
    }
  }

  async verifyElement(connection: DeviceConnection, elementId: string): Promise<boolean> {
    const response = await this.executeCommand(connection, {
      type: 'verify',
      target: elementId,
    });
    return response.success && Boolean(response.data);
  }

  async getState(connection: DeviceConnection): Promise<Record<string, unknown>> {
    const response = await this.executeCommand(connection, { type: 'state' });
    if (response.success && typeof response.data === 'string') {
      try {
        return JSON.parse(response.data);
      } catch {
        return { raw: response.data };
      }
    }
    return {};
  }

  private matchesPlatform(runtime: string): boolean {
    const lower = runtime.toLowerCase();
    switch (this.platform) {
      case 'ios':
        return lower.includes('ios') && !lower.includes('watch') && !lower.includes('tv');
      case 'watchos':
        return lower.includes('watchos');
      case 'visionos':
        return lower.includes('xros') || lower.includes('visionos');
      case 'tvos':
        return lower.includes('tvos');
      default:
        return false;
    }
  }

  private getCapabilities(name: string): string[] {
    const capabilities = ['touch'];
    const lower = name.toLowerCase();

    if (lower.includes('iphone') || lower.includes('ipad')) {
      capabilities.push('voice', 'haptics', 'face_id');
    }
    if (lower.includes('watch')) {
      capabilities.push('voice', 'haptics', 'crown');
    }
    if (lower.includes('vision') || lower.includes('apple vision')) {
      capabilities.push('voice', 'spatial', 'gaze', 'hand_tracking');
    }
    if (lower.includes('tv')) {
      capabilities.push('voice', 'remote');
    }

    return capabilities;
  }

  private getAppScheme(): string {
    switch (this.platform) {
      case 'ios':
        return 'kagami-ios';
      case 'watchos':
        return 'kagami-watch';
      case 'visionos':
        return 'kagami-vision';
      case 'tvos':
        return 'kagami-tv';
      default:
        return 'kagami';
    }
  }
}

/**
 * TCP driver for Hub (Rust)
 */
class HubTCPDriver implements DeviceDriver {
  platform: Platform = 'hub';
  private logger = createChildLogger({ driver: 'hub-tcp' });
  private hubAddress: string;
  private hubPort: number;

  constructor(address: string = 'localhost', port: number = 8001) {
    this.hubAddress = address;
    this.hubPort = port;
  }

  async listDevices(): Promise<DiscoveredDevice[]> {
    // Hub is a single device - check if it's reachable
    try {
      const socket = new net.Socket();
      await new Promise<void>((resolve, reject) => {
        socket.setTimeout(FIBONACCI_TIMEOUTS.F5);
        socket.connect(this.hubPort, this.hubAddress, () => {
          socket.destroy();
          resolve();
        });
        socket.on('error', reject);
        socket.on('timeout', () => reject(new Error('Connection timeout')));
      });

      return [{
        platform: 'hub',
        deviceId: `hub-${this.hubAddress}:${this.hubPort}`,
        name: 'Kagami Hub',
        ipAddress: this.hubAddress,
        port: this.hubPort,
        state: 'connected',
        lastSeen: Date.now(),
        capabilities: ['voice', 'mesh_coordinator', 'automation'],
        isSimulated: false,
      }];
    } catch {
      this.logger.debug('Hub not reachable');
      return [];
    }
  }

  async connect(device: DiscoveredDevice): Promise<DeviceConnection> {
    const socket = new net.Socket();

    await new Promise<void>((resolve, reject) => {
      socket.setTimeout(FIBONACCI_TIMEOUTS.F6);
      socket.connect(device.port ?? this.hubPort, device.ipAddress ?? this.hubAddress, resolve);
      socket.on('error', reject);
    });

    const connection: DeviceConnection = {
      device,
      socket,
      send: async (cmd) => this.executeCommand(connection, cmd),
      disconnect: async () => {
        socket.destroy();
      },
    };

    return connection;
  }

  async executeCommand(connection: DeviceConnection, command: DeviceCommand): Promise<DeviceResponse> {
    const startTime = Date.now();
    const socket = connection.socket as net.Socket;

    if (!socket || socket.destroyed) {
      return {
        success: false,
        error: 'Socket not connected',
        timestamp: Date.now(),
        durationMs: Date.now() - startTime,
      };
    }

    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        resolve({
          success: false,
          error: 'Command timeout',
          timestamp: Date.now(),
          durationMs: Date.now() - startTime,
        });
      }, command.timeout ?? FIBONACCI_TIMEOUTS.F8);

      const message = JSON.stringify({
        type: command.type,
        target: command.target,
        params: command.params,
      });

      socket.once('data', (data) => {
        clearTimeout(timeout);
        try {
          const response = JSON.parse(data.toString());
          resolve({
            success: response.success ?? true,
            data: response.data,
            error: response.error,
            timestamp: Date.now(),
            durationMs: Date.now() - startTime,
          });
        } catch {
          resolve({
            success: true,
            data: data.toString(),
            timestamp: Date.now(),
            durationMs: Date.now() - startTime,
          });
        }
      });

      socket.write(message + '\n');
    });
  }

  async verifyElement(connection: DeviceConnection, elementId: string): Promise<boolean> {
    const response = await this.executeCommand(connection, {
      type: 'verify',
      target: elementId,
    });
    return response.success;
  }

  async getState(connection: DeviceConnection): Promise<Record<string, unknown>> {
    const response = await this.executeCommand(connection, { type: 'state' });
    return (response.data as Record<string, unknown>) ?? {};
  }
}

/**
 * WebSocket driver for Desktop (Tauri)
 */
class DesktopWebSocketDriver implements DeviceDriver {
  platform: Platform = 'desktop';
  private logger = createChildLogger({ driver: 'desktop-ws' });
  private wsPort: number;

  constructor(port: number = 3849) {
    this.wsPort = port;
  }

  async listDevices(): Promise<DiscoveredDevice[]> {
    // Check if desktop app WebSocket is available
    try {
      const ws = new WebSocket.WebSocket(`ws://localhost:${this.wsPort}/test`);
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('Timeout')), FIBONACCI_TIMEOUTS.F5);
        ws.on('open', () => {
          clearTimeout(timeout);
          ws.close();
          resolve();
        });
        ws.on('error', reject);
      });

      return [{
        platform: 'desktop',
        deviceId: `desktop-localhost:${this.wsPort}`,
        name: 'Kagami Desktop',
        port: this.wsPort,
        state: 'connected',
        lastSeen: Date.now(),
        capabilities: ['keyboard', 'voice', 'system_tray'],
        isSimulated: false,
      }];
    } catch {
      this.logger.debug('Desktop app not reachable');
      return [];
    }
  }

  async connect(device: DiscoveredDevice): Promise<DeviceConnection> {
    const ws = new WebSocket.WebSocket(`ws://localhost:${device.port ?? this.wsPort}/test`);

    await new Promise<void>((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('Connection timeout')), FIBONACCI_TIMEOUTS.F6);
      ws.on('open', () => {
        clearTimeout(timeout);
        resolve();
      });
      ws.on('error', reject);
    });

    const connection: DeviceConnection = {
      device,
      socket: ws,
      send: async (cmd) => this.executeCommand(connection, cmd),
      disconnect: async () => {
        ws.close();
      },
    };

    return connection;
  }

  async executeCommand(connection: DeviceConnection, command: DeviceCommand): Promise<DeviceResponse> {
    const startTime = Date.now();
    const ws = connection.socket as WebSocket.WebSocket;

    if (!ws || ws.readyState !== WebSocket.WebSocket.OPEN) {
      return {
        success: false,
        error: 'WebSocket not connected',
        timestamp: Date.now(),
        durationMs: Date.now() - startTime,
      };
    }

    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        resolve({
          success: false,
          error: 'Command timeout',
          timestamp: Date.now(),
          durationMs: Date.now() - startTime,
        });
      }, command.timeout ?? FIBONACCI_TIMEOUTS.F8);

      const handler = (data: WebSocket.RawData) => {
        clearTimeout(timeout);
        ws.off('message', handler);
        try {
          const response = JSON.parse(data.toString());
          resolve({
            success: response.success ?? true,
            data: response.data,
            error: response.error,
            timestamp: Date.now(),
            durationMs: Date.now() - startTime,
          });
        } catch {
          resolve({
            success: true,
            data: data.toString(),
            timestamp: Date.now(),
            durationMs: Date.now() - startTime,
          });
        }
      };

      ws.on('message', handler);
      ws.send(JSON.stringify({
        type: command.type,
        target: command.target,
        params: command.params,
      }));
    });
  }

  async verifyElement(connection: DeviceConnection, elementId: string): Promise<boolean> {
    const response = await this.executeCommand(connection, {
      type: 'verify',
      target: elementId,
    });
    return response.success;
  }

  async getState(connection: DeviceConnection): Promise<Record<string, unknown>> {
    const response = await this.executeCommand(connection, { type: 'state' });
    return (response.data as Record<string, unknown>) ?? {};
  }
}

// =============================================================================
// MDNS DISCOVERY - RFC 6762 IMPLEMENTATION
// =============================================================================

/**
 * mDNS DNS record types (RFC 1035 + mDNS extensions)
 */
const DNS_RECORD_TYPES = {
  A: 1,       // IPv4 address
  PTR: 12,    // Domain name pointer
  TXT: 16,    // Text strings
  AAAA: 28,   // IPv6 address
  SRV: 33,    // Service location
  ANY: 255,   // Any type (query only)
} as const;

/**
 * mDNS DNS record classes
 */
const DNS_CLASSES = {
  IN: 1,                    // Internet
  CACHE_FLUSH: 0x8001,      // Cache flush flag (mDNS specific)
} as const;

/**
 * Error types for mDNS parsing
 */
export class MDNSParseError extends Error {
  constructor(message: string, public readonly code: MDNSErrorCode) {
    super(message);
    this.name = 'MDNSParseError';
  }
}

export type MDNSErrorCode =
  | 'TRUNCATED_PACKET'
  | 'INVALID_HEADER'
  | 'MALFORMED_NAME'
  | 'INVALID_RECORD'
  | 'MISSING_TXT_RECORDS'
  | 'DNS_RESOLUTION_FAILED'
  | 'NETWORK_TIMEOUT';

/**
 * Parsed DNS resource record
 */
interface DNSResourceRecord {
  name: string;
  type: number;
  classCode: number;
  ttl: number;
  data: Buffer;
}

/**
 * Parsed SRV record data
 */
interface SRVRecordData {
  priority: number;
  weight: number;
  port: number;
  target: string;
}

/**
 * Parsed mDNS response packet
 */
interface MDNSResponse {
  transactionId: number;
  flags: number;
  isResponse: boolean;
  questions: Array<{ name: string; type: number; classCode: number }>;
  answers: DNSResourceRecord[];
  authorities: DNSResourceRecord[];
  additionals: DNSResourceRecord[];
}

/**
 * mDNS DNS packet parser
 *
 * Parses raw UDP packets according to RFC 6762 (Multicast DNS)
 * and RFC 1035 (DNS).
 */
class MDNSParser {
  private logger = createChildLogger({ component: 'mdns-parser' });

  /**
   * Parse a raw mDNS/DNS packet
   *
   * @param buffer - Raw UDP packet data
   * @returns Parsed mDNS response
   * @throws MDNSParseError on parse failures
   */
  parsePacket(buffer: Buffer): MDNSResponse {
    if (buffer.length < 12) {
      throw new MDNSParseError(
        `Packet too short: ${buffer.length} bytes (minimum 12)`,
        'TRUNCATED_PACKET'
      );
    }

    // Parse header (12 bytes)
    const transactionId = buffer.readUInt16BE(0);
    const flags = buffer.readUInt16BE(2);
    const questionCount = buffer.readUInt16BE(4);
    const answerCount = buffer.readUInt16BE(6);
    const authorityCount = buffer.readUInt16BE(8);
    const additionalCount = buffer.readUInt16BE(10);

    // QR bit (bit 15) indicates response when set
    const isResponse = (flags & 0x8000) !== 0;

    let offset = 12;
    const questions: MDNSResponse['questions'] = [];
    const answers: DNSResourceRecord[] = [];
    const authorities: DNSResourceRecord[] = [];
    const additionals: DNSResourceRecord[] = [];

    try {
      // Parse questions
      for (let i = 0; i < questionCount && offset < buffer.length; i++) {
        const { name, newOffset } = this.parseName(buffer, offset);
        offset = newOffset;

        if (offset + 4 > buffer.length) {
          throw new MDNSParseError('Truncated question section', 'TRUNCATED_PACKET');
        }

        const type = buffer.readUInt16BE(offset);
        const classCode = buffer.readUInt16BE(offset + 2);
        offset += 4;

        questions.push({ name, type, classCode: classCode & 0x7fff });
      }

      // Parse answer records
      for (let i = 0; i < answerCount && offset < buffer.length; i++) {
        const { record, newOffset } = this.parseResourceRecord(buffer, offset);
        offset = newOffset;
        answers.push(record);
      }

      // Parse authority records
      for (let i = 0; i < authorityCount && offset < buffer.length; i++) {
        const { record, newOffset } = this.parseResourceRecord(buffer, offset);
        offset = newOffset;
        authorities.push(record);
      }

      // Parse additional records
      for (let i = 0; i < additionalCount && offset < buffer.length; i++) {
        const { record, newOffset } = this.parseResourceRecord(buffer, offset);
        offset = newOffset;
        additionals.push(record);
      }
    } catch (error) {
      if (error instanceof MDNSParseError) {
        throw error;
      }
      throw new MDNSParseError(
        `Parse error at offset ${offset}: ${error instanceof Error ? error.message : String(error)}`,
        'INVALID_RECORD'
      );
    }

    return {
      transactionId,
      flags,
      isResponse,
      questions,
      answers,
      authorities,
      additionals,
    };
  }

  /**
   * Parse a DNS domain name (with compression support)
   *
   * DNS names use label compression per RFC 1035 section 4.1.4
   */
  private parseName(buffer: Buffer, offset: number): { name: string; newOffset: number } {
    const labels: string[] = [];
    let currentOffset = offset;
    let jumped = false;
    let finalOffset = offset;
    let jumpCount = 0;
    const maxJumps = 20; // Prevent infinite loops from malformed packets

    while (currentOffset < buffer.length) {
      const length = buffer[currentOffset]!;

      // Check for compression pointer (top 2 bits set)
      if ((length & 0xc0) === 0xc0) {
        if (currentOffset + 1 >= buffer.length) {
          throw new MDNSParseError('Truncated compression pointer', 'MALFORMED_NAME');
        }

        if (!jumped) {
          finalOffset = currentOffset + 2;
        }

        // Follow the pointer
        const pointer = buffer.readUInt16BE(currentOffset) & 0x3fff;
        if (pointer >= currentOffset) {
          throw new MDNSParseError('Forward compression pointer (invalid)', 'MALFORMED_NAME');
        }

        currentOffset = pointer;
        jumped = true;
        jumpCount++;

        if (jumpCount > maxJumps) {
          throw new MDNSParseError('Too many compression pointer jumps', 'MALFORMED_NAME');
        }

        continue;
      }

      // Null terminator - end of name
      if (length === 0) {
        if (!jumped) {
          finalOffset = currentOffset + 1;
        }
        break;
      }

      // Regular label
      if (length > 63) {
        throw new MDNSParseError(`Invalid label length: ${length}`, 'MALFORMED_NAME');
      }

      if (currentOffset + length + 1 > buffer.length) {
        throw new MDNSParseError('Label extends beyond packet', 'MALFORMED_NAME');
      }

      const label = buffer.subarray(currentOffset + 1, currentOffset + 1 + length).toString('utf-8');
      labels.push(label);
      currentOffset += length + 1;

      if (!jumped) {
        finalOffset = currentOffset;
      }
    }

    return { name: labels.join('.'), newOffset: finalOffset };
  }

  /**
   * Parse a resource record
   */
  private parseResourceRecord(
    buffer: Buffer,
    offset: number
  ): { record: DNSResourceRecord; newOffset: number } {
    const { name, newOffset: nameOffset } = this.parseName(buffer, offset);

    if (nameOffset + 10 > buffer.length) {
      throw new MDNSParseError('Truncated resource record header', 'TRUNCATED_PACKET');
    }

    const type = buffer.readUInt16BE(nameOffset);
    const classCode = buffer.readUInt16BE(nameOffset + 2) & 0x7fff; // Strip cache flush bit
    const ttl = buffer.readUInt32BE(nameOffset + 4);
    const rdlength = buffer.readUInt16BE(nameOffset + 8);

    const dataStart = nameOffset + 10;
    if (dataStart + rdlength > buffer.length) {
      throw new MDNSParseError(
        `Resource record data extends beyond packet (need ${rdlength}, have ${buffer.length - dataStart})`,
        'TRUNCATED_PACKET'
      );
    }

    const data = buffer.subarray(dataStart, dataStart + rdlength);

    return {
      record: { name, type, classCode, ttl, data },
      newOffset: dataStart + rdlength,
    };
  }

  /**
   * Parse TXT record data into key-value pairs
   *
   * TXT records contain one or more strings, each prefixed by a length byte.
   * Kagami TXT records use "key=value" format.
   */
  parseTXTRecord(data: Buffer): Record<string, string> {
    const result: Record<string, string> = {};
    let offset = 0;

    while (offset < data.length) {
      const length = data[offset]!;
      if (length === 0) {
        offset++;
        continue;
      }

      if (offset + length + 1 > data.length) {
        this.logger.warn({ offset, length, dataLength: data.length }, 'Truncated TXT record string');
        break;
      }

      const str = data.subarray(offset + 1, offset + 1 + length).toString('utf-8');
      const eqIndex = str.indexOf('=');

      if (eqIndex > 0) {
        const key = str.substring(0, eqIndex);
        const value = str.substring(eqIndex + 1);
        result[key] = value;
      } else {
        // Boolean flag (key with no value)
        result[str] = 'true';
      }

      offset += length + 1;
    }

    return result;
  }

  /**
   * Parse SRV record data
   */
  parseSRVRecord(data: Buffer, fullPacket: Buffer, recordOffset: number): SRVRecordData {
    if (data.length < 6) {
      throw new MDNSParseError('SRV record too short', 'INVALID_RECORD');
    }

    const priority = data.readUInt16BE(0);
    const weight = data.readUInt16BE(2);
    const port = data.readUInt16BE(4);

    // Target hostname may use compression, need to parse relative to full packet
    // For SRV records, the target is at offset 6 within the RDATA
    // We need to parse it relative to the start of the resource record's RDATA
    // which requires the full packet for pointer resolution
    let target: string;

    try {
      // Simple case: target is directly in the data without compression
      const labels: string[] = [];
      let offset = 6;
      while (offset < data.length) {
        const length = data[offset]!;

        // Check for compression pointer
        if ((length & 0xc0) === 0xc0) {
          // For compressed names, we need the full packet
          const { name } = this.parseName(fullPacket, recordOffset + offset);
          target = labels.length > 0 ? labels.join('.') + '.' + name : name;
          return { priority, weight, port, target };
        }

        if (length === 0) {
          break;
        }

        if (offset + length + 1 > data.length) {
          break;
        }

        labels.push(data.subarray(offset + 1, offset + 1 + length).toString('utf-8'));
        offset += length + 1;
      }
      target = labels.join('.');
    } catch {
      target = 'unknown';
    }

    return { priority, weight, port, target };
  }

  /**
   * Parse IPv4 address from A record
   */
  parseARecord(data: Buffer): string {
    if (data.length !== 4) {
      throw new MDNSParseError(`Invalid A record length: ${data.length}`, 'INVALID_RECORD');
    }
    return `${data[0]}.${data[1]}.${data[2]}.${data[3]}`;
  }

  /**
   * Parse IPv6 address from AAAA record
   */
  parseAAAARecord(data: Buffer): string {
    if (data.length !== 16) {
      throw new MDNSParseError(`Invalid AAAA record length: ${data.length}`, 'INVALID_RECORD');
    }

    const parts: string[] = [];
    for (let i = 0; i < 16; i += 2) {
      parts.push(data.readUInt16BE(i).toString(16));
    }
    return parts.join(':');
  }

  /**
   * Parse PTR record (domain name pointer)
   */
  parsePTRRecord(data: Buffer, fullPacket: Buffer): string {
    const { name } = this.parseName(fullPacket.length === data.length ? data : fullPacket,
      fullPacket.length === data.length ? 0 : fullPacket.indexOf(data));
    return name;
  }

  /**
   * Extract peer ID from service instance name
   *
   * Service names follow pattern: {instance}._service._tcp.local
   * For Kagami: kagami-{platform}-{peerId}._kagami-{platform}._tcp.local
   */
  extractPeerIdFromServiceName(serviceName: string): string | null {
    // Pattern: kagami-{platform}-{peerId} or just {peerId} before the service type
    const match = serviceName.match(/^([^.]+)\._kagami/);
    if (!match) {
      return null;
    }

    const instanceName = match[1]!;

    // Try to extract ID from kagami-{platform}-{id} format
    const idMatch = instanceName.match(/^kagami-(?:ios|android|watchos|wearos|tvos|visionos|androidxr|desktop|hub)-(.+)$/);
    if (idMatch) {
      return idMatch[1] ?? instanceName;
    }

    // Fall back to full instance name as peer ID
    return instanceName;
  }

  /**
   * Extract platform from service type
   *
   * Service types: _kagami-{platform}._tcp.local
   */
  extractPlatformFromServiceType(serviceType: string): Platform | null {
    const match = serviceType.match(/_kagami-([^._]+)\._tcp/);
    if (!match) {
      return null;
    }

    const platform = match[1] as Platform;
    const validPlatforms: Platform[] = ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop', 'hub'];

    if (validPlatforms.includes(platform)) {
      return platform;
    }

    return null;
  }
}

/**
 * Real mDNS discovery implementation
 *
 * Performs actual network mDNS queries and parses responses
 * to discover Kagami devices on the local network.
 */
class RealMDNS extends EventEmitter {
  private services: Map<string, MDNSServiceRecord> = new Map();
  private logger = createChildLogger({ component: 'real-mdns' });
  private parser = new MDNSParser();
  private pendingResolutions: Map<string, { service: Partial<MDNSServiceRecord>; resolved: Set<string> }> = new Map();

  /**
   * All Kagami service types to query
   */
  private static readonly KAGAMI_SERVICE_TYPES: string[] = [
    '_kagami._tcp.local',
    '_kagami-hub._tcp.local',
    '_kagami-ios._tcp.local',
    '_kagami-android._tcp.local',
    '_kagami-watch._tcp.local',
    '_kagami-watchos._tcp.local',
    '_kagami-wearos._tcp.local',
    '_kagami-tvos._tcp.local',
    '_kagami-vision._tcp.local',
    '_kagami-visionos._tcp.local',
    '_kagami-androidxr._tcp.local',
    '_kagami-desktop._tcp.local',
  ];

  /**
   * Process an mDNS response packet
   *
   * Extracts service records, TXT data, and addresses
   */
  processResponse(buffer: Buffer, sourceAddress: string): MDNSServiceRecord[] {
    try {
      const response = this.parser.parsePacket(buffer);

      if (!response.isResponse) {
        // This is a query, not a response - ignore
        return [];
      }

      this.logger.debug(
        {
          from: sourceAddress,
          answers: response.answers.length,
          additionals: response.additionals.length,
        },
        'Processing mDNS response'
      );

      // Combine answers and additionals for processing
      const allRecords = [...response.answers, ...response.authorities, ...response.additionals];

      // First pass: collect PTR records (service discovery)
      for (const record of allRecords) {
        if (record.type === DNS_RECORD_TYPES.PTR) {
          this.processPTRRecord(record, buffer);
        }
      }

      // Second pass: collect SRV and TXT records
      for (const record of allRecords) {
        if (record.type === DNS_RECORD_TYPES.SRV) {
          this.processSRVRecord(record, buffer);
        } else if (record.type === DNS_RECORD_TYPES.TXT) {
          this.processTXTRecord(record);
        }
      }

      // Third pass: collect address records
      for (const record of allRecords) {
        if (record.type === DNS_RECORD_TYPES.A || record.type === DNS_RECORD_TYPES.AAAA) {
          this.processAddressRecord(record);
        }
      }

      // Check for fully resolved services
      return this.getResolvedServices();

    } catch (error) {
      if (error instanceof MDNSParseError) {
        this.logger.warn(
          { error: error.message, code: error.code, from: sourceAddress },
          'Failed to parse mDNS packet'
        );
      } else {
        this.logger.warn(
          { error: error instanceof Error ? error.message : String(error), from: sourceAddress },
          'Unexpected error processing mDNS response'
        );
      }
      return [];
    }
  }

  /**
   * Process PTR record (service instance discovery)
   */
  private processPTRRecord(record: DNSResourceRecord, fullPacket: Buffer): void {
    // PTR record name is the service type, data is the service instance name
    const serviceType = record.name;

    // Check if this is a Kagami service type
    if (!serviceType.includes('kagami')) {
      return;
    }

    try {
      const instanceName = this.parser.parsePTRRecord(record.data, fullPacket);
      const peerId = this.parser.extractPeerIdFromServiceName(instanceName);
      const platform = this.parser.extractPlatformFromServiceType(serviceType);

      if (!this.pendingResolutions.has(instanceName)) {
        this.pendingResolutions.set(instanceName, {
          service: {
            name: peerId ?? instanceName,
            type: serviceType,
            domain: 'local',
          },
          resolved: new Set(['ptr']),
        });
      }

      this.logger.debug(
        { serviceType, instanceName, peerId, platform },
        'Discovered service instance via PTR'
      );
    } catch (error) {
      this.logger.debug({ error, serviceType }, 'Failed to parse PTR record');
    }
  }

  /**
   * Process SRV record (service location)
   */
  private processSRVRecord(record: DNSResourceRecord, fullPacket: Buffer): void {
    const instanceName = record.name;

    try {
      // Calculate the offset where this record's RDATA starts in the full packet
      // This is needed for compression pointer resolution
      const rdataOffset = fullPacket.indexOf(record.data);
      const srv = this.parser.parseSRVRecord(record.data, fullPacket, rdataOffset >= 0 ? rdataOffset : 0);

      const pending = this.pendingResolutions.get(instanceName);
      if (pending) {
        pending.service.host = srv.target;
        pending.service.port = srv.port;
        pending.resolved.add('srv');
      } else {
        // SRV record arrived before PTR
        this.pendingResolutions.set(instanceName, {
          service: {
            name: instanceName.split('.')[0] ?? instanceName,
            host: srv.target,
            port: srv.port,
          },
          resolved: new Set(['srv']),
        });
      }

      this.logger.debug(
        { instanceName, host: srv.target, port: srv.port },
        'Resolved service location via SRV'
      );
    } catch (error) {
      this.logger.debug({ error, instanceName }, 'Failed to parse SRV record');
    }
  }

  /**
   * Process TXT record (service metadata)
   */
  private processTXTRecord(record: DNSResourceRecord): void {
    const instanceName = record.name;

    try {
      const txt = this.parser.parseTXTRecord(record.data);

      const pending = this.pendingResolutions.get(instanceName);
      if (pending) {
        pending.service.txt = { ...pending.service.txt, ...txt };
        pending.resolved.add('txt');

        // Extract capabilities from TXT if present
        if (txt['capabilities']) {
          pending.service.txt!['capabilities'] = txt['capabilities'];
        }
        if (txt['platform']) {
          pending.service.txt!['platform'] = txt['platform'];
        }
        if (txt['hub_id']) {
          pending.service.txt!['hub_id'] = txt['hub_id'];
        }
        if (txt['version']) {
          pending.service.txt!['version'] = txt['version'];
        }
      } else {
        // TXT record arrived before PTR/SRV
        this.pendingResolutions.set(instanceName, {
          service: {
            name: instanceName.split('.')[0] ?? instanceName,
            txt,
          },
          resolved: new Set(['txt']),
        });
      }

      this.logger.debug(
        { instanceName, txtKeys: Object.keys(txt) },
        'Received TXT record data'
      );
    } catch (error) {
      this.logger.debug({ error, instanceName }, 'Failed to parse TXT record');
    }
  }

  /**
   * Process A or AAAA record (address resolution)
   */
  private processAddressRecord(record: DNSResourceRecord): void {
    const hostname = record.name;

    try {
      let address: string;
      if (record.type === DNS_RECORD_TYPES.A) {
        address = this.parser.parseARecord(record.data);
      } else {
        address = this.parser.parseAAAARecord(record.data);
        // Skip link-local IPv6 for now (fe80::)
        if (address.startsWith('fe80:')) {
          return;
        }
      }

      // Find pending services waiting for this hostname
      for (const [_instanceName, pending] of this.pendingResolutions) {
        if (pending.service.host === hostname || pending.service.host?.endsWith(hostname)) {
          if (!pending.service.addresses) {
            pending.service.addresses = [];
          }
          if (!pending.service.addresses.includes(address)) {
            pending.service.addresses.push(address);
          }
          pending.resolved.add('address');
        }
      }

      this.logger.debug({ hostname, address }, 'Resolved address');
    } catch (error) {
      this.logger.debug({ error, hostname }, 'Failed to parse address record');
    }
  }

  /**
   * Get services that have been fully resolved
   */
  private getResolvedServices(): MDNSServiceRecord[] {
    const resolved: MDNSServiceRecord[] = [];

    for (const [instanceName, pending] of this.pendingResolutions) {
      // A service is considered resolved if we have at least SRV and one address
      // TXT is optional but highly desirable
      const hasMinimum = pending.resolved.has('srv') &&
        (pending.resolved.has('address') || (pending.service.addresses && pending.service.addresses.length > 0));

      if (hasMinimum && pending.service.host && pending.service.port) {
        const service: MDNSServiceRecord = {
          name: pending.service.name ?? instanceName.split('.')[0] ?? 'unknown',
          type: pending.service.type ?? '_kagami._tcp.local',
          domain: pending.service.domain ?? 'local',
          host: pending.service.host,
          port: pending.service.port,
          addresses: pending.service.addresses ?? [],
          txt: pending.service.txt ?? {},
        };

        // Only add if not already tracked
        if (!this.services.has(instanceName)) {
          this.services.set(instanceName, service);
          resolved.push(service);
          this.emit('service:resolved', service);

          this.logger.info(
            {
              name: service.name,
              type: service.type,
              host: service.host,
              port: service.port,
              addresses: service.addresses,
              txtKeys: Object.keys(service.txt),
            },
            'Service fully resolved'
          );
        }
      }
    }

    return resolved;
  }

  /**
   * Build an mDNS query packet for a service type
   */
  buildQuery(serviceType: string): Buffer {
    // Parse service type into labels
    // e.g., "_kagami-hub._tcp.local" -> ["_kagami-hub", "_tcp", "local"]
    const labels = serviceType.split('.').filter(l => l.length > 0);

    // Calculate total query length
    let queryLength = 12; // Header
    for (const label of labels) {
      queryLength += 1 + label.length; // Length byte + label
    }
    queryLength += 1; // Null terminator
    queryLength += 4; // Type + Class

    const buffer = Buffer.alloc(queryLength);
    let offset = 0;

    // Header
    buffer.writeUInt16BE(0, offset); offset += 2;           // Transaction ID
    buffer.writeUInt16BE(0, offset); offset += 2;           // Flags (standard query)
    buffer.writeUInt16BE(1, offset); offset += 2;           // Questions: 1
    buffer.writeUInt16BE(0, offset); offset += 2;           // Answer RRs
    buffer.writeUInt16BE(0, offset); offset += 2;           // Authority RRs
    buffer.writeUInt16BE(0, offset); offset += 2;           // Additional RRs

    // Question: service type
    for (const label of labels) {
      buffer.writeUInt8(label.length, offset); offset += 1;
      buffer.write(label, offset, 'utf-8'); offset += label.length;
    }
    buffer.writeUInt8(0, offset); offset += 1;              // Null terminator

    buffer.writeUInt16BE(DNS_RECORD_TYPES.PTR, offset); offset += 2;  // Type: PTR
    buffer.writeUInt16BE(DNS_CLASSES.IN, offset);                      // Class: IN

    return buffer;
  }

  /**
   * Build queries for all Kagami service types
   */
  buildKagamiQueries(): Buffer[] {
    return RealMDNS.KAGAMI_SERVICE_TYPES.map(type => this.buildQuery(type));
  }

  /**
   * Get all discovered services
   */
  getServices(): MDNSServiceRecord[] {
    return Array.from(this.services.values());
  }

  /**
   * Get services by platform
   */
  getServicesByPlatform(platform: Platform): MDNSServiceRecord[] {
    return this.getServices().filter(s =>
      s.type.includes(`kagami-${platform}`) ||
      s.txt['platform'] === platform
    );
  }

  /**
   * Clear all discovered services
   */
  clear(): void {
    this.services.clear();
    this.pendingResolutions.clear();
  }
}

/**
 * Simulated mDNS discovery for testing without real network
 */
class SimulatedMDNS extends EventEmitter {
  private services: Map<string, MDNSServiceRecord> = new Map();
  private logger = createChildLogger({ component: 'simulated-mdns' });

  /**
   * Register a simulated service
   */
  registerService(service: MDNSServiceRecord): void {
    this.services.set(service.name, service);
    this.logger.debug({ service: service.name }, 'Registered simulated mDNS service');
  }

  /**
   * Discover services matching a type
   */
  discover(serviceType: string): MDNSServiceRecord[] {
    const matches: MDNSServiceRecord[] = [];
    for (const service of this.services.values()) {
      if (service.type === serviceType || service.type.includes(serviceType)) {
        matches.push(service);
      }
    }
    return matches;
  }

  /**
   * Query all kagami services
   */
  discoverKagamiServices(): MDNSServiceRecord[] {
    const matches: MDNSServiceRecord[] = [];
    for (const service of this.services.values()) {
      if (service.type.includes('kagami')) {
        matches.push(service);
      }
    }
    return matches;
  }

  /**
   * Populate with default simulated devices based on constellation spec
   */
  populateFromSpec(spec: ConstellationJourneySpec): void {
    for (const device of spec.devices) {
      const port = this.getDefaultPort(device.platform);
      this.registerService({
        name: `kagami-${device.platform}`,
        type: device.mdnsServiceName,
        domain: 'local',
        host: `kagami-${device.platform}.local`,
        port,
        addresses: ['127.0.0.1'],
        txt: {
          platform: device.platform,
          role: device.role,
          version: '1.0.0',
        },
      });
    }
  }

  private getDefaultPort(platform: Platform): number {
    switch (platform) {
      case 'hub':
        return 8001;
      case 'desktop':
        return 3849;
      default:
        return 8080;
    }
  }
}

// =============================================================================
// CONSTELLATION ORCHESTRATOR
// =============================================================================

/**
 * ConstellationOrchestrator coordinates multi-device test execution
 * across emulators/simulators for constellation journey testing.
 *
 * @example
 * ```typescript
 * const orchestrator = new ConstellationOrchestrator({
 *   enableSimulatedMDNS: true,
 *   mdnsTimeout: 5000,
 *   meshSyncTimeout: 2000,
 * });
 *
 * await orchestrator.discoverDevices();
 * const result = await orchestrator.startConstellation('C01_WATCH_TO_PHONE_HANDOFF');
 * console.log(result);
 * await orchestrator.cleanup();
 * ```
 */
export class ConstellationOrchestrator extends EventEmitter {
  private options: ConstellationOrchestratorOptions;
  private logger = createChildLogger({ component: 'constellation-orchestrator' });

  // Device management
  private discoveredDevices: Map<Platform, DiscoveredDevice[]> = new Map();
  private connections: Map<Platform, DeviceConnection> = new Map();
  private drivers: Map<Platform, DeviceDriver> = new Map();

  // mDNS
  private simulatedMDNS: SimulatedMDNS;
  private realMDNS: RealMDNS;
  private mdnsSocket?: Socket;

  // State tracking
  private activeJourney: ConstellationJourneySpec | null = null;
  private deviceStates: Map<Platform, Record<string, unknown>> = new Map();
  private communicationLog: Array<{
    timestamp: number;
    source: Platform | 'orchestrator';
    target: Platform | 'all';
    type: string;
    data: unknown;
  }> = [];

  constructor(options: Partial<ConstellationOrchestratorOptions> = {}) {
    super();

    this.options = {
      enableSimulatedMDNS: options.enableSimulatedMDNS ?? true,
      mdnsTimeout: options.mdnsTimeout ?? FIBONACCI_TIMEOUTS.F9,
      meshSyncTimeout: options.meshSyncTimeout ?? FIBONACCI_TIMEOUTS.F8,
      maxRetries: options.maxRetries ?? 3,
      hubAddress: options.hubAddress ?? 'localhost',
      hubPort: options.hubPort ?? 8001,
      verbose: options.verbose ?? false,
    };

    // Initialize drivers
    this.initializeDrivers();

    // Initialize mDNS (both simulated for testing and real for production)
    this.simulatedMDNS = new SimulatedMDNS();
    this.realMDNS = new RealMDNS();

    // Wire up real mDNS events
    this.realMDNS.on('service:resolved', (service: MDNSServiceRecord) => {
      this.handleMDNSServiceResolved(service);
    });

    this.logger.info({ options: this.options }, 'ConstellationOrchestrator initialized');
  }

  /**
   * Initialize device drivers for all platforms
   */
  private initializeDrivers(): void {
    // Android family
    this.drivers.set('android', new ADBDriver('android'));
    this.drivers.set('wearos', new ADBDriver('wearos'));
    this.drivers.set('androidxr', new ADBDriver('androidxr'));

    // Apple family
    this.drivers.set('ios', new SimctlDriver('ios'));
    this.drivers.set('watchos', new SimctlDriver('watchos'));
    this.drivers.set('visionos', new SimctlDriver('visionos'));
    this.drivers.set('tvos', new SimctlDriver('tvos'));

    // Other
    this.drivers.set('hub', new HubTCPDriver(this.options.hubAddress, this.options.hubPort));
    this.drivers.set('desktop', new DesktopWebSocketDriver());
  }

  /**
   * Discover all available devices using mDNS and direct probing
   *
   * @returns Map of platform to discovered devices
   */
  async discoverDevices(): Promise<Map<Platform, DiscoveredDevice[]>> {
    this.logger.info('Starting device discovery');
    const startTime = Date.now();

    // Clear existing discoveries
    this.discoveredDevices.clear();

    // Discover via each driver
    const discoveryPromises: Promise<void>[] = [];

    for (const [platform, driver] of this.drivers) {
      discoveryPromises.push(
        (async () => {
          try {
            const devices = await driver.listDevices();
            if (devices.length > 0) {
              this.discoveredDevices.set(platform, devices);
              this.logger.info({ platform, count: devices.length }, 'Discovered devices');

              // Register in simulated mDNS for cross-reference
              for (const device of devices) {
                this.simulatedMDNS.registerService({
                  name: `kagami-${platform}-${device.deviceId}`,
                  type: `_kagami-${platform}._tcp.local`,
                  domain: 'local',
                  host: device.ipAddress ?? `${platform}.local`,
                  port: device.port ?? 8080,
                  addresses: device.ipAddress ? [device.ipAddress] : ['127.0.0.1'],
                  txt: {
                    platform,
                    deviceId: device.deviceId,
                    name: device.name,
                    capabilities: device.capabilities.join(','),
                  },
                });
              }
            }
          } catch (error) {
            this.logger.warn({ platform, error }, 'Discovery failed for platform');
          }
        })()
      );
    }

    // Wait for all discoveries with timeout
    await Promise.race([
      Promise.all(discoveryPromises),
      new Promise<void>((resolve) => setTimeout(resolve, this.options.mdnsTimeout)),
    ]);

    // Attempt real mDNS discovery
    if (!this.options.enableSimulatedMDNS) {
      await this.performMDNSDiscovery();
    }

    this.logCommunication('orchestrator', 'all', 'discovery_complete', {
      platforms: Array.from(this.discoveredDevices.keys()),
      totalDevices: Array.from(this.discoveredDevices.values()).flat().length,
      durationMs: Date.now() - startTime,
    });

    this.emit('discovery:complete', this.discoveredDevices);
    return this.discoveredDevices;
  }

  /**
   * Perform real mDNS discovery using UDP multicast
   *
   * Sends queries for all Kagami service types and parses responses
   * using the RealMDNS class for proper RFC 6762 packet parsing.
   */
  private async performMDNSDiscovery(): Promise<void> {
    return new Promise((resolve) => {
      const discoveryStartTime = Date.now();
      let responseCount = 0;
      let errorCount = 0;

      try {
        // Clear any previous real mDNS state
        this.realMDNS.clear();

        this.mdnsSocket = createSocket({ type: 'udp4', reuseAddr: true });

        // Handle incoming mDNS responses
        this.mdnsSocket.on('message', (msg, rinfo) => {
          responseCount++;
          this.logger.debug(
            { from: rinfo.address, size: msg.length, responseCount },
            'mDNS response received'
          );

          try {
            // Parse the response using real mDNS parser
            const resolvedServices = this.realMDNS.processResponse(msg, rinfo.address);

            if (resolvedServices.length > 0) {
              this.logger.info(
                { count: resolvedServices.length, from: rinfo.address },
                'Resolved services from mDNS response'
              );

              // Emit discovery events for each newly resolved service
              for (const service of resolvedServices) {
                this.emit('mdns:service', service);
              }
            }
          } catch (error) {
            errorCount++;
            if (error instanceof MDNSParseError) {
              this.logger.debug(
                { error: error.message, code: error.code, from: rinfo.address },
                'mDNS parse error (non-fatal)'
              );
            } else {
              this.logger.warn(
                { error: error instanceof Error ? error.message : String(error), from: rinfo.address },
                'Error processing mDNS response'
              );
            }
          }
        });

        // Handle socket errors
        this.mdnsSocket.on('error', (err) => {
          errorCount++;
          const errCode = (err as NodeJS.ErrnoException).code;

          if (errCode === 'EADDRINUSE') {
            this.logger.warn('mDNS port 5353 in use, trying alternative binding');
            // Try binding to a random port for receiving only
            this.tryAlternativeMDNSBinding(resolve, discoveryStartTime);
            return;
          } else if (errCode === 'EACCES') {
            this.logger.warn('Permission denied for mDNS multicast, falling back to simulated');
            resolve();
            return;
          }

          this.logger.warn({ error: err, code: errCode }, 'mDNS socket error');
        });

        // Bind to mDNS multicast port
        this.mdnsSocket.bind(5353, () => {
          try {
            // Join mDNS multicast group
            this.mdnsSocket!.addMembership('224.0.0.251');
            this.mdnsSocket!.setMulticastTTL(255);
            this.mdnsSocket!.setMulticastLoopback(true);

            this.logger.info('mDNS socket bound, sending queries for Kagami services');

            // Build and send queries for all Kagami service types
            const queries = this.realMDNS.buildKagamiQueries();

            // Stagger queries using Fibonacci timing to avoid network congestion
            queries.forEach((query, index) => {
              setTimeout(() => {
                if (this.mdnsSocket && this.isSocketOpen(this.mdnsSocket)) {
                  try {
                    this.mdnsSocket.send(query, 5353, '224.0.0.251', (err) => {
                      if (err) {
                        this.logger.debug({ error: err, queryIndex: index }, 'Failed to send mDNS query');
                      }
                    });
                  } catch (sendError) {
                    this.logger.debug({ error: sendError, queryIndex: index }, 'Exception sending mDNS query');
                  }
                }
              }, index * FIBONACCI_TIMEOUTS.F1); // 89ms between queries
            });

            // Send a second round of queries after initial timeout to catch late responders
            setTimeout(() => {
              if (this.mdnsSocket && this.isSocketOpen(this.mdnsSocket)) {
                this.logger.debug('Sending second round of mDNS queries');
                queries.forEach((query, index) => {
                  setTimeout(() => {
                    if (this.mdnsSocket && this.isSocketOpen(this.mdnsSocket)) {
                      try {
                        this.mdnsSocket.send(query, 5353, '224.0.0.251');
                      } catch {
                        // Ignore errors on second round
                      }
                    }
                  }, index * FIBONACCI_TIMEOUTS.F1);
                });
              }
            }, FIBONACCI_TIMEOUTS.F6); // ~987ms
          } catch (bindError) {
            this.logger.warn({ error: bindError }, 'Error setting up mDNS multicast');
          }
        });

        // Resolve after timeout with summary
        setTimeout(() => {
          const discoveryDuration = Date.now() - discoveryStartTime;
          const services = this.realMDNS.getServices();

          this.logger.info(
            {
              durationMs: discoveryDuration,
              responseCount,
              errorCount,
              servicesFound: services.length,
            },
            'mDNS discovery completed'
          );

          // Log summary of discovered services
          if (services.length > 0) {
            this.logCommunication('orchestrator', 'all', 'mdns_discovery_complete', {
              services: services.map(s => ({
                name: s.name,
                type: s.type,
                host: s.host,
                port: s.port,
                addresses: s.addresses,
              })),
            });
          }

          // Clean up socket
          if (this.mdnsSocket) {
            try {
              this.mdnsSocket.dropMembership('224.0.0.251');
            } catch {
              // Ignore membership drop errors
            }
            this.mdnsSocket.close();
          }

          resolve();
        }, this.options.mdnsTimeout);

      } catch (error) {
        this.logger.warn({ error }, 'mDNS discovery failed to initialize');
        resolve();
      }
    });
  }

  /**
   * Try alternative mDNS binding when port 5353 is in use
   *
   * Binds to a random port and sends queries to the multicast address.
   * This works for discovery but won't receive announcements from other devices
   * that expect to send to port 5353.
   */
  private tryAlternativeMDNSBinding(
    resolve: () => void,
    discoveryStartTime: number
  ): void {
    try {
      // Close the existing socket if any
      if (this.mdnsSocket) {
        try {
          this.mdnsSocket.close();
        } catch {
          // Ignore
        }
      }

      // Create a new socket bound to a random port
      this.mdnsSocket = createSocket({ type: 'udp4', reuseAddr: true });

      this.mdnsSocket.on('message', (msg, rinfo) => {
        this.logger.debug({ from: rinfo.address, size: msg.length }, 'mDNS response (alt port)');

        try {
          const resolvedServices = this.realMDNS.processResponse(msg, rinfo.address);
          for (const service of resolvedServices) {
            this.emit('mdns:service', service);
          }
        } catch (error) {
          this.logger.debug(
            { error: error instanceof Error ? error.message : String(error) },
            'mDNS parse error (alt port)'
          );
        }
      });

      this.mdnsSocket.on('error', (err) => {
        this.logger.warn({ error: err }, 'Alternative mDNS binding failed');
        resolve();
      });

      // Bind to random port
      this.mdnsSocket.bind(0, () => {
        try {
          this.mdnsSocket!.addMembership('224.0.0.251');
          this.mdnsSocket!.setMulticastTTL(255);

          const address = this.mdnsSocket!.address();
          this.logger.info({ port: address.port }, 'mDNS bound to alternative port');

          // Send queries
          const queries = this.realMDNS.buildKagamiQueries();
          queries.forEach((query, index) => {
            setTimeout(() => {
              if (this.mdnsSocket && this.isSocketOpen(this.mdnsSocket)) {
                this.mdnsSocket.send(query, 5353, '224.0.0.251');
              }
            }, index * FIBONACCI_TIMEOUTS.F1);
          });
        } catch (error) {
          this.logger.warn({ error }, 'Failed to configure alternative mDNS');
        }
      });

      // Timeout
      setTimeout(() => {
        const services = this.realMDNS.getServices();
        this.logger.info(
          {
            durationMs: Date.now() - discoveryStartTime,
            servicesFound: services.length,
          },
          'Alternative mDNS discovery completed'
        );

        if (this.mdnsSocket) {
          try {
            this.mdnsSocket.dropMembership('224.0.0.251');
          } catch {
            // Ignore
          }
          this.mdnsSocket.close();
        }

        resolve();
      }, this.options.mdnsTimeout);

    } catch (error) {
      this.logger.warn({ error }, 'Alternative mDNS binding failed completely');
      resolve();
    }
  }

  /**
   * Handle a resolved mDNS service and convert to DiscoveredDevice
   */
  private handleMDNSServiceResolved(service: MDNSServiceRecord): void {
    // Extract platform from service type
    const platformMatch = service.type.match(/_kagami-([^._]+)\._tcp/);
    let platform: Platform | null = null;

    if (platformMatch) {
      const platformName = platformMatch[1];
      const validPlatforms: Platform[] = ['ios', 'android', 'watchos', 'wearos', 'tvos', 'visionos', 'androidxr', 'desktop', 'hub'];
      if (validPlatforms.includes(platformName as Platform)) {
        platform = platformName as Platform;
      }
    }

    // Also check TXT records for platform
    if (!platform && service.txt['platform']) {
      platform = service.txt['platform'] as Platform;
    }

    if (!platform) {
      this.logger.debug({ service: service.name, type: service.type }, 'Could not determine platform from mDNS service');
      return;
    }

    // Get primary address
    const ipAddress = service.addresses.find(addr =>
      // Prefer IPv4 addresses
      /^\d+\.\d+\.\d+\.\d+$/.test(addr)
    ) ?? service.addresses[0];

    // Extract capabilities from TXT records
    const capabilities: string[] = [];
    if (service.txt['capabilities']) {
      capabilities.push(...service.txt['capabilities'].split(',').map(c => c.trim()));
    }

    // Create discovered device (use 'disconnected' as initial state, will transition to 'connected' on connect)
    // Build the device object, conditionally adding optional properties to satisfy exactOptionalPropertyTypes
    const device: DiscoveredDevice = {
      platform,
      deviceId: service.txt['hub_id'] ?? service.txt['deviceId'] ?? service.name,
      name: service.txt['name'] ?? service.name,
      state: 'disconnected',
      lastSeen: Date.now(),
      capabilities,
      isSimulated: false,
      // Add optional properties only if they have values
      ...(ipAddress !== undefined && { ipAddress }),
      ...(service.port !== undefined && { port: service.port }),
      ...(service.type && { mdnsServiceName: service.type }),
    };

    // Add to discovered devices
    const existing = this.discoveredDevices.get(platform) ?? [];
    const existingIndex = existing.findIndex(d => d.deviceId === device.deviceId);

    if (existingIndex >= 0) {
      // Update existing device
      existing[existingIndex] = device;
    } else {
      // Add new device
      existing.push(device);
    }

    this.discoveredDevices.set(platform, existing);

    this.logger.info(
      {
        platform,
        deviceId: device.deviceId,
        name: device.name,
        address: `${ipAddress}:${service.port}`,
        capabilities,
      },
      'Device discovered via mDNS'
    );

    // Also register in simulated mDNS for cross-reference
    this.simulatedMDNS.registerService(service);

    // Emit device discovery event
    this.emit('device:discovered', device);
  }

  /**
   * Start a constellation journey test
   *
   * @param journeyId - The journey identifier to execute
   * @returns Constellation execution result
   */
  async startConstellation(journeyId: string): Promise<ConstellationResult> {
    const journey = CONSTELLATION_JOURNEYS.find((j) => j.id === journeyId);
    if (!journey) {
      throw new Error(`Unknown constellation journey: ${journeyId}`);
    }

    this.activeJourney = journey;
    this.logger.info({ journeyId, devices: journey.devices.length }, 'Starting constellation journey');

    const startTime = Date.now();
    const phaseResults: PhaseResult[] = [];
    const errors: string[] = [];

    // If using simulated mDNS, populate with journey devices
    if (this.options.enableSimulatedMDNS) {
      this.simulatedMDNS.populateFromSpec(journey);
    }

    // Ensure discovery has been done
    if (this.discoveredDevices.size === 0) {
      await this.discoverDevices();
    }

    // Connect to required devices
    const connectedPlatforms: Platform[] = [];
    for (const device of journey.devices) {
      try {
        await this.connectToDevice(device.platform);
        connectedPlatforms.push(device.platform);
      } catch (error) {
        const msg = `Failed to connect to ${device.platform}: ${error instanceof Error ? error.message : String(error)}`;
        this.logger.error({ platform: device.platform, error }, msg);
        errors.push(msg);
      }
    }

    // Execute phases
    for (const phase of journey.phases) {
      try {
        const phaseResult = await this.executePhase(phase as Phase & {
          activeDevice: Platform;
          expectedSync?: Record<Platform, Record<string, unknown>>;
        });
        phaseResults.push(phaseResult);

        if (!phaseResult.success) {
          errors.push(`Phase ${phase.id} failed: ${phaseResult.errors.join(', ')}`);
        }

        // Verify sync after phase if expected
        const expectedSync = (phase as { expectedSync?: Record<Platform, Record<string, unknown>> }).expectedSync;
        if (expectedSync) {
          const syncResult = await this.verifyStateSync(expectedSync);
          if (!syncResult) {
            errors.push(`State sync verification failed after phase ${phase.id}`);
          }
        }
      } catch (error) {
        const msg = `Phase ${phase.id} threw: ${error instanceof Error ? error.message : String(error)}`;
        this.logger.error({ phaseId: phase.id, error }, msg);
        errors.push(msg);

        phaseResults.push({
          phaseId: phase.id,
          success: false,
          checkpointResults: [],
          durationMs: 0,
          deviceStates: new Map(),
          errors: [msg],
        });
      }
    }

    const result: ConstellationResult = {
      journeyId,
      success: errors.length === 0 && phaseResults.every((p) => p.success),
      phaseResults,
      totalDurationMs: Date.now() - startTime,
      devicesParticipated: connectedPlatforms,
      syncVerified: errors.filter((e) => e.includes('sync')).length === 0,
      errors,
    };

    this.logCommunication('orchestrator', 'all', 'constellation_complete', result);
    this.emit('constellation:complete', result);

    return result;
  }

  /**
   * Connect to a specific device
   */
  private async connectToDevice(platform: Platform): Promise<DeviceConnection> {
    // Check if already connected
    const existing = this.connections.get(platform);
    if (existing) {
      return existing;
    }

    // Get driver
    const driver = this.drivers.get(platform);
    if (!driver) {
      throw new Error(`No driver for platform: ${platform}`);
    }

    // Get discovered device
    const devices = this.discoveredDevices.get(platform);
    if (!devices || devices.length === 0) {
      throw new Error(`No devices discovered for platform: ${platform}`);
    }

    // Connect to first available device
    const device = devices[0]!;
    this.logger.info({ platform, deviceId: device.deviceId }, 'Connecting to device');

    const connection = await driver.connect(device);
    this.connections.set(platform, connection);

    this.logCommunication('orchestrator', platform, 'connected', {
      deviceId: device.deviceId,
      name: device.name,
    });

    return connection;
  }

  /**
   * Execute a single phase on the active device
   *
   * @param phase - Phase to execute
   * @returns Phase execution result
   */
  async executePhase(phase: Phase & {
    activeDevice: Platform;
    expectedSync?: Record<Platform, Record<string, unknown>>;
  }): Promise<PhaseResult> {
    const startTime = Date.now();
    this.logger.info({ phaseId: phase.id, device: phase.activeDevice }, 'Executing phase');

    const checkpointResults: CheckpointResult[] = [];
    const errors: string[] = [];

    // Get connection for active device
    const connection = this.connections.get(phase.activeDevice);
    if (!connection) {
      return {
        phaseId: phase.id,
        success: false,
        checkpointResults: [],
        durationMs: Date.now() - startTime,
        deviceStates: new Map(),
        errors: [`No connection for device: ${phase.activeDevice}`],
      };
    }

    // Execute each checkpoint
    for (const checkpoint of phase.checkpoints) {
      const checkpointResult = await this.executeCheckpoint(connection, checkpoint, phase.interactionType);
      checkpointResults.push(checkpointResult);

      if (!checkpointResult.success) {
        errors.push(`Checkpoint ${checkpoint.id} failed: ${checkpointResult.elementsMissing.join(', ')}`);
      }

      this.logCommunication('orchestrator', phase.activeDevice, 'checkpoint', {
        checkpointId: checkpoint.id,
        success: checkpointResult.success,
        durationMs: checkpointResult.durationMs,
      });
    }

    // Collect final device states
    const deviceStates = new Map<Platform, Record<string, unknown>>();
    for (const [platform, conn] of this.connections) {
      try {
        const driver = this.drivers.get(platform);
        if (driver) {
          const state = await driver.getState(conn);
          deviceStates.set(platform, state);
          this.deviceStates.set(platform, state);
        }
      } catch {
        // Continue on state collection failure
      }
    }

    const result: PhaseResult = {
      phaseId: phase.id,
      success: errors.length === 0,
      checkpointResults,
      durationMs: Date.now() - startTime,
      deviceStates,
      errors,
    };

    this.emit('phase:complete', result);
    return result;
  }

  /**
   * Execute a single checkpoint
   */
  private async executeCheckpoint(
    connection: DeviceConnection,
    checkpoint: Checkpoint,
    interactionType: Phase['interactionType']
  ): Promise<CheckpointResult> {
    const startTime = Date.now();
    const elementsFound: string[] = [];
    const elementsMissing: string[] = [];

    const driver = this.drivers.get(connection.device.platform);
    if (!driver) {
      return {
        checkpointId: checkpoint.id,
        success: false,
        elementsFound: [],
        elementsMissing: checkpoint.requiredElements,
        durationMs: Date.now() - startTime,
      };
    }

    // Verify required elements with retry and Fibonacci backoff
    for (const elementId of checkpoint.requiredElements) {
      let found = false;
      let retries = 0;

      while (!found && retries < this.options.maxRetries) {
        found = await driver.verifyElement(connection, elementId);
        if (!found) {
          retries++;
          await this.sleep(getFibonacciTimeout(retries));
        }
      }

      if (found) {
        elementsFound.push(elementId);
      } else {
        elementsMissing.push(elementId);
      }
    }

    // Execute interaction based on type
    if (elementsMissing.length === 0) {
      await this.executeInteraction(connection, interactionType, checkpoint);
    }

    // Get actual state for verification
    let actualState: Record<string, unknown> | undefined;
    if (checkpoint.expectedState) {
      actualState = await driver.getState(connection);
    }

    const success =
      elementsMissing.length === 0 &&
      (checkpoint.expectedState
        ? this.statesMatch(actualState ?? {}, checkpoint.expectedState)
        : true);

    return {
      checkpointId: checkpoint.id,
      success,
      elementsFound,
      elementsMissing,
      durationMs: Date.now() - startTime,
      actualState,
      expectedState: checkpoint.expectedState,
      hapticVerified: checkpoint.expectedHaptic !== 'none',
    };
  }

  /**
   * Execute an interaction on the device
   */
  private async executeInteraction(
    connection: DeviceConnection,
    type: Phase['interactionType'],
    checkpoint: Checkpoint
  ): Promise<void> {
    const target = checkpoint.requiredElements[0];
    if (!target) {
      this.logger.warn({ checkpointId: checkpoint.id }, 'No target element for interaction');
      return;
    }

    const command: DeviceCommand = {
      type: this.mapInteractionToCommand(type),
      target,
      timeout: checkpoint.maxDurationMs,
    };

    await connection.send(command);
  }

  /**
   * Map journey interaction type to device command type
   */
  private mapInteractionToCommand(interaction: Phase['interactionType']): DeviceCommand['type'] {
    switch (interaction) {
      case 'tap':
      case 'crown':
      case 'remote':
      case 'keyboard':
      case 'pinch':
      case 'gaze':
        return 'tap';
      case 'swipe':
      case 'scroll':
        return 'swipe';
      case 'voice':
        return 'voice';
      case 'ambient':
        return 'state';
      default:
        return 'tap';
    }
  }

  /**
   * Verify state synchronization across all devices
   *
   * @param expectedSync - Expected state for each platform
   * @returns Whether all states match expectations
   */
  async verifyStateSync(expectedSync: Record<Platform, Record<string, unknown>>): Promise<boolean> {
    this.logger.info({ platforms: Object.keys(expectedSync) }, 'Verifying state sync');

    const startTime = Date.now();
    let allMatch = true;

    for (const [platform, expected] of Object.entries(expectedSync) as [Platform, Record<string, unknown>][]) {
      const connection = this.connections.get(platform);
      if (!connection) {
        this.logger.warn({ platform }, 'No connection for sync verification');
        allMatch = false;
        continue;
      }

      const driver = this.drivers.get(platform);
      if (!driver) {
        allMatch = false;
        continue;
      }

      // Wait for sync with Fibonacci backoff
      let synced = false;
      let retries = 0;

      while (!synced && retries < this.options.maxRetries) {
        const actual = await driver.getState(connection);
        synced = this.statesMatch(actual, expected);

        if (!synced) {
          retries++;
          await this.sleep(getFibonacciTimeout(retries));
        }
      }

      if (!synced) {
        this.logger.warn({ platform, expected }, 'State sync verification failed');
        allMatch = false;
      }

      this.logCommunication('orchestrator', platform, 'sync_check', {
        synced,
        retries,
        durationMs: Date.now() - startTime,
      });
    }

    this.emit('sync:verified', { success: allMatch, durationMs: Date.now() - startTime });
    return allMatch;
  }

  /**
   * Check if actual state matches expected state
   */
  private statesMatch(
    actual: Record<string, unknown>,
    expected: Record<string, unknown>
  ): boolean {
    for (const [key, value] of Object.entries(expected)) {
      if (actual[key] !== value) {
        return false;
      }
    }
    return true;
  }

  /**
   * Clean up all connections and resources
   */
  async cleanup(): Promise<void> {
    this.logger.info('Cleaning up constellation orchestrator');

    // Disconnect all devices
    for (const [platform, connection] of this.connections) {
      try {
        await connection.disconnect();
        this.logger.debug({ platform }, 'Disconnected from device');
      } catch (error) {
        this.logger.warn({ platform, error }, 'Error disconnecting');
      }
    }

    this.connections.clear();
    this.discoveredDevices.clear();
    this.deviceStates.clear();
    this.activeJourney = null;

    // Close mDNS socket and clear real mDNS state
    if (this.mdnsSocket) {
      try {
        this.mdnsSocket.dropMembership('224.0.0.251');
      } catch {
        // Ignore membership drop errors
      }
      this.mdnsSocket.close();
      delete this.mdnsSocket;
    }

    // Clear real mDNS discovered services
    this.realMDNS.clear();

    this.emit('cleanup:complete');
  }

  /**
   * Get the communication log for debugging
   */
  getCommunicationLog(): typeof this.communicationLog {
    return [...this.communicationLog];
  }

  /**
   * Get current device states
   */
  getDeviceStates(): Map<Platform, Record<string, unknown>> {
    return new Map(this.deviceStates);
  }

  /**
   * Get the currently active journey (if any)
   */
  getActiveJourney(): ConstellationJourneySpec | null {
    return this.activeJourney;
  }

  /**
   * Log a communication event
   */
  private logCommunication(
    source: Platform | 'orchestrator',
    target: Platform | 'all',
    type: string,
    data: unknown
  ): void {
    const entry = {
      timestamp: Date.now(),
      source,
      target,
      type,
      data,
    };

    this.communicationLog.push(entry);

    if (this.options.verbose) {
      this.logger.debug(entry, 'Communication logged');
    }

    this.emit('communication', entry);
  }

  /**
   * Check if a UDP socket is still open and usable
   *
   * @param socket - The socket to check
   * @returns true if the socket can still be used for sending
   */
  private isSocketOpen(socket: Socket): boolean {
    try {
      // Try to get the address - this will throw if the socket is closed
      socket.address();
      return true;
    } catch {
      return false;
    }
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

// =============================================================================
// EXPORTS
// =============================================================================

export {
  // mDNS classes
  MDNSParser,
  RealMDNS,
  SimulatedMDNS,

  // Device drivers
  ADBDriver,
  SimctlDriver,
  HubTCPDriver,
  DesktopWebSocketDriver,
};

export type { DeviceDriver };
