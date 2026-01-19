#!/usr/bin/env python3
"""
Shopping Curator - A Generalized System for Product Curation

This is the SINGLE SOURCE OF TRUTH for product data.
Validates URLs, verifies images with Gemini VLM, and generates HTML.

Usage:
    python scripts/shopping_curator.py verify          # Verify all URLs and images
    python scripts/shopping_curator.py fix-images     # Auto-fix failed images
    python scripts/shopping_curator.py fix-urls       # Suggest URL fixes
    python scripts/shopping_curator.py generate-html  # Regenerate HTML from data
    python scripts/shopping_curator.py audit          # Full audit report
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

import httpx
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# =============================================================================
# Paths
# =============================================================================
SCRIPT_DIR = Path(__file__).parent
GALLERY_PATH = SCRIPT_DIR.parent
IMAGES_PATH = GALLERY_PATH / "images"
DATA_PATH = GALLERY_PATH / "data"
HTML_PATH = GALLERY_PATH / "index.html"

# =============================================================================
# Configuration
# =============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# URL validation rules - NO search URLs allowed
FORBIDDEN_URL_PATTERNS = [
    r'/sr\?',           # Nordstrom search
    r'/s\?k=',          # Amazon search  
    r'/search\?q=',     # Generic search (except Todd Snyder which is ok)
    r'google\.com/search',
    r'bing\.com/search',
]

# Trusted retailers (these are okay even with search)
TRUSTED_SEARCH_DOMAINS = [
    'toddsnyder.com',    # Their search works well
    'etsy.com',          # Search is the product
]


# =============================================================================
# Product Data Model
# =============================================================================
@dataclass
class Product:
    """A curated product with all metadata."""
    id: str
    name: str
    brand: str
    category: str
    price: int
    product_url: str
    local_image: str
    
    # For verification
    expected_description: str  # What Gemini should see
    search_query: str          # For finding replacement images
    
    # Optional metadata
    color: str = ""
    material: str = ""
    origin: str = ""
    badge: str = ""
    
    # Verification status (populated at runtime)
    url_status: Optional[int] = None
    image_verified: Optional[bool] = None
    image_description: Optional[str] = None


# =============================================================================
# SINGLE SOURCE OF TRUTH - All Products
# =============================================================================
PRODUCTS = [
    # ===== ESSENTIALS =====
    Product(
        id="ladywhite-tshirt",
        name="Our T-Shirt",
        brand="Lady White Co",
        category="Essentials",
        price=90,
        product_url="https://www.ladywhiteco.com/collections/t-shirts",
        local_image="ladywhite-tshirt.jpg",
        expected_description="plain white crew neck cotton t-shirt, simple minimal design",
        search_query="plain white t-shirt cotton minimal menswear product photo",
        color="White",
        material="100% Cotton",
        origin="Los Angeles",
        badge="Essential",
    ),
    Product(
        id="sunspel-riviera",
        name="Riviera Polo",
        brand="Sunspel",
        category="Essentials",
        price=115,
        product_url="https://us.sunspel.com/collections/mens-polo-shirts",
        local_image="sunspel-riviera.jpg",
        expected_description="polo shirt with collar and buttons, cotton pique knit",
        search_query="polo shirt cotton pique menswear collar product photo",
        color="Grey",
        material="Sea Island Cotton",
        origin="England",
        badge="Classic",
    ),
    Product(
        id="drakes-oxford",
        name="Oxford BD Shirt",
        brand="Drake's",
        category="Essentials",
        price=295,
        product_url="https://www.drakes.com/usa/shirts",
        local_image="drakes-oxford.jpg",
        expected_description="light blue oxford cloth button-down shirt, plain no pattern",
        search_query="light blue oxford button down shirt plain cotton product",
        color="Light Blue",
        material="Oxford Cotton",
        origin="England",
        badge="Versatile",
    ),
    Product(
        id="lucafaloni-cashmere",
        name="Cashmere Crewneck",
        brand="Luca Faloni",
        category="Essentials",
        price=395,
        product_url="https://www.lucafaloni.com/collections/cashmere",
        local_image="lucafaloni-cashmere.jpg",
        expected_description="cream or oatmeal colored cashmere sweater crewneck, knitwear",
        search_query="cream oatmeal cashmere sweater crewneck knitwear product",
        color="Oatmeal",
        material="100% Cashmere",
        origin="Italy",
        badge="Luxury",
    ),
    Product(
        id="ironheart-denim",
        name="21oz Selvedge Denim",
        brand="Iron Heart",
        category="Essentials",
        price=395,
        product_url="https://www.ironheartamerica.com/bottoms/",
        local_image="ironheart-denim.jpg",
        expected_description="dark indigo raw selvedge denim jeans, heavy weight",
        search_query="dark indigo raw selvedge denim jeans Japanese product",
        color="Indigo",
        material="21oz Denim",
        origin="Japan",
        badge="Heritage",
    ),
    
    # ===== OUTERWEAR =====
    Product(
        id="burberry-trench",
        name="Kensington Trench",
        brand="Burberry",
        category="Outerwear",
        price=2290,
        product_url="https://us.burberry.com/",
        local_image="burberry-trench.jpg",
        expected_description="tan honey beige trench coat with belt, cotton gabardine, classic style",
        search_query="tan beige trench coat belted cotton classic product photo",
        color="Tan",
        material="Cotton Gabardine",
        origin="England",
        badge="Iconic",
    ),
    Product(
        id="schott-perfecto",
        name="Perfecto 618",
        brand="Schott NYC",
        category="Outerwear",
        price=900,
        product_url="https://www.schottnyc.com/products/classic-perfecto-steerhide-leather-motorcycle-jacket.htm",
        local_image="schott-perfecto.jpg",
        expected_description="black leather motorcycle biker jacket, asymmetric zipper, classic",
        search_query="black leather motorcycle jacket Perfecto biker product",
        color="Black",
        material="Steerhide Leather",
        origin="USA",
        badge="Rebel",
    ),
    Product(
        id="barbour-bedale",
        name="Bedale Waxed Jacket",
        brand="Barbour",
        category="Outerwear",
        price=450,
        product_url="https://www.barbour.com/us/",
        local_image="barbour-bedale.jpg",
        expected_description="olive green waxed cotton field jacket, British heritage style",
        search_query="olive green waxed cotton jacket Barbour field product",
        color="Olive",
        material="Waxed Cotton",
        origin="England",
        badge="Country",
    ),
    
    # ===== FOOTWEAR =====
    Product(
        id="cp-achilles",
        name="Achilles Low",
        brand="Common Projects",
        category="Footwear",
        price=450,
        product_url="https://www.ssense.com/en-us/men/designers/common-projects",
        local_image="cp-achilles.jpg",
        expected_description="white minimalist leather sneakers, clean simple low-top, gold serial number",
        search_query="white minimalist leather sneakers clean simple low-top product",
        color="White",
        material="Italian Leather",
        origin="Italy",
        badge="Minimal",
    ),
    Product(
        id="alden-990",
        name="990 Plain Toe Blucher",
        brand="Alden",
        category="Footwear",
        price=799,
        product_url="https://www.theshoemart.com/alden-mens-990-plain-toe-blucher-color-8-shell-cordovan/",
        local_image="alden-990.jpg",
        expected_description="burgundy oxblood shell cordovan dress shoes, plain toe derby",
        search_query="burgundy cordovan dress shoes derby plain toe product",
        color="Color 8",
        material="Shell Cordovan",
        origin="USA",
        badge="Heirloom",
    ),
    Product(
        id="edwardgreen-chelsea",
        name="Chelsea Boot",
        brand="Edward Green",
        category="Footwear",
        price=1650,
        product_url="https://www.edwardgreen.com/shop",
        local_image="edwardgreen-chelsea.jpg",
        expected_description="brown leather chelsea boots, elegant dress boot",
        search_query="brown chelsea boots mens luxury leather",
        color="Chestnut",
        material="Calf Leather",
        origin="England",
        badge="Bespoke",
    ),
    
    # ===== ACCESSORIES =====
    Product(
        id="grandseiko-snowflake",
        name="Snowflake SBGA211",
        brand="Grand Seiko",
        category="Accessories",
        price=6300,
        product_url="https://www.grand-seiko.com/us-en/collections/sbga211g",
        local_image="grandseiko-snowflake.jpg",
        expected_description="silver titanium watch white textured dial, elegant dress watch metal bracelet",
        search_query="silver white dial dress watch elegant titanium product",
        color="White",
        material="Titanium",
        origin="Japan",
        badge="Precision",
    ),
    Product(
        id="persol-714",
        name="714 Steve McQueen",
        brand="Persol",
        category="Accessories",
        price=418,
        product_url="https://www.persol.com/usa",
        local_image="persol-714.jpg",
        expected_description="tortoise havana brown folding sunglasses, acetate classic style",
        search_query="tortoise brown folding sunglasses acetate classic product",
        color="Havana",
        material="Acetate",
        origin="Italy",
        badge="Icon",
    ),
    Product(
        id="andersons-belt",
        name="Woven Leather Belt",
        brand="Anderson's",
        category="Accessories",
        price=195,
        product_url="https://toddsnyder.com/search?q=andersons+belt",
        local_image="andersons-belt.jpg",
        expected_description="tan brown woven braided leather belt",
        search_query="braided woven leather belt tan brown mens",
        color="Tan",
        material="Woven Leather",
        origin="Italy",
        badge="Artisan",
    ),
    Product(
        id="frankclegg-briefcase",
        name="Zip-Top Briefcase",
        brand="Frank Clegg",
        category="Accessories",
        price=1100,
        product_url="https://frankclegg.com/collections/briefcases/products/zip-top-briefcase",
        local_image="frankclegg-briefcase.jpg",
        expected_description="tan brown leather briefcase business bag",
        search_query="tan leather briefcase business bag mens luxury",
        color="Chestnut",
        material="Bridle Leather",
        origin="USA",
        badge="Executive",
    ),
]


# =============================================================================
# URL Validation
# =============================================================================
def is_search_url(url: str) -> bool:
    """Check if URL is a forbidden search URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    
    # Allow trusted search domains
    for trusted in TRUSTED_SEARCH_DOMAINS:
        if trusted in domain:
            return False
    
    # Check forbidden patterns
    for pattern in FORBIDDEN_URL_PATTERNS:
        if re.search(pattern, url):
            return True
    
    return False


