/**
 * Desktop Control API — Frontend Integration
 *
 * Cross-platform desktop automation: mouse, keyboard, clipboard, processes,
 * screen capture, accessibility, and system info.
 *
 * Focus: Integration, Coordination
 *
 * Safety first
 *   - All actions rate-limited on backend
 *   - Input injection logged for audit
 */

// Check if running in Tauri
const isTauri = window.__TAURI_INTERNALS__ !== undefined;

// Import Tauri API dynamically
let invoke = null;
if (isTauri) {
    import('@tauri-apps/api/core').then(module => {
        invoke = module.invoke;
    });
} else {
    // Mock for browser preview
    invoke = async (cmd, args) => {
        console.log(`[Mock] Desktop Control: ${cmd}`, args);
        return mockDesktopResponse(cmd, args);
    };
}

// Mock responses for browser preview
function mockDesktopResponse(cmd, args) {
    switch (cmd) {
        case 'desktop_mouse_move':
        case 'desktop_mouse_click':
        case 'desktop_mouse_scroll':
        case 'desktop_type_text':
        case 'desktop_hotkey':
        case 'desktop_key_press':
        case 'desktop_clipboard_set':
        case 'desktop_kill_process':
            return { success: true, error: null };

        case 'desktop_clipboard_get':
            return 'Mock clipboard content';

        case 'desktop_start_process':
            return 12345; // Mock PID

        case 'desktop_list_processes':
            return [
                { pid: 1, name: 'kernel_task', status: 'Running', cpu_percent: 0.5, memory_bytes: 1000000 },
                { pid: 123, name: 'Finder', status: 'Running', cpu_percent: 1.2, memory_bytes: 50000000 },
                { pid: 456, name: 'Safari', status: 'Running', cpu_percent: 3.5, memory_bytes: 200000000 },
                { pid: 789, name: 'Code', status: 'Running', cpu_percent: 8.0, memory_bytes: 500000000 },
            ];

        case 'desktop_system_info':
            return {
                hostname: 'kagami-mac',
                os_name: 'macOS',
                os_version: '15.2',
                kernel_version: '24.2.0',
                cpu_count: 12,
                cpu_brand: 'Apple M2 Pro',
                total_memory_bytes: 32000000000,
                used_memory_bytes: 16000000000,
                uptime_secs: 86400,
                disks: [
                    { name: 'Macintosh HD', mount_point: '/', total_bytes: 1000000000000, available_bytes: 500000000000, fs_type: 'apfs', is_removable: false },
                ],
                networks: [
                    { name: 'en0', ip_addresses: ['192.168.1.100'], mac_address: 'aa:bb:cc:dd:ee:ff', is_up: true, is_loopback: false },
                ],
            };

        case 'vision_check_permission':
        case 'check_accessibility':
            return true;

        case 'vision_get_displays':
            return [
                { id: 1, width: 3456, height: 2234, is_main: true, is_builtin: true, scale_factor: 2.0 },
            ];

        case 'vision_capture_screen':
        case 'vision_capture_region':
        case 'vision_capture_window':
            return {
                success: true,
                error: null,
                data: 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
                format: 'png',
                width: 1920,
                height: 1080,
            };

        case 'vision_get_windows':
            return [
                { window_id: 1, owner_name: 'Finder', window_name: 'Desktop', bounds: { x: 0, y: 0, width: 1920, height: 1080 }, layer: 0 },
                { window_id: 2, owner_name: 'Safari', window_name: 'Google', bounds: { x: 100, y: 100, width: 1200, height: 800 }, layer: 0 },
            ];

        case 'get_focused_application':
            return { name: 'Code', bundle_id: 'com.microsoft.VSCode', pid: 789, is_frontmost: true, windows: [] };

        case 'get_applications':
            return [
                { name: 'Finder', bundle_id: 'com.apple.finder', pid: 123, is_frontmost: false, windows: [] },
                { name: 'Safari', bundle_id: 'com.apple.Safari', pid: 456, is_frontmost: false, windows: [] },
                { name: 'Code', bundle_id: 'com.microsoft.VSCode', pid: 789, is_frontmost: true, windows: [] },
            ];

        default:
            console.warn(`Unknown mock command: ${cmd}`);
            return null;
    }
}

