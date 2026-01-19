#!/usr/bin/env python3
"""
Shopping Gallery Smart Verification & Image Crawler.

Uses Gemini VLM to verify images and automatically find correct replacements.
Adapted from mugs gallery verification system.

Usage:
    cd ~/projects/art/style
    python scripts/verify_and_fix.py              # Verify existing images
    python scripts/verify_and_fix.py --fix        # Find and download correct images
    python scripts/verify_and_fix.py --fix --dry  # Show what would be downloaded
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Paths
GALLERY_PATH = Path(__file__).parent.parent
IMAGES_PATH = GALLERY_PATH / "images"
REPORT_PATH = GALLERY_PATH / "data" / "verification_report.json"

# Get Gemini API key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


# =============================================================================
# Product Definitions - The Curated Wardrobe
# =============================================================================

@dataclass
class Product:
    """A clothing product with verification details."""
    id: str
    name: str
    brand: str
    expected_content: str  # What Gemini should detect
    local_image: str  # Filename in IMAGES_PATH
    product_url: str  # Direct link to buy
    category: str
    price: int
    search_query: str  # For finding correct images


# All products in the gallery - with specific search queries
PRODUCTS = [
    # ===== ESSENTIALS =====
    Product(
        id="ladywhite-tshirt",
        name="Our T-Shirt",
        brand="Lady White Co",
        expected_content="plain white crew neck cotton t-shirt, simple minimal design",
        local_image="ladywhite-tshirt.jpg",
        product_url="https://www.ladywhiteco.com/collections/t-shirts",
        category="Essentials",
        price=90,
        search_query="plain white t-shirt cotton minimal menswear",
    ),
    Product(
        id="sunspel-riviera",
        name="Riviera Polo",
        brand="Sunspel",
        expected_content="white or grey polo shirt with collar and buttons, cotton pique knit",
        local_image="sunspel-riviera.jpg",
        product_url="https://us.sunspel.com/collections/mens-polo-shirts",
        category="Essentials",
        price=145,
        search_query="grey polo shirt cotton pique menswear collar",
    ),
    Product(
        id="drakes-oxford",
        name="Oxford BD Shirt",
        brand="Drake's",
        expected_content="light blue oxford cloth button-down shirt, plain no pattern",
        local_image="drakes-oxford.jpg",
        product_url="https://www.drakes.com/usa/shirts",
        category="Essentials",
        price=295,
        search_query="light blue oxford button down shirt plain cotton",
    ),
    Product(
        id="lucafaloni-cashmere",
        name="Cashmere Crewneck",
        brand="Luca Faloni",
        expected_content="cream or oatmeal colored cashmere sweater crewneck, knitwear",
        local_image="lucafaloni-cashmere.jpg",
        product_url="https://www.lucafaloni.com/collections/cashmere",
        category="Essentials",
        price=395,
        search_query="cream oatmeal cashmere sweater crewneck knitwear",
    ),
    Product(
        id="ironheart-denim",
        name="21oz Selvedge Denim",
        brand="Iron Heart",
        expected_content="dark indigo raw selvedge denim jeans, heavy weight",
        local_image="ironheart-denim.jpg",
        product_url="https://www.ironheartamerica.com/bottoms/",
        category="Essentials",
        price=395,
        search_query="dark indigo raw selvedge denim jeans Japanese",
    ),
    
    # ===== OUTERWEAR =====
    Product(
        id="burberry-trench",
        name="Kensington Trench",
        brand="Burberry",
        expected_content="tan honey beige trench coat with belt, cotton gabardine, classic style",
        local_image="burberry-trench.jpg",
        product_url="https://us.burberry.com/",
        category="Outerwear",
        price=2290,
        search_query="tan beige trench coat belted cotton classic",
    ),
    Product(
        id="schott-perfecto",
        name="Perfecto 618",
        brand="Schott NYC",
        expected_content="black leather motorcycle biker jacket, asymmetric zipper, classic",
        local_image="schott-perfecto.jpg",
        product_url="https://www.schottnyc.com/products/classic-perfecto-steerhide-leather-motorcycle-jacket.htm",
        category="Outerwear",
        price=900,
        search_query="black leather motorcycle jacket Perfecto biker",
    ),
    Product(
        id="barbour-bedale",
        name="Bedale Waxed Jacket",
        brand="Barbour",
        expected_content="olive green waxed cotton field jacket, British heritage style",
        local_image="barbour-bedale.jpg",
        product_url="https://www.nordstrom.com/sr?keyword=barbour%20bedale",
        category="Outerwear",
        price=450,
        search_query="olive green waxed cotton jacket Barbour field",
    ),
    
    # ===== FOOTWEAR =====
    Product(
        id="cp-achilles",
        name="Achilles Low",
        brand="Common Projects",
        expected_content="white minimalist leather sneakers, clean simple low-top, gold serial",
        local_image="cp-achilles.jpg",
        product_url="https://www.ssense.com/en-us/men/designers/common-projects",
        category="Footwear",
        price=450,
        search_query="white minimalist leather sneakers Common Projects clean",
    ),
    Product(
        id="alden-990",
        name="990 Plain Toe Blucher",
        brand="Alden",
        expected_content="burgundy oxblood shell cordovan dress shoes, plain toe derby",
        local_image="alden-990.jpg",
        product_url="https://www.theshoemart.com/alden-mens-990-plain-toe-blucher-color-8-shell-cordovan/",
        category="Footwear",
        price=799,
        search_query="burgundy cordovan dress shoes Alden derby plain toe",
    ),
    Product(
        id="edwardgreen-chelsea",
        name="Chelsea Boot",
        brand="Edward Green",
        expected_content="brown leather chelsea boots, elastic side panels, elegant dress boot",
        local_image="edwardgreen-chelsea.jpg",
        product_url="https://www.nordstrom.com/sr?keyword=edward%20green%20boots",
        category="Footwear",
        price=1650,
        search_query="brown leather chelsea boots elegant dress elastic",
    ),
    
    # ===== ACCESSORIES =====
    Product(
        id="grandseiko-snowflake",
        name="Snowflake SBGA211",
        brand="Grand Seiko",
        expected_content="silver titanium watch white textured dial, elegant dress watch metal bracelet",
        local_image="grandseiko-snowflake.jpg",
        product_url="https://www.grand-seiko.com/us-en/collections/sbga211g",
        category="Accessories",
        price=6300,
        search_query="silver white dial dress watch elegant titanium",
    ),
    Product(
        id="persol-714",
        name="714 Steve McQueen",
        brand="Persol",
        expected_content="tortoise havana brown folding sunglasses, acetate classic style",
        local_image="persol-714.jpg",
        product_url="https://www.nordstrom.com/sr?keyword=persol%20714",
        category="Accessories",
        price=418,
        search_query="tortoise brown folding sunglasses Persol classic acetate",
    ),
    Product(
        id="andersons-belt",
        name="Woven Leather Belt",
        brand="Anderson's",
        expected_content="tan brown woven braided leather belt, Italian craftsmanship",
        local_image="andersons-belt.jpg",
        product_url="https://www.amazon.com/s?k=andersons+woven+leather+belt",
        category="Accessories",
        price=195,
        search_query="tan brown woven braided leather belt Italian",
    ),
    Product(
        id="frankclegg-briefcase",
        name="Zip-Top Briefcase",
        brand="Frank Clegg",
        expected_content="chestnut tan leather briefcase business bag, American made quality",
        local_image="frankclegg-briefcase.jpg",
        product_url="https://frankclegg.com/collections/briefcases/products/zip-top-briefcase",
        category="Accessories",
        price=1100,
        search_query="chestnut tan leather briefcase bag American quality",
    ),
]


# =============================================================================
# Gemini VLM Verification
# =============================================================================

async def verify_image_with_gemini(
    image_path: Path,
    expected_content: str,
    api_key: str,
) -> dict[str, Any]:
    """Verify an image using Gemini VLM."""
    if not api_key:
        return {"error": "No API key", "verified": False}
    
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_b64 = base64.b64encode(image_data).decode()
    except Exception as e:
        return {"error": f"Failed to read image: {e}", "verified": False}
    
    img = Image.open(image_path)
    mime_type = f"image/{img.format.lower()}" if img.format else "image/jpeg"
    
    prompt = f"""Analyze this image carefully.

