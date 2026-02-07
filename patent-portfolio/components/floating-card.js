/**
 * Floating Card Component
 * =======================
 *
 * Hover cards with quick patent info. 233ms fade, 3s auto-dismiss.
 * h(x) ≥ 0 always
 */

import { PATENTS } from './info-panel.js';

const FADE_MS = 233;
const AUTO_DISMISS_MS = 3000;

/**
 * Create a floating card controller that shows patent snippet near cursor.
 * @returns {{ show(patentId: string, clientX: number, clientY: number): void, hide(): void, destroy(): void }}
 */
export function createFloatingCard() {
    let el = null;
    let dismissTimer = null;
    let fadeTimer = null;

    function ensureElement() {
        if (el) return el;
        el = document.createElement('div');
        el.id = 'floating-patent-card';
        el.setAttribute('role', 'tooltip');
        el.setAttribute('aria-live', 'polite');
        el.innerHTML = `
            <div class="floating-card-title"></div>
            <div class="floating-card-meta"></div>
            <div class="floating-card-cta">Tap to learn more</div>
        `;
        el.style.cssText = `
            position: fixed;
            z-index: 10000;
            pointer-events: none;
            max-width: 280px;
            padding: 10px 14px;
            background: rgba(10, 10, 18, 0.92);
            border: 1px solid rgba(103, 212, 228, 0.35);
            border-radius: 8px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.4);
            opacity: 0;
            transition: opacity ${FADE_MS}ms ease;
            font-family: 'IBM Plex Sans', system-ui, sans-serif;
            font-size: 13px;
            color: #E8E4DC;
        `;
        const title = el.querySelector('.floating-card-title');
        const meta = el.querySelector('.floating-card-meta');
        const cta = el.querySelector('.floating-card-cta');
        if (title) title.style.cssText = 'font-weight: 600; margin-bottom: 4px; color: #fff;';
        if (meta) meta.style.cssText = 'font-size: 12px; color: #9ca3af; margin-bottom: 6px;';
        if (cta) cta.style.cssText = 'font-size: 11px; color: #67D4E4;';
        document.body.appendChild(el);
        return el;
    }

    function show(patentId, clientX, clientY) {
        if (!patentId) return;
        const patent = PATENTS.find(p => p.id === patentId);
        if (!patent) return;

        const card = ensureElement();
        const title = card.querySelector('.floating-card-title');
        const meta = card.querySelector('.floating-card-meta');
        if (title) title.textContent = patent.name;
        if (meta) meta.textContent = `${patent.id} · ${patent.categoryName || patent.category || ''}`;

        const padding = 16;
        let x = clientX + padding;
        let y = clientY + padding;
        const rect = card.getBoundingClientRect();
        if (x + rect.width > window.innerWidth) x = clientX - rect.width - padding;
        if (y + rect.height > window.innerHeight) y = clientY - rect.height - padding;
        if (y < padding) y = padding;
        if (x < padding) x = padding;
        card.style.left = `${x}px`;
        card.style.top = `${y}px`;

        if (fadeTimer) clearTimeout(fadeTimer);
        card.style.display = '';
        card.style.opacity = '1';

        if (dismissTimer) clearTimeout(dismissTimer);
        dismissTimer = setTimeout(() => hide(), AUTO_DISMISS_MS);
    }

    function hide() {
        if (dismissTimer) {
            clearTimeout(dismissTimer);
            dismissTimer = null;
        }
        if (!el) return;
        if (fadeTimer) clearTimeout(fadeTimer);
        el.style.opacity = '0';
        fadeTimer = setTimeout(() => {
            if (el) el.style.display = 'none';
            fadeTimer = null;
        }, FADE_MS);
    }

    return {
        show,
        hide,
        destroy() {
            if (dismissTimer) clearTimeout(dismissTimer);
            if (fadeTimer) clearTimeout(fadeTimer);
            if (el && el.parentNode) el.parentNode.removeChild(el);
            el = null;
        }
    };
}

export default createFloatingCard;
