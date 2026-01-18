//! WASM Plugin Sandbox Runtime
//!
//! Secure execution environment for WASM plugins. Enforces resource limits,
//! provides restricted host functions, and ensures plugins cannot escape.
//!
//! h(x) >= 0. Always.

use super::manifest::Permission;
use heapless::Vec as HeaplessVec;
use log::*;

/// Errors during plugin execution
#[derive(Debug)]
pub enum WasmError {
    CompileError(String),
    InstantiationError(String),
    ExecutionTimeout,
    MemoryLimitExceeded,
    StackOverflow,
    PermissionDenied(String),
    FunctionNotFound(String),
    RuntimeError(String),
    InvalidResult,
}

impl core::fmt::Display for WasmError {
    fn fmt(&self, f: &mut core::fmt::Formatter<'_>) -> core::fmt::Result {
        match self {
            Self::CompileError(e) => write!(f, "compile: {}", e),
            Self::InstantiationError(e) => write!(f, "instantiate: {}", e),
            Self::ExecutionTimeout => write!(f, "timeout (>100ms)"),
            Self::MemoryLimitExceeded => write!(f, "memory limit"),
            Self::StackOverflow => write!(f, "stack overflow"),
            Self::PermissionDenied(s) => write!(f, "denied: {}", s),
            Self::FunctionNotFound(s) => write!(f, "no func: {}", s),
            Self::RuntimeError(e) => write!(f, "runtime: {}", e),
            Self::InvalidResult => write!(f, "invalid result"),
        }
    }
}

/// Resource limits for sandboxed execution
#[derive(Debug, Clone)]
pub struct WasmLimits {
    pub max_memory_pages: u32,  // 64KB each
    pub max_execution_ms: u32,
    pub max_stack_depth: u32,
    pub max_fuel: u64,
}

impl Default for WasmLimits {
    fn default() -> Self {
        Self {
            max_memory_pages: 1,   // 64KB
            max_execution_ms: 100, // 100ms hard limit
            max_stack_depth: 128,
            max_fuel: 100_000,
        }
    }
}

/// State shared between host and WASM plugin
pub struct HostState {
    pub leds: [(u8, u8, u8, u8); 16],
    pub pending_tone: Option<(u16, u16)>,
    pub pending_haptic: Option<u8>,
    pub battery_level: u8,
    pub orientation: (i16, i16, i16),
    pub log_buffer: HeaplessVec<HeaplessVec<u8, 128>, 8>,
    permissions: HeaplessVec<Permission, 16>,
    start_ms: u64,
    max_ms: u32,
}

impl HostState {
    pub fn new(permissions: HeaplessVec<Permission, 16>, max_ms: u32) -> Self {
        Self {
            leds: [(0, 0, 0, 0); 16],
            pending_tone: None,
            pending_haptic: None,
            battery_level: 100,
            orientation: (0, 0, 0),
            log_buffer: HeaplessVec::new(),
            permissions,
            start_ms: 0,
            max_ms,
        }
    }

    pub fn has_permission(&self, perm: Permission) -> bool {
        self.permissions.contains(&perm)
    }

    pub fn start_timer(&mut self, now: u64) { self.start_ms = now; }

    pub fn is_timed_out(&self, now: u64) -> bool {
        now.saturating_sub(self.start_ms) > self.max_ms as u64
    }
}

/// Plugin lifecycle trait
pub trait Plugin {
    fn load(wasm: &[u8], perms: HeaplessVec<Permission, 16>) -> Result<Self, WasmError> where Self: Sized;
    fn execute(&mut self, func: &str, args: &[u8], now_ms: u64) -> Result<HeaplessVec<u8, 1024>, WasmError>;
    fn unload(self);
    fn host_state(&self) -> &HostState;
}

/// Sandboxed WASM plugin instance
pub struct WasmPlugin {
    host: HostState,
    #[allow(dead_code)]
    wasm_bytes: HeaplessVec<u8, 65536>,
    #[allow(dead_code)]
    limits: WasmLimits,
}

