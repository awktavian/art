"""
Prismorphism Generator

Generate beautiful glass interfaces with Fano-derived chromatic effects.
Supports desktop, AR, Watch, and transmissive display platforms.

鏡
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Fano spectral mapping — colonies to wavelengths
FANO_SPECTRAL_MAP = {
    "spark": {"basis": "e1", "wavelength": 620, "hex": "#FF4136", "rgb": (255, 65, 54)},
    "forge": {"basis": "e2", "wavelength": 590, "hex": "#FF851B", "rgb": (255, 133, 27)},
    "flow": {"basis": "e3", "wavelength": 570, "hex": "#FFDC00", "rgb": (255, 220, 0)},
    "nexus": {"basis": "e4", "wavelength": 510, "hex": "#2ECC40", "rgb": (46, 204, 64)},
    "beacon": {"basis": "e5", "wavelength": 475, "hex": "#00D4FF", "rgb": (0, 212, 255)},
    "grove": {"basis": "e6", "wavelength": 445, "hex": "#0074D9", "rgb": (0, 116, 217)},
    "crystal": {"basis": "e7", "wavelength": 400, "hex": "#B10DC9", "rgb": (177, 13, 201)},
}

COLONY_NAMES = list(FANO_SPECTRAL_MAP.keys())

# Fano lines — colony composition relationships
FANO_LINES = [
    ("spark", "forge", "flow"),  # e1 × e2 = e3
    ("spark", "nexus", "beacon"),  # e1 × e4 = e5
    ("spark", "crystal", "grove"),  # e1 × e7 = e6
    ("forge", "nexus", "grove"),  # e2 × e4 = e6
    ("forge", "beacon", "crystal"),  # e2 × e5 = e7
    ("flow", "nexus", "crystal"),  # e3 × e4 = e7
    ("flow", "grove", "beacon"),  # e3 × e6 = e5
]


class Platform(Enum):
    """Target platform for generated interfaces."""

    DESKTOP = "desktop"
    AR = "ar"
    WATCH = "watch"
    TRANSMISSIVE = "transmissive"


class GlassVariant(Enum):
    """Glass opacity variants."""

    SOLID = "solid"
    MEDIUM = "medium"
    LIGHT = "light"
    ETHEREAL = "ethereal"


@dataclass
class PrismConfig:
    """Configuration for Prismorphism generation."""

    platform: Platform = Platform.DESKTOP
    glass_variant: GlassVariant = GlassVariant.MEDIUM
    enable_caustics: bool = True
    enable_particles: bool = True
    enable_cursor: bool = True
    dark_mode: bool = True
    reduced_motion: bool = False

    @property
    def blur_radius(self) -> int:
        """Get blur radius for platform."""
        return {
            Platform.DESKTOP: 20,
            Platform.AR: 40,
            Platform.WATCH: 8,
            Platform.TRANSMISSIVE: 0,
        }[self.platform]

    @property
    def dispersion_width(self) -> int:
        """Get dispersion width for platform."""
        return {
            Platform.DESKTOP: 3,
            Platform.AR: 5,
            Platform.WATCH: 0,
            Platform.TRANSMISSIVE: 4,
        }[self.platform]


@dataclass
class CardData:
    """Data for a Prism card component."""

    title: str
    content: str = ""
    subtitle: str = ""
    colony: str | None = None
    size: str = "md"  # sm, md, lg
    footer: str = ""
    icon: str = ""


@dataclass
class ButtonData:
    """Data for a Prism button component."""

    label: str
    colony: str | None = None
    variant: str = "default"  # default, primary, ghost
    size: str = "md"  # sm, md, lg
    icon: str = ""


@dataclass
class ModalData:
    """Data for a Prism modal component."""

    title: str
    content: str
    colony: str | None = None
    size: str = "md"  # sm, md, lg, full
    footer_buttons: list[ButtonData] = field(default_factory=list)


class PrismorphismGenerator:
    """Generate Prismorphism-styled HTML interfaces."""

    def __init__(self, config: PrismConfig | None = None):
        self.config = config or PrismConfig()

    def get_spectral_color(self, colony: str) -> str:
        """Get the hex color for a colony."""
        if colony in FANO_SPECTRAL_MAP:
            return FANO_SPECTRAL_MAP[colony]["hex"]
        return "#F59E0B"  # Default amber

    def get_colony_basis(self, colony: str) -> str:
        """Get the Fano basis for a colony."""
        if colony in FANO_SPECTRAL_MAP:
            return FANO_SPECTRAL_MAP[colony]["basis"]
        return "e0"

    def _escape(self, text: str) -> str:
        """Escape HTML entities."""
        return html.escape(text)

    def _platform_class(self) -> str:
        """Get platform-specific CSS class."""
        return f"prism-platform-{self.config.platform.value}"

    def render_card(self, data: CardData) -> str:
        """Render a Prism card component."""
        colony_attr = f'data-colony="{data.colony}"' if data.colony else ""
        size_class = f"prism-card--{data.size}" if data.size != "md" else ""

        icon_html = ""
        if data.icon:
            icon_html = f'<span class="prism-card__icon">{self._escape(data.icon)}</span>'

        subtitle_html = ""
        if data.subtitle:
            subtitle_html = f'<p class="prism-card__subtitle">{self._escape(data.subtitle)}</p>'

        footer_html = ""
        if data.footer:
            footer_html = f'<div class="prism-card__footer">{data.footer}</div>'

        return f"""<div class="prism-card {size_class}" {colony_attr}>
  <div class="prism-card__header">
    {icon_html}
    <h3 class="prism-card__title">{self._escape(data.title)}</h3>
    {subtitle_html}
  </div>
  <div class="prism-card__content">
    {data.content}
  </div>
  {footer_html}
