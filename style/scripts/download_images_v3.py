#!/usr/bin/env python3
"""
Download product images - V3 with more specific search terms.
Using Pexels and carefully selected Unsplash images.
"""

import asyncio
import aiohttp
from pathlib import Path

IMAGES_DIR = Path("/Users/schizodactyl/projects/art/style/images")

# Using specific image URLs that have been visually verified
IMAGES = {
    # White t-shirt (keeping - this one was correct)
    "ladywhite-tshirt.jpg": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80",
    
    # Polo shirt - white/grey knit polo
    "sunspel-riviera.jpg": "https://images.pexels.com/photos/6311392/pexels-photo-6311392.jpeg?w=800",
    
    # Light blue oxford button-down shirt
    "drakes-oxford.jpg": "https://images.pexels.com/photos/3755706/pexels-photo-3755706.jpeg?w=800",
    
    # Cream/beige cashmere sweater
    "lucafaloni-cashmere.jpg": "https://images.pexels.com/photos/6046183/pexels-photo-6046183.jpeg?w=800",
    
    # Indigo denim jeans
    "ironheart-denim.jpg": "https://images.pexels.com/photos/1598507/pexels-photo-1598507.jpeg?w=800",
    
    # Tan/beige trench coat
    "burberry-trench.jpg": "https://images.pexels.com/photos/7679720/pexels-photo-7679720.jpeg?w=800",
    
    # Black leather biker jacket (keeping - was correct)
    "schott-perfecto.jpg": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800&q=80",
    
    # Olive green waxed/field jacket
    "barbour-bedale.jpg": "https://images.pexels.com/photos/6764007/pexels-photo-6764007.jpeg?w=800",
    
    # White leather sneakers
    "cp-achilles.jpg": "https://images.pexels.com/photos/2529148/pexels-photo-2529148.jpeg?w=800",
    
    # Brown/burgundy leather dress shoes
    "alden-990.jpg": "https://images.pexels.com/photos/292999/pexels-photo-292999.jpeg?w=800",
    
    # Brown leather chelsea boots
    "edwardgreen-chelsea.jpg": "https://images.pexels.com/photos/6046227/pexels-photo-6046227.jpeg?w=800",
    
    # Silver/white dial dress watch
    "grandseiko-snowflake.jpg": "https://images.pexels.com/photos/190819/pexels-photo-190819.jpeg?w=800",
    
    # Tortoise/brown sunglasses
    "persol-714.jpg": "https://images.pexels.com/photos/701877/pexels-photo-701877.jpeg?w=800",
    
    # Tan leather woven belt
    "andersons-belt.jpg": "https://images.pexels.com/photos/45055/pexels-photo-45055.jpeg?w=800",
    
    # Brown leather briefcase/bag
    "frankclegg-briefcase.jpg": "https://images.pexels.com/photos/1152077/pexels-photo-1152077.jpeg?w=800",
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
                    print(f"  ✗ {filename}: Not an image")
                    return False
            else:
                print(f"  ✗ {filename}: HTTP {resp.status}")
                return False
    except Exception as e:
        print(f"  ✗ {filename}: {str(e)[:40]}")
        return False

async def main():
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n=== Downloading {len(IMAGES)} Product Images (V3) ===\n")
    
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [download_image(session, fn, url) for fn, url in IMAGES.items()]
        results = await asyncio.gather(*tasks)
    
    success = sum(results)
    print(f"\n✓ Downloaded: {success}/{len(IMAGES)}")

if __name__ == "__main__":
    asyncio.run(main())
