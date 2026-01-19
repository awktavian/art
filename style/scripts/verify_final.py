#!/usr/bin/env python3
"""Final verification of all product URLs."""

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
    ("Barbour (Orvis)", "https://www.orvis.com/barbour-bedale-wax-jacket/2WXK.html"),
    ("Common Projects (SSENSE)", "https://www.ssense.com/en-us/men/designers/common-projects"),
    ("Alden (Shoe Mart)", "https://www.theshoemart.com/alden-mens-990-plain-toe-blucher-color-8-shell-cordovan/"),
    ("Edward Green (Skoaktiebolaget)", "https://www.skoaktiebolaget.com/collections/edward-green"),
    ("Grand Seiko", "https://www.grand-seiko.com/us-en/collections/sbga211g"),
    ("Persol (Amazon)", "https://www.amazon.com/dp/B001CNEQJ8"),
    ("Anderson's (Amazon)", "https://www.amazon.com/s?k=andersons+woven+leather+belt"),
    ("Frank Clegg", "https://frankclegg.com/collections/briefcases/products/zip-top-briefcase"),
]

async def check_url(session, name, url):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    try:
        async with session.get(url, headers=headers, timeout=15, allow_redirects=True) as resp:
            status = "✓" if resp.status == 200 else f"✗ ({resp.status})"
            print(f"  {status} {name}")
            return resp.status == 200
    except asyncio.TimeoutError:
        print(f"  ✗ (TIMEOUT) {name}")
        return False
    except Exception as e:
        print(f"  ✗ (ERROR) {name}: {str(e)[:30]}")
        return False

async def main():
    print("\n=== Final URL Verification ===\n")
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        results = await asyncio.gather(*[check_url(session, n, u) for n, u in PRODUCTS])
    
    verified = sum(results)
    print(f"\n✓ Verified: {verified}/{len(PRODUCTS)}")
    if verified == len(PRODUCTS):
        print("🎉 All links working!")
    else:
        print(f"✗ Failed: {len(PRODUCTS) - verified}/{len(PRODUCTS)}")

if __name__ == "__main__":
    asyncio.run(main())
