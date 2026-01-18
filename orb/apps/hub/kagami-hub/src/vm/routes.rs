//! VM HTTP Routes
//!
//! REST API endpoints for virtual machine management.
//!
//! # Endpoints
//!
//! ## Discovery
//! - `GET /vm/hypervisors` - List available hypervisors
//! - `GET /vm` - List all VMs
//! - `GET /vm/:name` - Get VM details
//!
//! ## Lifecycle
//! - `POST /vm/:name/start` - Start VM
//! - `POST /vm/:name/stop` - Stop VM
//! - `POST /vm/:name/force-stop` - Force stop VM
//! - `POST /vm/:name/pause` - Pause VM
//! - `POST /vm/:name/resume` - Resume VM
//! - `POST /vm/:name/restart` - Restart VM
//!
//! ## Provisioning
//! - `POST /vm` - Create VM
//! - `POST /vm/:name/clone` - Clone VM
//! - `DELETE /vm/:name` - Delete VM
//!
//! ## Snapshots
//! - `GET /vm/:name/snapshots` - List snapshots
//! - `POST /vm/:name/snapshots` - Create snapshot
//! - `POST /vm/:name/snapshots/:snapshot/restore` - Restore snapshot
//! - `DELETE /vm/:name/snapshots/:snapshot` - Delete snapshot
//!
//! ## Guest Operations
//! - `POST /vm/:name/execute` - Execute command
//! - `GET /vm/:name/screenshot` - Capture screenshot