I need to verify if this image shows: "{expected_content}"

Answer these questions:
1. MATCH: Does this image show what's described above? Answer YES or NO.
2. DESCRIPTION: In one sentence, describe exactly what you see in the image.
3. PERSON: Does this image contain a real human person as the main subject? YES or NO.
4. PRODUCT: Is this a product photo suitable for a fashion e-commerce gallery? YES or NO.

Format exactly as:
MATCH: [YES/NO]
DESCRIPTION: [description]
PERSON: [YES/NO]
PRODUCT: [YES/NO]"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": image_b64}}
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500}
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        result = {
            "matches": False,
            "description": "",
            "contains_person": False,
            "is_product_photo": False,
            "raw": text,
        }
        
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("MATCH:"):
                result["matches"] = "YES" in line.upper()
            elif line.startswith("DESCRIPTION:"):
                result["description"] = line.replace("DESCRIPTION:", "").strip()
            elif line.startswith("PERSON:"):
                result["contains_person"] = "YES" in line.upper()
            elif line.startswith("PRODUCT:"):
                result["is_product_photo"] = "YES" in line.upper()
        
        # Product photos CAN contain models wearing the item
        result["verified"] = result["matches"] and result["is_product_photo"]
        
        confidence = 0.0
        if result["matches"]:
            confidence += 0.5
        if result["is_product_photo"]:
            confidence += 0.3
        if not result["contains_person"] or result["matches"]:
            confidence += 0.2
        result["confidence"] = confidence
        
        return result
        
    except Exception as e:
        return {"error": str(e), "verified": False}