async def verify_url(url: str, timeout: float = 15.0) -> tuple[int, str]:
    """Verify a URL returns 200 OK.
    
    Returns (status_code, error_message).
    """
    # First check if it's a forbidden search URL
    if is_search_url(url):
        return -1, "SEARCH_URL_FORBIDDEN"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            return response.status_code, ""
    except httpx.TimeoutException:
        return -2, "TIMEOUT"
    except Exception as e:
        return -3, str(e)[:50]


async def verify_all_urls() -> list[dict]:
    """Verify all product URLs."""
    results = []
    
    print("\n" + "=" * 70)
    print("URL VERIFICATION")
    print("=" * 70 + "\n")
    
    for product in PRODUCTS:
        status, error = await verify_url(product.product_url)
        
        if status == 200:
            icon = "✅"
        elif status == -1:
            icon = "🚫"
        elif status in (-2, -3):
            icon = "⏱️"
        else:
            icon = "❌"
        
        status_str = str(status) if status > 0 else error
        print(f"{icon} {product.brand:<15} {product.name:<20} | {status_str}")
        
        results.append({
            "id": product.id,
            "brand": product.brand,
            "name": product.name,
            "url": product.product_url,
            "status": status,
            "error": error,
            "ok": status == 200,
        })
    
    ok_count = sum(1 for r in results if r["ok"])
    print(f"\n{'─' * 70}")
    print(f"URLS: {ok_count}/{len(results)} verified")
    
    return results