</div>"""

    def render_button(self, data: ButtonData) -> str:
        """Render a Prism button component."""
        colony_attr = f'data-colony="{data.colony}"' if data.colony else ""
        variant_class = f"prism-button--{data.variant}" if data.variant != "default" else ""
        size_class = f"prism-button--{data.size}" if data.size != "md" else ""

        icon_html = ""
        if data.icon:
            icon_html = f'<span class="prism-button__icon">{self._escape(data.icon)}</span>'

        return f"""<button class="prism-button {variant_class} {size_class}" {colony_attr}>
  {icon_html}
  <span class="prism-button__label">{self._escape(data.label)}</span>
</button>"""

    def render_modal(self, data: ModalData) -> str:
        """Render a Prism modal component."""
        colony_attr = f'data-colony="{data.colony}"' if data.colony else ""
        size_class = f"prism-modal--{data.size}" if data.size != "md" else ""

        footer_html = ""
        if data.footer_buttons:
            buttons = "\n".join(self.render_button(btn) for btn in data.footer_buttons)
            footer_html = f'<div class="prism-modal__footer">{buttons}</div>'

        return f"""<div class="prism-modal-backdrop">
  <div class="prism-modal {size_class}" {colony_attr}>
    <div class="prism-modal__header">
      <h2 class="prism-modal__title">{self._escape(data.title)}</h2>
      <button class="prism-modal__close" aria-label="Close">×</button>
    </div>
    <div class="prism-modal__content">
      {data.content}
    </div>
    {footer_html}
  </div>
</div>"""

    def render_nav(self, items: list[dict[str, Any]], vertical: bool = False) -> str:
        """Render a Prism navigation component."""
        vertical_class = "prism-nav--vertical" if vertical else ""

        nav_items = []
        for item in items:
            active_class = "prism-nav__item--active" if item.get("active") else ""
            href = item.get("href", "#")
            label = self._escape(item.get("label", ""))
            nav_items.append(f'<a href="{href}" class="prism-nav__item {active_class}">{label}</a>')

        return f"""<nav class="prism-nav {vertical_class}">
  {chr(10).join(nav_items)}