// ============================================================================
// Mouse Control
// ============================================================================

/**
 * Move mouse cursor to absolute position
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function mouseMove(x, y) {
    return await invoke('desktop_mouse_move', { x, y });
}

/**
 * Click mouse button at position
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @param {'left'|'right'|'middle'} button - Mouse button
 * @param {boolean} doubleClick - Whether to double-click
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function mouseClick(x, y, button = 'left', doubleClick = false) {
    return await invoke('desktop_mouse_click', {
        x,
        y,
        button,
        doubleClick,
    });
}

/**
 * Double-click at position
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @param {'left'|'right'|'middle'} button - Mouse button
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function mouseDoubleClick(x, y, button = 'left') {
    return await mouseClick(x, y, button, true);
}

/**
 * Right-click at position
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function mouseRightClick(x, y) {
    return await mouseClick(x, y, 'right', false);
}

/**
 * Scroll the mouse wheel
 * @param {number} deltaX - Horizontal scroll (positive = right)
 * @param {number} deltaY - Vertical scroll (positive = down)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function mouseScroll(deltaX, deltaY) {
    return await invoke('desktop_mouse_scroll', { deltaX, deltaY });
}

/**
 * Scroll up
 * @param {number} amount - Scroll amount (default: 3)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function scrollUp(amount = 3) {
    return await mouseScroll(0, amount);
}

/**
 * Scroll down
 * @param {number} amount - Scroll amount (default: 3)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function scrollDown(amount = 3) {
    return await mouseScroll(0, -amount);
}

// ============================================================================
// Keyboard Control
// ============================================================================

/**
 * Type a string of text
 * @param {string} text - Text to type
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function typeText(text) {
    return await invoke('desktop_type_text', { text });
}

/**
 * Press a hotkey combination
 * @param {Object} modifiers - Modifier keys { shift, control, alt, meta }
 * @param {string} key - Key to press
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function hotkey(modifiers, key) {
    return await invoke('desktop_hotkey', { modifiers, key });
}

/**
 * Press Cmd+key (macOS) / Ctrl+key (Windows/Linux)
 * @param {string} key - Key to press
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function cmdKey(key) {
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    return await hotkey(
        isMac ? { meta: true } : { control: true },
        key
    );
}

/**
 * Copy (Cmd/Ctrl+C)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function copy() {
    return await cmdKey('c');
}

/**
 * Paste (Cmd/Ctrl+V)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function paste() {
    return await cmdKey('v');
}

/**
 * Cut (Cmd/Ctrl+X)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function cut() {
    return await cmdKey('x');
}

/**
 * Undo (Cmd/Ctrl+Z)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function undo() {
    return await cmdKey('z');
}

/**
 * Redo (Cmd/Ctrl+Shift+Z)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function redo() {
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0;
    return await hotkey(
        isMac ? { meta: true, shift: true } : { control: true, shift: true },
        'z'
    );
}

/**
 * Select All (Cmd/Ctrl+A)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function selectAll() {
    return await cmdKey('a');
}

/**
 * Save (Cmd/Ctrl+S)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function save() {
    return await cmdKey('s');
}

/**
 * Press a single key
 * @param {string} key - Key name (e.g., 'enter', 'tab', 'escape', 'f1')
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function keyPress(key) {
    return await invoke('desktop_key_press', { key });
}

/**
 * Press Enter
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function enter() {
    return await keyPress('enter');
}

/**
 * Press Tab
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function tab() {
    return await keyPress('tab');
}

/**
 * Press Escape
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function escape() {
    return await keyPress('escape');
}

/**
 * Press Backspace
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function backspace() {
    return await keyPress('backspace');
}

/**
 * Press Delete
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function deleteKey() {
    return await keyPress('delete');
}

// ============================================================================
// Clipboard
// ============================================================================

/**
 * Get clipboard text content
 * @returns {Promise<string>}
 */
export async function clipboardGet() {
    return await invoke('desktop_clipboard_get');
}

/**
 * Set clipboard text content
 * @param {string} text - Text to set
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function clipboardSet(text) {
    return await invoke('desktop_clipboard_set', { text });
}

// ============================================================================
// Process Management
// ============================================================================

/**
 * @typedef {Object} ProcessInfo
 * @property {number} pid - Process ID
 * @property {string} name - Process name
 * @property {string} [exe_path] - Executable path
 * @property {string} [cmd_line] - Command line
 * @property {string} status - Process status
 * @property {number} cpu_percent - CPU usage percentage
 * @property {number} memory_bytes - Memory usage in bytes
 * @property {number} [parent_pid] - Parent process ID
 */

