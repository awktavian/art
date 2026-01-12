#!/usr/bin/env python3
"""Generate beautiful HTML documentation from markdown files.

This script converts markdown files to styled HTML using the Kagami Orb design system.
"""

import re
import sys
from pathlib import Path
from datetime import datetime

# Try to import markdown, fall back to basic conversion if not available
try:
    import markdown
    from markdown.extensions.tables import TableExtension
    from markdown.extensions.fenced_code import FencedCodeExtension
    from markdown.extensions.toc import TocExtension
    from markdown.extensions.nl2br import Nl2BrExtension

    HAS_MARKDOWN = True
except ImportError:
    HAS_MARKDOWN = False
    print("Warning: markdown library not installed. Using basic conversion.")
    print("Install with: pip install markdown")


def basic_markdown_to_html(md_content: str) -> str:
    """Basic markdown to HTML conversion without external libraries."""
    html = md_content

    # Escape HTML
    html = html.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Headers
    html = re.sub(r"^######\s+(.+)$", r"<h6>\1</h6>", html, flags=re.MULTILINE)
    html = re.sub(r"^#####\s+(.+)$", r"<h5>\1</h5>", html, flags=re.MULTILINE)
    html = re.sub(r"^####\s+(.+)$", r"<h4>\1</h4>", html, flags=re.MULTILINE)
    html = re.sub(r"^###\s+(.+)$", r'<h3 id="\1">\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r"^##\s+(.+)$", r'<h2 id="\1">\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r"^#\s+(.+)$", r"<h1>\1</h1>", html, flags=re.MULTILINE)

    # Bold and italic
    html = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", html)
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\*(.+?)\*", r"<em>\1</em>", html)

    # Links
    html = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', html)

    # Inline code
    html = re.sub(r"`([^`]+)`", r"<code>\1</code>", html)

    # Code blocks
    html = re.sub(
        r"```(\w*)\n([\s\S]*?)```", r'<pre><code class="language-\1">\2</code></pre>', html
    )

    # Horizontal rules
    html = re.sub(r"^---+$", r"<hr>", html, flags=re.MULTILINE)

    # Lists
    html = re.sub(r"^- (.+)$", r"<li>\1</li>", html, flags=re.MULTILINE)
    html = re.sub(r"(<li>.*</li>\n)+", r"<ul>\g<0></ul>", html)

    # Paragraphs
    html = re.sub(r"\n\n([^<\n].+)", r"\n\n<p>\1</p>", html)

    # Tables (basic)
    def convert_table(match):
        lines = match.group(0).strip().split("\n")
        if len(lines) < 2:
            return match.group(0)

        header = lines[0].strip("|").split("|")
        rows = [
            line.strip("|").split("|")
            for line in lines[2:]
            if line.strip() and not line.startswith("|--")
        ]

        html_table = '<div class="table-wrapper"><table>\n<thead><tr>'
        for cell in header:
            html_table += f"<th>{cell.strip()}</th>"
        html_table += "</tr></thead>\n<tbody>"

        for row in rows:
            html_table += "<tr>"
            for cell in row:
                cell = cell.strip()
                # Add special styling for prices
                if cell.startswith("$"):
                    html_table += f'<td class="price">{cell}</td>'
                elif cell in ("✅", "⚠️", "❌"):
                    html_table += f'<td class="status">{cell}</td>'
                else:
                    html_table += f"<td>{cell}</td>"
            html_table += "</tr>\n"

        html_table += "</tbody></table></div>"
        return html_table

    # Match tables (lines starting with |)
    html = re.sub(r"(\|[^\n]+\|\n)+", convert_table, html)

    return html


def markdown_to_html(md_content: str) -> str:
    """Convert markdown to HTML with full library support."""
    if HAS_MARKDOWN:
        md = markdown.Markdown(
            extensions=[
                "tables",
                "fenced_code",
                "toc",
                "nl2br",
                "sane_lists",
            ]
        )
        return md.convert(md_content)
    else:
        return basic_markdown_to_html(md_content)


def post_process_html(html: str) -> str:
    """Post-process HTML to add styling classes and wrappers."""

    # Wrap tables
    html = re.sub(r"<table>", r'<div class="table-wrapper"><table>', html)
    html = re.sub(r"</table>", r"</table></div>", html)

    # Style warning sections
    html = re.sub(
        r"<p>⚠️\s*<strong>([^<]+)</strong>",
        r'<div class="alert alert-warning"><p><strong>⚠️ \1</strong>',
        html,
    )

    # Style critical/deprecated items
    html = re.sub(
        r"<td>([^<]*DEPRECATED[^<]*)</td>",
        r'<td class="status-deprecated">\1</td>',
        html,
        flags=re.IGNORECASE,
    )

    # Style validated status
    html = re.sub(r"<td>✅([^<]*)</td>", r'<td class="status-validated">✅\1</td>', html)

    # Style warning status
    html = re.sub(r"<td>⚠️([^<]*)</td>", r'<td class="status-warning">⚠️\1</td>', html)

    # Make external links open in new tab
    html = re.sub(
        r'<a href="(https?://[^"]+)"',
        r'<a href="\1" target="_blank" rel="noopener noreferrer"',
        html,
    )

    return html