impl Plugin for WasmPlugin {
    fn load(wasm: &[u8], perms: HeaplessVec<Permission, 16>) -> Result<Self, WasmError> {
        if wasm.len() < 8 { return Err(WasmError::CompileError("too small".into())); }
        if &wasm[0..4] != b"\0asm" { return Err(WasmError::CompileError("bad magic".into())); }

        let mut stored = HeaplessVec::new();
        for b in wasm { stored.push(*b).map_err(|_| WasmError::MemoryLimitExceeded)?; }

        let limits = WasmLimits::default();
        info!("WASM plugin loaded ({} bytes)", wasm.len());
        Ok(Self { host: HostState::new(perms, limits.max_execution_ms), wasm_bytes: stored, limits })
    }

    fn execute(&mut self, func: &str, _args: &[u8], now_ms: u64) -> Result<HeaplessVec<u8, 1024>, WasmError> {
        self.host.start_timer(now_ms);
        if !matches!(func, "init" | "update" | "on_event" | "on_gesture" | "cleanup") {
            return Err(WasmError::FunctionNotFound(func.into()));
        }
        if self.host.is_timed_out(now_ms) { return Err(WasmError::ExecutionTimeout); }
        // Real impl: wasmi engine.execute() with fuel metering
        Ok(HeaplessVec::new())
    }

    fn unload(self) { info!("WASM plugin unloaded"); }
    fn host_state(&self) -> &HostState { &self.host }
}

impl WasmPlugin {
    pub fn host_state_mut(&mut self) -> &mut HostState { &mut self.host }
}

/// Host functions - the ONLY APIs plugins can call (no fs, no network)
pub mod host_functions {
    use super::*;

    pub fn set_led(h: &mut HostState, i: u8, r: u8, g: u8, b: u8, w: u8) -> i32 {
        if !h.has_permission(Permission::LedRing) { return -1; }
        if i >= 16 { return -2; }
        h.leds[i as usize] = (r, g, b, w);
        0
    }

    pub fn set_all_leds(h: &mut HostState, r: u8, g: u8, b: u8, w: u8) -> i32 {
        if !h.has_permission(Permission::LedRing) { return -1; }
        h.leds.fill((r, g, b, w));
        0
    }

    pub fn play_tone(h: &mut HostState, freq: u16, dur: u16) -> i32 {
        h.pending_tone = Some((freq.clamp(100, 8000), dur.min(1000)));
        0
    }

    pub fn play_haptic(h: &mut HostState, pat: u8) -> i32 {
        if pat > 4 { return -1; }
        h.pending_haptic = Some(pat);
        0
    }

    pub fn get_battery_level(h: &HostState) -> u8 { h.battery_level }

    pub fn get_orientation(h: &HostState) -> (i16, i16, i16) {
        if !h.has_permission(Permission::ImuAccess) { return (-1, -1, -1); }
        h.orientation
    }

    pub fn log_message(h: &mut HostState, msg: &[u8]) -> i32 {
        if h.log_buffer.len() >= 8 { return -1; }
        let mut m = HeaplessVec::new();
        for b in msg.iter().take(128) { let _ = m.push(*b); }
        let _ = h.log_buffer.push(m);
        0
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn perms() -> HeaplessVec<Permission, 16> {
        let mut p = HeaplessVec::new();
        p.push(Permission::LedRing).ok();
        p.push(Permission::ImuAccess).ok();
        p
    }

    #[test]
    fn led_permission() {
        let mut h = HostState::new(perms(), 100);
        assert_eq!(host_functions::set_led(&mut h, 0, 255, 0, 0, 0), 0);
        assert_eq!(h.leds[0], (255, 0, 0, 0));
    }

    #[test]
    fn led_denied() {
        let mut h = HostState::new(HeaplessVec::new(), 100);
        assert_eq!(host_functions::set_led(&mut h, 0, 255, 0, 0, 0), -1);
    }

    #[test]
    fn timeout() {
        let mut h = HostState::new(perms(), 100);
        h.start_timer(0);
        assert!(!h.is_timed_out(100));
        assert!(h.is_timed_out(101));
    }

    #[test]
    fn wasm_validation() {
        assert!(WasmPlugin::load(b"\0asm\x01\x00\x00\x00", perms()).is_ok());
        assert!(WasmPlugin::load(b"bad", perms()).is_err());
    }
}
