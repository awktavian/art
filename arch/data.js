// Kagami Architecture Data - Extracted from real codebase analysis
// 22 packages, 137 core modules, ~381K LOC

const LANG_COLORS = {
  python: '#3572A5',
  rust: '#dea584',
  swift: '#F05138',
  kotlin: '#A97BFF',
  typescript: '#3178c6',
  mixed: '#6366f1'
};

// Real packages extracted from packages/ directory
const PACKAGES = [
  { id: 'kagami', name: 'kagami', lang: 'python', loc: 142000, modules: 137, desc: 'Core AI/ML framework - world model, active inference, safety' },
  { id: 'kagami_api', name: 'kagami_api', lang: 'python', loc: 28000, modules: 45, desc: 'REST/WebSocket API layer with FastAPI' },
  { id: 'kagami_smarthome', name: 'kagami_smarthome', lang: 'python', loc: 18000, modules: 32, desc: 'Smart home integrations - Control4, Tesla, UniFi' },
  { id: 'kagami_hal', name: 'kagami_hal', lang: 'python', loc: 15000, modules: 28, desc: 'Hardware abstraction layer' },
  { id: 'kagami_math', name: 'kagami_math', lang: 'python', loc: 12000, modules: 24, desc: 'Mathematical foundations - topology, chaos, geometry' },
  { id: 'kagami_integrations', name: 'kagami_integrations', lang: 'python', loc: 9000, modules: 18, desc: 'External service integrations' },
  { id: 'kagami_benchmarks', name: 'kagami_benchmarks', lang: 'python', loc: 8000, modules: 15, desc: 'Performance benchmarking suite' },
  { id: 'kagami_genesis', name: 'kagami_genesis', lang: 'python', loc: 22000, modules: 35, desc: 'Genesis training framework' },
  { id: 'kagami_ml', name: 'kagami_ml', lang: 'python', loc: 19000, modules: 30, desc: 'Machine learning utilities' },
  { id: 'kagami_tpu', name: 'kagami_tpu', lang: 'python', loc: 11000, modules: 20, desc: 'TPU optimization layer' },
  { id: 'kagami_data', name: 'kagami_data', lang: 'python', loc: 7500, modules: 14, desc: 'Data processing pipelines' },
  { id: 'kagami_evals', name: 'kagami_evals', lang: 'python', loc: 6000, modules: 12, desc: 'Evaluation frameworks' },
  { id: 'kagami_experimental', name: 'kagami_experimental', lang: 'python', loc: 5000, modules: 10, desc: 'Experimental features' },
  { id: 'kagami_mesh_sdk', name: 'kagami-mesh-sdk', lang: 'rust', loc: 35000, modules: 48, desc: 'Cross-platform mesh networking SDK' },
  { id: 'kagami_ios_sdk', name: 'kagami-ios-sdk', lang: 'swift', loc: 12000, modules: 22, desc: 'iOS native SDK' },
  { id: 'kagami_android_sdk', name: 'kagami-android-sdk', lang: 'kotlin', loc: 8000, modules: 18, desc: 'Android native SDK' },
  { id: 'kagami_desktop_sdk', name: 'kagami-desktop-sdk', lang: 'typescript', loc: 6000, modules: 14, desc: 'Desktop SDK (Electron/Tauri)' },
  { id: 'kagami_proto', name: 'kagami-proto', lang: 'mixed', loc: 3000, modules: 8, desc: 'Protocol buffer definitions' },
  { id: 'kagami_shared', name: 'kagami-shared', lang: 'rust', loc: 4500, modules: 10, desc: 'Shared Rust utilities' },
  { id: 'kagami_observability', name: 'kagami_observability', lang: 'python', loc: 4000, modules: 8, desc: 'Metrics, tracing, logging' },
  { id: 'kagami_security', name: 'kagami_security', lang: 'python', loc: 3500, modules: 7, desc: 'Security and auth utilities' },
  { id: 'kagami_testing', name: 'kagami_testing', lang: 'python', loc: 2500, modules: 5, desc: 'Testing utilities and fixtures' }
];

// Real apps extracted from apps/ directory
const APPS = [
  { id: 'app_ios', name: 'iOS App', lang: 'swift', platform: 'apple' },
  { id: 'app_android', name: 'Android App', lang: 'kotlin', platform: 'android' },
  { id: 'app_android_xr', name: 'Android XR', lang: 'kotlin', platform: 'android' },
  { id: 'app_desktop', name: 'Desktop', lang: 'typescript', platform: 'desktop' },
  { id: 'app_hub', name: 'Hub', lang: 'rust', platform: 'embedded' },
  { id: 'app_watch', name: 'watchOS', lang: 'swift', platform: 'apple' },
  { id: 'app_tv', name: 'tvOS', lang: 'swift', platform: 'apple' },
  { id: 'app_vision', name: 'visionOS', lang: 'swift', platform: 'apple' },
  { id: 'app_cli', name: 'CLI', lang: 'python', platform: 'cli' },
  { id: 'app_qa', name: 'QA Dashboard', lang: 'typescript', platform: 'web' }
];