# =============================================================================
# DuckDuckGo Image Search
# =============================================================================

async def search_images_ddg(query: str, max_results: int = 8) -> list[dict]:
    """Search DuckDuckGo for images (no API key needed)."""
    import re
    from urllib.parse import quote_plus
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            token_url = f"https://duckduckgo.com/?q={quote_plus(query)}&iar=images&iax=images&ia=images"
            response = await client.get(token_url, headers=headers)
            
            match = re.search(r'vqd=["\']?([^"\'&]+)', response.text)
            if not match:
                logger.warning("Could not get DDG token")
                return []
            
            vqd = match.group(1)
            
            search_url = "https://duckduckgo.com/i.js"
            params = {
                "l": "us-en",
                "o": "json", 
                "q": query,
                "vqd": vqd,
                "f": ",,,,,",
                "p": "1",
            }
            
            response = await client.get(search_url, params=params, headers=headers)
            data = response.json()
            
            results = []
            for r in data.get("results", [])[:max_results]:
                results.append({
                    "url": r.get("image", ""),
                    "source": r.get("url", ""),
                    "title": r.get("title", ""),
                    "width": r.get("width", 0),
                    "height": r.get("height", 0),
                })
            
            return results
            
    except Exception as e:
        logger.warning(f"DDG search failed: {e}")
        return []