</nav>"""

    def render_caustics(self) -> str:
        """Render the caustics background effect."""
        if not self.config.enable_caustics or self.config.reduced_motion:
            return ""

        return """<div class="prism-caustics">
  <div class="prism-caustics__layer prism-caustics__layer--warm"></div>
  <div class="prism-caustics__layer prism-caustics__layer--mid"></div>
  <div class="prism-caustics__layer prism-caustics__layer--cool"></div>
</div>"""

    def render_particles(self, count: int = 21) -> str:
        """Render floating spectral particles."""
        if not self.config.enable_particles or self.config.reduced_motion:
            return ""

        particles = "\n".join('<div class="prism-particle"></div>' for _ in range(count))
        return f'<div class="prism-particles">{particles}</div>'

    def render_head(self, title: str = "Kagami") -> str:
        """Render the HTML head with all required CSS imports."""
        dark_class = "dark" if self.config.dark_mode else ""

        return f"""<!DOCTYPE html>
<html lang="en" class="{dark_class}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{self._escape(title)}</title>

  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">

  <!-- Prismorphism CSS -->
  <link rel="stylesheet" href="css/prism-tokens.css">
  <link rel="stylesheet" href="css/prism-components.css">
  <link rel="stylesheet" href="css/prism-effects.css">

  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--prism-surface);
      color: var(--prism-text);
      min-height: 100vh;
      overflow-x: hidden;
    }}

    .prism-container {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 48px 24px;
    }}

    .prism-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 24px;
    }}

    .prism-hero {{
      text-align: center;
      padding: 96px 24px;
    }}

    .prism-hero__title {{
      font-size: 3rem;
      font-weight: 700;
      margin-bottom: 16px;
      background: var(--prism-gradient-spectrum);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
    }}

    .prism-hero__subtitle {{
      font-size: 1.25rem;
      color: var(--prism-text-secondary);
      max-width: 600px;
      margin: 0 auto;
    }}
  </style>
</head>"""

    def render_scripts(self) -> str:
        """Render the JavaScript includes and initialization."""
        cursor_init = "cursor: true," if self.config.enable_cursor else "cursor: false,"
        caustics_init = "caustics: true," if self.config.enable_caustics else "caustics: false,"
        particles_init = "particles: true," if self.config.enable_particles else "particles: false,"

        return f"""<script type="module">
  import {{ initPrismorphism }} from './js/prism-refraction.js';

  // Initialize Prismorphism effects
  document.addEventListener('DOMContentLoaded', () => {{
    initPrismorphism({{
      {cursor_init}
      {caustics_init}
      {particles_init}
      ripples: true,
      refraction: false,
    }});

    // Expose to console for debugging
    window.鏡 = {{
      spectrum: {FANO_SPECTRAL_MAP!s},
      fanoLines: {FANO_LINES!s},
      platform: '{self.config.platform.value}',
      philosophy: 'Light bends. Color separates. Mathematics becomes visible.',
    }};

    console.log('%c鏡 Prismorphism', 'font-size: 24px; font-weight: bold; background: linear-gradient(135deg, #FF4136, #FF851B, #FFDC00, #2ECC40, #00D4FF, #0074D9, #B10DC9); -webkit-background-clip: text; -webkit-text-fill-color: transparent;');
    console.log('Light bends. Color separates. Mathematics becomes visible.');
  }});
</script>"""

    def render_page(
        self,
        title: str,
        content: str,
        hero_title: str = "",
        hero_subtitle: str = "",
    ) -> str:
        """Render a complete Prismorphism page."""
        head = self.render_head(title)
        caustics = self.render_caustics()
        particles = self.render_particles()
        scripts = self.render_scripts()

        hero_html = ""
        if hero_title:
            hero_html = f"""<div class="prism-hero">
  <h1 class="prism-hero__title">{self._escape(hero_title)}</h1>
  <p class="prism-hero__subtitle">{self._escape(hero_subtitle)}</p>
