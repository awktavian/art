"""Agent HTML Renderer — Generate HTML from agent schema.

This module renders markdown agents to HTML:
- Applies i_embody visual configuration
- Renders i_structure content blocks
- Injects i_react real-time scripts
- Adds i_hide secret triggers
- Personalizes with i_perceive profiles

Colony: Forge (e2) — Building
Created: January 7, 2026
鏡
"""

from __future__ import annotations

import html
import json
import logging

import markdown

from kagami.core.agents.schema import (
    AgentSchema,
    ContentBlock,
)

logger = logging.getLogger(__name__)


# =============================================================================
# HTML Template
# =============================================================================


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-agent-id="{agent_id}" data-craft-level="{craft_level}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="kagami-agent" content="{agent_id}">
    <meta name="kagami-colony" content="{colony}">
    <title>{title}</title>

    <!-- Design System -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">

    <style>
{css}
    </style>
</head>
<body>
{body}

    <!-- Agent Runtime -->
    <script type="module">
{runtime_js}
    </script>

    <!-- Secrets -->
    <script>
{secrets_js}
    </script>
</body>
</html>"""


# =============================================================================
# CSS Generation
# =============================================================================


def generate_css(schema: AgentSchema) -> str:
    """Generate CSS from agent's i_embody configuration.

    Args:
        schema: Agent schema.

    Returns:
        CSS string.
    """
    palette = schema.i_embody.palette
    motion = schema.i_embody.motion
    typography = schema.i_embody.typography

    css = f"""
:root {{
    /* Palette */
    --color-primary: {palette.primary};
    --color-secondary: {palette.secondary};
    --color-accent: {palette.accent};
    --color-background: {palette.background};
    --color-text: {palette.text};
    --color-muted: {palette.muted};
    --color-success: {palette.success};
    --color-warning: {palette.warning};
    --color-error: {palette.error};

    /* Motion */
    --motion-fast: {motion.get("fast", 150)}ms;
    --motion-normal: {motion.get("normal", 233)}ms;
    --motion-slow: {motion.get("slow", 377)}ms;
    --motion-slower: {motion.get("slower", 610)}ms;

    /* Typography */
    --font-body: '{typography.get("body", "IBM Plex Sans")}', -apple-system, sans-serif;
    --font-mono: '{typography.get("mono", "IBM Plex Mono")}', monospace;
    --font-heading: '{typography.get("heading", "IBM Plex Sans")}', -apple-system, sans-serif;

    /* Spacing */
    --space-xs: 4px;
    --space-sm: 8px;
    --space-md: 16px;
    --space-lg: 24px;
    --space-xl: 32px;
    --space-2xl: 48px;
    --space-3xl: 64px;

    /* Audio Reactive */
    --audio-bass: 0;
    --audio-mid: 0;
    --audio-high: 0;
}}

* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

html {{
    scroll-behavior: smooth;
}}

body {{
    font-family: var(--font-body);
    font-size: 16px;
    line-height: 1.6;
    color: var(--color-text);
    background: var(--color-background);
    min-height: 100vh;
}}

h1, h2, h3, h4, h5, h6 {{
    font-family: var(--font-heading);
    font-weight: 600;
    line-height: 1.2;
    margin-bottom: var(--space-md);
}}

h1 {{ font-size: 2.5rem; }}
h2 {{ font-size: 2rem; }}
h3 {{ font-size: 1.5rem; }}
h4 {{ font-size: 1.25rem; }}

p {{
    margin-bottom: var(--space-md);
}}

a {{
    color: var(--color-accent);
    text-decoration: none;
    transition: color var(--motion-fast);
}}

a:hover {{
    color: var(--color-text);
}}

code {{
    font-family: var(--font-mono);
    background: var(--color-secondary);
    padding: 2px 6px;
    border-radius: 4px;
}}