/**
 * List all running processes
 * @returns {Promise<ProcessInfo[]>}
 */
export async function listProcesses() {
    return await invoke('desktop_list_processes');
}

/**
 * Kill a process by PID
 * @param {number} pid - Process ID
 * @param {boolean} force - Force kill (SIGKILL vs SIGTERM)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function killProcess(pid, force = false) {
    return await invoke('desktop_kill_process', { pid, force });
}

/**
 * Start a new process
 * @param {string} command - Command to execute
 * @param {string[]} args - Arguments
 * @returns {Promise<number>} - Process ID
 */
export async function startProcess(command, args = []) {
    return await invoke('desktop_start_process', { command, args });
}

/**
 * Find processes by name
 * @param {string} name - Process name (partial match)
 * @returns {Promise<ProcessInfo[]>}
 */
export async function findProcesses(name) {
    const processes = await listProcesses();
    const lowerName = name.toLowerCase();
    return processes.filter(p => p.name.toLowerCase().includes(lowerName));
}

/**
 * Kill processes by name
 * @param {string} name - Process name (partial match)
 * @param {boolean} force - Force kill
 * @returns {Promise<{killed: number, errors: string[]}>}
 */
export async function killProcessesByName(name, force = false) {
    const processes = await findProcesses(name);
    const results = { killed: 0, errors: [] };

    for (const proc of processes) {
        const result = await killProcess(proc.pid, force);
        if (result.success) {
            results.killed++;
        } else {
            results.errors.push(`Failed to kill ${proc.name} (${proc.pid}): ${result.error}`);
        }
    }

    return results;
}

// ============================================================================
// System Information
// ============================================================================

/**
 * @typedef {Object} DiskInfo
 * @property {string} name - Disk name
 * @property {string} mount_point - Mount point
 * @property {number} total_bytes - Total space in bytes
 * @property {number} available_bytes - Available space in bytes
 * @property {string} fs_type - Filesystem type
 * @property {boolean} is_removable - Whether removable
 */

/**
 * @typedef {Object} NetworkInfo
 * @property {string} name - Interface name
 * @property {string[]} ip_addresses - IP addresses
 * @property {string} [mac_address] - MAC address
 * @property {boolean} is_up - Whether interface is up
 * @property {boolean} is_loopback - Whether loopback interface
 */

/**
 * @typedef {Object} ExtendedSystemInfo
 * @property {string} hostname - System hostname
 * @property {string} os_name - OS name
 * @property {string} os_version - OS version
 * @property {string} kernel_version - Kernel version
 * @property {number} cpu_count - Number of CPUs
 * @property {string} cpu_brand - CPU brand string
 * @property {number} total_memory_bytes - Total memory
 * @property {number} used_memory_bytes - Used memory
 * @property {number} uptime_secs - System uptime in seconds
 * @property {DiskInfo[]} disks - Disk information
 * @property {NetworkInfo[]} networks - Network interfaces
 */

/**
 * Get extended system information
 * @returns {Promise<ExtendedSystemInfo>}
 */
export async function getSystemInfo() {
    return await invoke('desktop_system_info');
}

/**
 * Format bytes to human readable
 * @param {number} bytes - Bytes
 * @returns {string}
 */
export function formatBytes(bytes) {
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let unit = 0;
    let value = bytes;

    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit++;
    }

    return `${value.toFixed(1)} ${units[unit]}`;
}

/**
 * Format uptime seconds to human readable
 * @param {number} seconds - Uptime in seconds
 * @returns {string}
 */
export function formatUptime(seconds) {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    const parts = [];
    if (days > 0) parts.push(`${days}d`);
    if (hours > 0) parts.push(`${hours}h`);
    if (minutes > 0) parts.push(`${minutes}m`);

    return parts.join(' ') || '< 1m';
}

// ============================================================================
// Screen Capture (Vision)
// ============================================================================

