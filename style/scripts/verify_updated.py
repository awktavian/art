#!/usr/bin/env python3
"""Verify updated product URLs."""

import asyncio
import aiohttp

PRODUCTS = [
    ("Lady White Co", "https://www.ladywhiteco.com/collections/t-shirts"),
    ("Sunspel", "https://us.sunspel.com/collections/mens-polo-shirts"),
    ("Drake's", "https://www.drakes.com/usa/shirts"),
    ("Luca Faloni", "https://www.lucafaloni.com/collections/cashmere"),
    ("Iron Heart", "https://www.ironheartamerica.com/bottoms/"),
    ("Burberry", "https://us.burberry.com/"),
    ("Schott NYC", "https://www.schottnyc.com/products/classic-perfecto-steerhide-leather-motorcycle-jacket.htm"),
    ("Barbour", "https://www.barbour.com/us/categories/mens/wax-jackets"),
    ("Common Projects (SSENSE)", "https://www.ssense.com/en-us/men/designers/common-projects"),
    ("Alden (Shoe Mart)", "https://www.theshoemart.com/alden-mens-990-plain-toe-blucher-color-8-shell-cordovan/"),
    ("Edward Green", "https://www.edwardgreen.com/shop/shoes/boots.html"),
    ("Grand Seiko", "https://www.grand-seiko.com/us-en/collections/sbga211g"),
    ("Persol (Sunglass Hut)", "https://www.sunglasshut.com/us/persol"),
    ("Anderson's (Mr Porter)", "https://www.mrporter.com/en-us/mens/designer/andersons"),
    ("Frank Clegg", "https://frankclegg.com/collections/briefcases/products/zip-top-briefcase"),
]

async def check_url(session, name, url):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        async with session.get(url, headers=headers, timeout=15, allow_redirects=True) as resp:
            status = "✓" if resp.status == 200 else f"✗ ({resp.status})"
            print(f"  {status} {name}: {url}")
            return resp.status == 200
    except asyncio.TimeoutError:
        print(f"  ✗ (TIMEOUT) {name}: {url}")
        return False
    except Exception as e:
        print(f"  ✗ (ERROR) {name}: {str(e)[:30]}")
        return False

async def main():
    print("\n=== Verifying Updated URLs ===\n")
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        results = await asyncio.gather(*[check_url(session, n, u) for n, u in PRODUCTS])
    
    verified = sum(results)
    print(f"\n✓ Verified: {verified}/{len(PRODUCTS)}")
    print(f"✗ Failed: {len(PRODUCTS) - verified}/{len(PRODUCTS)}")

if __name__ == "__main__":
    asyncio.run(main())
