# Kagami Design System V2 Component Library

> Volumetric glass-morphic design system with noise textures, depth layers, and colony-aware theming.

This document provides comprehensive documentation for the Kagami Desktop client's design system component library. All components follow Apple HIG standards, support standard animation timing, and are fully accessible.

---

## Table of Contents

1. [Design Tokens](#design-tokens)
2. [Button](#button)
3. [Input Fields](#input-fields)
4. [Cards and Surfaces](#cards-and-surfaces)
5. [Modals and Dialogs](#modals-and-dialogs)
6. [Navigation](#navigation)
7. [Feedback Components](#feedback-components)
8. [Color Usage](#color-usage)
9. [Typography](#typography)
10. [Spacing](#spacing)
11. [Animation Timing](#animation-timing)

---

## Design Tokens

Import the design tokens in your CSS:

```css
@import 'css/prism-tokens.css';
```

### Core Palette

| Token | Value | Usage |
|-------|-------|-------|
| `--prism-void` | `#07060B` | Primary background |
| `--prism-void-warm` | `#0D0A0F` | Elevated background |
| `--prism-surface` | `rgba(255, 255, 255, 0.04)` | Glass surface |
| `--prism-surface-elevated` | `rgba(255, 255, 255, 0.08)` | Elevated glass |
| `--prism-border` | `rgba(255, 255, 255, 0.08)` | Default border |

### Colony Colors (Fano Plane / Octonion Basis)

| Token | Color | Colony | Purpose |
|-------|-------|--------|---------|
| `--prism-spark` | `#FF6B35` | e1 | Ideation, Error |
| `--prism-forge` | `#FF9500` | e2 | Building, Warning |
| `--prism-flow` | `#5AC8FA` | e3 | Resilience |
| `--prism-nexus` | `#AF52DE` | e4 | Integration, Success |
| `--prism-beacon` | `#FFD60A` | e5 | Planning, Primary |
| `--prism-grove` | `#32D74B` | e6 | Research |
| `--prism-crystal` | `#64D2FF` | e7 | Verification |

---

## Button

World-class visionOS-quality buttons with volumetric glass depth, liquid ripple effects, and spring physics.

### Basic Usage

```html
<!-- Primary (Solid) Button -->
<button class="prism-btn prism-btn--solid" data-colony="beacon">
  <span class="prism-btn__text">Primary Action</span>
</button>

<!-- Secondary (Outline) Button -->
<button class="prism-btn prism-btn--outline">
  <span class="prism-btn__text">Secondary</span>
</button>

<!-- Ghost Button -->
<button class="prism-btn prism-btn--ghost">
  <span class="prism-btn__text">Ghost</span>
</button>

<!-- Link Button -->
<button class="prism-btn prism-btn--link">
  <span class="prism-btn__text">Link Style</span>
</button>
```

### Button Variants

| Class | Description |
|-------|-------------|
| `.prism-btn--solid` | Filled button with volumetric glow |
| `.prism-btn--outline` | Bordered button with transparent background |
| `.prism-btn--ghost` | Minimal button, shows glass on hover |
| `.prism-btn--link` | Text-only, underlines on hover |

### Button Sizes

```html
<button class="prism-btn prism-btn--solid prism-btn--xs">Extra Small (28px)</button>
<button class="prism-btn prism-btn--solid prism-btn--sm">Small (36px)</button>
<button class="prism-btn prism-btn--solid">Medium (44px - default)</button>
<button class="prism-btn prism-btn--solid prism-btn--lg">Large (52px)</button>
<button class="prism-btn prism-btn--solid prism-btn--xl">Extra Large (60px)</button>
```

### Button with Icons

```html
<!-- Icon on Left -->
<button class="prism-btn prism-btn--solid prism-btn--icon-left">
  <span class="prism-btn__icon">
    <svg><!-- icon --></svg>
  </span>
  <span class="prism-btn__text">With Icon</span>
</button>

<!-- Icon on Right -->
<button class="prism-btn prism-btn--solid prism-btn--icon-right">
  <span class="prism-btn__text">With Icon</span>
  <span class="prism-btn__icon">
    <svg><!-- icon --></svg>
  </span>
</button>

<!-- Icon Only -->
<button class="prism-btn prism-btn--solid prism-btn--icon-only">
  <span class="prism-btn__icon">
    <svg><!-- icon --></svg>
  </span>
</button>
```

### Button States

```html
<!-- Loading State -->
<button class="prism-btn prism-btn--solid prism-btn--loading">
  <span class="prism-btn__spinner"></span>
  <span class="prism-btn__text">Loading</span>
</button>

<!-- Disabled State -->
<button class="prism-btn prism-btn--solid" disabled>
  <span class="prism-btn__text">Disabled</span>
</button>

<!-- Error State -->
<button class="prism-btn prism-btn--solid prism-btn--error">
  <span class="prism-btn__text">Error</span>
</button>

<!-- Success State -->
<button class="prism-btn prism-btn--solid prism-btn--success">
  <span class="prism-btn__text">Success</span>
</button>
```

### Button Group

```html
<div class="prism-btn-group">
  <button class="prism-btn">Left</button>
  <button class="prism-btn">Center</button>
  <button class="prism-btn">Right</button>
</div>
```

### Colony Colors

Apply colony theming with `data-colony` attribute:

```html
<button class="prism-btn prism-btn--solid" data-colony="spark">Spark</button>
<button class="prism-btn prism-btn--solid" data-colony="forge">Forge</button>
<button class="prism-btn prism-btn--solid" data-colony="flow">Flow</button>
<button class="prism-btn prism-btn--solid" data-colony="nexus">Nexus</button>
<button class="prism-btn prism-btn--solid" data-colony="beacon">Beacon</button>
<button class="prism-btn prism-btn--solid" data-colony="grove">Grove</button>
<button class="prism-btn prism-btn--solid" data-colony="crystal">Crystal</button>
```

---

## Input Fields

### Text Field

Glass-effect text inputs with focus animations and validation states.

```html
<!-- Basic Text Field -->
<div class="prism-text-field">
  <label class="prism-text-field__label">Label</label>
  <div class="prism-text-field__container">
    <input type="text" class="prism-text-field__input" placeholder="Enter text...">
  </div>
</div>

<!-- With Helper Text -->
<div class="prism-text-field">
  <label class="prism-text-field__label">Email</label>
  <div class="prism-text-field__container">
    <input type="email" class="prism-text-field__input" placeholder="you@example.com">
  </div>
  <span class="prism-text-field__helper">We'll never share your email</span>
</div>

<!-- Required Field -->
<div class="prism-text-field">
  <label class="prism-text-field__label prism-text-field__label--required">Username</label>
  <div class="prism-text-field__container">
    <input type="text" class="prism-text-field__input" required>
  </div>
</div>
```

### Text Field with Icons

```html
<!-- Prefix Icon -->
<div class="prism-text-field">
  <label class="prism-text-field__label">Search</label>
  <div class="prism-text-field__container">
    <span class="prism-text-field__prefix">
      <span class="prism-text-field__icon">
        <svg><!-- search icon --></svg>
      </span>
    </span>
    <input type="text" class="prism-text-field__input" placeholder="Search...">
  </div>
</div>

<!-- Suffix with Clear Button -->
<div class="prism-text-field">
  <div class="prism-text-field__container">
    <input type="text" class="prism-text-field__input" value="Some text">
    <button class="prism-text-field__clear">
      <svg><!-- x icon --></svg>
    </button>
  </div>
</div>
```

### Text Field States

```html
<!-- Error State -->
<div class="prism-text-field prism-text-field--error">
  <label class="prism-text-field__label">Password</label>
  <div class="prism-text-field__container">
    <input type="password" class="prism-text-field__input">
  </div>
  <span class="prism-text-field__helper">Password must be at least 8 characters</span>
</div>

<!-- Success State -->
<div class="prism-text-field prism-text-field--success">
  <label class="prism-text-field__label">Username</label>
  <div class="prism-text-field__container">
    <input type="text" class="prism-text-field__input" value="available_name">
  </div>
  <span class="prism-text-field__helper">Username is available</span>
</div>

<!-- Disabled State -->
<div class="prism-text-field prism-text-field--disabled">
  <label class="prism-text-field__label">Disabled</label>
  <div class="prism-text-field__container prism-text-field__container--disabled">
    <input type="text" class="prism-text-field__input" disabled value="Cannot edit">
  </div>
</div>

<!-- Loading State -->
<div class="prism-text-field prism-text-field--loading">
  <label class="prism-text-field__label">Validating</label>
  <div class="prism-text-field__container">
    <input type="text" class="prism-text-field__input">
    <div class="prism-text-field__spinner"></div>
  </div>
</div>
```

### Text Field Sizes

```html
<div class="prism-text-field prism-text-field--sm"><!-- Small: 36px --></div>
<div class="prism-text-field"><!-- Medium: 44px (default) --></div>
<div class="prism-text-field prism-text-field--lg"><!-- Large: 52px --></div>
```

### Text Field Variants

```html
<!-- Filled Variant -->
<div class="prism-text-field prism-text-field--filled">
  <label class="prism-text-field__label">Filled Input</label>
  <div class="prism-text-field__container">
    <input type="text" class="prism-text-field__input">
  </div>
</div>

<!-- Underline Variant -->
<div class="prism-text-field prism-text-field--underline">
  <label class="prism-text-field__label">Underline Input</label>
  <div class="prism-text-field__container">
    <input type="text" class="prism-text-field__input">
  </div>
</div>
```

### Switch (Toggle)

iOS-quality toggle with elastic physics.

```html
<!-- Basic Switch -->
<label class="prism-switch">
  <input type="checkbox" class="prism-switch__input">
  <span class="prism-switch__track">
    <span class="prism-switch__thumb"></span>
  </span>
  <div class="prism-switch__content">
    <span class="prism-switch__label">Enable notifications</span>
    <span class="prism-switch__description">Receive push notifications</span>
  </div>
</label>

<!-- Switch with Colony Color -->
<label class="prism-switch" data-colony="nexus">
  <input type="checkbox" class="prism-switch__input" checked>
  <span class="prism-switch__track">
    <span class="prism-switch__thumb"></span>
  </span>
  <span class="prism-switch__label">Custom color</span>
</label>
```

### Switch Sizes

```html
<label class="prism-switch prism-switch--sm"><!-- 42x26 --></label>
<label class="prism-switch"><!-- 51x31 (iOS default) --></label>
<label class="prism-switch prism-switch--lg"><!-- 61x37 --></label>
```

---

## Cards and Surfaces

### Card

The quintessential container with glass effects.

```html
<!-- Basic Card -->
<div class="prism-card prism-card--md prism-card--elevated">
  <div class="prism-card__content">
    <h3 class="prism-card__title">Card Title</h3>
    <p class="prism-card__subtitle">Optional subtitle</p>
    <div class="prism-card__body">
      Card content goes here.
    </div>
  </div>
</div>

<!-- Full Card Structure -->
<div class="prism-card prism-card--md prism-card--glass">
  <div class="prism-card__media">
    <img src="image.jpg" alt="Card image">
  </div>
  <div class="prism-card__content">
    <header class="prism-card__header">
      <h3 class="prism-card__title">Card Title</h3>
      <p class="prism-card__subtitle">Subtitle text</p>
    </header>
    <div class="prism-card__body">
      <p>Main content of the card.</p>
    </div>
    <footer class="prism-card__footer">
      <button class="prism-btn prism-btn--ghost">Cancel</button>
      <button class="prism-btn prism-btn--solid">Action</button>
    </footer>
  </div>
</div>
```

### Card Variants

```html
<!-- Elevated (default) - Subtle shadow -->
<div class="prism-card prism-card--elevated">...</div>

<!-- Glass - Enhanced transparency with chromatic shadow -->
<div class="prism-card prism-card--glass">...</div>

<!-- Outlined - Border emphasis -->
<div class="prism-card prism-card--outlined">...</div>

<!-- Filled - Solid background -->
<div class="prism-card prism-card--filled">...</div>
```

### Card Sizes

```html
<div class="prism-card prism-card--sm"><!-- 12px padding, smaller radius --></div>
<div class="prism-card prism-card--md"><!-- 16px padding (default) --></div>
<div class="prism-card prism-card--lg"><!-- 24px padding, larger radius --></div>
```

### Interactive Card

```html
<div class="prism-card prism-card--interactive" tabindex="0" role="button">
  <div class="prism-card__content">
    Click me!
  </div>
</div>
```

### Card with Colony Accent

```html
<div class="prism-card prism-card--glass" data-colony="nexus">
  <!-- Border and hover glow will use nexus color -->
</div>
```

---

## Modals and Dialogs

### Dialog

Spring-based entry with focus trap and gesture support.

```html
<!-- Dialog Structure -->
<div class="prism-dialog-backdrop prism-dialog-backdrop--open">
  <div class="prism-dialog" role="dialog" aria-modal="true" aria-labelledby="dialog-title">
    <div class="prism-dialog__reflection"></div>

    <header class="prism-dialog__header">
      <div class="prism-dialog__header-content">
        <h2 class="prism-dialog__title" id="dialog-title">Dialog Title</h2>
        <p class="prism-dialog__description">Optional description text</p>
      </div>
      <button class="prism-dialog__close" aria-label="Close">
        <svg class="prism-dialog__close-icon"><!-- x icon --></svg>
      </button>
    </header>

    <div class="prism-dialog__content">
      <p>Dialog content goes here.</p>
    </div>

    <footer class="prism-dialog__footer">
      <button class="prism-btn prism-btn--ghost">Cancel</button>
      <button class="prism-btn prism-btn--solid">Confirm</button>
    </footer>
  </div>
</div>
```

### Dialog Sizes

```html
<div class="prism-dialog prism-dialog--sm"><!-- 400px max-width --></div>
<div class="prism-dialog"><!-- 500px (default) --></div>
<div class="prism-dialog prism-dialog--lg"><!-- 700px --></div>
<div class="prism-dialog prism-dialog--xl"><!-- 900px --></div>
<div class="prism-dialog prism-dialog--full"><!-- Full viewport --></div>
```

### Confirmation Dialog

```html
<div class="prism-dialog prism-dialog--confirm">
  <div class="prism-dialog__content">
    <div class="prism-dialog__icon">
      <svg><!-- warning/info icon --></svg>
    </div>
    <h2 class="prism-dialog__title">Are you sure?</h2>
    <p class="prism-dialog__description">This action cannot be undone.</p>
  </div>
  <footer class="prism-dialog__footer">
    <button class="prism-btn prism-btn--ghost">Cancel</button>
    <button class="prism-btn prism-btn--solid" data-colony="spark">Delete</button>
  </footer>
</div>
```

### Dialog States

```html
<!-- Opening -->
<div class="prism-dialog-backdrop prism-dialog-backdrop--open">
  <!-- Spring animation plays automatically -->
</div>

<!-- Closing -->
<div class="prism-dialog-backdrop prism-dialog-backdrop--closing">
  <!-- Exit animation plays -->
</div>

<!-- Destructive -->
<div class="prism-dialog prism-dialog--destructive">
  <!-- Red-tinted icon container -->
</div>
```

---

## Navigation

### Sidebar

Collapsible sidebar with glass styling and nested items.

```html
<nav class="prism-sidebar">
  <header class="prism-sidebar__header">
    <div class="prism-sidebar__logo">
      <img class="prism-sidebar__logo-icon" src="logo.svg" alt="">
      <span class="prism-sidebar__logo-text">Kagami</span>
    </div>
    <button class="prism-sidebar__toggle">
      <svg class="prism-sidebar__toggle-icon"><!-- chevron --></svg>
    </button>
  </header>

  <div class="prism-sidebar__content">
    <div class="prism-sidebar__nav">
      <div class="prism-sidebar__section">
        <span class="prism-sidebar__section-title">Main</span>

        <a href="#" class="prism-sidebar__item prism-sidebar__item--active" data-tooltip="Dashboard">
          <svg class="prism-sidebar__item-icon"><!-- icon --></svg>
          <span class="prism-sidebar__item-label">Dashboard</span>
        </a>

        <a href="#" class="prism-sidebar__item" data-tooltip="Settings">
          <svg class="prism-sidebar__item-icon"><!-- icon --></svg>
          <span class="prism-sidebar__item-label">Settings</span>
          <span class="prism-sidebar__item-badge">3</span>
        </a>
      </div>
    </div>
  </div>

  <footer class="prism-sidebar__footer">
    <div class="prism-sidebar__user">
      <img class="prism-sidebar__user-avatar" src="avatar.jpg" alt="">
      <div class="prism-sidebar__user-info">
        <span class="prism-sidebar__user-name">Tim Jacoby</span>
        <span class="prism-sidebar__user-email">tim@example.com</span>
      </div>
    </div>
  </footer>
</nav>
```

### Sidebar with Submenu

```html
<div class="prism-sidebar__item prism-sidebar__item--expanded">
  <svg class="prism-sidebar__item-icon"><!-- icon --></svg>
  <span class="prism-sidebar__item-label">Projects</span>
  <svg class="prism-sidebar__expand-icon"><!-- chevron-right --></svg>
</div>
<div class="prism-sidebar__submenu prism-sidebar__submenu--open">
  <div class="prism-sidebar__submenu-inner">
    <a href="#" class="prism-sidebar__submenu-item">Project Alpha</a>
    <a href="#" class="prism-sidebar__submenu-item prism-sidebar__submenu-item--active">Project Beta</a>
    <a href="#" class="prism-sidebar__submenu-item">Project Gamma</a>
  </div>
</div>
```

### Collapsed Sidebar

```html
<nav class="prism-sidebar prism-sidebar--collapsed">
  <!-- Tooltips appear on hover when collapsed -->
</nav>
```

### Tabs

Tab navigation with chromatic underline animations.

```html
<!-- Basic Tabs -->
<div class="prism-tabs">
  <ul class="prism-tabs__list" role="tablist">
    <li>
      <button class="prism-tabs__trigger prism-tabs__trigger--active"
              role="tab" aria-selected="true">
        Tab One
      </button>
    </li>
    <li>
      <button class="prism-tabs__trigger" role="tab">Tab Two</button>
    </li>
    <li>
      <button class="prism-tabs__trigger" role="tab">Tab Three</button>
    </li>
  </ul>

  <div class="prism-tabs__panel" role="tabpanel">
    Content for tab one.
  </div>
</div>
```

### Tab Variants

```html
<!-- Underline Style -->
<div class="prism-tabs prism-tabs--underline">...</div>

<!-- Pill Style -->
<div class="prism-tabs prism-tabs--pill">...</div>

<!-- Vertical Tabs -->
<div class="prism-tabs prism-tabs--vertical">...</div>

<!-- Animated Indicator -->
<div class="prism-tabs prism-tabs--animated">
  <div class="prism-tabs__indicator"></div>
  <!-- tabs -->
</div>
```

### Tabs with Icons and Badges

```html
<button class="prism-tabs__trigger">
  <svg class="prism-tabs__icon"><!-- icon --></svg>
  <span>Messages</span>
  <span class="prism-tabs__badge">5</span>
</button>
```

---

## Feedback Components

### Toast Notifications

Spring-based entry with swipe-to-dismiss.

```html
<!-- Toast Container -->
<div class="prism-toast-container prism-toast-container--top-right">

  <!-- Success Toast -->
  <div class="prism-toast prism-toast--success prism-toast--entering">
    <span class="prism-toast__icon">
      <svg><!-- check icon --></svg>
    </span>
    <div class="prism-toast__content">
      <p class="prism-toast__title">Success!</p>
      <p class="prism-toast__message">Your changes have been saved.</p>
    </div>
    <button class="prism-toast__dismiss">
      <svg><!-- x icon --></svg>
    </button>
    <div class="prism-toast__progress">
      <div class="prism-toast__progress-bar" style="animation-duration: 5s"></div>
    </div>
  </div>

</div>
```

### Toast Variants

```html
<!-- Info -->
<div class="prism-toast prism-toast--info">...</div>

<!-- Success -->
<div class="prism-toast prism-toast--success">...</div>

<!-- Warning -->
<div class="prism-toast prism-toast--warning">...</div>

<!-- Error -->
<div class="prism-toast prism-toast--error">...</div>
```

### Toast Positions

```html
<div class="prism-toast-container prism-toast-container--top-left">...</div>
<div class="prism-toast-container prism-toast-container--top-center">...</div>
<div class="prism-toast-container prism-toast-container--top-right">...</div>
<div class="prism-toast-container prism-toast-container--bottom-left">...</div>
<div class="prism-toast-container prism-toast-container--bottom-center">...</div>
<div class="prism-toast-container prism-toast-container--bottom-right">...</div>
```

### Toast with Actions

```html
<div class="prism-toast prism-toast--info">
  <div class="prism-toast__content">
    <p class="prism-toast__title">Update available</p>
    <p class="prism-toast__message">A new version is ready to install.</p>
    <div class="prism-toast__actions">
      <button class="prism-toast__action">Install Now</button>
      <button class="prism-toast__action">Later</button>
    </div>
  </div>
</div>
```

### Badge

Status indicators and labels.

```html
<!-- Basic Badge -->
<span class="prism-badge prism-badge--md prism-badge--solid">Badge</span>

<!-- With Icon -->
<span class="prism-badge prism-badge--md prism-badge--subtle prism-badge--success">
  <svg class="prism-badge__icon"><!-- check icon --></svg>
  Active
</span>

<!-- Dot Indicator -->
<span class="prism-badge prism-badge--dot prism-badge--success"></span>

<!-- Pulsing Badge (for live status) -->
<span class="prism-badge prism-badge--md prism-badge--solid prism-badge--success prism-badge--pulse">
  Live
</span>
```

### Badge Variants

```html
<!-- Styles -->
<span class="prism-badge prism-badge--solid">Solid</span>
<span class="prism-badge prism-badge--subtle">Subtle</span>
<span class="prism-badge prism-badge--outline">Outline</span>
<span class="prism-badge prism-badge--dot"></span>

<!-- Colors -->
<span class="prism-badge prism-badge--solid prism-badge--success">Success</span>
<span class="prism-badge prism-badge--solid prism-badge--error">Error</span>
<span class="prism-badge prism-badge--solid prism-badge--warning">Warning</span>
<span class="prism-badge prism-badge--solid prism-badge--info">Info</span>

<!-- Colony Colors -->
<span class="prism-badge prism-badge--solid prism-badge--spark">Spark</span>
<span class="prism-badge prism-badge--solid prism-badge--grove">Grove</span>
<span class="prism-badge prism-badge--solid prism-badge--crystal">Crystal</span>
```

---

## Color Usage

### Text Colors

```css
/* Primary text - white */
color: var(--prism-text-primary);

/* Secondary text - 70% opacity */
color: var(--prism-text-secondary);

/* Tertiary text - 40% opacity */
color: var(--prism-text-tertiary);

/* Disabled text - 25% opacity */
color: var(--prism-text-disabled);
```

### Semantic Colors

```css
/* Success states */
color: var(--prism-success);          /* #32D74B */
background: var(--prism-success-light); /* 15% opacity */

/* Warning states */
color: var(--prism-warning);          /* #FFD60A */
background: var(--prism-warning-light);

/* Error states */
color: var(--prism-error);            /* #FF3B30 */
background: var(--prism-error-light);

/* Info states */
color: var(--prism-info);             /* #5AC8FA */
background: var(--prism-info-light);
```

### Colony Colors at 8% Opacity (for backgrounds)

```css
background: var(--prism-spark-08);
background: var(--prism-forge-08);
background: var(--prism-flow-08);
background: var(--prism-nexus-08);
background: var(--prism-beacon-08);
background: var(--prism-grove-08);
background: var(--prism-crystal-08);
```

### Gradients

```css
/* Full spectrum gradient */
background: var(--prism-gradient-spectrum);

/* Chromatic aberration effects */
background: var(--prism-gradient-red-shift);
background: var(--prism-gradient-blue-shift);

/* Light caustics */
background: var(--prism-gradient-caustics);
```

---

## Typography

### Font Families

```css
/* Primary sans-serif */
font-family: var(--prism-font-sans);
/* "Inter", "SF Pro", -apple-system, BlinkMacSystemFont, sans-serif */

/* Monospace */
font-family: var(--prism-font-mono);
/* "JetBrains Mono", "SF Mono", "Fira Code", monospace */

/* Display/Headers */
font-family: var(--prism-font-display);
/* "Newsreader", Georgia, serif */

/* Japanese */
font-family: var(--prism-font-jp);
/* "Noto Sans JP", sans-serif */
```

### Font Sizes

| Token | Value | Usage |
|-------|-------|-------|
| `--prism-text-xs` | 11px | Badges, captions |
| `--prism-text-sm` | 13px | Helper text, labels |
| `--prism-text-base` | 15px | Body text |
| `--prism-text-md` | 17px | Emphasized body |
| `--prism-text-lg` | 20px | Subheadings |
| `--prism-text-xl` | 24px | Headings |
| `--prism-text-2xl` | 28px | Large headings |
| `--prism-text-3xl` | 34px | Display headings |

### Font Weights

```css
font-weight: var(--prism-font-regular);  /* 400 */
font-weight: var(--prism-font-medium);   /* 500 */
font-weight: var(--prism-font-semibold); /* 600 */
font-weight: var(--prism-font-bold);     /* 700 */
```

### Letter Spacing

```css
letter-spacing: var(--prism-tracking-tight);  /* -0.02em */
letter-spacing: var(--prism-tracking-normal); /* 0 */
letter-spacing: var(--prism-tracking-wide);   /* 0.05em */
```

### Line Heights

```css
line-height: var(--prism-leading-none);    /* 1 */
line-height: var(--prism-leading-tight);   /* 1.25 */
line-height: var(--prism-leading-normal);  /* 1.5 */
line-height: var(--prism-leading-relaxed); /* 1.75 */
```

---

## Spacing

Based on an 8px grid system.

| Token | Value | Usage |
|-------|-------|-------|
| `--prism-space-0-5` | 2px | Hairline spacing |
| `--prism-space-1` | 4px | Tight inline spacing |
| `--prism-space-1-5` | 6px | Badge padding |
| `--prism-space-2` | 8px | Base unit |
| `--prism-space-2-5` | 10px | Button icon gap |
| `--prism-space-3` | 12px | Card section gaps |
| `--prism-space-4` | 16px | Standard padding |
| `--prism-space-5` | 20px | Content spacing |
| `--prism-space-6` | 24px | Dialog padding |
| `--prism-space-7` | 28px | Large component padding |
| `--prism-space-8` | 32px | Section spacing |
| `--prism-space-10` | 40px | Large gaps |
| `--prism-space-12` | 48px | Page sections |
| `--prism-space-16` | 64px | Major sections |

### Border Radius

| Token | Value | Usage |
|-------|-------|-------|
| `--prism-radius-xs` | 4px | Small elements, badges |
| `--prism-radius-sm` | 8px | Buttons (sm), inputs |
| `--prism-radius-md` | 12px | Buttons (md), cards (sm) |
| `--prism-radius-lg` | 16px | Buttons (lg), cards (md) |
| `--prism-radius-xl` | 24px | Cards (default), dialogs |
| `--prism-radius-2xl` | 32px | Large cards |
| `--prism-radius-full` | 9999px | Pills, avatars |

---

## Animation Timing

All animations use standard timing for natural feel.

### Durations

| Token | Value | Usage |
|-------|-------|-------|
| `--prism-dur-instant` | 50ms | Immediate feedback |
| `--prism-dur-micro` | 89ms | Micro-interactions, hover states |
| `--prism-dur-fast` | 144ms | Fast transitions, button states |
| `--prism-dur-normal` | 233ms | Standard transitions |
| `--prism-dur-medium` | 377ms | Modal appear, complex reveals |
| `--prism-dur-slow` | 610ms | Sidebar collapse, page transitions |
| `--prism-dur-slower` | 987ms | Ambient motion |
| `--prism-dur-slowest` | 1597ms | Loading states |
| `--prism-dur-breathing` | 2584ms | Breathing/pulse effects |

### Easing Curves

| Token | Value | Usage |
|-------|-------|-------|
| `--prism-ease-cusp` | `cubic-bezier(0.4, 0.0, 0.2, 1.0)` | Standard easing |
| `--prism-ease-fold` | `cubic-bezier(0.0, 0.0, 0.2, 1.0)` | Decelerate (entrances) |
| `--prism-ease-swallowtail` | `cubic-bezier(0.4, 0.0, 1.0, 1.0)` | Accelerate (exits) |
| `--prism-ease-butterfly` | `cubic-bezier(0.4, 0.0, 0.6, 1.0)` | Sharp transitions |
| `--prism-ease-spring` | `cubic-bezier(0.34, 1.56, 0.64, 1.0)` | Overshoot (bouncy) |

### Animation Examples

```css
/* Standard hover transition */
transition: background var(--prism-dur-fast) var(--prism-ease-cusp);

/* Button press with spring */
transition: transform var(--prism-dur-fast) var(--prism-ease-spring);

/* Modal entrance */
transition: opacity var(--prism-dur-medium) var(--prism-ease-fold);

/* Sidebar collapse */
transition: width var(--prism-dur-slow) var(--prism-ease-spring);
```

### Respecting Reduced Motion

All components include reduced motion support:

```css
@media (prefers-reduced-motion: reduce) {
  .component {
    transition: none;
    animation: none;
  }
}
```

---

## Z-Index Layers

| Token | Value | Usage |
|-------|-------|-------|
| `--prism-z-base` | 0 | Default stacking |
| `--prism-z-dropdown` | 100 | Dropdown menus |
| `--prism-z-sticky` | 200 | Sticky headers |
| `--prism-z-modal-backdrop` | 299 | Modal backdrop |
| `--prism-z-modal` | 300 | Modal dialogs |
| `--prism-z-popover` | 400 | Popovers |
| `--prism-z-tooltip` | 500 | Tooltips |
| `--prism-z-toast` | 600 | Toast notifications |

---

## Accessibility

All components follow WCAG 2.1 AA standards:

- Text colors meet 4.5:1 contrast ratio on `--prism-void` background
- Touch targets are minimum 44x44px (`--prism-touch-target`)
- Focus states use visible outlines with chromatic rings
- Reduced motion is respected via `prefers-reduced-motion` media query
- Semantic HTML and ARIA attributes for screen readers

### Focus Ring Pattern

```css
.component:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px color-mix(
    in srgb,
    var(--colony-color, var(--prism-beacon)) 40%,
    transparent
  );
}
```

---

## Component Index

| Component | CSS File |
|-----------|----------|
| Button | `css/components/actions/button.css` |
| Icon Button | `css/components/actions/icon-button.css` |
| FAB | `css/components/actions/fab.css` |
| Toggle | `css/components/actions/toggle.css` |
| Text Field | `css/components/inputs/text-field.css` |
| Textarea | `css/components/inputs/textarea.css` |
| Select | `css/components/inputs/select.css` |
| Checkbox | `css/components/inputs/checkbox.css` |
| Radio | `css/components/inputs/radio.css` |
| Switch | `css/components/inputs/switch.css` |
| Slider | `css/components/inputs/slider.css` |
| Search | `css/components/inputs/search.css` |
| Card | `css/components/data-display/card.css` |
| Badge | `css/components/data-display/badge.css` |
| Avatar | `css/components/data-display/avatar.css` |
| List | `css/components/data-display/list.css` |
| Table | `css/components/data-display/table.css` |
| Tag | `css/components/data-display/tag.css` |
| Dialog | `css/components/overlays/dialog.css` |
| Alert Dialog | `css/components/overlays/alert-dialog.css` |
| Drawer | `css/components/overlays/drawer.css` |
| Sheet | `css/components/overlays/sheet.css` |
| Popover | `css/components/overlays/popover.css` |
| Tooltip | `css/components/overlays/tooltip.css` |
| Dropdown Menu | `css/components/overlays/dropdown-menu.css` |
| Context Menu | `css/components/overlays/context-menu.css` |
| Toast | `css/components/feedback/toast.css` |
| Alert | `css/components/feedback/alert.css` |
| Progress Bar | `css/components/feedback/progress-bar.css` |
| Spinner | `css/components/feedback/spinner.css` |
| Skeleton | `css/components/feedback/skeleton.css` |
| Sidebar | `css/components/navigation/sidebar.css` |
| Tabs | `css/components/navigation/tabs.css` |
| App Bar | `css/components/navigation/app-bar.css` |
| Breadcrumb | `css/components/navigation/breadcrumb.css` |
| Pagination | `css/components/navigation/pagination.css` |

---

*Kagami Design System V2*
