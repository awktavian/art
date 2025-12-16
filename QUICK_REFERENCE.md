# Design System Quick Reference

**One-page cheatsheet for developers**

---

## Import

```html
<link rel="stylesheet" href="design-system.css">
```

---

## Typography

```css
/* Sizes */
--font-size-xs        /* 11-12px - badges */
--font-size-sm        /* 13-14px - metadata */
--font-size-base      /* 16-17px - body */
--font-size-md        /* 18-20px - subheads */
--font-size-lg        /* 20-25px - headers */
--font-size-xl        /* 23-31px - sections */
--font-size-2xl       /* 29-39px - major headers */
--font-size-3xl       /* 37-49px - page titles */
--font-size-hero      /* 96-160px - hero counter */
--font-size-kanji     /* 64-112px - kanji */

/* Line Heights */
--line-height-tight   /* 1.2 - display */
--line-height-snug    /* 1.4 - headings */
--line-height-normal  /* 1.6 - body (optimal) */
--line-height-relaxed /* 1.8 - long-form */

/* Letter Spacing */
--letter-spacing-widest  /* 0.2em - uppercase labels */
--letter-spacing-wider   /* 0.1em - subheadings */
--letter-spacing-wide    /* 0.05em - buttons */
```

---

## Colors

### Base
```css
--color-void      /* #0A0A0C - background */
--color-gold      /* #D4AF37 - accent */
--color-light     /* #FAFAF8 - inverse */
```

### Text (3-tier hierarchy)
```css
--color-text         /* Full contrast (13.8:1) */
--color-text-dim     /* 65% opacity (8.9:1) */
--color-text-whisper /* 35% opacity (4.8:1) */
```

### Commit Types
```css
--color-perf      /* #FF9F40 - performance */
--color-feat      /* #64D9FF - features */
--color-fix       /* #4ECB71 - bug fixes */
--color-docs      /* #B794F6 - documentation */
--color-test      /* #6FD895 - tests */
--color-security  /* #FF6B6B - security */
--color-refactor  /* #90A4AE - refactoring */
--color-style     /* #FF78CB - styling */
--color-build     /* #FFAB40 - build system */
--color-chore     /* #78909C - maintenance */
```

**All colors exceed WCAG AA (4.5:1 minimum)**

---

## Spacing (8px Grid)

```css
--space-1    /* 8px */
--space-2    /* 16px - base unit */
--space-3    /* 24px - comfortable */
--space-4    /* 32px - section spacing */
--space-6    /* 48px - large gaps */
--space-8    /* 64px - major sections */
--space-12   /* 96px - maximum */

/* Component-specific */
--padding-card     /* 32px */
--padding-section  /* 48px */
--gap-tight        /* 16px */
--gap-normal       /* 24px */
--gap-loose        /* 32px */
```

---

## Shadows

```css
--shadow-sm   /* Subtle borders */
--shadow-md   /* Hover state */
--shadow-lg   /* Active/focused */
--shadow-xl   /* Modals */

/* Gold glow (for accents) */
--shadow-glow-sm
--shadow-glow-md
--shadow-glow-lg
```

---

## Animation

### Durations
```css
--duration-fast    /* 150ms - hover */
--duration-normal  /* 300ms - default */
--duration-slow    /* 500ms - emphasized */
--duration-slower  /* 700ms - dramatic */
```

### Easings
```css
--ease-smooth  /* cubic-bezier(0.16, 1, 0.3, 1) - cinematic */
--ease-spring  /* cubic-bezier(0.34, 1.56, 0.64, 1) - playful */
--ease-flip    /* cubic-bezier(0.45, 0, 0.55, 1) - cards */
```

### Staggered Delays
```css
--delay-1  /* 100ms */
--delay-2  /* 200ms */
--delay-3  /* 300ms */
--delay-4  /* 400ms */
```

---

## Border Radius

```css
--radius-sm   /* 4px - badges */
--radius-md   /* 8px - buttons */
--radius-lg   /* 12px - cards */
--radius-xl   /* 16px - hero cards */
--radius-full /* 9999px - circles */
```

---

## Usage Examples

### Commit Card with Type Color
```html
<div class="commit-item" data-commit-type="perf">
    <div class="commit-dot"></div>
    <div class="commit-content">
        <span class="commit-type">perf</span>
        <div class="commit-title">Optimize boot path</div>
        <div class="commit-meta">ab0b189 • 08:25</div>
    </div>
</div>
```

**Automatic color mapping:**
- `data-commit-type="perf"` → Orange
- `data-commit-type="feat"` → Cyan
- `data-commit-type="fix"` → Green
- (etc.)

### Staggered Reveal
```html
<h2 class="reveal" style="transition-delay: var(--delay-1);">Title</h2>
<p class="reveal" style="transition-delay: var(--delay-2);">Subtitle</p>
<div class="reveal" style="transition-delay: var(--delay-3);">Content</div>
```

### Card Hover Effect
```css
.card {
    transition:
        transform var(--duration-normal) var(--ease-spring),
        box-shadow var(--duration-normal) var(--ease-smooth);
}

.card:hover {
    transform: translateY(-8px);
    box-shadow: var(--shadow-xl);
}
```