pre {{
    font-family: var(--font-mono);
    background: var(--color-secondary);
    padding: var(--space-md);
    border-radius: 8px;
    overflow-x: auto;
    margin-bottom: var(--space-md);
}}

/* Layout */
.container {{
    max-width: 1200px;
    margin: 0 auto;
    padding: var(--space-lg);
}}

.section {{
    padding: var(--space-3xl) 0;
}}

/* Components */
.hero {{
    min-height: 60vh;
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: var(--space-3xl);
}}

.hero h1 {{
    font-size: 3.5rem;
    margin-bottom: var(--space-lg);
}}

.hero p {{
    font-size: 1.25rem;
    color: var(--color-muted);
    max-width: 600px;
}}

.cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: var(--space-lg);
}}

.card {{
    background: var(--color-secondary);
    border-radius: 12px;
    padding: var(--space-lg);
    transition: transform var(--motion-fast), box-shadow var(--motion-fast);
}}

.card:hover {{
    transform: translateY(-4px);
    box-shadow: 0 12px 40px rgba(0,0,0,0.3);
}}

.card h3 {{
    margin-bottom: var(--space-sm);
}}

.card p {{
    color: var(--color-muted);
    margin-bottom: 0;
}}

/* Audio Reactive */
.audio-reactive {{
    transition: all var(--motion-fast);
}}

.audio-reactive.bass {{
    transform: scale(calc(1 + var(--audio-bass) * 0.1));
}}

.audio-reactive.mid {{
    filter: brightness(calc(1 + var(--audio-mid) * 0.3));
}}

.audio-reactive.high {{
    opacity: calc(0.7 + var(--audio-high) * 0.3);
}}
"""

    # Add custom cursor if enabled
    cursor = schema.i_embody.cursor
    if cursor.enabled:
        css += f"""
/* Custom Cursor */
body {{
    cursor: none;
}}

.custom-cursor {{
    position: fixed;
    pointer-events: none;
    z-index: 9999;
    width: {cursor.size}px;
    height: {cursor.size}px;
    border-radius: 50%;
    background: {cursor.color};
    transform: translate(-50%, -50%);
    transition: transform var(--motion-fast);
    mix-blend-mode: difference;
}}

.custom-cursor.glow {{
    box-shadow: 0 0 20px {cursor.color};
}}
"""

    # Add particles if enabled
    particles = schema.i_embody.particles
    if particles.enabled:
        css += """
/* Particles */
#particles-canvas {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 0;
}

.content {
    position: relative;
    z-index: 1;
}
"""

    return css


# =============================================================================
# Content Rendering
# =============================================================================


def render_content(schema: AgentSchema, user_profile: str | None = None) -> str:
    """Render content from i_structure blocks.

    Args:
        schema: Agent schema.
        user_profile: Optional user profile for personalization.

    Returns:
        HTML content string.
    """
    parts = []

    # Add particles canvas if enabled
    if schema.i_embody.particles.enabled:
        parts.append('<canvas id="particles-canvas"></canvas>')

    parts.append('<div class="content">')

    # Render structure blocks
    for block in schema.i_structure.blocks:
        parts.append(render_block(block, schema, user_profile))

    # Render markdown content
    if schema.content:
        md = markdown.Markdown(extensions=["fenced_code", "tables", "toc"])
        html_content = md.convert(schema.content)
        parts.append(f'<div class="container markdown-content">{html_content}</div>')

    parts.append("</div>")

    # Add custom cursor if enabled
    if schema.i_embody.cursor.enabled:
        glow_class = "glow" if schema.i_embody.cursor.glow else ""
        parts.append(f'<div class="custom-cursor {glow_class}" id="cursor"></div>')

    return "\n".join(parts)


def render_block(block: ContentBlock, schema: AgentSchema, user_profile: str | None = None) -> str:
    """Render a single content block.

    Args:
        block: Content block to render.
        schema: Agent schema for context.
        user_profile: Optional user profile.

    Returns:
        HTML string for the block.
    """
    content = block.content
    block_id = f'id="{block.id}"' if block.id else ""

    if block.type == "hero":
        title = html.escape(content.get("title", schema.i_am.name))
        subtitle = html.escape(content.get("subtitle", schema.i_am.essence))
        return f"""
