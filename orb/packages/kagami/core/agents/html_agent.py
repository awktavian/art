"""HTML Agent — Cognitive Substrate for Distributed Intelligence.

HTML files as agentic cognitive units that:
1. Connect to Kagami ecosystem via mDNS/WebSocket
2. Participate in Byzantine consensus for distributed cognition
3. Serve as high-craft visual objects for humans
4. Influence and receive influence from the organism's cognition

Architecture:
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HTML AGENT COGNITIVE SUBSTRATE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐        │
│   │  Human Reader   │    │   HTML Agent    │    │ Kagami Backend  │        │
│   │                 │    │                 │    │                 │        │
│   │  Visual craft   │◄──►│  #de_memo       │◄──►│  PBFT Consensus │        │
│   │  Narrative      │    │  Cognitive      │    │  Quantum-safe   │        │
│   │  Understanding  │    │  Substrate      │    │  State sync     │        │
│   └─────────────────┘    └────────┬────────┘    └─────────────────┘        │
│                                   │                                         │
│                                   ▼                                         │
│   ┌─────────────────────────────────────────────────────────────────────┐  │
│   │                    BYZANTINE CONSENSUS LAYER                         │  │
│   │                                                                      │  │
│   │   Agent A ◄────────► Agent B ◄────────► Agent C                     │  │
│   │     │                   │                   │                        │  │
│   │     └───────────────────┴───────────────────┘                        │  │
│   │                         │                                            │  │
│   │                    CONSENSUS                                         │  │
│   │                         │                                            │  │
│   │                    TRUTH ──► Organism State                          │  │
│   │                                                                      │  │
│   └─────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

#de_memo Pattern:
- Each HTML file is a de-memorized cognitive unit
- Contains both human-readable content AND executable agent code
- Participates in consensus through embedded JavaScript
- Influences organism cognition through state updates
- Receives organism state through WebSocket subscriptions

Colony: Nexus (A₅) — Connection and integration
h(x) ≥ 0. Always.

Created: January 2026
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# =============================================================================
# Agent Types
# =============================================================================


class AgentType(Enum):
    """Types of HTML agents."""

    OBSERVER = auto()  # Read-only, subscribes to state
    PARTICIPANT = auto()  # Can propose state changes
    VALIDATOR = auto()  # Participates in consensus
    ORCHESTRATOR = auto()  # Coordinates other agents


class AgentState(Enum):
    """Agent lifecycle states."""

    DORMANT = auto()  # Not connected
    CONNECTING = auto()  # Establishing connection
    ACTIVE = auto()  # Connected and participating
    VOTING = auto()  # In consensus round
    SUSPENDED = auto()  # Temporarily inactive


# =============================================================================
# Configuration
# =============================================================================


@dataclass
class HTMLAgentConfig:
    """HTML agent configuration.

    Attributes:
        agent_id: Unique agent identifier (UUID).
        agent_type: Type of agent.
        colony: Colony affiliation (spark, forge, flow, nexus, beacon, grove, crystal).
        display_name: Human-readable name.
        description: Agent purpose description.
        backend_url: Kagami backend WebSocket URL.
        consensus_weight: Weight in consensus (0.0-1.0).
        auto_connect: Connect on page load.
        heartbeat_interval: Heartbeat interval (seconds).
        reconnect_delay: Delay before reconnection (seconds).
        voice_stability: ElevenLabs stability parameter (0.0-1.0).
        voice_similarity_boost: ElevenLabs similarity boost (0.0-1.0).
        voice_style: ElevenLabs style parameter (0.0-1.0).
        voice_speed: ElevenLabs speed multiplier (0.5-2.0).
        personality_prompt: Voice personality/system prompt for TTS.
    """

    agent_id: str = ""
    agent_type: AgentType = AgentType.OBSERVER
    colony: str = "nexus"  # Default to nexus (integration hub)
    display_name: str = "HTML Agent"
    description: str = ""
    backend_url: str = "ws://localhost:8000/ws/agent"
    consensus_weight: float = 1.0
    auto_connect: bool = True
    heartbeat_interval: float = 30.0
    reconnect_delay: float = 5.0
    # Voice settings (ElevenLabs parameters per colony)
    voice_stability: float = 0.45
    voice_similarity_boost: float = 0.78
    voice_style: float = 0.32
    voice_speed: float = 1.0
    personality_prompt: str = ""

    def __post_init__(self) -> None:
        """Generate agent ID if not provided."""
        if not self.agent_id:
            self.agent_id = str(uuid.uuid4())


@dataclass
class AgentMessage:
    """Message between agents or to backend."""

    type: str
    agent_id: str
    timestamp: float
    payload: dict[str, Any]
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.type,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "payload": self.payload,
            "signature": self.signature,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentMessage:
        """Deserialize from dictionary."""
        return cls(
            type=data["type"],
            agent_id=data["agent_id"],
            timestamp=data["timestamp"],
            payload=data.get("payload", {}),
            signature=data.get("signature", ""),
        )


# =============================================================================
# HTML Agent Template
# =============================================================================


HTML_AGENT_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-agent-id="{agent_id}" data-agent-type="{agent_type}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="kagami-agent" content="{agent_id}">
    <meta name="kagami-type" content="{agent_type}">
    <meta name="kagami-colony" content="{colony}">
    <meta name="kagami-weight" content="{consensus_weight}">

    <!-- Voice Configuration (ElevenLabs) -->
    <meta name="kagami:voice:stability" content="{voice_stability}">
    <meta name="kagami:voice:similarity_boost" content="{voice_similarity_boost}">
    <meta name="kagami:voice:style" content="{voice_style}">
    <meta name="kagami:voice:speed" content="{voice_speed}">
    <meta name="kagami:personality" content="{personality_prompt}">

    <title>{display_name}</title>

    <!-- Colony Favicon -->
    <link rel="icon" type="image/png" sizes="16x16" href="/_sdk/favicons/{colony}-16.png">
    <link rel="icon" type="image/png" sizes="32x32" href="/_sdk/favicons/{colony}-32.png">
    <link rel="icon" type="image/png" sizes="48x48" href="/_sdk/favicons/{colony}-48.png">
    <link rel="apple-touch-icon" sizes="180x180" href="/_sdk/favicons/{colony}-180.png">

    <!-- Agent Configuration -->
    <script type="application/json" id="agent-config">
    {config_json}
    </script>

    <!-- Kagami Agent Runtime -->
    <script type="module">
    /**
     * #de_memo — Cognitive Agent Runtime
     *
     * This agent participates in Kagami's distributed cognition through:
     * 1. Permission-gated WebSocket connection (audio enabled = WebSocket)
     * 2. HTTP polling fallback (audio disabled = 30s polling)
     * 3. Byzantine consensus participation
     * 4. State synchronization
     * 5. Voice integration via ElevenLabs
     *
     * localStorage Keys:
     * - kagami:audio:enabled - Gate WebSocket connection
     * - kagami:video:enabled - Enable video features
     */

    // localStorage keys for domain-level persistence
    const STORAGE_KEYS = {{
        AUDIO_ENABLED: 'kagami:audio:enabled',
        VIDEO_ENABLED: 'kagami:video:enabled',
        AUDIO_VOLUME: 'kagami:audio:volume',
        VOICE_COLONY: 'kagami:voice:colony'
    }};

    class KagamiAgent {{
        constructor(config) {{
            this.config = config;
            this.state = 'dormant';
            this.ws = null;
            this.reconnectTimer = null;
            this.heartbeatTimer = null;
            this.pollInterval = null;
            this.localState = {{}};
            this.consensusRound = 0;
            this.votes = {{}};

            // Permission state from localStorage
            this.audioEnabled = localStorage.getItem(STORAGE_KEYS.AUDIO_ENABLED) === 'true';
            this.videoEnabled = localStorage.getItem(STORAGE_KEYS.VIDEO_ENABLED) === 'true';
            this.connectionMode = this.audioEnabled ? 'websocket' : 'polling';

            // Bind methods
            this.connect = this.connect.bind(this);
            this.disconnect = this.disconnect.bind(this);
            this.sendMessage = this.sendMessage.bind(this);
            this.handleMessage = this.handleMessage.bind(this);

            // Auto-connect if configured
            if (config.auto_connect) {{
                this.connect();
            }}

            // Listen for permission changes
            window.addEventListener('storage', (e) => {{
                if (e.key === STORAGE_KEYS.AUDIO_ENABLED) {{
                    this.audioEnabled = e.newValue === 'true';
                    this.handlePermissionChange();
                }}
            }});

            // Expose to window for debugging
            window.kagamiAgent = this;
        }}

        handlePermissionChange() {{
            if (this.audioEnabled) {{
                // Switch from polling to WebSocket
                this.stopPolling();
                this.connectionMode = 'websocket';
                this.connectWebSocket();
            }} else {{
                // Switch from WebSocket to polling
                this.disconnectWebSocket();
                this.connectionMode = 'polling';
                this.startPolling();
            }}
            this.dispatchStateChange();
        }}

        async connect() {{
            if (this.state === 'active' || this.state === 'connecting') {{
                return;
            }}

            // Permission-gated connection
            if (this.audioEnabled) {{
                await this.connectWebSocket();
            }} else {{
                this.startPolling();
            }}
        }}

        async connectWebSocket() {{
            if (!this.audioEnabled) {{
                console.log('Audio not enabled, using polling mode');
                this.startPolling();
                return;
            }}

            this.state = 'connecting';
            this.dispatchStateChange();

            try {{
                // Discover backend via mDNS or fallback to configured URL
                const backendUrl = await this.discoverBackend();

                this.ws = new WebSocket(backendUrl);

                this.ws.onopen = () => {{
                    this.state = 'active';
                    this.connectionMode = 'websocket';
                    this.dispatchStateChange();

                    // Send registration with voice settings
                    this.sendMessage({{
                        type: 'agent.register',
                        payload: {{
                            agent_id: this.config.agent_id,
                            agent_type: this.config.agent_type,
                            display_name: this.config.display_name,
                            consensus_weight: this.config.consensus_weight,
                            capabilities: this.getCapabilities(),
                            voice_settings: {{
                                stability: this.config.voice_stability,
                                similarity_boost: this.config.voice_similarity_boost,
                                style: this.config.voice_style,
                                speed: this.config.voice_speed,
                            }},
                            personality_prompt: this.config.personality_prompt,
                        }}
                    }});

                    // Start heartbeat
                    this.startHeartbeat();

                    console.log(`🔗 Agent ${{this.config.agent_id}} connected via WebSocket`);
                }};

                this.ws.onmessage = (event) => {{
                    try {{
                        const message = JSON.parse(event.data);
                        this.handleMessage(message);
                    }} catch (e) {{
                        console.error('Failed to parse message:', e);
                    }}
                }};

                this.ws.onclose = () => {{
                    this.state = 'dormant';
                    this.dispatchStateChange();
                    this.stopHeartbeat();

                    // Only reconnect if audio still enabled
                    if (this.audioEnabled) {{
                        this.scheduleReconnect();
                    }}
                    console.log(`🔌 Agent ${{this.config.agent_id}} disconnected`);
                }};

                this.ws.onerror = (error) => {{
                    console.error('WebSocket error:', error);
                }};

            }} catch (error) {{
                console.error('Connection failed:', error);
                this.state = 'dormant';
                if (this.audioEnabled) {{
                    this.scheduleReconnect();
                }} else {{
                    this.startPolling();
                }}
            }}
        }}

        disconnectWebSocket() {{
            if (this.ws) {{
                this.ws.close();
                this.ws = null;
            }}
            this.stopHeartbeat();
            if (this.reconnectTimer) {{
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }}
        }}

        startPolling() {{
            if (this.pollInterval) return; // Already polling

            this.state = 'active';
            this.connectionMode = 'polling';
            this.dispatchStateChange();

            console.log(`📡 Agent ${{this.config.agent_id}} using HTTP polling (30s interval)`);

            // Immediate fetch
            this.fetchSnapshot();

            // Poll every 30 seconds
            this.pollInterval = setInterval(() => this.fetchSnapshot(), 30000);
        }}

        stopPolling() {{
            if (this.pollInterval) {{
                clearInterval(this.pollInterval);
                this.pollInterval = null;
            }}
        }}

        async fetchSnapshot() {{
            try {{
                const response = await fetch('/api/v1/agents/state');
                if (response.ok) {{
                    const data = await response.json();
                    this.handleStateUpdate({{ payload: data }});
                }}
            }} catch (error) {{
                console.warn('Polling failed, will retry:', error);
            }}
        }}

        async discoverBackend() {{
            // Try mDNS discovery first (via service worker or fetch)
            try {{
                const response = await fetch('/.well-known/kagami-backend');
                if (response.ok) {{
                    const data = await response.json();
                    return data.websocket_url;
                }}
            }} catch (e) {{
                // mDNS discovery failed, use configured URL
            }}

            return this.config.backend_url;
        }}

        disconnect() {{
            this.disconnectWebSocket();
            this.stopPolling();
            this.state = 'dormant';
            this.dispatchStateChange();
        }}

        sendMessage(message) {{
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {{
                const fullMessage = {{
                    ...message,
                    agent_id: this.config.agent_id,
                    timestamp: Date.now() / 1000,
                }};
                this.ws.send(JSON.stringify(fullMessage));
            }}
        }}

        handleMessage(message) {{
            const handlers = {{
                'state.update': this.handleStateUpdate.bind(this),
                'consensus.propose': this.handleConsensusPropose.bind(this),
                'consensus.vote': this.handleConsensusVote.bind(this),
                'consensus.commit': this.handleConsensusCommit.bind(this),
                'agent.ping': this.handlePing.bind(this),
                'voice.speak': this.handleVoiceSpeak.bind(this),
            }};

            const handler = handlers[message.type];
            if (handler) {{
                handler(message);
            }} else {{
                // Dispatch custom event for application-specific handlers
                window.dispatchEvent(new CustomEvent('kagami-message', {{
                    detail: message
                }}));
            }}
        }}

        handleStateUpdate(message) {{
            this.localState = {{ ...this.localState, ...message.payload }};
            window.dispatchEvent(new CustomEvent('kagami-state', {{
                detail: this.localState
            }}));
        }}

        handleConsensusPropose(message) {{
            if (this.config.agent_type === 'OBSERVER') {{
                return; // Observers don't vote
            }}

            this.state = 'voting';
            this.dispatchStateChange();

            // Validate proposal and vote
            const vote = this.validateProposal(message.payload);

            this.sendMessage({{
                type: 'consensus.vote',
                payload: {{
                    round: message.payload.round,
                    proposal_hash: message.payload.hash,
                    vote: vote,
                    weight: this.config.consensus_weight,
                }}
            }});
        }}

        handleConsensusVote(message) {{
            const round = message.payload.round;
            if (!this.votes[round]) {{
                this.votes[round] = [];
            }}
            this.votes[round].push(message.payload);
        }}

        handleConsensusCommit(message) {{
            this.consensusRound = message.payload.round;
            this.localState = {{ ...this.localState, ...message.payload.state }};
            this.state = 'active';
            this.dispatchStateChange();

            window.dispatchEvent(new CustomEvent('kagami-consensus', {{
                detail: message.payload
            }}));
        }}

        handlePing(message) {{
            this.sendMessage({{
                type: 'agent.pong',
                payload: {{ ping_id: message.payload.ping_id }}
            }});
        }}

        handleVoiceSpeak(message) {{
            // Voice synthesis event - dispatch for external handling
            window.dispatchEvent(new CustomEvent('kagami-voice', {{
                detail: {{
                    text: message.payload.text,
                    voice_settings: {{
                        stability: this.config.voice_stability,
                        similarity_boost: this.config.voice_similarity_boost,
                        style: this.config.voice_style,
                        speed: this.config.voice_speed,
                    }},
                    personality: this.config.personality_prompt,
                }}
            }}));
        }}

        validateProposal(proposal) {{
            // Override in subclass for custom validation
            return true;
        }}

        proposeStateChange(key, value, reason) {{
            if (this.config.agent_type === 'OBSERVER') {{
                console.warn('Observers cannot propose state changes');
                return;
            }}

            this.sendMessage({{
                type: 'consensus.propose',
                payload: {{
                    key: key,
                    value: value,
                    reason: reason,
                    round: this.consensusRound + 1,
                }}
            }});
        }}

        getCapabilities() {{
            return {{
                consensus: this.config.agent_type !== 'OBSERVER',
                propose: ['PARTICIPANT', 'VALIDATOR', 'ORCHESTRATOR'].includes(this.config.agent_type),
                validate: ['VALIDATOR', 'ORCHESTRATOR'].includes(this.config.agent_type),
                orchestrate: this.config.agent_type === 'ORCHESTRATOR',
                voice: this.audioEnabled,
                video: this.videoEnabled,
            }};
        }}

        startHeartbeat() {{
            this.heartbeatTimer = setInterval(() => {{
                this.sendMessage({{
                    type: 'agent.heartbeat',
                    payload: {{
                        state: this.state,
                        consensus_round: this.consensusRound,
                        connection_mode: this.connectionMode,
                    }}
                }});
            }}, this.config.heartbeat_interval * 1000);
        }}

        stopHeartbeat() {{
            if (this.heartbeatTimer) {{
                clearInterval(this.heartbeatTimer);
                this.heartbeatTimer = null;
            }}
        }}

        scheduleReconnect() {{
            if (this.reconnectTimer) return;

            this.reconnectTimer = setTimeout(() => {{
                this.reconnectTimer = null;
                this.connect();
            }}, this.config.reconnect_delay * 1000);
        }}

        dispatchStateChange() {{
            window.dispatchEvent(new CustomEvent('kagami-agent-state', {{
                detail: {{
                    state: this.state,
                    agent_id: this.config.agent_id,
                    connection_mode: this.connectionMode,
                    audio_enabled: this.audioEnabled,
                    video_enabled: this.videoEnabled,
                }}
            }}));
        }}

        // Permission methods

        async requestAudioPermission() {{
            // Dispatch event for UI to show permission dialog
            return new Promise((resolve) => {{
                window.dispatchEvent(new CustomEvent('kagami-permission-request', {{
                    detail: {{ type: 'audio', resolve }}
                }}));
            }});
        }}

        setAudioEnabled(enabled) {{
            localStorage.setItem(STORAGE_KEYS.AUDIO_ENABLED, enabled ? 'true' : 'false');
            this.audioEnabled = enabled;
            this.handlePermissionChange();
        }}

        setVideoEnabled(enabled) {{
            localStorage.setItem(STORAGE_KEYS.VIDEO_ENABLED, enabled ? 'true' : 'false');
            this.videoEnabled = enabled;
            this.dispatchStateChange();
        }}

        // Cognitive influence methods

        async influence(target, influence_type, data) {{
            /**
             * Propagate cognitive influence to organism or other agents.
             * This is how HTML agents affect Kagami's decision-making.
             */
            this.sendMessage({{
                type: 'cognitive.influence',
                payload: {{
                    target: target,
                    influence_type: influence_type,
                    data: data,
                    source_weight: this.config.consensus_weight,
                }}
            }});
        }}

        async perceive(query) {{
            /**
             * Request perception from organism.
             * HTML agents can query the organism's sensory state.
             */
            return new Promise((resolve, reject) => {{
                const query_id = crypto.randomUUID();

                const handler = (event) => {{
                    if (event.detail.query_id === query_id) {{
                        window.removeEventListener('kagami-perception', handler);
                        resolve(event.detail.result);
                    }}
                }};

                window.addEventListener('kagami-perception', handler);

                this.sendMessage({{
                    type: 'cognitive.perceive',
                    payload: {{
                        query_id: query_id,
                        query: query,
                    }}
                }});

                // Timeout
                setTimeout(() => {{
                    window.removeEventListener('kagami-perception', handler);
                    reject(new Error('Perception query timeout'));
                }}, 10000);
            }});
        }}
    }}

    // Initialize agent from embedded config
    const configElement = document.getElementById('agent-config');
    const config = JSON.parse(configElement.textContent);
    const agent = new KagamiAgent(config);

    // Export for use in page scripts
    window.KagamiAgent = KagamiAgent;
    window.KAGAMI_STORAGE_KEYS = STORAGE_KEYS;
    </script>

    <style>
    {custom_css}
    </style>
</head>
<body>
    {content}

    <!-- Agent Status Indicator -->
    <div id="kagami-agent-status" style="position: fixed; bottom: 8px; right: 8px; font-size: 10px; opacity: 0.5;">
        <span id="agent-state-indicator">●</span>
        <span id="agent-id">{agent_id_short}</span>
    </div>

    <script>
    // Update status indicator
    window.addEventListener('kagami-agent-state', (event) => {{
        const indicator = document.getElementById('agent-state-indicator');
        const colors = {{
            'dormant': '#666',
            'connecting': '#f90',
            'active': '#0f0',
            'voting': '#0ff',
            'suspended': '#f00',
        }};
        indicator.style.color = colors[event.detail.state] || '#666';
    }});
    </script>
</body>
</html>"""


