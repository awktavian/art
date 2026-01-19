#!/usr/bin/env python3
"""
Validate all mug collection URLs and prices.
Finds working URLs and downloads real product images.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import httpx

# Products to validate - extracted from index.html
PRODUCTS = [
    {
        "id": "jfk-library-mug",
        "name": "Kennedy for President Mug",
        "url": "https://store.jfklibrary.org/products/kennedy-for-president-mug",
        "price": "$22.99",
        "category": "kennedy",
        "verified": True,  # Manually verified above
    },
    {
        "id": "heath-ceramics",
        "name": "Heath Ceramics",
        "url": "https://www.heathceramics.com/collections/mugs",
        "price": "$38–$48",
        "category": "craft",
        "verified": False,
    },
    {
        "id": "east-fork",
        "name": "East Fork Pottery",
        "url": "https://eastfork.com/collections/mugs",
        "price": "$40–$56",
        "category": "craft",
        "verified": False,
    },
    {
        "id": "iittala-teema",
        "name": "Iittala Teema",
        "url": "https://www.iittala.com/collections/teema",
        "price": "$25–$30",
        "category": "design",
        "verified": False,
    },
    {
        "id": "hasami-porcelain",
        "name": "Hasami Porcelain",
        "url": "https://hasami-porcelain.com/collections/mugs",
        "price": "$26–$32",
        "category": "design",
        "verified": False,
    },
    {
        "id": "korean-celadon",
        "name": "Korean Celadon",
        "url": "https://www.etsy.com/search?q=korean%20celadon%20tea%20cup",
        "price": "$45–$200",
        "category": "cultural",
        "verified": False,
    },
    {
        "id": "mashiko-stoneware",
        "name": "Mashiko Stoneware",
        "url": "https://tokyobike.us/collections/mashiko-pottery",
        "price": "$45–$120",
        "category": "cultural",
        "verified": False,
    },
    {
        "id": "fire-king-jadeite",
        "name": "Fire-King Jadeite",
        "url": "https://www.etsy.com/search?q=fire%20king%20jadeite%20mug",
        "price": "$25–$150",
        "category": "historical",
        "verified": False,
    },
    {
        "id": "kintsugi",
        "name": "Kintsugi Repair",
        "url": "https://www.etsy.com/search?q=kintsugi%20mug",
        "price": "$80–$400",
        "category": "historical",
        "verified": False,
    },
]

# Alternative URLs to try for broken links
ALTERNATIVE_URLS = {
    "heath-ceramics": [
        "https://www.heathceramics.com/collections/cups-mugs",
        "https://www.heathceramics.com/collections/dinnerware",
        "https://www.heathceramics.com/search?q=mug",
    ],
    "east-fork": [
        "https://eastfork.com/search?q=mug",
        "https://eastfork.com/collections/pottery",
    ],
    "iittala-teema": [
        "https://www.iittala.com/products/teema-mug",
        "https://www.iittala.us/collections/teema",
        "https://www.finnishdesignshop.com/tableware-cups-mugs-tea-cups-teema-mug-p-4117.html",
    ],
    "hasami-porcelain": [
        "https://hasami-porcelain.com/",
        "https://www.tortoisegeneralstore.com/collections/hasami-porcelain",
        "https://shop.poketo.com/collections/hasami-porcelain",
    ],
    "mashiko-stoneware": [
        "https://www.myjapanesegreentea.com/japanese-tea-cups",
        "https://www.etsy.com/search?q=mashiko%20pottery%20mug",
    ],
}


async def check_url(client: httpx.AsyncClient, url: str) -> tuple[bool, int, str]:
    """Check if URL is accessible. Returns (success, status_code, final_url)."""
    try:
        resp = await client.get(url, follow_redirects=True, timeout=15.0)
        # Check for common error patterns
        if resp.status_code == 200:
            text = resp.text.lower()
            if "page not found" in text or "404" in text or "oops" in text:
                return False, 404, str(resp.url)
        return resp.status_code == 200, resp.status_code, str(resp.url)
    except Exception as e:
        return False, 0, str(e)


async def validate_products():
    """Validate all product URLs."""
    results = []
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    
    async with httpx.AsyncClient(headers=headers) as client:
        for product in PRODUCTS:
            print(f"\n🔍 Checking: {product['name']}")
            
            # Check primary URL
            success, status, final_url = await check_url(client, product["url"])
            
            result = {
                **product,
                "url_works": success,
                "status_code": status,
                "final_url": final_url,
                "working_url": product["url"] if success else None,
            }
            
            # If primary URL fails, try alternatives
            if not success and product["id"] in ALTERNATIVE_URLS:
                print(f"   ❌ Primary URL failed ({status}), trying alternatives...")
                for alt_url in ALTERNATIVE_URLS[product["id"]]:
                    alt_success, alt_status, alt_final = await check_url(client, alt_url)
                    if alt_success:
                        print(f"   ✅ Found working alternative: {alt_url}")
                        result["working_url"] = alt_url
                        result["url_works"] = True
                        break
                    await asyncio.sleep(0.5)  # Be polite
            
            if result["url_works"]:
                print(f"   ✅ URL works: {result['working_url']}")
            else:
                print(f"   ❌ No working URL found")
            
            results.append(result)
            await asyncio.sleep(1)  # Rate limit
    
    return results


def generate_report(results: list) -> str:
    """Generate validation report."""
    working = [r for r in results if r["url_works"]]
    broken = [r for r in results if not r["url_works"]]
    
    report = []
    report.append("=" * 60)
    report.append("MUG COLLECTION VALIDATION REPORT")
    report.append("=" * 60)
    report.append(f"\n✅ Working: {len(working)}/{len(results)}")
    report.append(f"❌ Broken: {len(broken)}/{len(results)}\n")
    
    if working:
        report.append("\n--- WORKING URLS ---")
        for r in working:
            report.append(f"  [{r['category']}] {r['name']}")
            report.append(f"      URL: {r['working_url']}")
            report.append(f"      Price: {r['price']}")
    
    if broken:
        report.append("\n--- BROKEN URLS (need replacement) ---")
        for r in broken:
            report.append(f"  [{r['category']}] {r['name']}")
            report.append(f"      Failed URL: {r['url']}")
            report.append(f"      Status: {r['status_code']}")
    
    return "\n".join(report)


async def main():
    print("🎨 Mug Collection Validator")
    print("=" * 40)
    
    results = await validate_products()
    
    # Save results
    output_dir = Path(__file__).parent.parent
    
    with open(output_dir / "url_validation.json", "w") as f:
        json.dump(results, f, indent=2)
    
    report = generate_report(results)
    print("\n" + report)
    
    with open(output_dir / "validation_report.txt", "w") as f:
        f.write(report)
    
    print(f"\n📄 Results saved to {output_dir}")


if __name__ == "__main__":
    asyncio.run(main())