<section class="hero" {block_id}>
    <div class="container">
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
</section>
"""

    elif block.type == "section":
        title = html.escape(content.get("title", ""))
        body = content.get("body", "")
        if isinstance(body, str):
            body = html.escape(body)
        return f"""
<section class="section" {block_id}>
    <div class="container">
        <h2>{title}</h2>
        <p>{body}</p>
    </div>
</section>
"""

    elif block.type == "cards":
        title = html.escape(content.get("title", ""))
        items = content.get("items", [])

        cards_html = ""
        for item in items:
            card_title = html.escape(item.get("title", ""))
            card_body = html.escape(item.get("body", ""))
            icon = item.get("icon", "")
            icon_html = f'<div class="card-icon">{icon}</div>' if icon else ""

            cards_html += f"""
        <div class="card">
            {icon_html}
            <h3>{card_title}</h3>
            <p>{card_body}</p>
        </div>
"""

        return f"""
<section class="section" {block_id}>
    <div class="container">
        <h2>{title}</h2>
        <div class="cards">
{cards_html}
        </div>
    </div>
</section>
"""

    elif block.type == "code":
        language = content.get("language", "")
        code = html.escape(content.get("code", ""))
        return f"""
<section class="section" {block_id}>
    <div class="container">
        <pre><code class="language-{language}">{code}</code></pre>
    </div>
</section>
"""

    elif block.type == "custom":
        # Raw HTML block - SECURITY WARNING: This is trusted content only
        # Only allow custom HTML in high-trust environments
        raw_html = content.get("html", "")
        # Strip dangerous patterns even in custom blocks
        import re

        dangerous_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
        ]
        sanitized = raw_html
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE | re.DOTALL)
        return sanitized

    else:
        # Unknown block type, render children
        children_html = "\n".join(
            render_block(child, schema, user_profile) for child in block.children
        )
        return f'<div class="block-{block.type}" {block_id}>{children_html}</div>'


# =============================================================================
# Runtime JavaScript
# =============================================================================


def generate_runtime_js(schema: AgentSchema) -> str:
    """Generate runtime JavaScript for the agent.

    Includes:
    - WebSocket connection to agent API
    - Audio reactivity handlers
    - Custom cursor tracking
    - Particle system
    - Scroll tracking
    - Keyboard shortcuts

    Args:
        schema: Agent schema.

    Returns:
        JavaScript code string.
    """
    agent_id = schema.i_am.id
    config_json = json.dumps(
        {
            "agent_id": agent_id,
            "audio": schema.i_react.audio.model_dump(),
            "cursor": schema.i_embody.cursor.model_dump(),
            "particles": schema.i_embody.particles.model_dump(),
            "scroll": schema.i_react.scroll,
            "keyboard": schema.i_react.keyboard,
        }
    )

    js = f"""
const AGENT_CONFIG = {config_json};
const AGENT_ID = '{agent_id}';

// WebSocket connection
let ws;
function connectWebSocket() {{
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${{protocol}}//${{location.host}}/v1/ws/agent/${{AGENT_ID}}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {{
        console.log('🔗 Agent connected');
        ws.send(JSON.stringify({{ type: 'subscribe', events: ['*'] }}));
    }};

    ws.onmessage = (event) => {{
        const data = JSON.parse(event.data);
        handleAgentMessage(data);
    }};

    ws.onclose = () => {{
        console.log('🔌 Agent disconnected, reconnecting...');
        setTimeout(connectWebSocket, 3000);
    }};
}}

