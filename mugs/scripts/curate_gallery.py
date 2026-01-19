#!/usr/bin/env python3
"""
Curated Mug Gallery Builder.

Uses the general ProductCrawler to find and verify diverse mug images
following museum curation principles:

1. ONE centerpiece (Kennedy Cup) - the focus
2. DIVERSE supporting pieces - different makers, styles, eras
3. QUALITY over quantity - each piece earns its place
4. STORYTELLING - each mug has a narrative connection

Curation Categories (museum-inspired):
- Historical: Pieces with provenance and story
- Craft: Handmade, artisan, studio pottery
- Design: Iconic designers, recognized brands
- Cultural: Regional traditions, heritage pieces
- Contemporary: Modern makers, emerging studios

Usage:
    export GEMINI_API_KEY=...
    cd ~/projects/art/mugs
    python scripts/curate_gallery.py
    python scripts/curate_gallery.py --dry-run
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

# Add kagami to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "kagami" / "packages"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Gallery Configuration - Museum Curation
# =============================================================================

@dataclass
class GalleryItem:
    """A curated gallery item."""
    name: str
    category: str  # kennedy, historical, craft, design, cultural, contemporary
    maker: str
    description: str
    story: str  # The narrative - why this piece matters
    product_url: str
    filename: str
    price_range: str = ""
    expected_type: str = "ceramic mug"


# The Curated Collection
# Following museum principle: ONE centerpiece, diverse supporting works
GALLERY = [
    # ═══════════════════════════════════════════════════════════════════════
    # THE CENTERPIECE - Jill's Kennedy Cup
    # ═══════════════════════════════════════════════════════════════════════
    GalleryItem(
        name="Kennedy for President",
        category="kennedy",
        maker="JFK Library Store · Boston",
        description="Ceramic reproduction of the 1960 campaign button design",
        story="The original 'Coffee with Kennedy' events made politics intimate. This mug carries that democratic spirit into your morning.",
        product_url="https://store.jfklibrary.org/products/kennedy-for-president-mug",
        filename="kennedy-centerpiece.jpg",
        price_range="$22.99",
        expected_type="ceramic mug with Kennedy portrait",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # CRAFT - Handmade, studio pottery
    # ═══════════════════════════════════════════════════════════════════════
    GalleryItem(
        name="Heath Ceramics Mug",
        category="craft",
        maker="Heath Ceramics · Sausalito, CA · Since 1948",
        description="Stoneware with signature pooling glaze",
        story="California craft heritage. Edith Heath's philosophy: useful objects can be beautiful. The glaze pools where it wants.",
        product_url="https://www.heathceramics.com/collections/mugs",
        filename="heath-ceramics.jpg",
        price_range="$38–$48",
        expected_type="ceramic mug with glaze",
    ),
    GalleryItem(
        name="East Fork Mug",
        category="craft",
        maker="East Fork Pottery · Asheville, NC · Est. 2009",
        description="Modern American pottery with distinctive glazes",
        story="New Southern craft. Glazes named 'Tequila Sunrise' and 'Night Swim'. Designed for daily use, built to outlast you.",
        product_url="https://eastfork.com/collections/mugs",
        filename="east-fork.jpg",
        price_range="$40–$56",
        expected_type="handmade ceramic mug",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # DESIGN - Iconic designers, recognized brands
    # ═══════════════════════════════════════════════════════════════════════
    GalleryItem(
        name="Hasami Porcelain",
        category="design",
        maker="Hasami · Nagasaki, Japan · 400-year tradition",
        description="Modular, stackable porcelain in matte finish",
        story="Four centuries of ceramic mastery in a modern form. Designed to stack, to mix, to become part of your life.",
        product_url="https://hasami-porcelain.com/collections/mugs",
        filename="hasami-porcelain.jpg",
        price_range="$26–$32",
        expected_type="minimalist porcelain mug",
    ),
    GalleryItem(
        name="Iittala Teema Mug",
        category="design",
        maker="Kaj Franck · Iittala, Finland · 1952",
        description="Timeless Scandinavian design in functional form",
        story="Kaj Franck believed good design should be democratic. Teema has remained unchanged since 1952 because perfection needs no revision.",
        product_url="https://www.iittala.com/collections/teema",
        filename="iittala-teema.jpg",
        price_range="$25–$30",
        expected_type="simple ceramic mug",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # CULTURAL - Regional traditions, heritage pieces
    # ═══════════════════════════════════════════════════════════════════════
    GalleryItem(
        name="Korean Celadon Cup",
        category="cultural",
        maker="Goryeo tradition · Korea",
        description="Jade-green crackle glaze, thousand-year technique",
        story="Celadon glazing reached perfection in 12th century Korea. The color was said to capture 'the blue of the sky after rain.'",
        product_url="https://www.etsy.com/search?q=korean%20celadon%20tea%20cup",
        filename="korean-celadon.jpg",
        price_range="$45–$200",
        expected_type="celadon green tea cup",
    ),
    GalleryItem(
        name="Mashiko Stoneware",
        category="cultural",
        maker="Mashiko, Japan · Mingei tradition",
        description="Wood-fired with natural ash glaze",
        story="The mingei (folk craft) movement celebrated humble beauty. Each cup is a collaboration between potter and kiln flame.",
        product_url="https://www.myjapanesegreentea.com/japanese-tea-cups",
        filename="mashiko-stoneware.jpg",
        price_range="$45–$120",
        expected_type="Japanese pottery mug",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # HISTORICAL - Pieces with provenance
    # ═══════════════════════════════════════════════════════════════════════
    GalleryItem(
        name="Fire-King Jadeite",
        category="historical",
        maker="Anchor Hocking · 1940s–1970s",
        description="Milk glass in impossible green",
        story="Diner counters, grandmother's cabinets, American nostalgia. Heavy, glowing, designed to survive the lunch rush forever.",
        product_url="https://www.etsy.com/search?q=fire%20king%20jadeite%20mug",
        filename="fire-king-jadeite.jpg",
        price_range="$25–$150",
        expected_type="green glass mug jadeite",
    ),
    
    # ═══════════════════════════════════════════════════════════════════════
    # CONTEMPORARY - Modern makers
    # ═══════════════════════════════════════════════════════════════════════
    GalleryItem(
        name="Kinto SCS Mug",
        category="contemporary",
        maker="Kinto · Japan · Slow Coffee Style",
        description="Heat-resistant glass with wooden handle",
        story="Japanese minimalism meets Scandinavian warmth. The wooden handle stays cool. The coffee stays visible.",
        product_url="https://kinto-usa.com/collections/mugs",
        filename="kinto-scs.jpg",
        price_range="$28–$35",
        expected_type="glass mug with wooden handle",
    ),
    GalleryItem(
        name="Jill Rosenwald Cup",
        category="contemporary",
        maker="Jill Rosenwald · Boston",
        description="Hand-thrown earthenware with bold patterns",
        story="Small vessels for big feelings. Each piece takes 4-6 weeks to make. A lifetime to love.",
        product_url="https://www.jillrosenwald.com/products/jilly-cup",
        filename="jill-rosenwald.jpg",
        price_range="$68",
        expected_type="colorful ceramic cup",
    ),
]


# =============================================================================
# Gallery Builder
# =============================================================================

async def build_gallery(dry_run: bool = False) -> None:
    """Build the curated gallery."""
    
    # Import crawler
    try:
        from kagami.core.services.shopping.product_crawler import (
            CrawlerConfig,
            ProductCrawler,
        )
    except ImportError:
        logger.error("Could not import ProductCrawler - ensure kagami is installed")
        sys.exit(1)
    
    images_dir = Path(__file__).parent.parent / "images" / "mugs"
    images_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info("🎨 Curated Mug Gallery Builder")
    logger.info(f"   Output: {images_dir}")
    logger.info(f"   Items: {len(GALLERY)}")
    logger.info(f"   Dry run: {dry_run}")
    logger.info("")
    
    # Group by category for reporting
    categories = {}
    for item in GALLERY:
        categories.setdefault(item.category, []).append(item)
    
    logger.info("📋 Collection Overview:")
    for cat, items in categories.items():
        logger.info(f"   {cat.title()}: {len(items)} piece(s)")
    logger.info("")
    
    if dry_run:
        logger.info("DRY RUN - showing what would be crawled:")
        for item in GALLERY:
            logger.info(f"   [{item.category}] {item.name}")
            logger.info(f"       → {item.product_url[:60]}...")
            logger.info(f"       → {item.filename}")
        return
    
    # Initialize crawler
    config = CrawlerConfig(
        use_vlm=True,
        vlm_confidence_threshold=0.5,  # Be a bit more permissive
        request_delay=3.0,  # Be polite
    )
    crawler = ProductCrawler(config)
    
    results = {"success": [], "failed": []}
    
    for item in GALLERY:
        logger.info(f"🔍 [{item.category.upper()}] {item.name}")
        logger.info(f"   URL: {item.product_url[:60]}...")
        
        # Check if we already have a good image
        existing = images_dir / item.filename
        if existing.exists() and existing.stat().st_size > 50000:
            logger.info(f"   ⏭️  Already have image: {item.filename}")
            results["success"].append(item.name)
            continue
        
        # Update config for this item's expected type
        crawler.config.expected_type = item.expected_type
        
        # Crawl and verify
        product, image = await crawler.crawl_and_verify(
            url=item.product_url,
            output_dir=images_dir,
            filename=item.filename,
        )
        
        if image and image.is_verified:
            results["success"].append(item.name)
        else:
            results["failed"].append(item.name)
            logger.warning(f"   ⚠️  Could not find verified image")
        
        # Rate limit
        await asyncio.sleep(2)
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("CURATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"✅ Success: {len(results['success'])}")
    logger.info(f"❌ Failed: {len(results['failed'])}")
    
    if results["failed"]:
        logger.info("")
        logger.info("Items needing manual curation:")
        for name in results["failed"]:
            logger.info(f"   - {name}")


# =============================================================================
# Entry Point
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Build curated mug gallery")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()
    
    if not os.environ.get("GEMINI_API_KEY"):
        logger.warning("⚠️  GEMINI_API_KEY not set - VLM verification will be skipped")
    
    asyncio.run(build_gallery(dry_run=args.dry_run))
