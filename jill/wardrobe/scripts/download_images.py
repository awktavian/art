#!/usr/bin/env python3
"""Download product images for Jill's Curated Wardrobe.

Uses the verified URLs from gallery.json to fetch product images.
"""

import asyncio
import json
import os
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

# Paths
SCRIPT_DIR = Path(__file__).parent
WARDROBE_DIR = SCRIPT_DIR.parent
DATA_DIR = WARDROBE_DIR / "data"
IMAGES_DIR = WARDROBE_DIR / "images"

# Ensure images directory exists
IMAGES_DIR.mkdir(exist_ok=True)

# Headers to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


async def fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    """Fetch a page's HTML content."""
    try:
        response = await client.get(url, follow_redirects=True, timeout=30.0)
        if response.status_code == 200:
            return response.text
        print(f"  ⚠ Status {response.status_code} for {url}")
        return None
    except Exception as e:
        print(f"  ✗ Error fetching {url}: {e}")
        return None


def extract_product_image(html: str, brand: str) -> str | None:
    """Extract the main product image URL from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    
    # Try common patterns
    image_selectors = [
        # OpenGraph image (most reliable)
        ("meta[property='og:image']", "content"),
        # Twitter card image
        ("meta[name='twitter:image']", "content"),
        # Schema.org product image
        ("meta[itemprop='image']", "content"),
        # Common product image classes
        ("img.product-image", "src"),
        ("img.product__image", "src"),
        ("img[data-src]", "data-src"),
        ("img.pdp-image", "src"),
        (".product-gallery img", "src"),
        (".product-image-container img", "src"),
        ("picture source", "srcset"),
    ]
    
    for selector, attr in image_selectors:
        element = soup.select_one(selector)
        if element:
            value = element.get(attr)
            if value:
                # Handle srcset (take first URL)
                if " " in value:
                    value = value.split()[0]
                # Clean up URL
                if value.startswith("//"):
                    value = "https:" + value
                if value and not value.startswith("data:"):
                    return value
    
    return None


async def download_image(client: httpx.AsyncClient, url: str, filepath: Path) -> bool:
    """Download an image to the specified path."""
    try:
        response = await client.get(url, follow_redirects=True, timeout=30.0)
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if "image" in content_type or url.endswith((".jpg", ".jpeg", ".png", ".webp")):
                filepath.write_bytes(response.content)
                return True
        return False
    except Exception as e:
        print(f"  ✗ Error downloading image: {e}")
        return False


async def process_product(client: httpx.AsyncClient, product: dict) -> bool:
    """Process a single product: fetch page, extract image, download."""
    product_id = product["id"]
    brand = product["brand"]
    local_image = product.get("local_image", f"{product_id}.jpg")
    image_path = IMAGES_DIR / local_image
    
    # Skip if image already exists
    if image_path.exists() and image_path.stat().st_size > 1000:
        print(f"  ✓ {brand}: Image already exists")
        return True
    
    url = product["product_url"]
    print(f"  → {brand}: Fetching {url[:60]}...")
    
    # Fetch the product page
    html = await fetch_page(client, url)
    if not html:
        return False
    
    # Extract image URL
    image_url = extract_product_image(html, brand)
    if not image_url:
        print(f"  ⚠ {brand}: Could not find product image")
        return False
    
    print(f"  → {brand}: Found image, downloading...")
    
    # Download the image
    success = await download_image(client, image_url, image_path)
    if success:
        print(f"  ✓ {brand}: Saved to {local_image}")
        return True
    else:
        print(f"  ✗ {brand}: Failed to download image")
        return False


async def main():
    """Main function to download all product images."""
    # Load gallery data
    gallery_path = DATA_DIR / "gallery.json"
    if not gallery_path.exists():
        print("✗ gallery.json not found")
        return
    
    with open(gallery_path) as f:
        gallery = json.load(f)
    
    products = gallery.get("products", [])
    print(f"\n{'='*60}")
    print(f"IMAGE DOWNLOADER — Jill's Curated Wardrobe")
    print(f"{'='*60}\n")
    print(f"Found {len(products)} products to process\n")
    
    success_count = 0
    
    async with httpx.AsyncClient(headers=HEADERS) as client:
        for product in products:
            success = await process_product(client, product)
            if success:
                success_count += 1
            await asyncio.sleep(1)  # Be nice to servers
    
    print(f"\n{'─'*60}")
    print(f"IMAGES: {success_count}/{len(products)} downloaded")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