use axum::{
    body::Body,
    extract::{Path, State},
    http::{header, StatusCode},
    response::IntoResponse,
    routing::{delete, get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use tokio::sync::RwLock;
use tracing::info;

use super::controller::VMController;
use super::error::VMError;
use super::types::{VMConfig, VMInfo};

// ============================================================================
// State
// ============================================================================

/// VM API state
#[derive(Clone)]
pub struct VMState {
    controller: Arc<RwLock<VMController>>,
}

impl VMState {
    pub fn new(controller: VMController) -> Self {
        Self {
            controller: Arc::new(RwLock::new(controller)),
        }
    }
}

// ============================================================================
// Request/Response Types
// ============================================================================

#[derive(Serialize)]
struct ApiError {
    error: String,
    code: u16,
}

impl From<VMError> for ApiError {
    fn from(err: VMError) -> Self {
        ApiError {
            code: err.status_code(),
            error: err.to_string(),
        }
    }
}

type ApiResult<T> = Result<T, (StatusCode, Json<ApiError>)>;

fn vm_err_to_response(err: VMError) -> (StatusCode, Json<ApiError>) {
    let code = err.status_code();
    (
        StatusCode::from_u16(code).unwrap_or(StatusCode::INTERNAL_SERVER_ERROR),
        Json(ApiError::from(err)),
    )
}

#[derive(Serialize)]
struct HypervisorsResponse {
    hypervisors: Vec<String>,
}

#[derive(Serialize)]
struct VMListResponse {
    vms: Vec<VMInfo>,
    total: usize,
}

#[derive(Deserialize)]
pub struct CreateVMRequest {
    /// Hypervisor to use (parallels, utm, lume, libvirt, hyperv)
    pub hypervisor: String,
    /// VM name
    pub name: String,
    /// OS type
    #[serde(default)]
    pub os_type: Option<String>,
    /// CPU count
    #[serde(default)]
    pub cpu_count: Option<u32>,
    /// Memory in MB
    #[serde(default)]
    pub memory_mb: Option<u64>,
    /// Disk size in GB
    #[serde(default)]
    pub disk_gb: Option<u64>,
    /// Base image for cloning
    #[serde(default)]
    pub base_image: Option<String>,
    /// Run headless
    #[serde(default)]
    pub headless: bool,
}

#[derive(Deserialize)]
pub struct CloneVMRequest {
    /// New VM name
    pub new_name: String,
}

#[derive(Deserialize)]
pub struct StartVMRequest {
    #[serde(default)]
    pub headless: bool,
}

#[derive(Deserialize)]
pub struct CreateSnapshotRequest {
    pub name: String,
    #[serde(default)]
    pub description: Option<String>,
}

#[derive(Deserialize)]
pub struct ExecuteCommandRequest {
    pub command: String,
    #[serde(default)]
    pub timeout_ms: Option<u64>,
}

#[derive(Deserialize)]
pub struct UpdateResourcesRequest {
    #[serde(default)]
    pub cpu_count: Option<u32>,
    #[serde(default)]
    pub memory_mb: Option<u64>,
}

#[derive(Deserialize)]
pub struct DeleteVMQuery {
    #[serde(default)]
    pub delete_files: bool,
}

// ============================================================================
// Router
// ============================================================================

/// Create VM router
pub fn vm_router(controller: VMController) -> Router {
    let state = VMState::new(controller);

    Router::new()
        // Discovery
        .route("/hypervisors", get(list_hypervisors))
        .route("/", get(list_vms))
        .route("/:name", get(get_vm))
        // Lifecycle
        .route("/:name/start", post(start_vm))
        .route("/:name/stop", post(stop_vm))
        .route("/:name/force-stop", post(force_stop_vm))
        .route("/:name/pause", post(pause_vm))
        .route("/:name/resume", post(resume_vm))
        .route("/:name/restart", post(restart_vm))
        // Provisioning
        .route("/", post(create_vm))
        .route("/:name/clone", post(clone_vm))
        .route("/:name", delete(delete_vm))
        // Resources
        .route("/:name/resources", post(update_resources))
        // Snapshots
        .route("/:name/snapshots", get(list_snapshots))
        .route("/:name/snapshots", post(create_snapshot))
        .route(
            "/:name/snapshots/:snapshot/restore",
            post(restore_snapshot),
        )
        .route("/:name/snapshots/:snapshot", delete(delete_snapshot))
        // Guest operations
        .route("/:name/execute", post(execute_command))
        .route("/:name/screenshot", get(screenshot))
        .with_state(state)
}

// ============================================================================
// Handlers
// ============================================================================

async fn list_hypervisors(State(state): State<VMState>) -> ApiResult<Json<HypervisorsResponse>> {
    let controller = state.controller.read().await;
    let hypervisors = controller.available_hypervisors().await;

    Ok(Json(HypervisorsResponse { hypervisors }))
}

async fn list_vms(State(state): State<VMState>) -> ApiResult<Json<VMListResponse>> {
    let controller = state.controller.read().await;
    let vms = controller.list_vms().await.map_err(vm_err_to_response)?;
    let total = vms.len();

    Ok(Json(VMListResponse { vms, total }))
}

async fn get_vm(State(state): State<VMState>, Path(name): Path<String>) -> ApiResult<Json<VMInfo>> {
    let controller = state.controller.read().await;
    let vm = controller.get_vm(&name).await.map_err(vm_err_to_response)?;

    Ok(Json(vm))
}

async fn start_vm(
    State(state): State<VMState>,
    Path(name): Path<String>,
    Json(req): Json<Option<StartVMRequest>>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;
    let headless = req.map(|r| r.headless).unwrap_or(false);

    info!("Starting VM: {} (headless={})", name, headless);
    controller
        .start_vm_with_options(&name, headless)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("VM '{}' started", name)
    })))
}

async fn stop_vm(
    State(state): State<VMState>,
    Path(name): Path<String>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Stopping VM: {}", name);
    controller
        .stop_vm(&name)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("VM '{}' stopped", name)
    })))
}

async fn force_stop_vm(
    State(state): State<VMState>,
    Path(name): Path<String>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Force stopping VM: {}", name);
    controller
        .force_stop_vm(&name)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("VM '{}' force stopped", name)
    })))
}

async fn pause_vm(
    State(state): State<VMState>,
    Path(name): Path<String>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Pausing VM: {}", name);
    controller
        .pause_vm(&name)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("VM '{}' paused", name)
    })))
}

async fn resume_vm(
    State(state): State<VMState>,
    Path(name): Path<String>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Resuming VM: {}", name);
    controller
        .resume_vm(&name)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("VM '{}' resumed", name)
    })))
}

async fn restart_vm(
    State(state): State<VMState>,
    Path(name): Path<String>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Restarting VM: {}", name);
    controller
        .restart_vm(&name)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("VM '{}' restarted", name)
    })))
}