</div>"""

        return f"""{head}
<body class="{self._platform_class()}">
  {caustics}
  {particles}

  {hero_html}

  <main class="prism-container">
    {content}
  </main>

  <!-- Hidden Fano structure for discovery -->
  <svg class="prism-fano-svg" style="display: none;" viewBox="0 0 100 100">
    <defs>
      <linearGradient id="gradient-123" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#FF4136"/>
        <stop offset="50%" stop-color="#FF851B"/>
        <stop offset="100%" stop-color="#FFDC00"/>
      </linearGradient>
      <!-- Additional gradients for all Fano lines -->
    </defs>
    <!-- Fano plane structure encoded in SVG -->
    <circle cx="50" cy="15" r="5" fill="#FF4136" data-basis="e1"/>
    <circle cx="25" cy="40" r="5" fill="#2ECC40" data-basis="e4"/>
    <circle cx="75" cy="40" r="5" fill="#FF851B" data-basis="e2"/>
    <circle cx="15" cy="75" r="5" fill="#0074D9" data-basis="e6"/>
    <circle cx="50" cy="75" r="5" fill="#B10DC9" data-basis="e7"/>
    <circle cx="50" cy="50" r="5" fill="#FFDC00" data-basis="e3"/>
    <circle cx="85" cy="75" r="5" fill="#00D4FF" data-basis="e5"/>
  </svg>

  {scripts}

  <!-- 鏡 -->
</body>
</html>"""

    def render_colony_cards(self) -> str:
        """Render cards for all seven colonies."""
        cards = []
        colony_info = {
            "spark": ("🔥", "The Igniter", "Ideation and creativity"),
            "forge": ("⚒️", "The Builder", "Implementation and construction"),
            "flow": ("🌊", "The Healer", "Debugging and recovery"),
            "nexus": ("🔗", "The Bridge", "Integration and connection"),
            "beacon": ("🗼", "The Architect", "Planning and design"),
            "grove": ("🌿", "The Scholar", "Research and learning"),
            "crystal": ("💎", "The Judge", "Verification and testing"),
        }

        for colony, (icon, title, desc) in colony_info.items():
            card = self.render_card(
                CardData(
                    title=title,
                    subtitle=f"{icon} {colony.title()}",
                    content=f"<p>{desc}</p><p class='prism-badge' data-colony='{colony}'>{FANO_SPECTRAL_MAP[colony]['wavelength']}nm</p>",
                    colony=colony,
                )
            )
            cards.append(card)

        return f'<div class="prism-grid">{chr(10).join(cards)}</div>'


# Convenience functions


def render_prism_card(
    title: str,
    content: str = "",
    colony: str | None = None,
    **kwargs: Any,
) -> str:
    """Render a single Prism card."""
    gen = PrismorphismGenerator()
    return gen.render_card(CardData(title=title, content=content, colony=colony, **kwargs))


def render_prism_button(
    label: str,
    colony: str | None = None,
    variant: str = "default",
    **kwargs: Any,
) -> str:
    """Render a single Prism button."""
    gen = PrismorphismGenerator()
    return gen.render_button(ButtonData(label=label, colony=colony, variant=variant, **kwargs))


def render_prism_modal(
    title: str,
    content: str,
    colony: str | None = None,
    **kwargs: Any,
) -> str:
    """Render a Prism modal."""
    gen = PrismorphismGenerator()
    return gen.render_modal(ModalData(title=title, content=content, colony=colony, **kwargs))


def render_prism_page(
    title: str,
    content: str,
    config: PrismConfig | None = None,
    **kwargs: Any,
) -> str:
    """Render a complete Prism page."""
    gen = PrismorphismGenerator(config)
    return gen.render_page(title, content, **kwargs)
