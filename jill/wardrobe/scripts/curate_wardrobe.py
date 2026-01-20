#!/usr/bin/env python3
"""
Jill's Curated Wardrobe Builder.

Uses the generalized shopping pipeline from kagami.core.services.shopping
to verify URLs, find images, and validate the wardrobe gallery.

Usage:
    cd ~/projects/art/jill/wardrobe
    python scripts/curate_wardrobe.py verify      # Verify all URLs
    python scripts/curate_wardrobe.py audit       # Full audit (URLs + images)
    python scripts/curate_wardrobe.py fix-images  # Auto-find missing images
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

# Add kagami to path
sys.path.insert(0, str(Path(__file__).parents[4] / "kagami" / "packages"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
SCRIPT_DIR = Path(__file__).parent
GALLERY_PATH = SCRIPT_DIR.parent
DATA_PATH = GALLERY_PATH / "data"
IMAGES_PATH = GALLERY_PATH / "images"
GALLERY_JSON = DATA_PATH / "gallery.json"


async def load_gallery() -> dict:
    """Load gallery JSON."""
    if not GALLERY_JSON.exists():
        logger.error(f"Gallery JSON not found: {GALLERY_JSON}")
        sys.exit(1)
    
    with open(GALLERY_JSON) as f:
        return json.load(f)


async def verify_urls() -> list[dict]:
    """Verify all product URLs."""
    import httpx
    
    gallery = await load_gallery()
    products = gallery.get("products", [])
    
    print("\n" + "=" * 70)
    print("URL VERIFICATION — Jill's Curated Wardrobe")
    print("=" * 70 + "\n")
    
    results = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for product in products:
            url = product.get("product_url", "")
            name = product.get("name", "Unknown")
            brand = product.get("brand", "Unknown")
            
            if not url:
                print(f"⚠️  {brand:<20} {name:<25} | NO URL")
                results.append({"id": product["id"], "status": -1, "error": "No URL"})
                continue
            
            try:
                response = await client.get(url, headers=headers)
                status = response.status_code
                
                if status == 200:
                    icon = "✅"
                elif status in (301, 302, 307, 308):
                    icon = "↪️"
                else:
                    icon = "❌"
                
                print(f"{icon} {brand:<20} {name:<25} | {status}")
                results.append({
                    "id": product["id"],
                    "brand": brand,
                    "name": name,
                    "url": url,
                    "status": status,
                    "ok": status == 200,
                })
                
            except Exception as e:
                print(f"❌ {brand:<20} {name:<25} | ERROR: {str(e)[:30]}")
                results.append({
                    "id": product["id"],
                    "status": -1,
                    "error": str(e)[:50],
                })
            
            await asyncio.sleep(0.5)  # Be polite
    
    ok_count = sum(1 for r in results if r.get("ok"))
    print(f"\n{'─' * 70}")
    print(f"URLS: {ok_count}/{len(results)} verified")
    
    return results


async def check_images() -> list[dict]:
    """Check which images exist locally."""
    gallery = await load_gallery()
    products = gallery.get("products", [])
    
    print("\n" + "=" * 70)
    print("IMAGE CHECK — Jill's Curated Wardrobe")
    print("=" * 70 + "\n")
    
    results = []
    
    for product in products:
        local_image = product.get("local_image", "")
        name = product.get("name", "Unknown")
        brand = product.get("brand", "Unknown")
        
        if not local_image:
            print(f"⚠️  {brand:<20} {name:<25} | NO IMAGE DEFINED")
            results.append({"id": product["id"], "status": "no_image"})
            continue
        
        image_path = IMAGES_PATH / local_image
        
        if image_path.exists():
            size = image_path.stat().st_size
            if size > 10000:
                print(f"✅ {brand:<20} {name:<25} | {size/1024:.1f} KB")
                results.append({"id": product["id"], "status": "exists", "size": size})
            else:
                print(f"⚠️  {brand:<20} {name:<25} | TOO SMALL ({size} bytes)")
                results.append({"id": product["id"], "status": "too_small", "size": size})
        else:
            print(f"❌ {brand:<20} {name:<25} | MISSING")
            results.append({"id": product["id"], "status": "missing"})
    
    exists_count = sum(1 for r in results if r.get("status") == "exists")
    print(f"\n{'─' * 70}")
    print(f"IMAGES: {exists_count}/{len(results)} present")
    
    return results


async def full_audit() -> None:
    """Run full audit of URLs and images."""
    print("\n" + "═" * 70)
    print("FULL AUDIT — Jill's Curated Wardrobe")
    print("═" * 70)
    
    # Verify URLs
    url_results = await verify_urls()
    
    # Check images
    image_results = await check_images()
    
    # Summary
    url_ok = sum(1 for r in url_results if r.get("ok"))
    img_ok = sum(1 for r in image_results if r.get("status") == "exists")
    total = len(url_results)
    
    print("\n" + "═" * 70)
    print("AUDIT SUMMARY")
    print("═" * 70)
    print(f"  URLs:   {url_ok}/{total} verified")
    print(f"  Images: {img_ok}/{total} present")
    
    if url_ok < total:
        print("\n⚠️  URL ISSUES:")
        for r in url_results:
            if not r.get("ok"):
                print(f"    - {r.get('brand', 'Unknown')} {r.get('name', 'Unknown')}: {r.get('error', r.get('status'))}")
    
    if img_ok < total:
        print("\n⚠️  IMAGE ISSUES:")
        for r in image_results:
            if r.get("status") != "exists":
                # Find product name
                gallery = await load_gallery()
                product = next((p for p in gallery["products"] if p["id"] == r["id"]), {})
                print(f"    - {product.get('brand', 'Unknown')} {product.get('name', 'Unknown')}: {r.get('status')}")
    
    # Save report
    report = {
        "urls": url_results,
        "images": image_results,
        "summary": {
            "total": total,
            "urls_ok": url_ok,
            "images_ok": img_ok,
        }
    }
    
    report_path = DATA_PATH / "audit_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Report saved to: {report_path}")


async def fix_images(dry_run: bool = False) -> None:
    """Attempt to find and download missing images."""
    try:
        from kagami.core.services.shopping.product_crawler import (
            ProductCrawler,
            CrawlerConfig,
        )
    except ImportError:
        logger.error("Could not import ProductCrawler - ensure kagami is installed")
        print("\nTo fix images, ensure kagami is installed:")
        print("  cd ~/projects/kagami && pip install -e packages/kagami")
        return
    
    gallery = await load_gallery()
    products = gallery.get("products", [])
    
    print("\n" + "=" * 70)
    print("FIX IMAGES" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 70 + "\n")
    
    # Find missing images
    missing = []
    for product in products:
        local_image = product.get("local_image", "")
        if not local_image:
            missing.append(product)
            continue
        
        image_path = IMAGES_PATH / local_image
        if not image_path.exists() or image_path.stat().st_size < 10000:
            missing.append(product)
    
    if not missing:
        print("✅ All images present!")
        return
    
    print(f"🔧 Fixing {len(missing)} images...\n")
    
    config = CrawlerConfig(
        use_vlm=True,
        vlm_confidence_threshold=0.5,
        request_delay=2.0,
    )
    crawler = ProductCrawler(config)
    
    IMAGES_PATH.mkdir(parents=True, exist_ok=True)
    
    for product in missing:
        name = product.get("name", "Unknown")
        brand = product.get("brand", "Unknown")
        url = product.get("product_url", "")
        local_image = product.get("local_image", f"{product['id']}.jpg")
        expected = product.get("expected_content", f"{name} {brand}")
        
        print(f"🔍 {brand} - {name}")
        
        if dry_run:
            print(f"   Would search for: {expected[:50]}...")
            continue
        
        # Try crawling the product page
        crawler.config.expected_type = expected
        
        try:
            result = await crawler.crawl_and_verify(
                url=url,
                output_dir=IMAGES_PATH,
                filename=local_image,
            )
            
            if result and result[1] and result[1].is_verified:
                print(f"   ✅ Found and verified image")
            else:
                print(f"   ⚠️  Could not verify image")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)[:50]}")
        
        await asyncio.sleep(2)
    
    print("\n✅ Image fix complete. Run 'audit' to verify.")


async def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="Jill's Curated Wardrobe Manager")
    parser.add_argument(
        "command",
        choices=["verify", "images", "audit", "fix-images"],
        help="Command to run"
    )
    parser.add_argument("--dry", action="store_true", help="Dry run (don't modify files)")
    args = parser.parse_args()
    
    if args.command == "verify":
        await verify_urls()
    elif args.command == "images":
        await check_images()
    elif args.command == "audit":
        await full_audit()
    elif args.command == "fix-images":
        await fix_images(dry_run=args.dry)
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