function handleAgentMessage(data) {{
    switch (data.type) {{
        case 'audio_reactive':
            updateAudioReactive(data.css_variables);
            break;
        case 'state':
            console.log('State update:', data);
            break;
        case 'secret_found':
            console.log('🎉 Secret found:', data.secret_id);
            break;
    }}
}}

// Audio Reactivity
function updateAudioReactive(vars) {{
    const root = document.documentElement;
    for (const [name, value] of Object.entries(vars)) {{
        root.style.setProperty(name, value);
    }}
}}

// Custom Cursor
if (AGENT_CONFIG.cursor?.enabled) {{
    const cursor = document.getElementById('cursor');
    if (cursor) {{
        document.addEventListener('mousemove', (e) => {{
            cursor.style.left = e.clientX + 'px';
            cursor.style.top = e.clientY + 'px';
        }});
    }}
}}

// Particles
if (AGENT_CONFIG.particles?.enabled) {{
    const canvas = document.getElementById('particles-canvas');
    if (canvas) {{
        const ctx = canvas.getContext('2d');
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;

        const particles = [];
        const count = AGENT_CONFIG.particles.count || 50;

        for (let i = 0; i < count; i++) {{
            particles.push({{
                x: Math.random() * canvas.width,
                y: Math.random() * canvas.height,
                vx: (Math.random() - 0.5) * AGENT_CONFIG.particles.speed,
                vy: (Math.random() - 0.5) * AGENT_CONFIG.particles.speed,
                size: Math.random() * 3 + 1,
            }});
        }}

        function animateParticles() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = getComputedStyle(document.documentElement)
                .getPropertyValue('--color-accent');

            for (const p of particles) {{
                p.x += p.vx;
                p.y += p.vy;

                if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

                ctx.beginPath();
                ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                ctx.fill();
            }}

            if (AGENT_CONFIG.particles.connections) {{
                ctx.strokeStyle = getComputedStyle(document.documentElement)
                    .getPropertyValue('--color-accent') + '40';
                for (let i = 0; i < particles.length; i++) {{
                    for (let j = i + 1; j < particles.length; j++) {{
                        const dx = particles[i].x - particles[j].x;
                        const dy = particles[i].y - particles[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist < 100) {{
                            ctx.beginPath();
                            ctx.moveTo(particles[i].x, particles[i].y);
                            ctx.lineTo(particles[j].x, particles[j].y);
                            ctx.stroke();
                        }}
                    }}
                }}
            }}

            requestAnimationFrame(animateParticles);
        }}

        animateParticles();

        window.addEventListener('resize', () => {{
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }});
    }}
}}