async def download_and_verify_image(
    url: str,
    expected_content: str,
    api_key: str,
) -> tuple[bytes | None, dict]:
    """Download an image and verify it with Gemini."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, follow_redirects=True)
            response.raise_for_status()
            
            content = response.content
            content_type = response.headers.get("content-type", "")
            
            if "text/html" in content_type:
                return None, {"error": "URL returned HTML, not image"}
            
            if len(content) < 5000:
                return None, {"error": f"Image too small ({len(content)} bytes)"}
            
            try:
                img = Image.open(io.BytesIO(content))
                if img.width < 300 or img.height < 300:
                    return None, {"error": f"Image dimensions too small: {img.width}x{img.height}"}
            except Exception as e:
                return None, {"error": f"Invalid image data: {e}"}
            
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
                f.write(content)
                temp_path = Path(f.name)
            
            try:
                result = await verify_image_with_gemini(temp_path, expected_content, api_key)
            finally:
                temp_path.unlink()
            
            return content, result
            
    except Exception as e:
        return None, {"error": str(e)}


async def find_and_download_best_image(
    product: Product,
    api_key: str,
    output_path: Path,
    dry_run: bool = False,
) -> dict:
    """Search for, verify, and download the best image for a product."""
    logger.info(f"🔍 Searching for: {product.brand} {product.name}")
    logger.info(f"   Query: {product.search_query}")
    
    candidates = await search_images_ddg(product.search_query, max_results=10)
    
    if not candidates:
        return {"success": False, "error": "No search results found"}
    
    logger.info(f"   Found {len(candidates)} candidates")
    
    for i, candidate in enumerate(candidates):
        url = candidate["url"]
        logger.info(f"   [{i+1}/{len(candidates)}] Checking: {url[:60]}...")
        
        content, result = await download_and_verify_image(url, product.expected_content, api_key)
        
        if content and result.get("verified"):
            logger.info(f"   ✅ VERIFIED: {result.get('description', '')[:50]}")
            
            if dry_run:
                return {
                    "success": True,
                    "dry_run": True,
                    "url": url,
                    "description": result.get("description", ""),
                }
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            
            return {
                "success": True,
                "url": url,
                "path": str(output_path),
                "description": result.get("description", ""),
                "confidence": result.get("confidence", 0),
            }
        else:
            reason = result.get("error") or result.get("description", "Did not match")
            logger.info(f"   ❌ Rejected: {reason[:50]}")
    
    return {"success": False, "error": f"No verified images found in {len(candidates)} candidates"}


# =============================================================================
# Main Verification Functions
# =============================================================================

async def verify_all_products(api_key: str) -> list[dict]:
    """Verify all product images with Gemini VLM."""
    results = []
    
    print("\n" + "=" * 70)
    print("CURATED WARDROBE VERIFICATION (Gemini VLM)")
    print("=" * 70 + "\n")
    
    for product in PRODUCTS:
        image_path = IMAGES_PATH / product.local_image
        
        if not image_path.exists():
            print(f"❌ {product.name:<25} FILE NOT FOUND: {product.local_image}")
            results.append({
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "status": "missing",
                "error": "File not found",
            })
            continue
        
        result = await verify_image_with_gemini(image_path, product.expected_content, api_key)
        
        if result.get("verified"):
            status = "✅"
            status_text = "PASS"
        elif result.get("matches"):
            status = "⚠️"
            status_text = "WARN"
        else:
            status = "❌"
            status_text = "FAIL"
        
        desc = result.get("description", "")[:40]
        print(f"{status} {product.brand:<15} {product.name:<20} {status_text:<5} | {desc}")
        
        if not result.get("verified"):
            if not result.get("matches"):
                print(f"   → Doesn't match: {product.expected_content[:50]}...")
        
        results.append({
            "id": product.id,
            "name": product.name,
            "brand": product.brand,
            "status": "pass" if result.get("verified") else "fail",
            "image": product.local_image,
            **result,
        })
        
        await asyncio.sleep(0.5)
    
    passed = sum(1 for r in results if r.get("status") == "pass")
    failed = sum(1 for r in results if r.get("status") == "fail")
    missing = sum(1 for r in results if r.get("status") == "missing")
    
    print("\n" + "-" * 70)
    print(f"SUMMARY: {passed} passed, {failed} failed, {missing} missing")
    print("-" * 70 + "\n")
    
    return results


async def fix_failed_images(api_key: str, dry_run: bool = False) -> None:
    """Find and download correct images for failed verifications."""
    print("\n" + "=" * 70)
    print("FINDING CORRECT IMAGES" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 70 + "\n")
    
    results = await verify_all_products(api_key)
    
    failed = [r for r in results if r.get("status") in ("fail", "missing")]
    
    if not failed:
        print("✅ All images verified! Nothing to fix.")
        return
    
    print(f"\n🔧 Fixing {len(failed)} images...\n")
    
    for result in failed:
        product = next((p for p in PRODUCTS if p.id == result["id"]), None)
        if not product:
            continue
        
        output_path = IMAGES_PATH / product.local_image
        fix_result = await find_and_download_best_image(product, api_key, output_path, dry_run)
        
        if fix_result.get("success"):
            print(f"   ✅ {product.brand} {product.name}: {fix_result.get('description', 'Downloaded')[:40]}")
        else:
            print(f"   ❌ {product.brand} {product.name}: {fix_result.get('error', 'Failed')}")
        
        print()
        await asyncio.sleep(1)
    
    if not dry_run:
        print("\n✅ Fix complete. Run verification again to confirm.")


# =============================================================================
# Main
# =============================================================================

async def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify and fix product gallery images")
    parser.add_argument("--fix", action="store_true", help="Find and download correct images")
    parser.add_argument("--dry", action="store_true", help="Dry run (don't actually download)")
    parser.add_argument("--api-key", help="Gemini API key (or set GEMINI_API_KEY)")
    args = parser.parse_args()
    
    api_key = args.api_key or GEMINI_API_KEY
    
    if not api_key:
        try:
            from kagami.core.security import get_secret
            api_key = get_secret("gemini_api_key")
        except:
            pass
    
    if not api_key:
        print("❌ No Gemini API key. Set GEMINI_API_KEY or use --api-key")
        return 1
    
    if args.fix:
        await fix_failed_images(api_key, dry_run=args.dry)
    else:
        results = await verify_all_products(api_key)
        
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(REPORT_PATH, "w") as f:
            json.dump(results, f, indent=2)
        print(f"📄 Report saved to: {REPORT_PATH}")
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
