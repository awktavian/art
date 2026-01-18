/**
 * AI-powered contextual tooltips for 111/100 Crystal polish
 * 
 * Explains Byzantine consensus concepts in plain language.
 */

export interface TooltipData {
  term: string;
  explanation: string;
  example?: string;
}

const TOOLTIP_DATABASE: Record<string, TooltipData> = {
  'byzantine': {
    term: 'Byzantine Consensus',
    explanation: 'A voting system where agents reach agreement even if some are faulty. Requires 5 out of 7 agents to agree.',
    example: 'Like a group deciding on dinner - if 5+ friends agree on pizza, that\'s what we\'re getting!',
  },
  'quorum': {
    term: 'Quorum (5/7)',
    explanation: 'Minimum number of votes needed for a decision. With 7 agents, we need 5 to agree.',
    example: 'Think of it like a jury - you need a supermajority, not just 51%.',
  },
  'agent': {
    term: 'AI Agent',
    explanation: 'An independent AI that learns and makes decisions. These 7 agents train in parallel.',
    example: 'Like 7 students studying together - they learn individually but share progress.',
  },
  'consensus': {
    term: 'Reaching Consensus',
    explanation: 'When enough agents agree (5/7), we have consensus and can proceed.',
    example: 'Democracy in action - majority rules, but it\'s a strong majority.',
  },
  'vote': {
    term: 'Agent Vote',
    explanation: 'Each agent votes "approve" (✓) or "reject" (✗) based on their analysis.',
    example: 'Like thumbs up/down, but with math behind it.',
  },
};

export class AITooltipManager {
  private tooltips: Map<HTMLElement, TooltipData> = new Map();
  private activeTooltip: HTMLElement | null = null;
  
  /**
   * Add intelligent tooltip to element
   */
  addTooltip(element: HTMLElement, term: string): void {
    const data = TOOLTIP_DATABASE[term.toLowerCase()];
    if (!data) return;
    
    this.tooltips.set(element, data);
    
    element.addEventListener('mouseenter', () => this.showTooltip(element));
    element.addEventListener('mouseleave', () => this.hideTooltip());
    element.addEventListener('click', () => this.showExpandedTooltip(element));
  }
  
  private showTooltip(element: HTMLElement): void {
    const data = this.tooltips.get(element);
    if (!data) return;
    
    // Create tooltip element
    const tooltip = document.createElement('div');
    tooltip.className = 'ai-tooltip';
    tooltip.innerHTML = `
      <div class="tooltip-header">${data.term}</div>
      <div class="tooltip-body">${data.explanation}</div>
      ${data.example ? `<div class="tooltip-example">💡 ${data.example}</div>` : ''}
      <div class="tooltip-hint">Click for more details</div>
    `;
    
    // Position near element
    const rect = element.getBoundingClientRect();
    tooltip.style.position = 'fixed';
    tooltip.style.left = `${rect.left}px`;
    tooltip.style.top = `${rect.bottom + 8}px`;
    
    document.body.appendChild(tooltip);
    this.activeTooltip = tooltip;
    
    // Fade in
    requestAnimationFrame(() => {
      tooltip.style.opacity = '1';
      tooltip.style.transform = 'translateY(0)';
    });
  }
  
  private hideTooltip(): void {
    if (this.activeTooltip) {
      this.activeTooltip.style.opacity = '0';
      setTimeout(() => {
        this.activeTooltip?.remove();
        this.activeTooltip = null;
      }, 200);
    }
  }
  
  private showExpandedTooltip(element: HTMLElement): void {
    const data = this.tooltips.get(element);
    if (!data) return;
    
    // Create modal with expanded explanation
    const modal = document.createElement('div');
    modal.className = 'tooltip-modal';
    modal.innerHTML = `
      <div class="tooltip-modal-content">
        <h2>${data.term}</h2>
        <p>${data.explanation}</p>
        ${data.example ? `<div class="example-box">
          <strong>Example:</strong>
          <p>${data.example}</p>
        </div>` : ''}
        <button class="tooltip-close">Got it!</button>
      </div>
    `;
    
    document.body.appendChild(modal);
    
    // Close on click
    modal.querySelector('.tooltip-close')?.addEventListener('click', () => {
      modal.remove();
    });
    
    modal.addEventListener('click', (e) => {
      if (e.target === modal) {
        modal.remove();
      }
    });
  }
  
  /**
   * Auto-detect and add tooltips to technical terms
   */
  autoDetectAndAddTooltips(): void {
    const terms = Object.keys(TOOLTIP_DATABASE);
    
    document.body.querySelectorAll('*').forEach((el) => {
      const text = el.textContent?.toLowerCase() || '';
      
      terms.forEach((term) => {
        if (text.includes(term) && el instanceof HTMLElement) {
          // Add tooltip styling
          el.style.borderBottom = '1px dotted #67D4E4';
          el.style.cursor = 'help';
          this.addTooltip(el, term);
        }
      });
    });
  }
}
