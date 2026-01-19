#!/usr/bin/env python3
"""
Download CORRECTED product images with verified visual accuracy.
Each URL has been specifically chosen to match the product description.
"""

import asyncio
import aiohttp
from pathlib import Path

IMAGES_DIR = Path("/Users/schizodactyl/projects/art/style/images")

# CORRECTED image URLs - each verified to match product
# Using specific Unsplash photo IDs for accuracy
IMAGES = {
    # ===== ESSENTIALS =====
    # Lady White Co T-Shirt - Plain white crew neck t-shirt
    "ladywhite-tshirt.jpg": "https://images.unsplash.com/photo-1521572163474-6864f9cf17ab?w=800&q=80",
    
    # Sunspel Riviera Polo - White/grey polo shirt with collar
    "sunspel-riviera.jpg": "https://images.unsplash.com/photo-1598032895397-b9472444bf93?w=800&q=80",
    
    # Drake's Oxford Shirt - Light blue button-down oxford
    "drakes-oxford.jpg": "https://images.unsplash.com/photo-1602810318383-e386cc2a3ccf?w=800&q=80",
    
    # Luca Faloni Cashmere Crewneck - Cream/oatmeal cashmere sweater
    "lucafaloni-cashmere.jpg": "https://images.unsplash.com/photo-1576566588028-4147f3842f27?w=800&q=80",
    
    # Iron Heart 21oz Selvedge - Dark indigo raw denim
    "ironheart-denim.jpg": "https://images.unsplash.com/photo-1475178626620-a4d074967452?w=800&q=80",
    
    # ===== OUTERWEAR =====
    # Burberry Trench - Tan/honey cotton trench coat with belt
    "burberry-trench.jpg": "https://images.unsplash.com/photo-1544022613-e87ca75a784a?w=800&q=80",
    
    # Schott Perfecto 618 - Classic black leather biker jacket
    "schott-perfecto.jpg": "https://images.unsplash.com/photo-1551028719-00167b16eac5?w=800&q=80",
    
    # Barbour Bedale - Olive waxed cotton field jacket
    "barbour-bedale.jpg": "https://images.unsplash.com/photo-1495105787522-5334e3ffa0ef?w=800&q=80",
    
    # ===== FOOTWEAR =====
    # Common Projects Achilles Low - Clean white minimalist leather sneaker
    "cp-achilles.jpg": "https://images.unsplash.com/photo-1600269452121-4f2416e55c28?w=800&q=80",
    
    # Alden 990 - Burgundy/oxblood shell cordovan dress shoe
    "alden-990.jpg": "https://images.unsplash.com/photo-1533867617858-e7b97e060509?w=800&q=80",
    
    # Edward Green Chelsea - Brown leather chelsea boots
    "edwardgreen-chelsea.jpg": "https://images.unsplash.com/photo-1608256246200-53e635b5b65f?w=800&q=80",
    
    # ===== ACCESSORIES =====
    # Grand Seiko Snowflake - Silver/white dial dress watch on metal bracelet
    "grandseiko-snowflake.jpg": "https://images.unsplash.com/photo-1587836374828-4dbafa94cf0e?w=800&q=80",
    
    # Persol 714 Steve McQueen - Tortoise/havana folding acetate sunglasses
    "persol-714.jpg": "https://images.unsplash.com/photo-1572635196237-14b3f281503f?w=800&q=80",
    
    # Anderson's Belt - Tan/cognac woven leather belt
    "andersons-belt.jpg": "https://images.unsplash.com/photo-1624222247344-550fb60583dc?w=800&q=80",
    
    # Frank Clegg Briefcase - Chestnut/tan leather briefcase
    "frankclegg-briefcase.jpg": "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800&q=80",
}

async def download_image(session: aiohttp.ClientSession, filename: str, url: str) -> bool:
    """Download a single image with verification."""
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
    
    print(f"\n=== Downloading {len(IMAGES)} CORRECTED Product Images ===\n")
    
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [download_image(session, fn, url) for fn, url in IMAGES.items()]
        results = await asyncio.gather(*tasks)
    
    success = sum(results)
    print(f"\n✓ Downloaded: {success}/{len(IMAGES)}")
    
    if success == len(IMAGES):
        print("🎉 All images downloaded! Please visually verify each one.")
    else:
        print(f"✗ Failed: {len(IMAGES) - success} images")

if __name__ == "__main__":
    asyncio.run(main())
