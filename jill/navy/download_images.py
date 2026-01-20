#!/usr/bin/env python3
"""
Parallel Image Downloader with Crawling for Navy Gallery
Downloads product images from various CDNs with fallback strategies
"""

import asyncio
import aiohttp
import os
from pathlib import Path
from typing import Optional, List, Dict
import re

# Configuration
IMAGES_DIR = Path("/Users/schizodactyl/projects/art/jill/navy/images")
MIN_VALID_SIZE = 10000  # bytes - anything smaller is likely a placeholder

# Headers to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Image sources with fallback URLs for each product
IMAGE_SOURCES: Dict[str, List[str]] = {
    "naadam-cashmere-jogger.jpg": [
        "https://naadam.co/cdn/shop/files/CASHMERE_SWEATPANTS_NAVY_4.jpg?v=1700000000&width=1000",
        "https://cdn.shopify.com/s/files/1/0301/9114/3029/files/CASHMERE_SWEATPANTS_NAVY_4.jpg",
    ],
    "alex-mill-chino.jpg": [
        "https://cdn.shopify.com/s/files/1/0070/1922/files/STD-PLT-CHN-DNV_01.jpg?v=1700000000",
        "https://www.alexmill.com/cdn/shop/files/STD-PLT-CHN-DNV_01.jpg?v=1700000000",
    ],
    "staud-myla.jpg": [
        "https://staud.clothing/cdn/shop/files/midi-marlowe-dress-navy-01.jpg?v=1700000000",
        "https://cdn.shopify.com/s/files/1/2426/0250/files/midi-marlowe-dress-navy-01.jpg",
    ],
    "reformation-heron.jpg": [
        "https://media.thereformation.com/image/upload/f_auto,q_auto:eco,w_1000/prod/catalog/images/1316625NAV/1316625NAV-1.jpg",
        "https://media.thereformation.com/image/upload/w_1000/v1/prod/catalog/images/1316625MNR/1316625MNR-1.jpg",
    ],
    "faithfull-sundress.jpg": [
        "https://cdn.shopify.com/s/files/1/0072/0554/1853/files/VALERIA_MIDI_DRESS-Navy_Sailor_Stripe_01.jpg",
        "https://faithfullthebrand.com/cdn/shop/products/VALERIA_MIDI_DRESS-Navy_Sailor_Stripe_01.jpg",
    ],
    "velvet-blazer.jpg": [
        "https://velvet-tees.com/cdn/shop/files/kyla-silk-velvet-blazer-navy-01.jpg",
        "https://cdn.shopify.com/s/files/1/0027/5053/files/kyla-silk-velvet-blazer-navy-01.jpg",
    ],
    "eileen-fisher-linen.jpg": [
        "https://www.eileenfisher.com/dw/image/v2/AAJW_PRD/on/demandware.static/-/Sites-ef_storefront_catalog/default/dwf8a8b8a8/images/large/S5RII-P4701-400_1.jpg",
    ],
    "jenni-kayne-jogger.jpg": [
        "https://naadam.co/cdn/shop/files/CASHMERE_SWEATPANTS_NAVY_4.jpg?v=1700000000&width=1000",
    ],
}


async def download_image(session: aiohttp.ClientSession, url: str, filepath: Path) -> bool:
    """Download a single image from URL"""
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status == 200:
                content = await response.read()
                if len(content) >= MIN_VALID_SIZE:
                    filepath.write_bytes(content)
                    print(f"  ✓ Downloaded {filepath.name}: {len(content):,} bytes")
                    return True
                else:
                    print(f"  ⚠ {filepath.name}: Too small ({len(content)} bytes)")
            else:
                print(f"  ✗ {filepath.name}: HTTP {response.status}")
    except Exception as e:
        print(f"  ✗ {filepath.name}: {str(e)[:50]}")
    return False


async def download_with_fallbacks(session: aiohttp.ClientSession, filename: str, urls: List[str]) -> bool:
    """Try downloading from multiple URLs until one succeeds"""
    filepath = IMAGES_DIR / filename

    # Skip if already have a valid image
    if filepath.exists() and filepath.stat().st_size >= MIN_VALID_SIZE:
        print(f"✓ {filename}: Already valid ({filepath.stat().st_size:,} bytes)")
        return True

    print(f"\n📥 Downloading {filename}...")
    for i, url in enumerate(urls, 1):
        print(f"  Trying source {i}/{len(urls)}...")
        if await download_image(session, url, filepath):
            return True

    print(f"  ❌ All sources failed for {filename}")
    return False


async def main():
    """Main download orchestration"""
    print("=" * 60)
    print("Navy Gallery Image Downloader")
    print("=" * 60)

    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    connector = aiohttp.TCPConnector(limit=10)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for filename, urls in IMAGE_SOURCES.items():
            tasks.append(download_with_fallbacks(session, filename, urls))

        results = await asyncio.gather(*tasks)

        success = sum(1 for r in results if r)
        total = len(results)
        print("\n" + "=" * 60)
        print(f"Downloaded: {success}/{total} images")

        print("\n📊 Current Image Status:")
        for img in sorted(IMAGES_DIR.glob("*.jpg")):
            size = img.stat().st_size
            status = "✓" if size >= MIN_VALID_SIZE else "⚠ placeholder"
            print(f"  {size:>10,} bytes  {img.name}  {status}")


if __name__ == "__main__":
    asyncio.run(main())
