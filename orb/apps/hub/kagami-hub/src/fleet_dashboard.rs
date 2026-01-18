//! Fleet Health Dashboard
//!
//! Web UI showing all hubs in the mesh:
//! - Hub status, location, zone level
//! - State cache age, last sync
//! - Leader indicator
//! - Health metrics (CPU, memory, uptime)
//!
//! Colony: Beacon (e₅) — Oversight and monitoring
//!
//! η → s → μ → a → η′
//! h(x) ≥ 0. Always.

use serde::Serialize;

use crate::state_cache::ZoneLevel;

#[cfg(feature = "mesh")]
use crate::mesh::Peer;

/// Fleet overview data
#[derive(Debug, Clone, Serialize)]
pub struct FleetOverview {
    /// Total hubs in mesh
    pub hub_count: usize,
    /// Current leader hub ID
    pub leader_hub_id: Option<String>,
    /// Number of hubs online
    pub online_count: usize,
    /// Average state cache age (seconds)
    pub avg_cache_age: f64,
    /// Fleet health percentage (0-100)
    pub health_percent: f32,
}

/// Individual hub status for dashboard
#[derive(Debug, Clone, Serialize)]
pub struct HubDashboardStatus {
    /// Hub unique ID
    pub hub_id: String,
    /// Human-readable name
    pub name: String,
    /// Location description
    pub location: String,
    /// Current zone level
    pub zone: ZoneLevel,
    /// Whether this hub is the leader
    pub is_leader: bool,
    /// Uptime in seconds
    pub uptime_secs: u64,
    /// State cache age in seconds
    pub cache_age_secs: u64,
    /// Last sync timestamp (Unix)
    pub last_sync: Option<u64>,
    /// CPU usage percentage
    pub cpu_percent: Option<f32>,
    /// Memory usage in MB
    pub memory_mb: Option<f32>,
    /// Disk usage percentage
    pub disk_percent: Option<f32>,
    /// Whether hub is responding
    pub online: bool,
    /// Hub version
    pub version: String,
}

/// Generate the fleet dashboard HTML
pub fn generate_dashboard_html(overview: &FleetOverview, hubs: &[HubDashboardStatus]) -> String {
    let hub_cards: String = hubs.iter().map(|hub| {
        let status_class = if hub.online { "online" } else { "offline" };
        let leader_badge = if hub.is_leader { "<span class='badge leader'>👑 LEADER</span>" } else { "" };

        format!(r#"
        <div class="hub-card {status_class}">
            <div class="hub-header">
                <h3>{name}</h3>
                {leader_badge}
                <span class="badge zone zone-{zone}">{zone:?}</span>
            </div>
            <div class="hub-meta">
                <span>📍 {location}</span>
                <span>v{version}</span>
            </div>
            <div class="hub-stats">
                <div class="stat">
                    <span class="label">Uptime</span>
                    <span class="value">{uptime}</span>
                </div>
                <div class="stat">
                    <span class="label">Cache Age</span>
                    <span class="value">{cache_age}s</span>
                </div>
                {cpu_stat}
                {mem_stat}
            </div>
            <div class="hub-footer">
                <span class="hub-id">{hub_id}</span>
            </div>
        </div>
        "#,
            name = hub.name,
            location = hub.location,
            version = hub.version,
            zone = hub.zone,
            uptime = format_duration(hub.uptime_secs),
            cache_age = hub.cache_age_secs,
            hub_id = hub.hub_id,
            cpu_stat = hub.cpu_percent.map(|p| format!(
                r#"<div class="stat"><span class="label">CPU</span><span class="value">{}%</span></div>"#,
                p as i32
            )).unwrap_or_default(),
            mem_stat = hub.memory_mb.map(|m| format!(
                r#"<div class="stat"><span class="label">Memory</span><span class="value">{:.0}MB</span></div>"#,
                m
            )).unwrap_or_default(),
        )
    }).collect();

    format!(r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Kagami Fleet Dashboard</title>
    <style>
        :root {{
            --void: #07060B;
            --obsidian: #12101A;
            --carbon: #252330;
            --spark: #ff6b35;
            --forge: #d4af37;
            --flow: #4ecdc4;
            --nexus: #9b7ebd;
            --beacon: #f59e0b;
            --grove: #7eb77f;
            --crystal: #67d4e4;
            --text-primary: #f5f0e8;
            --text-secondary: rgba(245, 240, 232, 0.65);
        }}

        * {{ box-sizing: border-box; margin: 0; padding: 0; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'SF Pro', system-ui, sans-serif;
            background: var(--void);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 24px;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
        }}

        h1 {{
            font-size: 1.5rem;
            font-weight: 600;
            background: linear-gradient(135deg, var(--crystal), var(--nexus));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .overview {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }}

        .overview-card {{
            background: var(--obsidian);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 16px;
            text-align: center;
        }}

        .overview-card .value {{
            font-size: 2rem;
            font-weight: 700;
            color: var(--crystal);
        }}

        .overview-card .label {{
            font-size: 0.75rem;
            color: var(--text-secondary);
            text-transform: uppercase;
        }}

        .hub-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 16px;
        }}

        .hub-card {{
            background: var(--obsidian);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 16px;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .hub-card:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }}

        .hub-card.offline {{
            opacity: 0.6;
            border-color: rgba(255,68,68,0.3);
        }}

        .hub-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 8px;
        }}

        .hub-header h3 {{
            flex: 1;
            font-size: 1rem;
            font-weight: 600;
        }}

        .badge {{
            font-size: 0.625rem;
            padding: 2px 8px;
            border-radius: 999px;
            text-transform: uppercase;
            font-weight: 600;
        }}

        .badge.leader {{
            background: linear-gradient(135deg, var(--forge), var(--beacon));
            color: var(--void);
        }}

        .badge.zone {{
            background: rgba(255,255,255,0.1);
        }}

        .zone-Transcend {{ color: var(--crystal); }}
        .zone-Beyond {{ color: var(--grove); }}
        .zone-SlowZone {{ color: var(--beacon); }}
        .zone-UnthinkingDepths {{ color: var(--spark); }}

        .hub-meta {{
            display: flex;
            gap: 16px;
            font-size: 0.75rem;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }}

        .hub-stats {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }}

        .stat {{
            background: var(--carbon);
            padding: 8px;
            border-radius: 8px;
        }}

        .stat .label {{
            font-size: 0.625rem;
            color: var(--text-secondary);
            text-transform: uppercase;
        }}

        .stat .value {{
            font-size: 0.875rem;
            font-weight: 600;
        }}

        .hub-footer {{
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(255,255,255,0.05);
        }}

        .hub-id {{
            font-family: monospace;
            font-size: 0.625rem;
            color: var(--text-secondary);
        }}

        .health-bar {{
            height: 4px;
            background: var(--carbon);
            border-radius: 2px;
            overflow: hidden;
        }}

        .health-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--grove), var(--crystal));
            transition: width 0.3s;
        }}
    </style>