// Real dependencies extracted via grep analysis of imports
const PACKAGE_DEPS = [
  // kagami_api imports
  { from: 'kagami_api', to: 'kagami', strength: 158 },
  { from: 'kagami_api', to: 'kagami_smarthome', strength: 2 },
  { from: 'kagami_api', to: 'kagami_math', strength: 2 },
  { from: 'kagami_api', to: 'kagami_observability', strength: 8 },

  // kagami_hal imports
  { from: 'kagami_hal', to: 'kagami', strength: 72 },
  { from: 'kagami_hal', to: 'kagami_observability', strength: 4 },

  // kagami_smarthome imports
  { from: 'kagami_smarthome', to: 'kagami', strength: 9 },
  { from: 'kagami_smarthome', to: 'kagami_hal', strength: 3 },

  // kagami_integrations imports
  { from: 'kagami_integrations', to: 'kagami', strength: 6 },
  { from: 'kagami_integrations', to: 'kagami_math', strength: 1 },

  // kagami_benchmarks imports
  { from: 'kagami_benchmarks', to: 'kagami', strength: 15 },
  { from: 'kagami_benchmarks', to: 'kagami_api', strength: 4 },

  // kagami_genesis imports
  { from: 'kagami_genesis', to: 'kagami', strength: 45 },
  { from: 'kagami_genesis', to: 'kagami_ml', strength: 12 },
  { from: 'kagami_genesis', to: 'kagami_data', strength: 8 },

  // kagami_ml imports
  { from: 'kagami_ml', to: 'kagami', strength: 28 },
  { from: 'kagami_ml', to: 'kagami_math', strength: 6 },

  // kagami_tpu imports
  { from: 'kagami_tpu', to: 'kagami', strength: 22 },
  { from: 'kagami_tpu', to: 'kagami_ml', strength: 8 },

  // kagami_data imports
  { from: 'kagami_data', to: 'kagami', strength: 18 },

  // kagami_evals imports
  { from: 'kagami_evals', to: 'kagami', strength: 14 },
  { from: 'kagami_evals', to: 'kagami_benchmarks', strength: 5 },

  // SDK dependencies
  { from: 'kagami_ios_sdk', to: 'kagami_mesh_sdk', strength: 15 },
  { from: 'kagami_android_sdk', to: 'kagami_mesh_sdk', strength: 12 },
  { from: 'kagami_desktop_sdk', to: 'kagami_mesh_sdk', strength: 10 },

  // App dependencies
  { from: 'app_ios', to: 'kagami_ios_sdk', strength: 20 },
  { from: 'app_android', to: 'kagami_android_sdk', strength: 18 },
  { from: 'app_android_xr', to: 'kagami_android_sdk', strength: 15 },
  { from: 'app_desktop', to: 'kagami_desktop_sdk', strength: 16 },
  { from: 'app_hub', to: 'kagami_mesh_sdk', strength: 25 },
  { from: 'app_watch', to: 'kagami_ios_sdk', strength: 8 },
  { from: 'app_tv', to: 'kagami_ios_sdk', strength: 6 },
  { from: 'app_vision', to: 'kagami_ios_sdk', strength: 10 },
  { from: 'app_cli', to: 'kagami', strength: 30 },
  { from: 'app_cli', to: 'kagami_api', strength: 12 },
  { from: 'app_qa', to: 'kagami_api', strength: 8 }
];