# =============================================================================
# Agent Generator
# =============================================================================


class HTMLAgentGenerator:
    """Generates HTML agent files.

    Example:
        >>> generator = HTMLAgentGenerator()
        >>> agent_html = generator.generate(
        ...     config=HTMLAgentConfig(
        ...         display_name="Dashboard Agent",
        ...         agent_type=AgentType.VALIDATOR,
        ...     ),
        ...     content="<h1>Dashboard</h1>",
        ...     css=".dashboard { color: navy; }",
        ... )
        >>> Path("dashboard.html").write_text(agent_html)
    """

    def generate(
        self,
        config: HTMLAgentConfig,
        content: str = "",
        css: str = "",
    ) -> str:
        """Generate HTML agent file.

        Args:
            config: Agent configuration.
            content: HTML content for body.
            css: Custom CSS styles.

        Returns:
            Complete HTML agent file.
        """
        config_dict = {
            "agent_id": config.agent_id,
            "agent_type": config.agent_type.name,
            "colony": config.colony,
            "display_name": config.display_name,
            "description": config.description,
            "backend_url": config.backend_url,
            "consensus_weight": config.consensus_weight,
            "auto_connect": config.auto_connect,
            "heartbeat_interval": config.heartbeat_interval,
            "reconnect_delay": config.reconnect_delay,
            # Voice settings
            "voice_stability": config.voice_stability,
            "voice_similarity_boost": config.voice_similarity_boost,
            "voice_style": config.voice_style,
            "voice_speed": config.voice_speed,
            "personality_prompt": config.personality_prompt,
        }

        return HTML_AGENT_TEMPLATE.format(
            agent_id=config.agent_id,
            agent_type=config.agent_type.name,
            colony=config.colony,
            display_name=config.display_name,
            consensus_weight=config.consensus_weight,
            voice_stability=config.voice_stability,
            voice_similarity_boost=config.voice_similarity_boost,
            voice_style=config.voice_style,
            voice_speed=config.voice_speed,
            personality_prompt=config.personality_prompt,
            config_json=json.dumps(config_dict, indent=2),
            custom_css=css or self._default_css(),
            content=content or self._default_content(config),
            agent_id_short=config.agent_id[:8],
        )

    def _default_css(self) -> str:
        """Default CSS for agents."""
        return """
        :root {
            --kagami-primary: #1a1a2e;
            --kagami-secondary: #16213e;
            --kagami-accent: #0f3460;
            --kagami-highlight: #e94560;
            --kagami-text: #eee;
            --kagami-muted: #888;
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'IBM Plex Sans', -apple-system, sans-serif;
            background: var(--kagami-primary);
            color: var(--kagami-text);
            min-height: 100vh;
            line-height: 1.6;
        }

        #kagami-agent-status {
            font-family: 'IBM Plex Mono', monospace;
            background: rgba(0,0,0,0.3);
            padding: 4px 8px;
            border-radius: 4px;
        }
        """

    def _default_content(self, config: HTMLAgentConfig) -> str:
        """Default content for agents."""
        return f"""
        <main style="padding: 2rem; max-width: 800px; margin: 0 auto;">
            <h1 style="font-size: 2rem; margin-bottom: 1rem;">{config.display_name}</h1>
            <p style="color: var(--kagami-muted);">{config.description or "Kagami HTML Agent"}</p>

            <div id="agent-content" style="margin-top: 2rem;">
                <!-- Agent-specific content goes here -->
            </div>
        </main>
        """

    def generate_to_file(
        self,
        path: Path | str,
        config: HTMLAgentConfig,
        content: str = "",
        css: str = "",
    ) -> Path:
        """Generate and write HTML agent file.

        Args:
            path: Output file path.
            config: Agent configuration.
            content: HTML content.
            css: Custom CSS.

        Returns:
            Path to generated file.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        html = self.generate(config, content, css)
        path.write_text(html)

        logger.info(f"Generated HTML agent: {path}")
        return path


# =============================================================================
# Agent Registry
# =============================================================================


class HTMLAgentRegistry:
    """Registry of HTML agents in the filesystem.

    Tracks which HTML files are agents and their configurations.
    """

    def __init__(self, base_path: Path | str) -> None:
        self.base_path = Path(base_path)
        self._agents: dict[str, HTMLAgentConfig] = {}
        self._load_registry()

    def _load_registry(self) -> None:
        """Load agent registry from filesystem."""
        registry_path = self.base_path / ".kagami-agents.json"
        if registry_path.exists():
            data = json.loads(registry_path.read_text())
            for agent_id, config_dict in data.items():
                config_dict["agent_type"] = AgentType[config_dict["agent_type"]]
                self._agents[agent_id] = HTMLAgentConfig(**config_dict)

    def _save_registry(self) -> None:
        """Save agent registry to filesystem."""
        registry_path = self.base_path / ".kagami-agents.json"
        data = {}
        for agent_id, config in self._agents.items():
            config_dict = {
                "agent_id": config.agent_id,
                "agent_type": config.agent_type.name,
                "colony": config.colony,
                "display_name": config.display_name,
                "description": config.description,
                "backend_url": config.backend_url,
                "consensus_weight": config.consensus_weight,
                "auto_connect": config.auto_connect,
                "heartbeat_interval": config.heartbeat_interval,
                "reconnect_delay": config.reconnect_delay,
                # Voice settings
                "voice_stability": config.voice_stability,
                "voice_similarity_boost": config.voice_similarity_boost,
                "voice_style": config.voice_style,
                "voice_speed": config.voice_speed,
                "personality_prompt": config.personality_prompt,
            }
            data[agent_id] = config_dict
        registry_path.write_text(json.dumps(data, indent=2))

    def register(self, config: HTMLAgentConfig, path: Path | str) -> None:
        """Register an HTML agent.

        Args:
            config: Agent configuration.
            path: Path to the HTML agent file (stored for reference).
        """
        _ = path  # Path stored for future features (e.g., file watching)
        self._agents[config.agent_id] = config
        self._save_registry()

    def unregister(self, agent_id: str) -> None:
        """Unregister an HTML agent."""
        if agent_id in self._agents:
            del self._agents[agent_id]
            self._save_registry()

    def get(self, agent_id: str) -> HTMLAgentConfig | None:
        """Get agent configuration."""
        return self._agents.get(agent_id)

    def list_agents(self) -> list[HTMLAgentConfig]:
        """List all registered agents."""
        return list(self._agents.values())

    def find_agents_by_type(self, agent_type: AgentType) -> list[HTMLAgentConfig]:
        """Find agents by type."""
        return [c for c in self._agents.values() if c.agent_type == agent_type]


# =============================================================================
# Factory Functions
# =============================================================================


_generator: HTMLAgentGenerator | None = None
_registry: HTMLAgentRegistry | None = None


def get_agent_generator() -> HTMLAgentGenerator:
    """Get the singleton agent generator."""
    global _generator
    if _generator is None:
        _generator = HTMLAgentGenerator()
    return _generator


def get_agent_registry(base_path: Path | str | None = None) -> HTMLAgentRegistry:
    """Get the agent registry."""
    global _registry
    if _registry is None:
        path = base_path or Path.home() / ".kagami" / "agents"
        _registry = HTMLAgentRegistry(path)
    return _registry


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "AgentMessage",
    "AgentState",
    "AgentType",
    "HTMLAgentConfig",
    "HTMLAgentGenerator",
    "HTMLAgentRegistry",
    "get_agent_generator",
    "get_agent_registry",
]
