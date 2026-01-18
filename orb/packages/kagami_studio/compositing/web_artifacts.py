"""Web Artifact Generation — Interactive HTML composites.

Generates web-based presentation artifacts:
- DCC-style documentary pages
- Interactive video galleries
- Word-by-word reveal effects
- Glassmorphism overlays
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


async def create_web_artifact(
    video_path: Path | str,
    output_dir: Path | str,
    title: str = "Video Showcase",
    subtitle: str = "",
    style: str = "minimal",
) -> Path:
    """Create simple web artifact for video.

    Args:
        video_path: Source video
        output_dir: Output directory
        title: Page title
        subtitle: Optional subtitle
        style: 'minimal', 'dcc', 'gallery'

    Returns:
        Path to index.html
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy video
    video_dest = output_dir / "video.mp4"
    shutil.copy(video_path, video_dest)

    # Generate HTML
    html = _generate_minimal_html(
        video_name="video.mp4",
        title=title,
        subtitle=subtitle,
    )

    html_path = output_dir / "index.html"
    html_path.write_text(html)

    return html_path


async def create_dcc_artifact(
    video_path: Path | str,
    transcript: list[dict],
    output_dir: Path | str,
    style: str = "dcc",
    title: str = "Documentary",
) -> Path:
    """Create DCC-style documentary web artifact.

    Features:
    - Video panel with talking head
    - Word-by-word text reveal
    - Emotion-based word effects
    - Starfield background

    Args:
        video_path: Source video
        transcript: Word timing data [{"text": "...", "start": 0.5, "end": 1.0}]
        output_dir: Output directory
        style: Visual style
        title: Page title

    Returns:
        Path to index.html
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Copy video
    video_dest = output_dir / "video.mp4"
    shutil.copy(video_path, video_dest)

    # Generate HTML with DCC features
    html = _generate_dcc_html(
        video_name="video.mp4",
        transcript=transcript,
        title=title,
        style=style,
    )

    html_path = output_dir / "index.html"
    html_path.write_text(html)

    return html_path


async def create_gallery_artifact(
    videos: list[Path | str],
    output_dir: Path | str,
    title: str = "Video Gallery",
    thumbnails: list[Path | str] | None = None,
) -> Path:
    """Create video gallery web artifact.

    Args:
        videos: List of video paths
        output_dir: Output directory
        title: Gallery title
        thumbnails: Optional thumbnail images

    Returns:
        Path to index.html
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    video_data = []
    for i, video in enumerate(videos):
        video = Path(video)
        dest = output_dir / f"video_{i}.mp4"
        shutil.copy(video, dest)
        video_data.append(
            {
                "src": f"video_{i}.mp4",
                "title": video.stem,
            }
        )

    html = _generate_gallery_html(
        videos=video_data,
        title=title,
    )

    html_path = output_dir / "index.html"
    html_path.write_text(html)

    return html_path


def _generate_minimal_html(
    video_name: str,
    title: str,
    subtitle: str,
) -> str:
    """Generate minimal video page."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0a;
            color: #fff;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            max-width: 1200px;
            width: 100%;
            padding: 2rem;
        }}
        h1 {{
            font-size: clamp(2rem, 5vw, 3.5rem);
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #fff, #888);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        .subtitle {{
            color: rgba(255,255,255,0.6);
            margin-bottom: 2rem;
        }}
        video {{
            width: 100%;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.5);
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>
        {f'<p class="subtitle">{subtitle}</p>' if subtitle else ""}
        <video controls autoplay loop muted playsinline>
            <source src="{video_name}" type="video/mp4">
        </video>
    </div>
</body>
</html>
"""