def extract_metadata(md_content: str) -> dict:
    """Extract metadata from markdown frontmatter or content."""
    metadata = {
        "title": "Documentation",
        "description": "Kagami Orb documentation",
        "version": "2.0",
        "date": datetime.now().strftime("%B %d, %Y"),
    }

    # Try to extract title from first H1
    title_match = re.search(r"^#\s+(.+)$", md_content, re.MULTILINE)
    if title_match:
        metadata["title"] = title_match.group(1).strip()

    # Try to extract version
    version_match = re.search(r"\*\*Version:\*\*\s*(\S+)", md_content)
    if version_match:
        metadata["version"] = version_match.group(1)

    # Try to extract date
    date_match = re.search(
        r"\*\*(?:Date|Last Updated|Updated):\*\*\s*(.+)$", md_content, re.MULTILINE
    )
    if date_match:
        metadata["date"] = date_match.group(1).strip()

    # Generate description from first paragraph
    desc_match = re.search(r"^[^#\n][^\n]+", md_content, re.MULTILINE)
    if desc_match:
        desc = desc_match.group(0).strip()
        desc = re.sub(r"\*\*|\*|`", "", desc)  # Remove markdown formatting
        metadata["description"] = desc[:160]

    return metadata


def generate_html_doc(md_path: Path, template_path: Path, output_path: Path):
    """Generate HTML document from markdown using template."""
    print(f"Processing: {md_path.name}")

    # Read files
    md_content = md_path.read_text(encoding="utf-8")
    template = template_path.read_text(encoding="utf-8")

    # Extract metadata
    metadata = extract_metadata(md_content)

    # Remove the first H1 from content (it's in the doc-header)
    md_content = re.sub(r"^#\s+[^\n]+\n+", "", md_content, count=1)

    # Convert markdown to HTML
    html_content = markdown_to_html(md_content)
    html_content = post_process_html(html_content)

    # Fill template
    output = template
    output = output.replace("{{TITLE}}", metadata["title"])
    output = output.replace("{{DESCRIPTION}}", metadata["description"])
    output = output.replace("{{VERSION}}", metadata["version"])
    output = output.replace("{{DATE}}", metadata["date"])
    output = output.replace("{{FILENAME}}", output_path.name)
    output = output.replace("{{CONTENT}}", html_content)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    print(f"  → Generated: {output_path.name}")


def main():
    """Generate all HTML documentation."""
    base_dir = Path(__file__).parent.parent
    template_path = base_dir / "docs-template.html"

    if not template_path.exists():
        print(f"Error: Template not found at {template_path}")
        sys.exit(1)

    # Documents to convert (source, output)
    documents = [
        # Main docs
        ("HARDWARE_BOM.md", "bom.html"),
        ("ONE_CLICK_BUY.md", "buy.html"),
        ("ASSEMBLY_GUIDE.md", "assembly.html"),
        ("SYSTEM_DESIGN.md", "system.html"),
        ("README.md", "spec.html"),
        ("ALTERNATIVES.md", "alternatives.html"),
        ("EXPERIENCE_DESIGN.md", "experience.html"),
        ("VALIDATION_PLAN.md", "validation.html"),
        ("INTEGRATION_PROTOCOL.md", "integration.html"),
        ("FIRMWARE_ARCHITECTURE.md", "firmware.html"),
        ("DEPENDENCY_GRAPH.md", "dependencies.html"),
        # Hardware subdirectory docs
        ("hardware/ALTERNATIVES.md", "alternatives.html"),
        ("hardware/CUSTOM_PCB.md", "custom-pcb.html"),
        ("hardware/THERMAL_ANALYSIS.md", "thermal.html"),
        ("hardware/FMEA.md", "fmea.html"),
        ("hardware/DEGRADATION_MODES.md", "degradation.html"),
    ]

    generated = []
    for md_file, html_file in documents:
        md_path = base_dir / md_file
        output_path = base_dir / html_file

        if md_path.exists():
            generate_html_doc(md_path, template_path, output_path)
            generated.append(html_file)
        else:
            print(f"  ⚠️  {md_file} not found, skipping")

    print(f"\n✅ Done! Generated {len(generated)} HTML files:")
    for f in generated:
        print(f"   • {f}")


if __name__ == "__main__":
    main()