// Scroll Tracking
if (AGENT_CONFIG.scroll?.progress_bar) {{
    const progressBar = document.createElement('div');
    progressBar.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        height: 3px;
        background: var(--color-accent);
        z-index: 9999;
        transition: width 0.1s;
    `;
    document.body.appendChild(progressBar);

    window.addEventListener('scroll', () => {{
        const scrollTop = document.documentElement.scrollTop;
        const scrollHeight = document.documentElement.scrollHeight - window.innerHeight;
        const progress = (scrollTop / scrollHeight) * 100;
        progressBar.style.width = progress + '%';

        // Send scroll event
        if (ws && ws.readyState === WebSocket.OPEN) {{
            ws.send(JSON.stringify({{
                type: 'learn',
                event_type: 'scroll',
                data: {{ depth: progress / 100 }}
            }}));
        }}
    }});
}}

// Keyboard Shortcuts
const keyboardMap = AGENT_CONFIG.keyboard || {{}};
document.addEventListener('keydown', (e) => {{
    const key = e.key.toLowerCase();
    const action = keyboardMap[key];

    if (action && ws && ws.readyState === WebSocket.OPEN) {{
        ws.send(JSON.stringify({{
            type: 'action',
            action_type: action,
            parameters: {{}}
        }}));
    }}
}});

// Initialize
connectWebSocket();
console.log('🔮 Agent ready:', AGENT_ID);
"""

    return js


# =============================================================================
# Secrets JavaScript
# =============================================================================


def generate_secrets_js(schema: AgentSchema) -> str:
    """Generate JavaScript for secret triggers.

    Args:
        schema: Agent schema.

    Returns:
        JavaScript code for secrets.
    """
    secrets = schema.i_hide
    parts = []

    # Konami code
    if secrets.konami:
        parts.append(f"""
// Konami Code
(function() {{
    const konamiCode = ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowDown',
                        'ArrowLeft', 'ArrowRight', 'ArrowLeft', 'ArrowRight',
                        'b', 'a'];
    let konamiIndex = 0;

    document.addEventListener('keydown', (e) => {{
        if (e.key === konamiCode[konamiIndex]) {{
            konamiIndex++;
            if (konamiIndex === konamiCode.length) {{
                console.log('🎮 Konami!');
                window.dispatchEvent(new CustomEvent('kagami-secret', {{
                    detail: {{ id: 'konami', action: '{secrets.konami}' }}
                }}));
                konamiIndex = 0;

                // Report to agent
                if (ws && ws.readyState === WebSocket.OPEN) {{
                    ws.send(JSON.stringify({{
                        type: 'learn',
                        event_type: 'secret_found',
                        data: {{ secret_id: 'konami' }}
                    }}));
                }}
            }}
        }} else {{
            konamiIndex = 0;
        }}
    }});
}})();
""")

    # Typed sequences
    for seq in secrets.typed_sequences:
        sequence = seq.get("sequence", "")
        action = seq.get("action", "")
        if sequence and action:
            parts.append(f"""
// Typed sequence: {sequence}
(function() {{
    const sequence = '{sequence}'.toLowerCase();
    let buffer = '';

    document.addEventListener('keydown', (e) => {{
        if (e.key.length === 1) {{
            buffer += e.key.toLowerCase();
            buffer = buffer.slice(-sequence.length);

            if (buffer === sequence) {{
                console.log('🎯 Sequence: {sequence}');
                window.dispatchEvent(new CustomEvent('kagami-secret', {{
                    detail: {{ id: 'typed_{sequence}', action: '{action}' }}
                }}));
                buffer = '';

                if (ws && ws.readyState === WebSocket.OPEN) {{
                    ws.send(JSON.stringify({{
                        type: 'learn',
                        event_type: 'secret_found',
                        data: {{ secret_id: 'typed_{sequence}' }}
                    }}));
                }}
            }}
        }}
    }});
}})();
""")

    # Console API
    console = secrets.console
    if console.namespace:
        methods_json = json.dumps(console.methods)
        welcome = console.welcome_message or f"Welcome to {schema.i_am.name}"
        parts.append(f"""
// Console API
window.{console.namespace} = {{
    methods: {methods_json},
    help: function() {{
        console.log('Available methods:', this.methods);
    }}
}};
console.log('{welcome}');
console.log('Type {console.namespace}.help() for available methods');
""")

    return "\n".join(parts)


# =============================================================================
# Main Renderer
# =============================================================================


def render_agent_html(schema: AgentSchema, user_profile: str | None = None) -> str:
    """Render complete HTML page for an agent.

    Args:
        schema: Agent schema to render.
        user_profile: Optional user profile for personalization.

    Returns:
        Complete HTML page string.
    """
    return HTML_TEMPLATE.format(
        agent_id=schema.i_am.id,
        craft_level=schema.i_am.craft_level.value,
        colony=schema.i_am.colony.value,
        title=schema.i_am.name,
        css=generate_css(schema),
        body=render_content(schema, user_profile),
        runtime_js=generate_runtime_js(schema),
        secrets_js=generate_secrets_js(schema),
    )


# =============================================================================
# Exports
# =============================================================================


__all__ = [
    "generate_css",
    "generate_runtime_js",
    "generate_secrets_js",
    "render_agent_html",
    "render_block",
    "render_content",
]
