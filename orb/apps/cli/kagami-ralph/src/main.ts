/**
 * Ralph AI Monitor - Main Entry Point
 *
 * Real-time visualization of parallel Ralph AI training with Byzantine consensus.
 */

import { RalphWebSocketClient } from './lib/websocket';
import { ParticleSystem } from './lib/particles';
import { AudioFeedback } from './lib/audio';
import { AITooltipManager } from './lib/ai_tooltips';
import type { RalphMessage, AgentState, ConsensusRound, TrainingMetrics } from './types/agent';
import './style.css';

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

const agents: Map<number, AgentState> = new Map();
const consensus: ConsensusRound = {
  roundId: 1,
  phase: 'PRE_VOTE',
  votes: [],
  quorum: 5,
  threshold: 70,
};

let metrics: TrainingMetrics = {
  step: 0,
  loss: 0.0,
  phase: 'INIT',
  receipts: 0,
  validations: 0,
  uptime: 0,
};

// 111/100 CRYSTAL POLISH: Particles + Audio + AI Tooltips
const particles = new ParticleSystem();
const audio = new AudioFeedback();
const tooltips = new AITooltipManager();

// ═══════════════════════════════════════════════════════════════════════════
// WEBSOCKET CLIENT
// ═══════════════════════════════════════════════════════════════════════════

const wsUrl =
  (import.meta as any).env?.MODE === 'production'
    ? `wss://${window.location.host}/ws/ralph`
    : 'ws://localhost:8001/ws/ralph';

const wsClient = new RalphWebSocketClient({
  url: wsUrl,
  reconnectInterval: 3000,
  maxReconnectAttempts: 10,
  heartbeatInterval: 30000,
});

// Handle messages
wsClient.onMessage((message: RalphMessage) => {
  switch (message.type) {
    case 'agent_update':
      handleAgentUpdate(message.data as AgentState);
      break;
    case 'consensus_update':
      handleConsensusUpdate(message.data as unknown as ConsensusRound);
      break;
    case 'metrics_update':
      handleMetricsUpdate(message.data as TrainingMetrics);
      break;
    case 'error':
      console.error('[Ralph] Error:', message.data);
      break;
  }
});

// Handle connection status
wsClient.onConnection((connected: boolean) => {
  updateConnectionStatus(connected);
});

// Handle errors
wsClient.onError((error: Error) => {
  console.error('[Ralph] WebSocket error:', error);
  showError(error.message);
});

// ═══════════════════════════════════════════════════════════════════════════
// MESSAGE HANDLERS
// ═══════════════════════════════════════════════════════════════════════════

function handleAgentUpdate(agentData: AgentState): void {
  const oldAgent = agents.get(agentData.id);
  agents.set(agentData.id, agentData);
  
  // 111/100 POLISH: Sparkle on status change
  if (oldAgent && oldAgent.status !== agentData.status) {
    const agentEl = document.querySelector(`[data-agent-id="${agentData.id}"]`);
    if (agentEl) {
      const rect = agentEl.getBoundingClientRect();
      particles.emitAgentSparkle(
        rect.left + rect.width / 2,
        rect.top + rect.height / 2,
        agentData.status
      );
    }
    audio.playAgentActivity();
  }
  
  renderAgents();
}

function handleConsensusUpdate(consensusData: ConsensusRound): void {
  const oldVoteCount = consensus.votes.length;
  Object.assign(consensus, consensusData);
  
  // 111/100 POLISH: Particles + audio on consensus reached
  if (consensusData.votes.length >= consensus.quorum && oldVoteCount < consensus.quorum) {
    const approved = consensusData.votes.filter(v => v.vote).length >= consensus.quorum;
    
    // Emit particles from center
    particles.emitConsensusParticles(
      window.innerWidth / 2,
      window.innerHeight / 2,
      approved
    );
    
    // Play consensus sound
    audio.playConsensus(approved);
  }
  
  // Audio on each vote
  if (consensusData.votes.length > oldVoteCount && consensusData.votes.length > 0) {
    const lastVote = consensusData.votes[consensusData.votes.length - 1];
    if (lastVote !== undefined) {
      audio.playVote(lastVote.vote);
    }
  }
  
  renderConsensus();
}

function handleMetricsUpdate(metricsData: TrainingMetrics): void {
  metrics = metricsData;
  renderMetrics();
}

// ═══════════════════════════════════════════════════════════════════════════
// RENDERING
// ═══════════════════════════════════════════════════════════════════════════

function renderAgents(): void {
  const container = document.getElementById('agents-container');
  if (!container) return;

  const statusIcons: Record<string, string> = {
    idle: '⚪',
    starting: '🔵',
    running: '🟢',
    thinking: '🟡',
    consensus: '🟣',
    success: '✅',
    warning: '⚠️',
    error: '❌',
    complete: '🎉',
  };

  container.innerHTML = Array.from(agents.values())
    .map(
      (agent) => `
    <div class="agent-card ${agent.status === 'success' ? 'active' : ''}" data-agent-id="${agent.id}">
      <div class="agent-header">
        <div class="agent-status-icon">${statusIcons[agent.status] ?? '⚪'}</div>
        <div>
          <div class="agent-name">${agent.name}</div>
          <div class="agent-score">${agent.score.toFixed(0)}/100</div>
        </div>
      </div>
      <div class="agent-message">${agent.message}</div>
    </div>
  `
    )
    .join('');
}

function renderConsensus(): void {
  const container = document.getElementById('vote-display');
  if (!container) return;

  container.innerHTML = consensus.votes
    .map(
      (vote) => `
    <div class="vote-icon ${vote.vote ? 'approve' : 'reject'}">
      ${vote.vote ? '✓' : '✗'}
    </div>
  `
    )
    .join('');
}

function renderMetrics(): void {
  const step = document.getElementById('metric-step');
  const loss = document.getElementById('metric-loss');
  const phase = document.getElementById('metric-phase');

  if (step) step.textContent = metrics.step.toString();
  if (loss) loss.textContent = metrics.loss.toFixed(4);
  if (phase) phase.textContent = metrics.phase;
}

function updateConnectionStatus(connected: boolean): void {
  const badge = document.getElementById('connection-status');
  if (!badge) return;

  if (connected) {
    badge.className = 'status-badge connected';
    badge.innerHTML = '<span>🟢</span><span>Connected</span>';
  } else {
    badge.className = 'status-badge disconnected';
    badge.innerHTML = '<span>🔴</span><span>Disconnected</span>';
  }
}

function showError(message: string): void {
  // TODO: Implement toast notification
  console.error('[Ralph UI] Error:', message);
}

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZATION
// ═══════════════════════════════════════════════════════════════════════════

function init(): void {
  console.log('[Ralph] Initializing...');

  // Initialize 7 empty agents
  for (let i = 1; i <= 7; i++) {
    agents.set(i, {
      id: i,
      name: `Agent ${i}`,
      score: 0,
      status: 'idle',
      message: '',
      vote: null,
      lastUpdate: Date.now(),
    });
  }

  // Render initial state
  renderAgents();
  renderConsensus();
  renderMetrics();

  // Connect to WebSocket
  wsClient.connect();
  
  // 111/100 POLISH: Auto-detect and add AI tooltips
  setTimeout(() => {
    tooltips.autoDetectAndAddTooltips();
  }, 1000);

  console.log('[Ralph] Initialized');
}

// Start on DOM ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}

// Cleanup on unload
window.addEventListener('beforeunload', () => {
  wsClient.disconnect();
});
