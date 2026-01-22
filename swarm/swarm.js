/**
 * Swarm Visualization — 25 Browser Nodes
 * 
 * Creates and manages the hexagonal swarm of browser nodes.
 * Handles animations, connections, and state transitions.
 */

class SwarmVisualization {
    constructor(containerId, connectionsId) {
        this.container = document.getElementById(containerId);
        this.connectionsEl = document.getElementById(connectionsId);
        
        if (!this.container || !this.connectionsEl) return;
        
        this.nodes = [];
        this.nodeCount = 25;
        this.centerNode = null;
        this.connections = [];
        this.isBooted = false;
        
        // Node positions in hexagonal pattern
        this.positions = this.calculateHexPositions();
        
        this.init();
    }
    
    calculateHexPositions() {
        const positions = [];
        const centerX = 50; // percentage
        const centerY = 50;
        const ringSpacing = 18; // percentage between rings
        
        // Center node
        positions.push({ x: centerX, y: centerY, ring: 0 });
        
        // Ring 1 (6 nodes)
        for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i - Math.PI / 2;
            positions.push({
                x: centerX + Math.cos(angle) * ringSpacing,
                y: centerY + Math.sin(angle) * ringSpacing,
                ring: 1
            });
        }
        
        // Ring 2 (12 nodes)
        for (let i = 0; i < 12; i++) {
            const angle = (Math.PI / 6) * i - Math.PI / 2;
            const distance = ringSpacing * 2;
            positions.push({
                x: centerX + Math.cos(angle) * distance,
                y: centerY + Math.sin(angle) * distance,
                ring: 2
            });
        }
        