# =============================================================================
# Image Verification with Gemini
# =============================================================================
async def verify_image_with_gemini(
    image_path: Path,
    expected_content: str,
    api_key: str,
) -> dict[str, Any]:
    """Verify an image using Gemini VLM with improved prompt."""
    if not api_key:
        return {"error": "No API key", "verified": False}
    
    if not image_path.exists():
        return {"error": "File not found", "verified": False}
    
    try:
        with open(image_path, "rb") as f:
            image_data = f.read()
        image_b64 = base64.b64encode(image_data).decode()
    except Exception as e:
        return {"error": f"Failed to read: {e}", "verified": False}
    
    try:
        img = Image.open(image_path)
        mime_type = f"image/{img.format.lower()}" if img.format else "image/jpeg"
    except:
        mime_type = "image/jpeg"
    
    # Improved prompt for better accuracy
    prompt = f"""You are verifying product images for an e-commerce fashion gallery.

EXPECTED PRODUCT: {expected_content}

Analyze this image and answer:

1. MATCH: Does this image show the expected product? (YES/NO)
   - YES if it shows the described item type, color, and style
   - NO if it's a different product type or significantly different

2. DESCRIPTION: What exactly do you see? (one sentence)

3. QUALITY: Is this a good product photo? (YES/NO)
   - YES if it's a clear product image (can include model wearing it)
   - NO if it's blurry, wrong product, stock photo placeholder, or error image

Format your response EXACTLY as:
MATCH: YES or NO
DESCRIPTION: [your description]
QUALITY: YES or NO"""

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={api_key}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": mime_type, "data": image_b64}}
            ]
        }],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 300}
    }
    
    # Retry with exponential backoff for rate limiting
    max_retries = 3
    data = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 429:
                    wait_time = 2 ** (attempt + 1)
                    logger.warning(f"Rate limited, waiting {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    continue
                response.raise_for_status()
                data = response.json()
                break
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 2 ** (attempt + 1)
                await asyncio.sleep(wait_time)
                continue
            return {"error": str(e), "verified": False}
        except Exception as e:
            return {"error": str(e), "verified": False}
    
    if data is None:
        return {"error": "Rate limited after retries", "verified": False}
    
    try:
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        
        result = {
            "matches": False,
            "description": "",
            "quality": False,
            "raw": text,
        }
        
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("MATCH:"):
                result["matches"] = "YES" in line.upper()
            elif line.startswith("DESCRIPTION:"):
                result["description"] = line.replace("DESCRIPTION:", "").strip()
            elif line.startswith("QUALITY:"):
                result["quality"] = "YES" in line.upper()
        
        result["verified"] = result["matches"] and result["quality"]
        return result
        
    except Exception as e:
        return {"error": str(e), "verified": False}


async def verify_all_images(api_key: str) -> list[dict]:
    """Verify all product images."""
    results = []
    
    print("\n" + "=" * 70)
    print("IMAGE VERIFICATION (Gemini VLM)")
    print("=" * 70 + "\n")
    
    for product in PRODUCTS:
        image_path = IMAGES_PATH / product.local_image
        
        if not image_path.exists():
            print(f"❌ {product.brand:<15} {product.name:<20} | MISSING")
            results.append({
                "id": product.id,
                "brand": product.brand,
                "name": product.name,
                "status": "missing",
                "verified": False,
            })
            continue
        
        result = await verify_image_with_gemini(
            image_path, 
            product.expected_description,
            api_key
        )
        
        if result.get("verified"):
            icon = "✅"
        elif result.get("matches"):
            icon = "⚠️"
        else:
            icon = "❌"
        
        desc = result.get("description", "")[:35]
        print(f"{icon} {product.brand:<15} {product.name:<20} | {desc}")
        
        if not result.get("verified") and not result.get("error"):
            if not result.get("matches"):
                print(f"   └─ Expected: {product.expected_description[:50]}")
        
        results.append({
            "id": product.id,
            "brand": product.brand,
            "name": product.name,
            "status": "pass" if result.get("verified") else "fail",
            "verified": result.get("verified", False),
            "description": result.get("description", ""),
            "error": result.get("error", ""),
        })
        
        await asyncio.sleep(1.5)  # Rate limiting - Gemini needs ~1.5s between calls
    
    passed = sum(1 for r in results if r.get("verified"))
    print(f"\n{'─' * 70}")
    print(f"IMAGES: {passed}/{len(results)} verified")
    
    return results


# =============================================================================
# Image Search - Multiple Fallback Methods
# =============================================================================
async def search_images(query: str, max_results: int = 10) -> list[dict]:
    """Search for images using multiple methods with fallback."""
    
    # Try duckduckgo_search library first (more reliable)
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.images(query, max_results=max_results):
                results.append({
                    "url": r.get("image", ""),
                    "source": r.get("url", ""),
                    "title": r.get("title", ""),
                    "width": r.get("width", 0),
                    "height": r.get("height", 0),
                })
        if results:
            return results
    except ImportError:
        logger.info("duckduckgo_search not installed, trying fallback")
    except Exception as e:
        logger.warning(f"DDG search failed: {e}")
    
    # Fallback: Use Unsplash for generic product images
    try:
        results = await search_unsplash(query, max_results)
        if results:
            return results
    except Exception as e:
        logger.warning(f"Unsplash search failed: {e}")
    
    return []


async def search_unsplash(query: str, max_results: int = 10) -> list[dict]:
    """Search Unsplash for images (free, no API key for basic use)."""
    from urllib.parse import quote_plus
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    }
    
    # Unsplash has a public endpoint for search
    url = f"https://unsplash.com/napi/search/photos?query={quote_plus(query)}&per_page={max_results}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                return []
            
            data = response.json()
            results = []
            for photo in data.get("results", [])[:max_results]:
                urls = photo.get("urls", {})
                results.append({
                    "url": urls.get("regular", urls.get("full", "")),
                    "source": photo.get("links", {}).get("html", ""),
                    "title": photo.get("alt_description", ""),
                    "width": photo.get("width", 0),
                    "height": photo.get("height", 0),
                })
            return results
    except Exception as e:
        logger.warning(f"Unsplash search failed: {e}")
        return []


