/**
 * Swarm Visualization — 25 Browser Nodes
 * 
 * Creates and manages the hexagonal swarm of browser nodes.
 * Handles animations, connections, and state transitions.
 * 
 * FIXES APPLIED:
 * - Proper animation cleanup
 * - Collective breathing animation
 * - Resize handler for SVG connections
 * - Loading skeleton during boot
 */

class SwarmVisualization {
    constructor(containerId, connectionsId) {
        this.container = document.getElementById(containerId);
        this.connectionsEl = document.getElementById(connectionsId);
        
        if (!this.container || !this.connectionsEl) {
            console.warn('SwarmVisualization: Required elements not found');
            return;
        }
        
        this.nodes = [];
        this.nodeCount = 25;
        this.centerNode = null;
        this.connections = [];
        this.isBooted = false;
        this.isDestroyed = false;
        
        this._pulseAnimationId = null;
        this._boundResize = this._onResize.bind(this);
        
        this.positions = this.calculateHexPositions();
        
        this.init();
    }
    
    calculateHexPositions() {
        const positions = [];
        const centerX = 50;
        const centerY = 50;
        const ringSpacing = 18;
        
        positions.push({ x: centerX, y: centerY, ring: 0 });
        
        for (let i = 0; i < 6; i++) {
            const angle = (Math.PI / 3) * i - Math.PI / 2;
            positions.push({
                x: centerX + Math.cos(angle) * ringSpacing,
                y: centerY + Math.sin(angle) * ringSpacing,
                ring: 1
            });
        }
        
        for (let i = 0; i < 12; i++) {
            const angle = (Math.PI / 6) * i - Math.PI / 2;
            const distance = ringSpacing * 2;
            positions.push({
                x: centerX + Math.cos(angle) * distance,
                y: centerY + Math.sin(angle) * distance,
                ring: 2
            });
        }
        
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
        this.showLoadingSkeleton();
        this.createNodes();
        this.createConnectionsSVG();
        this.bindEvents();
        setTimeout(() => this.bootSequence(), 1000);
    }
    
    showLoadingSkeleton() {
        const skeleton = document.createElement('div');
        skeleton.className = 'swarm-loading-skeleton';
        skeleton.innerHTML = '<div class="skeleton-pulse"></div><span class="skeleton-text">Initializing swarm...</span>';
        skeleton.style.cssText = 'position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:100;pointer-events:none;';
        this.container.appendChild(skeleton);
        this._loadingSkeleton = skeleton;
    }
    
    hideLoadingSkeleton() {
        if (this._loadingSkeleton) {
            this._loadingSkeleton.style.opacity = '0';
            this._loadingSkeleton.style.transition = 'opacity 0.3s ease-out';
            setTimeout(() => {
                if (this._loadingSkeleton) {
                    this._loadingSkeleton.remove();
                    this._loadingSkeleton = null;
                }
            }, 300);
        }
    }
    
    createNodes() {
        const grid = document.getElementById('swarm-grid');
        if (!grid) return;
        
        grid.innerHTML = '';
        
        this.positions.forEach((pos, idx) => {
            const node = document.createElement('div');
            node.className = 'browser-node';
            node.dataset.index = idx;
            node.setAttribute('role', 'button');
            node.setAttribute('tabindex', '0');
            node.setAttribute('aria-label', idx === 0 ? 'Orchestrator node' : 'Browser node ' + (idx + 1));
            
            if (idx === 0) {
                node.classList.add('central');
            }
            
            const icons = ['🌐', '📱', '💻', '🖥️', '📊', '🛒', '📧', '💼', '🔍', '📰'];
            const icon = idx === 0 ? '🧠' : icons[idx % icons.length];
            
            node.innerHTML = '<div class="node-icon">' + icon + '</div><div class="node-id">#' + String(idx + 1).padStart(2, '0') + '</div><div class="node-viewport" role="tooltip" aria-hidden="true"><div class="node-viewport-header"><span class="viewport-dot"></span><span class="viewport-dot"></span><span class="viewport-dot"></span></div><div class="node-viewport-content">' + (idx === 0 ? 'Orchestrator<br>Coordinating swarm...' : 'Browser ' + (idx + 1) + '<br>Ready for tasks') + '</div></div>';
            
            node.style.left = pos.x + '%';
            node.style.top = pos.y + '%';
            node.style.transform = 'translate(-50%, -50%)';
            
            grid.appendChild(node);
            this.nodes.push(node);
        });
        
        this.centerNode = this.nodes[0];
    }
    