        // Ring 3 (6 nodes - just corners for aesthetics)
        for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i - Math.PI / 2;
            const distance = ringSpacing * 2.8;
            positions.push({
                x: centerX + Math.cos(angle) * distance,
                y: centerY + Math.sin(angle) * distance,
                ring: 3
            });
        }
        
        return positions.slice(0, this.nodeCount);
    }
    
    init() {
        this.createNodes();
        this.createConnectionsSVG();
        this.bindEvents();
        
        // Boot sequence after a delay
        setTimeout(() => this.bootSequence(), 1000);
    }
    
    createNodes() {
        const grid = document.getElementById('swarm-grid');
        if (!grid) return;
        
        grid.innerHTML = '';
        
        this.positions.forEach((pos, index) => {
            const node = document.createElement('div');
            node.className = 'browser-node';
            node.dataset.index = index;
            
            if (index === 0) {
                node.classList.add('central');
            }
            
            // Random website icons
            const icons = ['🌐', '📱', '💻', '🖥️', '📊', '🛒', '📧', '💼', '🔍', '📰'];
            const icon = index === 0 ? '🧠' : icons[index % icons.length];
            
            node.innerHTML = `
                <div class="node-icon">${icon}</div>
                <div class="node-id">#${String(index + 1).padStart(2, '0')}</div>
                <div class="node-viewport">
                    <div class="node-viewport-header">
                        <span class="viewport-dot"></span>
                        <span class="viewport-dot"></span>
                        <span class="viewport-dot"></span>
                    </div>
                    <div class="node-viewport-content">
                        ${index === 0 ? 'Orchestrator<br>Coordinating swarm...' : `Browser ${index + 1}<br>Ready for tasks`}
                    </div>
                </div>
            `;
            
            // Position the node
            node.style.left = `${pos.x}%`;
            node.style.top = `${pos.y}%`;
            node.style.transform = 'translate(-50%, -50%)';
            
            grid.appendChild(node);
            this.nodes.push(node);
        });
        
        this.centerNode = this.nodes[0];
    }
    
    createConnectionsSVG() {
        // Create SVG connections between nodes
        const svg = this.connectionsEl;
        svg.innerHTML = '';
        svg.setAttribute('viewBox', '0 0 100 100');
        svg.setAttribute('preserveAspectRatio', 'none');
        
        // Connect center to ring 1
        for (let i = 1; i <= 6; i++) {
            this.addConnection(svg, 0, i);
        }
        
        // Connect ring 1 to ring 2
        for (let i = 1; i <= 6; i++) {
            const ring2Start = 7;
            this.addConnection(svg, i, ring2Start + (i - 1) * 2);
            this.addConnection(svg, i, ring2Start + (i - 1) * 2 + 1);
        }
        
        // Connect ring 1 neighbors
        for (let i = 1; i <= 6; i++) {
            const next = i === 6 ? 1 : i + 1;
            this.addConnection(svg, i, next);
        }
    }
    
    addConnection(svg, fromIndex, toIndex) {
        if (fromIndex >= this.positions.length || toIndex >= this.positions.length) return;
        
        const from = this.positions[fromIndex];
        const to = this.positions[toIndex];
        
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', from.x);
        line.setAttribute('y1', from.y);
        line.setAttribute('x2', to.x);
        line.setAttribute('y2', to.y);
        line.classList.add('connection-line');
        line.dataset.from = fromIndex;
        line.dataset.to = toIndex;
        
        svg.appendChild(line);
        this.connections.push(line);
    }
    
    bootSequence() {
        // Boot nodes sequentially with staggered timing
        const bootOrder = this.getBootOrder();
        
        bootOrder.forEach((index, i) => {
            setTimeout(() => {
                const node = this.nodes[index];
                if (node) {
                    node.classList.add('booted');
                    
                    // Emit particles
                    if (window.particleSystem) {
                        const rect = node.getBoundingClientRect();
                        window.particleSystem.emit(
                            rect.left + rect.width / 2,
                            rect.top + rect.height / 2,
                            5,
                            index === 0 ? 'magenta' : 'cyan'
                        );
                    }
                }
            }, i * 80);
        });
        
        // After all nodes boot, start synchronized pulse
        setTimeout(() => {
            this.isBooted = true;
            this.startSynchronizedPulse();
        }, bootOrder.length * 80 + 500);
    }
    
    getBootOrder() {
        // Boot from center outward
        const order = [0]; // Center first
        
        // Ring 1
        for (let i = 1; i <= 6; i++) {
            order.push(i);
        }
        
        // Ring 2
        for (let i = 7; i <= 18; i++) {
            if (i < this.nodeCount) order.push(i);
        }
        
        // Ring 3
        for (let i = 19; i < this.nodeCount; i++) {
            order.push(i);
        }
        
        return order;
    }
    
    startSynchronizedPulse() {
        // All nodes pulse together in a breathing pattern
        let phase = 0;
        
        const pulse = () => {
            if (!this.isBooted) return;
            
            phase += 0.02;
            const intensity = 0.5 + Math.sin(phase) * 0.5;
            
            this.nodes.forEach((node, index) => {
                if (!node.classList.contains('active') && 
                    !node.classList.contains('processing') &&
                    !node.classList.contains('error')) {
                    node.style.boxShadow = `0 0 ${10 + intensity * 20}px rgba(0, 245, 212, ${0.1 + intensity * 0.2})`;
                }
            });
            
            requestAnimationFrame(pulse);
        };
        
        pulse();
    }
    
    bindEvents() {
        // Node hover and click
        this.container.addEventListener('click', (e) => {
            const node = e.target.closest('.browser-node');
            if (node) {
                this.activateNode(parseInt(node.dataset.index));
            }
        });
    }
    
    activateNode(index) {
        // Deactivate all
        this.nodes.forEach(node => node.classList.remove('active'));
        this.connections.forEach(conn => conn.classList.remove('active'));
        
        // Activate selected
        const node = this.nodes[index];
        if (node) {
            node.classList.add('active');
            
            // Activate connections to/from this node
            this.connections.forEach(conn => {
                if (parseInt(conn.dataset.from) === index || 
                    parseInt(conn.dataset.to) === index) {
                    conn.classList.add('active');
                }
            });
            
            // Emit particles
            if (window.particleSystem) {
                const rect = node.getBoundingClientRect();
                window.particleSystem.emit(
                    rect.left + rect.width / 2,
                    rect.top + rect.height / 2,
                    15,
                    'cyan'
                );
            }
        }
    }
    
    // Simulate processing across nodes
    simulateProcessing(nodeIndices, duration = 2000) {
        nodeIndices.forEach(index => {
            const node = this.nodes[index];
            if (node) {
                node.classList.add('processing');
                
                setTimeout(() => {
                    node.classList.remove('processing');
                }, duration);
            }
        });
    }
    
    // Simulate error and healing
    simulateError(index, healTime = 1500) {
        const node = this.nodes[index];
        if (!node) return;
        
        node.classList.add('error');
        
        setTimeout(() => {
            node.classList.remove('error');
            node.classList.add('healing');
            
            setTimeout(() => {
                node.classList.remove('healing');
                
                // Emit success particles
                if (window.particleSystem) {
                    const rect = node.getBoundingClientRect();
                    window.particleSystem.emit(
                        rect.left + rect.width / 2,
                        rect.top + rect.height / 2,
                        10,
                        'amber'
                    );
                }
            }, healTime);
        }, 500);
    }
    
    // Distribute tasks across the swarm
    distributeTasks(taskCount) {
        const availableNodes = this.nodes.slice(1); // Exclude central node
        const tasksPerNode = Math.ceil(taskCount / availableNodes.length);
        
        return availableNodes.map((node, index) => ({
            nodeIndex: index + 1,
            tasks: Math.min(tasksPerNode, taskCount - index * tasksPerNode)
        })).filter(n => n.tasks > 0);
    }
}

// Initialize on load
window.swarmViz = null;

document.addEventListener('DOMContentLoaded', () => {
    window.swarmViz = new SwarmVisualization('swarm-grid', 'swarm-connections');
});