async def search_images_ddg(query: str, max_results: int = 10) -> list[dict]:
    """Deprecated: Use search_images instead."""
    return await search_images(query, max_results)


async def download_image(url: str) -> tuple[bytes | None, str]:
    """Download an image from URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "image/*,*/*",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            content = response.content
            content_type = response.headers.get("content-type", "")
            
            if "text/html" in content_type:
                return None, "URL returned HTML"
            
            if len(content) < 5000:
                return None, f"Too small ({len(content)} bytes)"
            
            try:
                img = Image.open(io.BytesIO(content))
                if img.width < 300 or img.height < 300:
                    return None, f"Dimensions too small: {img.width}x{img.height}"
            except:
                return None, "Invalid image data"
            
            return content, ""
            
    except Exception as e:
        return None, str(e)[:50]


async def fix_failed_image(product: Product, api_key: str, dry_run: bool = False) -> dict:
    """Find and download a verified image for a product."""
    logger.info(f"🔍 Searching for: {product.brand} {product.name}")
    logger.info(f"   Query: {product.search_query}")
    
    candidates = await search_images_ddg(product.search_query, max_results=12)
    
    if not candidates:
        return {"success": False, "error": "No search results"}
    
    logger.info(f"   Found {len(candidates)} candidates")
    
    for i, candidate in enumerate(candidates):
        url = candidate["url"]
        logger.info(f"   [{i+1}/{len(candidates)}] {url[:50]}...")
        
        content, error = await download_image(url)
        if not content:
            logger.info(f"      ❌ Download failed: {error}")
            continue
        
        # Save temporarily and verify
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(content)
            temp_path = Path(f.name)
        
        try:
            result = await verify_image_with_gemini(
                temp_path,
                product.expected_description,
                api_key
            )
        finally:
            temp_path.unlink()
        
        if result.get("verified"):
            logger.info(f"      ✅ VERIFIED: {result.get('description', '')[:40]}")
            
            if dry_run:
                return {"success": True, "dry_run": True, "url": url}
            
            # Save the image
            output_path = IMAGES_PATH / product.local_image
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(content)
            
            return {
                "success": True,
                "url": url,
                "path": str(output_path),
                "description": result.get("description", ""),
            }
        else:
            desc = result.get("description", "No match")[:40]
            logger.info(f"      ❌ Rejected: {desc}")
        
        await asyncio.sleep(0.3)
    
    return {"success": False, "error": "No verified images found"}


async def fix_all_failed_images(api_key: str, dry_run: bool = False) -> None:
    """Fix all failed images."""
    print("\n" + "=" * 70)
    print("AUTO-FIX IMAGES" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 70 + "\n")
    
    # First verify to find failures
    image_results = await verify_all_images(api_key)
    
    failed = [r for r in image_results if not r.get("verified")]
    
    if not failed:
        print("\n✅ All images verified! Nothing to fix.")
        return
    
    print(f"\n🔧 Fixing {len(failed)} images...\n")
    
    for result in failed:
        product = next((p for p in PRODUCTS if p.id == result["id"]), None)
        if not product:
            continue
        
        fix_result = await fix_failed_image(product, api_key, dry_run)
        
        if fix_result.get("success"):
            print(f"✅ {product.brand} {product.name}")
        else:
            print(f"❌ {product.brand} {product.name}: {fix_result.get('error', 'Failed')}")
        
        await asyncio.sleep(1)
    
    if not dry_run:
        print("\n✅ Fix complete. Run 'verify' again to confirm.")


# =============================================================================
# Full Audit
# =============================================================================
async def full_audit(api_key: str) -> None:
    """Run full audit of URLs and images."""
    print("\n" + "═" * 70)
    print("FULL SHOPPING GALLERY AUDIT")
    print("═" * 70)
    
    # Verify URLs
    url_results = await verify_all_urls()
    
    # Verify images
    image_results = await verify_all_images(api_key)
    
    # Summary
    url_ok = sum(1 for r in url_results if r.get("ok"))
    img_ok = sum(1 for r in image_results if r.get("verified"))
    total = len(PRODUCTS)
    
    print("\n" + "═" * 70)
    print("AUDIT SUMMARY")
    print("═" * 70)
    print(f"  URLs:   {url_ok}/{total} verified")
    print(f"  Images: {img_ok}/{total} verified")
    print(f"  Total:  {min(url_ok, img_ok)}/{total} fully verified")
    
    if url_ok < total:
        print("\n⚠️  URL ISSUES:")
        for r in url_results:
            if not r.get("ok"):
                print(f"    - {r['brand']} {r['name']}: {r.get('error') or r.get('status')}")
    
    if img_ok < total:
        print("\n⚠️  IMAGE ISSUES:")
        for r in image_results:
            if not r.get("verified"):
                print(f"    - {r['brand']} {r['name']}: {r.get('description', 'Not verified')[:40]}")
    
    # Save report
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    report = {
        "urls": url_results,
        "images": image_results,
        "summary": {
            "total": total,
            "urls_ok": url_ok,
            "images_ok": img_ok,
        }
    }
    with open(DATA_PATH / "audit_report.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Report saved to: {DATA_PATH / 'audit_report.json'}")


# =============================================================================
# Main
# =============================================================================
async def main() -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="Shopping Curator - Verify and fix product gallery")
    parser.add_argument("command", choices=["verify", "fix-images", "fix-urls", "audit"],
                       help="Command to run")
    parser.add_argument("--dry", action="store_true", help="Dry run (don't modify files)")
    parser.add_argument("--api-key", help="Gemini API key (or set GEMINI_API_KEY)")
    args = parser.parse_args()
    
    api_key = args.api_key or GEMINI_API_KEY
    
    if not api_key:
        try:
            sys.path.insert(0, str(Path.home() / "projects/kagami/packages"))
            from kagami.core.security import get_secret
            api_key = get_secret("gemini_api_key")
        except:
            pass
    
    if args.command in ("verify", "fix-images", "audit") and not api_key:
        print("❌ Gemini API key required for image verification.")
        print("   Set GEMINI_API_KEY or use --api-key")
        return 1
    
    if args.command == "verify":
        await verify_all_urls()
        await verify_all_images(api_key)
    elif args.command == "fix-images":
        await fix_all_failed_images(api_key, dry_run=args.dry)
    elif args.command == "fix-urls":
        results = await verify_all_urls()
        failed = [r for r in results if not r["ok"]]
        if failed:
            print("\n⚠️  Manual fixes needed for:")
            for r in failed:
                print(f"    {r['brand']} {r['name']}: {r['url']}")
        else:
            print("\n✅ All URLs verified!")
    elif args.command == "audit":
        await full_audit(api_key)
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
