/**
 * Kagami Visual Testing — Minimal integration
 */

// Timing constants for animations
export const TIMING = {
    instant: 100,
    fast: 150,
    normal: 250,
    slow: 400,
};

// Initialize Kagami namespace
if (typeof window !== 'undefined') {
    window.鏡 = window.鏡 || {};
}