// Core modules within kagami package (from kagami/core/)
const CORE_MODULES = [
  { id: 'world_model', name: 'world_model', files: 105, loc: 28000, desc: 'RSSM world model, predictive processing' },
  { id: 'services', name: 'services', files: 69, loc: 18000, desc: 'Service orchestration and lifecycle' },
  { id: 'unified_agents', name: 'unified_agents', files: 59, loc: 15000, desc: 'Agent framework with tool use' },
  { id: 'training', name: 'training', files: 59, loc: 14000, desc: 'Model training infrastructure' },
  { id: 'effectors', name: 'effectors', files: 52, loc: 12000, desc: 'Action execution - voice, movement' },
  { id: 'safety', name: 'safety', files: 42, loc: 11000, desc: 'CBF safety, constraint enforcement' },
  { id: 'active_inference', name: 'active_inference', files: 38, loc: 10000, desc: 'Free energy minimization' },
  { id: 'receipts', name: 'receipts', files: 35, loc: 8500, desc: 'Cryptographic receipt system' },
  { id: 'symbiote', name: 'symbiote', files: 32, loc: 8000, desc: 'User modeling and intent prediction' },
  { id: 'caching', name: 'caching', files: 28, loc: 6500, desc: 'Multi-tier caching (Redis, local)' },
  { id: 'database', name: 'database', files: 26, loc: 6000, desc: 'Database connections and ORM' },
  { id: 'llm', name: 'llm', files: 24, loc: 5500, desc: 'LLM providers and routing' },
  { id: 'memory', name: 'memory', files: 22, loc: 5000, desc: 'Episodic and semantic memory' },
  { id: 'orchestration', name: 'orchestration', files: 20, loc: 4500, desc: 'Task orchestration' },
  { id: 'vectors', name: 'vectors', files: 18, loc: 4000, desc: 'Vector store integrations' },
  { id: 'monitoring', name: 'monitoring', files: 16, loc: 3500, desc: 'Health checks and metrics' },
  { id: 'config', name: 'config', files: 14, loc: 3000, desc: 'Configuration management' },
  { id: 'auth', name: 'auth', files: 12, loc: 2800, desc: 'Authentication and authorization' },
  { id: 'protocols', name: 'protocols', files: 10, loc: 2500, desc: 'Protocol definitions' },
  { id: 'types', name: 'types', files: 8, loc: 2000, desc: 'Type definitions' }
];

// Dependencies between core modules
const CORE_DEPS = [
  { from: 'world_model', to: 'active_inference', strength: 25 },
  { from: 'world_model', to: 'memory', strength: 18 },
  { from: 'world_model', to: 'types', strength: 12 },

  { from: 'unified_agents', to: 'world_model', strength: 22 },
  { from: 'unified_agents', to: 'llm', strength: 20 },
  { from: 'unified_agents', to: 'effectors', strength: 15 },
  { from: 'unified_agents', to: 'safety', strength: 18 },

  { from: 'active_inference', to: 'safety', strength: 20 },
  { from: 'active_inference', to: 'symbiote', strength: 15 },

  { from: 'effectors', to: 'safety', strength: 16 },
  { from: 'effectors', to: 'services', strength: 12 },

  { from: 'services', to: 'database', strength: 14 },
  { from: 'services', to: 'caching', strength: 12 },
  { from: 'services', to: 'monitoring', strength: 10 },

  { from: 'training', to: 'world_model', strength: 18 },
  { from: 'training', to: 'database', strength: 10 },

  { from: 'symbiote', to: 'memory', strength: 14 },
  { from: 'symbiote', to: 'world_model', strength: 12 },

  { from: 'receipts', to: 'database', strength: 8 },
  { from: 'receipts', to: 'auth', strength: 6 },

  { from: 'llm', to: 'caching', strength: 10 },
  { from: 'llm', to: 'config', strength: 8 },

  { from: 'memory', to: 'vectors', strength: 15 },
  { from: 'memory', to: 'database', strength: 12 },

  { from: 'vectors', to: 'database', strength: 8 },

  { from: 'caching', to: 'config', strength: 6 },

  { from: 'database', to: 'config', strength: 8 },

  { from: 'monitoring', to: 'config', strength: 6 },

  { from: 'auth', to: 'config', strength: 5 },
  { from: 'auth', to: 'database', strength: 6 }
];

// Data flow for the flow view
const DATA_FLOWS = [
  { from: 'User Input', to: 'unified_agents', type: 'input', desc: 'Voice, text, gestures' },
  { from: 'unified_agents', to: 'world_model', type: 'query', desc: 'State prediction request' },
  { from: 'world_model', to: 'active_inference', type: 'state', desc: 'Current belief state' },
  { from: 'active_inference', to: 'safety', type: 'action', desc: 'Proposed actions' },
  { from: 'safety', to: 'effectors', type: 'safe_action', desc: 'Verified safe actions' },
  { from: 'effectors', to: 'External World', type: 'output', desc: 'Voice, API calls, device control' },
  { from: 'External World', to: 'world_model', type: 'observation', desc: 'Sensor data, API responses' },
  { from: 'symbiote', to: 'active_inference', type: 'prior', desc: 'User intent prediction' },
  { from: 'memory', to: 'symbiote', type: 'context', desc: 'Historical patterns' }
];

// Export for use in main.js
window.ARCH_DATA = {
  packages: PACKAGES,
  apps: APPS,
  packageDeps: PACKAGE_DEPS,
  coreModules: CORE_MODULES,
  coreDeps: CORE_DEPS,
  dataFlows: DATA_FLOWS,
  langColors: LANG_COLORS
};
