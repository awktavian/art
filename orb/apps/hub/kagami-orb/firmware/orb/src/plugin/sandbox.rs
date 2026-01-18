//! WASM Sandbox
//!
//! Provides a restricted execution environment for plugins.
//! Plugins can only access APIs explicitly granted through permissions.
//!
//! h(x) >= 0. Always.

use super::manifest::Permission;
use heapless::Vec;

/// Resource limits for sandboxed execution
#[derive(Debug, Clone)]
pub struct SandboxLimits {
    /// Maximum memory (bytes)
    pub max_memory: usize,
    /// Maximum execution time (ms)
    pub max_execution_time: u32,
    /// Maximum stack depth
    pub max_stack_depth: u32,
    /// Maximum storage (bytes)
    pub max_storage: usize,
}

impl Default for SandboxLimits {
    fn default() -> Self {
        Self {
            max_memory: 64 * 1024,      // 64KB
            max_execution_time: 1000,    // 1 second
            max_stack_depth: 256,        // 256 call frames
            max_storage: 4 * 1024,       // 4KB per plugin
        }
    }
}

/// Sandbox execution context
pub struct SandboxContext {
    /// Allowed permissions
    permissions: Vec<Permission, 16>,
    /// Resource limits
    limits: SandboxLimits,
    /// Memory usage
    memory_used: usize,
    /// Execution start time
    start_time: Option<u64>,
}

impl SandboxContext {
    /// Create a new sandbox context
    pub fn new(permissions: Vec<Permission, 16>, limits: SandboxLimits) -> Self {
        Self {
            permissions,
            limits,
            memory_used: 0,
            start_time: None,
        }
    }

    /// Check if a permission is granted
    pub fn has_permission(&self, permission: Permission) -> bool {
        self.permissions.contains(&permission)
    }

    /// Check if memory allocation is allowed
    pub fn can_allocate(&self, size: usize) -> bool {
        self.memory_used + size <= self.limits.max_memory
    }

    /// Record memory allocation
    pub fn allocate(&mut self, size: usize) -> bool {
        if self.can_allocate(size) {
            self.memory_used += size;
            true
        } else {
            false
        }
    }

    /// Record memory deallocation
    pub fn deallocate(&mut self, size: usize) {
        self.memory_used = self.memory_used.saturating_sub(size);
    }

    /// Start execution timer
    pub fn start_timer(&mut self, current_time_ms: u64) {
        self.start_time = Some(current_time_ms);
    }

    /// Check if execution has timed out
    pub fn is_timed_out(&self, current_time_ms: u64) -> bool {
        if let Some(start) = self.start_time {
            current_time_ms - start > self.limits.max_execution_time as u64
        } else {
            false
        }
    }

    /// Get memory usage
    pub fn memory_used(&self) -> usize {
        self.memory_used
    }

    /// Get memory limit
    pub fn memory_limit(&self) -> usize {
        self.limits.max_memory
    }
}

/// Import resolver for WASM modules
///
/// This controls which host functions plugins can call.
pub struct ImportResolver {
    context: SandboxContext,
}

impl ImportResolver {
    pub fn new(context: SandboxContext) -> Self {
        Self { context }
    }

    /// Resolve an import request
    pub fn resolve(&self, module: &str, name: &str) -> Option<ImportFunction> {
        // Only allow imports from the "kagami" module
        if module != "kagami" {
            return None;
        }

        match name {
            // HID imports (require permissions)
            "hid_keyboard" if self.context.has_permission(Permission::HidKeyboard) => {
                Some(ImportFunction::HidKeyboard)
            }
            "hid_mouse" if self.context.has_permission(Permission::HidMouse) => {
                Some(ImportFunction::HidMouse)
            }
            "hid_consumer" if self.context.has_permission(Permission::HidConsumer) => {
                Some(ImportFunction::HidConsumer)
            }
            "hid_gamepad" if self.context.has_permission(Permission::HidGamepad) => {
                Some(ImportFunction::HidGamepad)
            }

            // Sensor imports
            "imu_read" if self.context.has_permission(Permission::ImuAccess) => {
                Some(ImportFunction::ImuRead)
            }

            // LED imports
            "led_pattern" if self.context.has_permission(Permission::LedRing) => {
                Some(ImportFunction::LedPattern)
            }
            "led_color" if self.context.has_permission(Permission::LedRing) => {
                Some(ImportFunction::LedColor)
            }

            // Storage imports
            "storage_read" if self.context.has_permission(Permission::Storage) => {
                Some(ImportFunction::StorageRead)
            }
            "storage_write" if self.context.has_permission(Permission::Storage) => {
                Some(ImportFunction::StorageWrite)
            }

            // Always available
            "log" => Some(ImportFunction::Log),
            "time_ms" => Some(ImportFunction::TimeMs),

            _ => None,
        }
    }
}

/// Available import functions
#[derive(Debug, Clone, Copy)]
pub enum ImportFunction {
    HidKeyboard,
    HidMouse,
    HidConsumer,
    HidGamepad,
    ImuRead,
    LedPattern,
    LedColor,
    StorageRead,
    StorageWrite,
    Log,
    TimeMs,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_permission_check() {
        let mut permissions = Vec::new();
        permissions.push(Permission::HidKeyboard).ok();
        permissions.push(Permission::LedRing).ok();

        let context = SandboxContext::new(permissions, SandboxLimits::default());

        assert!(context.has_permission(Permission::HidKeyboard));
        assert!(context.has_permission(Permission::LedRing));
        assert!(!context.has_permission(Permission::HidMouse));
    }

    #[test]
    fn test_memory_limits() {
        let context = SandboxContext::new(Vec::new(), SandboxLimits {
            max_memory: 1024,
            ..Default::default()
        });

        assert!(context.can_allocate(512));
        assert!(context.can_allocate(1024));
        assert!(!context.can_allocate(1025));
    }

    #[test]
    fn test_import_resolver() {
        let mut permissions = Vec::new();
        permissions.push(Permission::HidKeyboard).ok();

        let context = SandboxContext::new(permissions, SandboxLimits::default());
        let resolver = ImportResolver::new(context);

        // Allowed
        assert!(resolver.resolve("kagami", "hid_keyboard").is_some());
        assert!(resolver.resolve("kagami", "log").is_some());

        // Not allowed (no permission)
        assert!(resolver.resolve("kagami", "hid_mouse").is_none());

        // Unknown module
        assert!(resolver.resolve("unknown", "hid_keyboard").is_none());
    }
}