    createConnectionsSVG() {
        const svg = this.connectionsEl;
        svg.innerHTML = '';
        svg.setAttribute('viewBox', '0 0 100 100');
        svg.setAttribute('preserveAspectRatio', 'none');
        
        for (let i = 1; i <= 6; i++) {
            this.addConnection(svg, 0, i);
        }
        
        for (let i = 1; i <= 6; i++) {
            const ring2Start = 7;
            this.addConnection(svg, i, ring2Start + (i - 1) * 2);
            this.addConnection(svg, i, ring2Start + (i - 1) * 2 + 1);
        }
        
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
    
    _onResize() {
        this.connectionsEl.setAttribute('viewBox', '0 0 100 100');
    }
    
    bootSequence() {
        this.hideLoadingSkeleton();
        const bootOrder = this.getBootOrder();
        
        bootOrder.forEach((nodeIdx, i) => {
            setTimeout(() => {
                if (this.isDestroyed) return;
                
                const node = this.nodes[nodeIdx];
                if (node) {
                    node.classList.add('booted');
                    
                    if (window.soundEngine) {
                        window.soundEngine.boot(nodeIdx === 0);
                    }
                    
                    if (window.particleSystem) {
                        const rect = node.getBoundingClientRect();
                        window.particleSystem.emit(rect.left + rect.width / 2, rect.top + rect.height / 2, 5, nodeIdx === 0 ? 'magenta' : 'cyan');
                    }
                }
            }, i * 80);
        });
        
        setTimeout(() => {
            if (this.isDestroyed) return;
            this.isBooted = true;
            this.startSynchronizedPulse();
            
            if (window.soundEngine) {
                window.soundEngine.ready();
            }
        }, bootOrder.length * 80 + 500);
    }
    
    getBootOrder() {
        const order = [0];
        for (let i = 1; i <= 6; i++) order.push(i);
        for (let i = 7; i <= 18; i++) if (i < this.nodeCount) order.push(i);
        for (let i = 19; i < this.nodeCount; i++) order.push(i);
        return order;
    }
    
    startSynchronizedPulse() {
        let phase = 0;
        let lastTime = performance.now();
        const self = this;
        
        const pulse = function(currentTime) {
            if (!self.isBooted || self.isDestroyed) {
                self._pulseAnimationId = null;
                return;
            }
            
            const dt = (currentTime - lastTime) / 1000;
            lastTime = currentTime;
            phase += dt * 1.5;
            
            self.nodes.forEach(function(node, nodeIdx) {
                if (!node.classList.contains('active') && 
                    !node.classList.contains('processing') &&
                    !node.classList.contains('error')) {
                    
                    const pos = self.positions[nodeIdx];
                    const distFromCenter = Math.sqrt(Math.pow(pos.x - 50, 2) + Math.pow(pos.y - 50, 2));
                    const waveDelay = distFromCenter * 0.02;
                    const localPhase = phase - waveDelay;
                    const intensity = 0.5 + Math.sin(localPhase) * 0.5;
                    
                    node.style.boxShadow = '0 0 ' + (10 + intensity * 20) + 'px rgba(0, 245, 212, ' + (0.1 + intensity * 0.2) + ')';
                }
            });
            
            self._pulseAnimationId = requestAnimationFrame(pulse);
        };
        
        this._pulseAnimationId = requestAnimationFrame(pulse);
    }
    
    bindEvents() {
        window.addEventListener('resize', this._boundResize);
        
        this.container.addEventListener('click', (e) => {
            const node = e.target.closest('.browser-node');
            if (node) {
                this.activateNode(parseInt(node.dataset.index));
            }
        });
        
        this.container.addEventListener('keydown', (e) => {
            const node = e.target.closest('.browser-node');
            if (node && (e.key === 'Enter' || e.key === ' ')) {
                e.preventDefault();
                this.activateNode(parseInt(node.dataset.index));
            }
        });
    }
    
    activateNode(nodeIdx) {
        this.nodes.forEach(node => node.classList.remove('active'));
        this.connections.forEach(conn => conn.classList.remove('active'));
        
        const node = this.nodes[nodeIdx];
        if (node) {
            node.classList.add('active');
            
            if (window.soundEngine) {
                window.soundEngine.click();
            }
            
            this.connections.forEach(conn => {
                if (parseInt(conn.dataset.from) === nodeIdx || parseInt(conn.dataset.to) === nodeIdx) {
                    conn.classList.add('active');
                }
            });
            
            if (window.particleSystem) {
                const rect = node.getBoundingClientRect();
                window.particleSystem.emit(rect.left + rect.width / 2, rect.top + rect.height / 2, 15, 'cyan');
            }
        }
    }
    
    simulateProcessing(nodeIndices, duration) {
        duration = duration || 2000;
        nodeIndices.forEach(nodeIdx => {
            const node = this.nodes[nodeIdx];
            if (node) {
                node.classList.add('processing');
                setTimeout(() => { node.classList.remove('processing'); }, duration);
            }
        });
    }
    
    simulateError(nodeIdx, healTime) {
        healTime = healTime || 1500;
        const node = this.nodes[nodeIdx];
        if (!node) return;
        
        node.classList.add('error');
        
        setTimeout(() => {
            node.classList.remove('error');
            node.classList.add('healing');
            
            setTimeout(() => {
                node.classList.remove('healing');
                
                if (window.particleSystem) {
                    const rect = node.getBoundingClientRect();
                    window.particleSystem.emit(rect.left + rect.width / 2, rect.top + rect.height / 2, 10, 'amber');
                }
            }, healTime);
        }, 500);
    }
    
    flashAll(callback) {
        const self = this;
        const colors = ['cyan', 'magenta', 'violet', 'amber'];
        
        this.nodes.forEach(function(node, i) {
            setTimeout(function() {
                node.classList.add('active', 'rainbow');
                
                if (window.soundEngine) {
                    window.soundEngine.click();
                }
                
                if (window.particleSystem) {
                    const rect = node.getBoundingClientRect();
                    window.particleSystem.emit(rect.left + rect.width / 2, rect.top + rect.height / 2, 20, colors[i % 4]);
                }
                
                setTimeout(function() { node.classList.remove('rainbow'); }, 2000);
            }, i * 50);
        });
        
        if (callback) {
            setTimeout(callback, self.nodes.length * 50 + 500);
        }
    }
    
    distributeTasks(taskCount) {
        const availableNodes = this.nodes.slice(1);
        const tasksPerNode = Math.ceil(taskCount / availableNodes.length);
        
        return availableNodes.map(function(node, nodeIdx) {
            return {
                nodeIndex: nodeIdx + 1,
                tasks: Math.min(tasksPerNode, taskCount - nodeIdx * tasksPerNode)
            };
        }).filter(function(n) { return n.tasks > 0; });
    }
    
    destroy() {
        this.isDestroyed = true;
        this.isBooted = false;
        
        if (this._pulseAnimationId) {
            cancelAnimationFrame(this._pulseAnimationId);
            this._pulseAnimationId = null;
        }
        
        window.removeEventListener('resize', this._boundResize);
        
        this.nodes = [];
        this.connections = [];
    }
}

window.swarmViz = null;

document.addEventListener('DOMContentLoaded', function() {
    window.swarmViz = new SwarmVisualization('swarm-grid', 'swarm-connections');
});