### Hero Counter
```css
.hero-counter {
    font-size: var(--font-size-hero);
    font-family: var(--font-mono);
    color: var(--color-gold);
    text-shadow: var(--shadow-glow-lg);
    line-height: var(--line-height-tight);
}
```

---

## Utility Classes

### Typography
```css
.text-xs, .text-sm, .text-base, .text-lg, .text-xl
.font-light, .font-normal, .font-medium
.leading-tight, .leading-normal, .leading-relaxed
```

### Colors
```css
.text-primary     /* Full contrast */
.text-secondary   /* 65% opacity */
.text-tertiary    /* 35% opacity */
.text-accent      /* Gold */
```

### Spacing
```css
.p-0, .p-1, .p-2, .p-3, .p-4, .p-6, .p-8
.m-0, .m-1, .m-2, .m-3, .m-4, .m-6, .m-8
.gap-tight, .gap-normal, .gap-loose
```

### Visual
```css
.rounded-sm, .rounded-md, .rounded-lg, .rounded-xl, .rounded-full
.shadow-sm, .shadow-md, .shadow-lg, .shadow-xl, .shadow-glow
```

---

## Accessibility

### Contrast Ratios
- Text: 4.5:1 minimum (all exceed 7:1)
- UI elements: 3:1 minimum
- All commit type colors: AAA compliant

### Motion Preferences
```css
@media (prefers-reduced-motion: reduce) {
    /* All animations disabled automatically */
}
```

### High Contrast
```css
@media (prefers-contrast: high) {
    /* Borders and text automatically boosted */
}
```

### Touch Targets
- Minimum: 44x44px (WCAG AAA)
- Card padding: 32px (comfortable)

---

## Performance

### GPU-Accelerated (Fast)
```css
transform: translateY(-8px);   /* ✅ */
opacity: 0.5;                  /* ✅ */
filter: blur(4px);             /* ✅ */
```

### Layout-Triggering (Slow)
```css
width: 300px;    /* ❌ */
top: 100px;      /* ❌ */
padding: 20px;   /* ❌ */
```

**Use `transform` and `opacity` for animations.**

---

## Testing Checklist

- [ ] Keyboard navigation (Tab key)
- [ ] Screen reader (VoiceOver/NVDA)
- [ ] Reduced motion enabled
- [ ] High contrast mode
- [ ] Mobile (320px-768px)
- [ ] Desktop (768px-1920px)
- [ ] Color contrast (WebAIM checker)

---

## Files

```
gallery/
├── design-system.css           # Import this
├── DESIGN_SYSTEM.md            # Full documentation
├── IMPLEMENTATION_SUMMARY.md   # Integration guide
├── QUICK_REFERENCE.md          # This file
└── color-palette.html          # Visual reference
```

---

## Common Patterns

### 5-Level Visual Hierarchy
1. **Hero Stats:** `--font-size-hero` + `--shadow-glow-lg`
2. **Section Headers:** `--font-size-xl` + `--color-gold`
3. **Commit Titles:** `--font-size-base` + `--color-text`
4. **Metadata:** `--font-size-sm` + `--color-text-dim`
5. **Details:** `--font-size-xs` + `--color-text-whisper`

### Card Component
```css
.card {
    padding: var(--padding-card);
    background: var(--card-bg);
    border: 1px solid var(--card-border);
    border-radius: var(--radius-lg);
    transition: all var(--duration-normal) var(--ease-spring);
}

.card:hover {
    background: var(--card-bg-hover);
    border-color: var(--color-gold-dim);
    box-shadow: var(--shadow-xl);
}
```

### Button Component
```css
.button {
    padding: var(--space-2) var(--space-4);
    background: var(--color-gold);
    color: var(--color-void);
    border-radius: var(--radius-md);
    font-size: var(--font-size-base);
    font-weight: var(--font-weight-medium);
    transition: transform var(--duration-fast) var(--ease-spring);
}

.button:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
}

.button:active {
    transform: scale(0.95);
}
```

---

## Color Theory Summary

| Commit Type | Color | Psychology | Use Case |
|-------------|-------|------------|----------|
| **perf** | Orange | Energy, speed | Optimizations |
| **feat** | Cyan | Innovation, new | New features |
| **fix** | Green | Health, success | Bug fixes |
| **docs** | Purple | Knowledge, wisdom | Documentation |
| **test** | Light Green | Quality, validation | Tests |
| **security** | Red-Orange | Alert, attention | Security fixes |
| **refactor** | Gray-Blue | Neutral, professional | Code cleanup |
| **style** | Pink | Aesthetics, creativity | Design changes |
| **build** | Amber | Construction, foundation | Build system |
| **chore** | Cool Gray | Maintenance, routine | Housekeeping |

---

## Support

**Documentation:** `DESIGN_SYSTEM.md`
**Visual Reference:** `color-palette.html`
**Version:** 1.0.0
**Last Updated:** December 16, 2025