def _generate_dcc_html(
    video_name: str,
    transcript: list[dict],
    title: str,
    style: str,
) -> str:
    """Generate DCC-style documentary HTML."""
    # Convert transcript to JavaScript array
    words_js = json.dumps(
        [
            {
                "text": w.get("text", ""),
                "t": w.get("start", 0) / max(1, sum(x.get("end", 1) for x in transcript)),
            }
            for w in transcript
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600&family=Inter:wght@300;400;500&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        :root {{
            --gold: #d4af37;
            --bg: #0a0908;
            --text: #f5f5f5;
            --text-dim: rgba(245, 245, 245, 0.6);
        }}

        body {{
            background: var(--bg);
            color: var(--text);
            font-family: 'Inter', sans-serif;
            min-height: 100vh;
            overflow: hidden;
        }}

        #starfield {{
            position: fixed;
            inset: 0;
            z-index: 0;
            opacity: 0.5;
        }}

        .main {{
            display: flex;
            height: 100vh;
            position: relative;
            z-index: 1;
        }}

        .video-panel {{
            flex: 0.65;
            position: relative;
            overflow: hidden;
        }}

        .video-panel::after {{
            content: '';
            position: absolute;
            inset: 0;
            background: linear-gradient(to right, transparent 70%, var(--bg) 100%);
            pointer-events: none;
        }}

        video {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .text-panel {{
            flex: 0.35;
            display: flex;
            flex-direction: column;
            justify-content: center;
            padding: 4rem;
        }}

        .title {{
            font-family: 'Playfair Display', serif;
            font-size: clamp(1.5rem, 3vw, 2.5rem);
            margin-bottom: 2rem;
            background: linear-gradient(135deg, var(--gold), var(--text));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .quote {{
            font-size: clamp(1rem, 2vw, 1.4rem);
            line-height: 2;
            color: var(--text-dim);
        }}

        .word {{
            display: inline-block;
            opacity: 0;
            transform: translateY(15px);
            transition: all 0.3s ease;
            margin-right: 0.3em;
        }}

        .word.visible {{
            opacity: 1;
            transform: translateY(0);
        }}

        .word.current {{
            color: var(--text);
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <canvas id="starfield"></canvas>

    <div class="main">
        <div class="video-panel">
            <video id="video" autoplay loop playsinline>
                <source src="{video_name}" type="video/mp4">
            </video>
        </div>
        <div class="text-panel">
            <h1 class="title">{title}</h1>
            <div class="quote" id="quote"></div>
        </div>
    </div>

    <script>
        // Starfield
        const canvas = document.getElementById('starfield');
        const ctx = canvas.getContext('2d');
        let stars = [];

        function initStars() {{
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            stars = [];
            const count = Math.floor(canvas.width * canvas.height / 15000);
            for (let i = 0; i < count; i++) {{
                stars.push({{
                    x: Math.random() * canvas.width,
                    y: Math.random() * canvas.height,
                    r: Math.random() * 1.5 + 0.5,
                    twinkle: Math.random() * Math.PI * 2,
                    speed: Math.random() * 0.02 + 0.01,
                }});
            }}
        }}

        function animateStars() {{
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            stars.forEach(s => {{
                s.twinkle += s.speed;
                const alpha = 0.3 + Math.sin(s.twinkle) * 0.3;
                ctx.beginPath();
                ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(255,255,255,${{alpha}})`;
                ctx.fill();
            }});
            requestAnimationFrame(animateStars);
        }}

        window.addEventListener('resize', initStars);
        initStars();
        animateStars();

        // Word reveal
        const words = {words_js};
        const quote = document.getElementById('quote');
        const video = document.getElementById('video');

        words.forEach((w, i) => {{
            const span = document.createElement('span');
            span.className = 'word';
            span.textContent = w.text;
            span.dataset.t = w.t;
            quote.appendChild(span);
        }});

        const wordEls = quote.querySelectorAll('.word');

        video.addEventListener('timeupdate', () => {{
            const progress = video.currentTime / video.duration;
            wordEls.forEach((el, i) => {{
                const t = parseFloat(el.dataset.t);
                const nextT = wordEls[i + 1] ? parseFloat(wordEls[i + 1].dataset.t) : 1;
                if (progress >= t) {{
                    el.classList.add('visible');
                    el.classList.toggle('current', progress < nextT);
                }}
            }});
        }});
    </script>
</body>
</html>
"""


def _generate_gallery_html(
    videos: list[dict],
    title: str,
) -> str:
    """Generate video gallery HTML."""
    video_items = "\n".join(
        [
            f'''<div class="video-card" onclick="playVideo('{v["src"]}')">
            <video muted loop playsinline>
                <source src="{v["src"]}" type="video/mp4">
            </video>
            <div class="video-title">{v["title"]}</div>
        </div>'''
            for v in videos
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0a0a0a;
            color: #fff;
            min-height: 100vh;
            padding: 2rem;
        }}
        h1 {{
            font-size: 2.5rem;
            margin-bottom: 2rem;
            text-align: center;
        }}
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 2rem;
            max-width: 1400px;
            margin: 0 auto;
        }}
        .video-card {{
            background: #1a1a1a;
            border-radius: 12px;
            overflow: hidden;
            cursor: pointer;
            transition: transform 0.3s, box-shadow 0.3s;
        }}
        .video-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.4);
        }}
        .video-card video {{
            width: 100%;
            aspect-ratio: 16/9;
            object-fit: cover;
        }}
        .video-card:hover video {{
            opacity: 0.8;
        }}
        .video-title {{
            padding: 1rem;
            font-weight: 500;
        }}
        .modal {{
            display: none;
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            align-items: center;
            justify-content: center;
        }}
        .modal.active {{ display: flex; }}
        .modal video {{
            max-width: 90vw;
            max-height: 90vh;
            border-radius: 12px;
        }}
        .modal-close {{
            position: absolute;
            top: 2rem;
            right: 2rem;
            font-size: 2rem;
            cursor: pointer;
            color: #fff;
        }}
    </style>
</head>
<body>
    <h1>{title}</h1>
    <div class="gallery">
        {video_items}
    </div>

    <div class="modal" id="modal" onclick="closeModal()">
        <span class="modal-close">&times;</span>
        <video id="modalVideo" controls autoplay></video>
    </div>

    <script>
        function playVideo(src) {{
            const modal = document.getElementById('modal');
            const video = document.getElementById('modalVideo');
            video.src = src;
            modal.classList.add('active');
        }}

        function closeModal() {{
            const modal = document.getElementById('modal');
            const video = document.getElementById('modalVideo');
            video.pause();
            video.src = '';
            modal.classList.remove('active');
        }}

        // Hover play for cards
        document.querySelectorAll('.video-card video').forEach(v => {{
            const card = v.parentElement;
            card.addEventListener('mouseenter', () => v.play());
            card.addEventListener('mouseleave', () => {{ v.pause(); v.currentTime = 0; }});
        }});
    </script>
</body>
</html>
"""
