#!/usr/bin/env python3
"""
Download product images from reliable sources.
Uses Unsplash and direct brand images where available.
"""

import asyncio
import aiohttp
import os
from pathlib import Path

IMAGES_DIR = Path("/Users/schizodactyl/projects/art/style/images")

# Image sources - using Unsplash IDs for reliable, high-quality fashion photos
# Each image is selected to match the product color, style, and aesthetic
IMAGES = {
    # Essentials
    "ladywhite-tshirt.jpg": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80",  # White t-shirt
    "sunspel-riviera.jpg": "https://images.unsplash.com/photo-1620799140408-edc6dcb6d633?w=800&q=80",  # Grey polo
    "drakes-oxford.jpg": "https://images.unsplash.com/photo-1596755094514-f87e34085b2c?w=800&q=80",  # Blue oxford shirt
    "lucafaloni-cashmere.jpg": "https://images.unsplash.com/photo-1434389677669-e08b4cac3105?w=800&q=80",  # Cream knitwear
    "ironheart-denim.jpg": "https://images.unsplash.com/photo-1542272604-787c3835535d?w=800&q=80",  # Indigo denim
    
    # Outerwear  
    "burberry-trench.jpg": "https://images.unsplash.com/photo-1591047139829-d91aecb6caea?w=800&q=80",  # Tan trench coat
    "schott-perfecto.jpg": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800&q=80",  # Black leather jacket
    "barbour-bedale.jpg": "https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=800&q=80",  # Olive waxed jacket
    
    # Footwear
    "cp-achilles.jpg": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=800&q=80",  # White minimal sneaker
    "alden-990.jpg": "https://images.unsplash.com/photo-1614252235316-8c857d38b5f4?w=800&q=80",  # Brown dress shoe
    "edwardgreen-chelsea.jpg": "https://images.unsplash.com/photo-1638247025967-b4e38f787b76?w=800&q=80",  # Chelsea boots
    
    # Accessories
    "grandseiko-snowflake.jpg": "https://images.unsplash.com/photo-1523170335258-f5ed11844a49?w=800&q=80",  # Luxury watch
    "persol-714.jpg": "https://images.unsplash.com/photo-1511499767150-a48a237f0083?w=800&q=80",  # Tortoise sunglasses
    "andersons-belt.jpg": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800&q=80",  # Brown leather belt
    "frankclegg-briefcase.jpg": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=800&q=80",  # Leather briefcase
}

async def download_image(session: aiohttp.ClientSession, filename: str, url: str) -> bool:
    """Download a single image."""
    filepath = IMAGES_DIR / filename
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    try:
        async with session.get(url, headers=headers, timeout=30) as resp:
            if resp.status == 200:
                content_type = resp.headers.get('content-type', '')
                if 'image' in content_type:
                    content = await resp.read()
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    size_kb = len(content) / 1024
                    print(f"  ✓ {filename} ({size_kb:.1f}KB)")
                    return True
                else:
                    print(f"  ✗ {filename}: Not an image ({content_type})")
                    return False
            else:
                print(f"  ✗ {filename}: HTTP {resp.status}")
                return False
    except Exception as e:
        print(f"  ✗ {filename}: {str(e)[:40]}")
        return False

async def main():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n=== Downloading {len(IMAGES)} Product Images ===\n")
    
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [download_image(session, fn, url) for fn, url in IMAGES.items()]
        results = await asyncio.gather(*tasks)
    
    success = sum(results)
    print(f"\n✓ Downloaded: {success}/{len(IMAGES)}")
    
    if success == len(IMAGES):
        print("🎉 All images downloaded successfully!")
    else:
        print(f"✗ Failed: {len(IMAGES) - success} images")

if __name__ == "__main__":
    asyncio.run(main())