</head>
<body>
    <header>
        <h1>🔗 Kagami Fleet Dashboard</h1>
        <span class="badge">v{version}</span>
    </header>

    <div class="overview">
        <div class="overview-card">
            <div class="value">{hub_count}</div>
            <div class="label">Total Hubs</div>
        </div>
        <div class="overview-card">
            <div class="value">{online_count}</div>
            <div class="label">Online</div>
        </div>
        <div class="overview-card">
            <div class="value">{health}%</div>
            <div class="label">Fleet Health</div>
            <div class="health-bar"><div class="health-fill" style="width: {health}%"></div></div>
        </div>
        <div class="overview-card">
            <div class="value">{cache_age:.0}s</div>
            <div class="label">Avg Cache Age</div>
        </div>
    </div>

    <div class="hub-grid">
        {hub_cards}
    </div>

    <script>
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>"#,
        version = env!("CARGO_PKG_VERSION"),
        hub_count = overview.hub_count,
        online_count = overview.online_count,
        health = overview.health_percent as i32,
        cache_age = overview.avg_cache_age,
        hub_cards = hub_cards,
    )
}

/// Format duration in human-readable form
fn format_duration(secs: u64) -> String {
    if secs < 60 {
        format!("{}s", secs)
    } else if secs < 3600 {
        format!("{}m", secs / 60)
    } else if secs < 86400 {
        format!("{}h", secs / 3600)
    } else {
        format!("{}d", secs / 86400)
    }
}

/// Collect fleet data from mesh
#[cfg(feature = "mesh")]
pub async fn collect_fleet_data(
    hub_id: &str,
    hub_name: &str,
    peers: &[Peer],
    is_leader: bool,
    uptime: u64,
    cache_age: u64,
    zone: ZoneLevel,
) -> (FleetOverview, Vec<HubDashboardStatus>) {
    let mut hubs = Vec::new();

    // Add self
    hubs.push(HubDashboardStatus {
        hub_id: hub_id.to_string(),
        name: hub_name.to_string(),
        location: "Local".to_string(),
        zone,
        is_leader,
        uptime_secs: uptime,
        cache_age_secs: cache_age,
        last_sync: Some(std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_secs()),
        cpu_percent: get_cpu_usage(),
        memory_mb: get_memory_usage(),
        disk_percent: get_disk_usage(),
        online: true,
        version: env!("CARGO_PKG_VERSION").to_string(),
    });

    // Add peers
    for peer in peers {
        hubs.push(HubDashboardStatus {
            hub_id: peer.hub_id.clone(),
            name: peer.name.clone(),
            location: peer.address.clone(),
            zone: ZoneLevel::Beyond, // Would need to query peer
            is_leader: peer.is_leader,
            uptime_secs: 0,
            cache_age_secs: 0,
            last_sync: None,
            cpu_percent: None,
            memory_mb: None,
            disk_percent: None,
            online: peer.is_alive(std::time::Duration::from_secs(60)),
            version: peer.properties.get("version").cloned().unwrap_or_default(),
        });
    }

    let online_count = hubs.iter().filter(|h| h.online).count();
    let avg_cache = if online_count > 0 {
        hubs.iter().map(|h| h.cache_age_secs as f64).sum::<f64>() / online_count as f64
    } else {
        0.0
    };

    let overview = FleetOverview {
        hub_count: hubs.len(),
        leader_hub_id: hubs.iter().find(|h| h.is_leader).map(|h| h.hub_id.clone()),
        online_count,
        avg_cache_age: avg_cache,
        health_percent: (online_count as f32 / hubs.len() as f32) * 100.0,
    };

    (overview, hubs)
}

/// Get CPU usage (platform-specific)
fn get_cpu_usage() -> Option<f32> {
    // Placeholder - would use sysinfo crate in production
    None
}

/// Get memory usage in MB
fn get_memory_usage() -> Option<f32> {
    // Placeholder - would use sysinfo crate in production
    None
}

/// Get disk usage percentage
fn get_disk_usage() -> Option<f32> {
    // Placeholder - would use sysinfo crate in production
    None
}

/*
 * 鏡
 * The fleet as one. Each hub a seed.
 */