async fn create_vm(
    State(state): State<VMState>,
    Json(req): Json<CreateVMRequest>,
) -> ApiResult<Json<VMInfo>> {
    let controller = state.controller.read().await;

    // Build config
    let mut config = VMConfig::new(&req.name);

    if let Some(os_str) = &req.os_type {
        config.os_type = os_str.parse().unwrap_or_default();
    }
    if let Some(cpus) = req.cpu_count {
        config.resources.cpu_count = cpus;
    }
    if let Some(mem) = req.memory_mb {
        config.resources.memory_mb = mem;
    }
    if let Some(disk) = req.disk_gb {
        config.resources.disk_gb = disk;
    }
    config.base_image = req.base_image;
    config.headless = req.headless;

    info!("Creating VM: {} on {}", req.name, req.hypervisor);
    let vm = controller
        .create_vm(&req.hypervisor, config)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(vm))
}

async fn clone_vm(
    State(state): State<VMState>,
    Path(source_name): Path<String>,
    Json(req): Json<CloneVMRequest>,
) -> ApiResult<Json<VMInfo>> {
    let controller = state.controller.read().await;

    info!("Cloning VM: {} -> {}", source_name, req.new_name);
    let vm = controller
        .clone_vm(&source_name, &req.new_name)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(vm))
}

async fn delete_vm(
    State(state): State<VMState>,
    Path(name): Path<String>,
    axum::extract::Query(query): axum::extract::Query<DeleteVMQuery>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!(
        "Deleting VM: {} (delete_files={})",
        name, query.delete_files
    );
    controller
        .delete_vm(&name, query.delete_files)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("VM '{}' deleted", name)
    })))
}

async fn update_resources(
    State(state): State<VMState>,
    Path(name): Path<String>,
    Json(req): Json<UpdateResourcesRequest>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!(
        "Updating resources for VM: {} (cpu={:?}, mem={:?})",
        name, req.cpu_count, req.memory_mb
    );
    controller
        .update_resources(&name, req.cpu_count, req.memory_mb)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("VM '{}' resources updated", name)
    })))
}

async fn list_snapshots(
    State(state): State<VMState>,
    Path(name): Path<String>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;
    let snapshots = controller
        .list_snapshots(&name)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "vm": name,
        "snapshots": snapshots,
        "total": snapshots.len()
    })))
}

async fn create_snapshot(
    State(state): State<VMState>,
    Path(name): Path<String>,
    Json(req): Json<CreateSnapshotRequest>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Creating snapshot for VM: {} -> {}", name, req.name);
    let snapshot = controller
        .create_snapshot(&name, &req.name, req.description.as_deref())
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "snapshot": snapshot
    })))
}

async fn restore_snapshot(
    State(state): State<VMState>,
    Path((name, snapshot)): Path<(String, String)>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Restoring snapshot for VM: {} -> {}", name, snapshot);
    controller
        .restore_snapshot(&name, &snapshot)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("Snapshot '{}' restored for VM '{}'", snapshot, name)
    })))
}

async fn delete_snapshot(
    State(state): State<VMState>,
    Path((name, snapshot)): Path<(String, String)>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Deleting snapshot for VM: {} -> {}", name, snapshot);
    controller
        .delete_snapshot(&name, &snapshot)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": true,
        "message": format!("Snapshot '{}' deleted from VM '{}'", snapshot, name)
    })))
}

async fn execute_command(
    State(state): State<VMState>,
    Path(name): Path<String>,
    Json(req): Json<ExecuteCommandRequest>,
) -> ApiResult<Json<serde_json::Value>> {
    let controller = state.controller.read().await;

    info!("Executing command in VM: {} -> {:?}", name, req.command);
    let result = controller
        .execute_command(&name, &req.command, req.timeout_ms)
        .await
        .map_err(vm_err_to_response)?;

    Ok(Json(serde_json::json!({
        "success": result.is_success(),
        "exit_code": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "duration_ms": result.duration_ms
    })))
}

async fn screenshot(
    State(state): State<VMState>,
    Path(name): Path<String>,
) -> ApiResult<impl IntoResponse> {
    let controller = state.controller.read().await;

    info!("Capturing screenshot of VM: {}", name);
    let image_data = controller
        .screenshot(&name)
        .await
        .map_err(vm_err_to_response)?;

    Ok((
        [(header::CONTENT_TYPE, "image/png")],
        Body::from(image_data),
    ))
}