/**
 * @typedef {Object} DisplayInfo
 * @property {number} id - Display ID
 * @property {number} width - Width in pixels
 * @property {number} height - Height in pixels
 * @property {boolean} is_main - Whether main display
 * @property {boolean} is_builtin - Whether built-in display
 * @property {number} scale_factor - Display scale factor
 */

/**
 * @typedef {Object} CaptureResult
 * @property {boolean} success - Whether capture succeeded
 * @property {string} [error] - Error message if failed
 * @property {string} [data] - Base64-encoded image data
 * @property {string} format - Image format (png, jpeg)
 * @property {number} width - Image width
 * @property {number} height - Image height
 */

/**
 * @typedef {Object} WindowInfo
 * @property {number} window_id - Window ID
 * @property {string} owner_name - Owner application name
 * @property {string} [window_name] - Window title
 * @property {{x: number, y: number, width: number, height: number}} bounds - Window bounds
 * @property {number} layer - Window layer
 */

/**
 * Check screen recording permission
 * @returns {Promise<boolean>}
 */
export async function checkScreenPermission() {
    return await invoke('vision_check_permission');
}

/**
 * Request screen recording permission (opens system preferences)
 * @returns {Promise<void>}
 */
export async function requestScreenPermission() {
    return await invoke('vision_request_permission');
}

/**
 * Get all connected displays
 * @returns {Promise<DisplayInfo[]>}
 */
export async function getDisplays() {
    return await invoke('vision_get_displays');
}

/**
 * Capture the full screen
 * @returns {Promise<CaptureResult>}
 */
export async function captureScreen() {
    return await invoke('vision_capture_screen');
}

/**
 * Capture a region of the screen
 * @param {{x: number, y: number, width: number, height: number}} region - Region to capture
 * @returns {Promise<CaptureResult>}
 */
export async function captureRegion(region) {
    return await invoke('vision_capture_region', { region });
}

/**
 * Get list of capturable windows
 * @returns {Promise<WindowInfo[]>}
 */
export async function getWindows() {
    return await invoke('vision_get_windows');
}

/**
 * Capture a specific window
 * @param {number} windowId - Window ID
 * @returns {Promise<CaptureResult>}
 */
export async function captureWindow(windowId) {
    return await invoke('vision_capture_window', { windowId });
}

/**
 * Convert capture result to data URL
 * @param {CaptureResult} capture - Capture result
 * @returns {string|null} - Data URL or null if failed
 */
export function captureToDataUrl(capture) {
    if (!capture.success || !capture.data) return null;
    return `data:image/${capture.format};base64,${capture.data}`;
}

/**
 * Convert capture result to Image element
 * @param {CaptureResult} capture - Capture result
 * @returns {Promise<HTMLImageElement|null>} - Image element or null if failed
 */
export async function captureToImage(capture) {
    const url = captureToDataUrl(capture);
    if (!url) return null;

    return new Promise((resolve) => {
        const img = new Image();
        img.onload = () => resolve(img);
        img.onerror = () => resolve(null);
        img.src = url;
    });
}

// ============================================================================
// Accessibility
// ============================================================================

/**
 * @typedef {Object} AppInfo
 * @property {string} name - Application name
 * @property {string} [bundle_id] - Bundle identifier
 * @property {number} pid - Process ID
 * @property {boolean} is_frontmost - Whether app is frontmost
 * @property {Object[]} windows - Window list
 */

/**
 * Check accessibility permission
 * @param {boolean} prompt - Whether to prompt for permission
 * @returns {Promise<boolean>}
 */
export async function checkAccessibility(prompt = false) {
    return await invoke('check_accessibility', { prompt });
}

/**
 * Get the currently focused application
 * @returns {Promise<AppInfo|null>}
 */
export async function getFocusedApplication() {
    return await invoke('get_focused_application');
}

/**
 * Get all running applications
 * @returns {Promise<AppInfo[]>}
 */
export async function getApplications() {
    return await invoke('get_applications');
}

/**
 * Get accessibility element at screen position
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @returns {Promise<Object|null>}
 */
export async function getElementAt(x, y) {
    return await invoke('get_element_at', { x, y });
}

