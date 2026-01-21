#!/usr/bin/env python3
"""
Amélie Gallery Curation Script

Uses the core Kagami shopping services for:
- StockVerifier: Ensure all products are in-stock at Jill's sizes
- GalleryCurator: Download and verify product images

Usage:
    python scripts/curate_amelie.py verify     # Verify stock at Jill's sizes
    python scripts/curate_amelie.py images     # Download product images
    python scripts/curate_amelie.py full       # Full curation pipeline
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add kagami to path if running standalone
KAGAMI_PACKAGES = Path(__file__).parents[4] / "packages"
if KAGAMI_PACKAGES.exists():
    sys.path.insert(0, str(KAGAMI_PACKAGES))

from kagami.core.services.shopping.stock_verifier import StockVerifier
from kagami.core.services.shopping.gallery_curator import GalleryCurator
from kagami.core.services.shopping.gallery_schema import Gallery

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
GALLERY_DIR = Path(__file__).parent.parent
DATA_DIR = GALLERY_DIR / "data"
IMAGES_DIR = GALLERY_DIR / "images"
GALLERY_JSON = DATA_DIR / "gallery.json"


def load_gallery() -> dict:
    """Load gallery data from JSON."""
    with open(GALLERY_JSON) as f:
        return json.load(f)


def save_gallery(data: dict) -> None:
    """Save gallery data to JSON."""
    with open(GALLERY_JSON, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved gallery to {GALLERY_JSON}")


async def verify_stock() -> dict:
    """Verify all products are in-stock at Jill's sizes."""
    logger.info("🔍 Starting stock verification for Jill...")
    
    gallery = load_gallery()
    products = gallery["products"]
    
    # Convert to verification format
    products_to_verify = []
    for p in products:
        if p.get("stock_check_required", True):
            products_to_verify.append({
                "id": p["id"],
                "url": p.get("product_url", ""),
                "category": p.get("subcategory", p.get("category", "general")),
                "name": p["name"],
                "size_required": p.get("size_required", ""),
            })
    
    logger.info(f"   Checking {len(products_to_verify)} products...")
    
    # Run verification
    verifier = StockVerifier(request_delay=2.0)  # Be polite to servers
    results = await verifier.batch_verify_for_recipient(products_to_verify, "jill")
    
    # Update gallery with results
    in_stock_count = 0
    out_of_stock = []
    
    for product, result in results:
        product_id = product["id"]
        gallery_product = next((p for p in products if p["id"] == product_id), None)
        
        if gallery_product:
            gallery_product["verified"] = result.size_in_stock
            gallery_product["stock_check_required"] = False
            gallery_product["verification_date"] = result.last_checked.isoformat()
            
            if result.current_price:
                gallery_product["verified_price"] = result.current_price
            
            if result.size_in_stock:
                in_stock_count += 1
                logger.info(f"   ✅ {product['name']}: IN STOCK")
            else:
                out_of_stock.append(product["name"])
                logger.info(f"   ❌ {product['name']}: OUT OF STOCK or size unavailable")
    
    # Update meta
    gallery["meta"]["verified_count"] = in_stock_count
    gallery["meta"]["validation_status"] = "verified" if in_stock_count == len(products) else "partial"
    
    save_gallery(gallery)
    
    logger.info(f"\n📊 Verification Summary:")
    logger.info(f"   In stock: {in_stock_count}/{len(products)}")
    if out_of_stock:
        logger.info(f"   Out of stock: {', '.join(out_of_stock)}")
    
    return gallery


async def download_images() -> int:
    """Download product images using GalleryCurator."""
    logger.info("🖼️ Starting image download...")

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Load gallery using the schema
    gallery = Gallery.load(GALLERY_JSON)

    # Use GalleryCurator's download_images method
    curator = GalleryCurator()
    results = await curator.download_images(
        gallery=gallery,
        output_dir=IMAGES_DIR,
        use_vlm=True,  # Verify images are actually products
        skip_existing=True,
    )

    # Save updated gallery with local_image paths
    gallery.save(GALLERY_JSON)

    downloaded = sum(1 for v in results.values() if v)
    logger.info(f"\n📊 Downloaded {downloaded}/{len(results)} images")
    return downloaded


async def full_curation() -> None:
    """Run full curation pipeline."""
    logger.info("🎬 Starting full Amélie curation pipeline...")

    # Step 1: Verify stock
    await verify_stock()

    # Step 2: Download images
    await download_images()

    # Step 3: Summary
    gallery = Gallery.load(GALLERY_JSON)
    logger.info("\n" + "=" * 60)
    logger.info(f"🎉 Curation Complete: {gallery.meta.name}")
    logger.info(f"   Products: {len(gallery.products)}")
    logger.info(f"   Verified: {gallery.meta.verified_count}")
    logger.info("=" * 60)


def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: python curate_amelie.py [verify|images|full]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "verify":
        asyncio.run(verify_stock())
    elif command == "images":
        asyncio.run(download_images())
    elif command == "full":
        asyncio.run(full_curation())
    else:
        print(f"Unknown command: {command}")
        print("Available: verify, images, full")
        sys.exit(1)


if __name__ == "__main__":
    main()