/**
 * Perform an accessibility action
 * @param {string} elementId - Element ID
 * @param {string} action - Action to perform
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function accessibilityAction(elementId, action) {
    return await invoke('accessibility_action', { elementId, action });
}

/**
 * Set focus to an accessibility element
 * @param {string} elementId - Element ID
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function accessibilityFocus(elementId) {
    return await invoke('accessibility_focus', { elementId });
}

// ============================================================================
// High-Level Automation Helpers
// ============================================================================

/**
 * Click and type text at a position
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @param {string} text - Text to type
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function clickAndType(x, y, text) {
    const clickResult = await mouseClick(x, y);
    if (!clickResult.success) return clickResult;

    await sleep(50); // Small delay for focus

    return await typeText(text);
}

/**
 * Triple-click to select all at position
 * @param {number} x - X coordinate
 * @param {number} y - Y coordinate
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function tripleClick(x, y) {
    // Triple-click is usually select all for text
    await mouseClick(x, y, 'left', false);
    await sleep(50);
    await mouseClick(x, y, 'left', false);
    await sleep(50);
    return await mouseClick(x, y, 'left', false);
}

/**
 * Drag from one position to another
 * @param {number} fromX - Start X
 * @param {number} fromY - Start Y
 * @param {number} toX - End X
 * @param {number} toY - End Y
 * @param {number} duration - Duration in ms (default: 200)
 * @returns {Promise<{success: boolean, error?: string}>}
 */
export async function drag(fromX, fromY, toX, toY, duration = 200) {
    // Move to start
    await mouseMove(fromX, fromY);
    await sleep(50);

    // This would need mouse down/up events for proper drag
    // For now, just move the mouse
    const steps = Math.ceil(duration / 20);
    const dx = (toX - fromX) / steps;
    const dy = (toY - fromY) / steps;

    for (let i = 1; i <= steps; i++) {
        await mouseMove(fromX + dx * i, fromY + dy * i);
        await sleep(20);
    }

    return { success: true };
}

/**
 * Wait/sleep helper
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise<void>}
 */
export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Take a screenshot and return as data URL
 * @returns {Promise<string|null>}
 */
export async function screenshot() {
    const capture = await captureScreen();
    return captureToDataUrl(capture);
}

/**
 * Get memory usage as percentage
 * @returns {Promise<number>}
 */
export async function getMemoryPercent() {
    const info = await getSystemInfo();
    return (info.used_memory_bytes / info.total_memory_bytes) * 100;
}

/**
 * Get disk usage as percentage for main disk
 * @returns {Promise<number|null>}
 */
export async function getDiskPercent() {
    const info = await getSystemInfo();
    const mainDisk = info.disks.find(d => d.mount_point === '/');
    if (!mainDisk) return null;
    const used = mainDisk.total_bytes - mainDisk.available_bytes;
    return (used / mainDisk.total_bytes) * 100;
}

// ============================================================================
// Export as window global for non-module usage
// ============================================================================

window.DesktopControl = {
    // Mouse
    mouseMove,
    mouseClick,
    mouseDoubleClick,
    mouseRightClick,
    mouseScroll,
    scrollUp,
    scrollDown,

    // Keyboard
    typeText,
    hotkey,
    cmdKey,
    copy,
    paste,
    cut,
    undo,
    redo,
    selectAll,
    save,
    keyPress,
    enter,
    tab,
    escape,
    backspace,
    deleteKey,

    // Clipboard
    clipboardGet,
    clipboardSet,

    // Processes
    listProcesses,
    killProcess,
    startProcess,
    findProcesses,
    killProcessesByName,

    // System Info
    getSystemInfo,
    formatBytes,
    formatUptime,
    getMemoryPercent,
    getDiskPercent,

    // Screen Capture
    checkScreenPermission,
    requestScreenPermission,
    getDisplays,
    captureScreen,
    captureRegion,
    getWindows,
    captureWindow,
    captureToDataUrl,
    captureToImage,
    screenshot,

    // Accessibility
    checkAccessibility,
    getFocusedApplication,
    getApplications,
    getElementAt,
    accessibilityAction,
    accessibilityFocus,

    // Helpers
    clickAndType,
    tripleClick,
    drag,
    sleep,
};

console.log('%c鏡 Desktop Control API loaded', 'color: #8B5CF6; font-weight: bold;');
console.log('Access via window.DesktopControl or ES6 imports');

/*
 * 鏡
 *
 *
 * Desktop control is power.
 * Use it responsibly.
 */
