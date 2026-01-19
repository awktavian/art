#!/usr/bin/env python3
"""
Product Link & Image Verification System
Systematically verify all product links and download real product images.
"""

import asyncio
import aiohttp
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional
import re

@dataclass
class Product:
    id: str
    brand: str
    name: str
    price: int
    color: str
    material: str
    origin: str
    url: str
    image_url: Optional[str] = None
    url_verified: bool = False
    url_status: Optional[int] = None
    image_downloaded: bool = False
    notes: str = ""

# Define all products with their expected details
PRODUCTS = [
    Product(
        id="ladywhite",
        brand="Lady White Co",
        name="Our T-Shirt",
        price=90,
        color="White",
        material="100% Cotton",
        origin="Los Angeles",
        url="https://www.ladywhiteco.com/collections/t-shirts"
    ),
    Product(
        id="sunspel",
        brand="Sunspel",
        name="Riviera Polo",
        price=115,
        color="White",
        material="Cotton",
        origin="England",
        url="https://www.sunspel.com/us/mens/polos"
    ),
    Product(
        id="drakes",
        brand="Drake's",
        name="Oxford BD Shirt",
        price=295,
        color="Light Blue",
        material="Oxford Cotton",
        origin="England",
        url="https://www.drakes.com/usa/shirts"
    ),
    Product(
        id="lucafaloni",
        brand="Luca Faloni",
        name="Cashmere Crewneck",
        price=395,
        color="Light Grey",
        material="100% Cashmere",
        origin="Italy",
        url="https://www.lucafaloni.com/collections/cashmere"
    ),
    Product(
        id="ironheart",
        brand="Iron Heart",
        name="21oz Selvedge Denim",
        price=395,
        color="Indigo",
        material="21oz Selvedge Denim",
        origin="Japan",
        url="https://www.ironheartamerica.com/bottoms/"
    ),
    Product(
        id="burberry",
        brand="Burberry",
        name="Kensington Trench",
        price=2290,
        color="Honey",
        material="Cotton Gabardine",
        origin="England",
        url="https://us.burberry.com/mens-trench-coats/"
    ),
    Product(
        id="schott",
        brand="Schott NYC",
        name="Perfecto 618",
        price=900,
        color="Black",
        material="Steerhide Leather",
        origin="USA",
        url="https://www.schottnyc.com/products/classic-perfecto-steerhide-leather-motorcycle-jacket.htm"
    ),
    Product(
        id="barbour",
        brand="Barbour",
        name="Bedale Waxed Jacket",
        price=450,
        color="Olive",
        material="Waxed Cotton",
        origin="England",
        url="https://www.barbour.com/us/barbour-bedale-wax-jacket"
    ),
    Product(
        id="cp",
        brand="Common Projects",
        name="Achilles Low",
        price=450,
        color="White",
        material="Nappa Leather",
        origin="Italy",
        url="https://www.mrporter.com/en-us/mens/designer/common-projects"
    ),
    Product(
        id="alden",
        brand="Alden",
        name="990 Plain Toe Blucher",
        price=799,
        color="Color 8",
        material="Shell Cordovan",
        origin="USA",
        url="https://www.theshoemart.com/alden-mens-990-plain-toe-blucher-color-8-shell-cordovan/"
    ),
    Product(
        id="edwardgreen",
        brand="Edward Green",
        name="Chelsea Boot",
        price=1495,
        color="Dark Oak",
        material="Calf Leather",
        origin="England",
        url="https://www.edwardgreen.com/shop/shoes/chelsea-dark-oak-antique-82-last.html"
    ),
    Product(
        id="grandseiko",
        brand="Grand Seiko",
        name="Snowflake SBGA211",
        price=5800,
        color="White Dial",
        material="Titanium",
        origin="Japan",
        url="https://www.grand-seiko.com/us-en/collections/sbga211g"
    ),
    Product(
        id="persol",
        brand="Persol",
        name="714 Steve McQueen",
        price=340,
        color="Havana",
        material="Acetate",
        origin="Italy",
        url="https://www.persol.com/usa/0PO0714-24-31.html"
    ),
    Product(
        id="andersons",
        brand="Anderson's",
        name="Woven Leather Belt",
        price=195,
        color="Tan",
        material="Woven Leather",
        origin="Italy",
        url="https://www.andersonsbelt.com/collections/braided-leather-belts"
    ),
    Product(
        id="frankclegg",
        brand="Frank Clegg",
        name="Zip-Top Briefcase",
        price=1100,
        color="Chestnut",
        material="Full Grain Leather",
        origin="USA",
        url="https://frankclegg.com/collections/briefcases/products/zip-top-briefcase"
    ),
]

async def verify_url(session: aiohttp.ClientSession, product: Product) -> Product:
    """Verify a product URL returns 200."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }
    try:
        async with session.get(product.url, headers=headers, timeout=15, allow_redirects=True) as resp:
            product.url_status = resp.status
            product.url_verified = resp.status == 200
            if resp.status != 200:
                product.notes = f"URL returned {resp.status}"
            print(f"  [{resp.status}] {product.brand}: {product.url}")
    except asyncio.TimeoutError:
        product.url_status = 0
        product.url_verified = False
        product.notes = "Timeout"
        print(f"  [TIMEOUT] {product.brand}: {product.url}")
    except Exception as e:
        product.url_status = 0
        product.url_verified = False
        product.notes = str(e)[:50]
        print(f"  [ERROR] {product.brand}: {e}")
    return product

async def verify_all_urls():
    """Verify all product URLs."""
    print("\n=== Verifying Product URLs ===\n")
    
    connector = aiohttp.TCPConnector(limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = [verify_url(session, p) for p in PRODUCTS]
        results = await asyncio.gather(*tasks)
    
    return results

def generate_report(products: list[Product]) -> str:
    """Generate verification report."""
    report = []
    report.append("\n" + "="*60)
    report.append("PRODUCT VERIFICATION REPORT")
    report.append("="*60 + "\n")
    
    verified = [p for p in products if p.url_verified]
    failed = [p for p in products if not p.url_verified]
    
    report.append(f"✓ Verified: {len(verified)}/{len(products)}")
    report.append(f"✗ Failed: {len(failed)}/{len(products)}\n")
    
    if failed:
        report.append("FAILED URLS:")
        for p in failed:
            report.append(f"  - {p.brand} {p.name}: {p.notes}")
            report.append(f"    URL: {p.url}")
        report.append("")
    
    report.append("ALL PRODUCTS:")
    for p in products:
        status = "✓" if p.url_verified else "✗"
        report.append(f"  {status} {p.brand} {p.name} - ${p.price}")
        report.append(f"    {p.url}")
    
    return "\n".join(report)

def save_products_json(products: list[Product], path: str):
    """Save products to JSON for HTML generation."""
    data = [asdict(p) for p in products]
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\nSaved products to {path}")

async def main():
    # Create output directories
    Path("/Users/schizodactyl/projects/art/style/data").mkdir(parents=True, exist_ok=True)
    
    # Verify URLs
    products = await verify_all_urls()
    
    # Generate report
    report = generate_report(products)
    print(report)
    
    # Save results
    save_products_json(products, "/Users/schizodactyl/projects/art/style/data/products_verified.json")
    
    # Save report
    with open("/Users/schizodactyl/projects/art/style/data/verification_report.txt", "w") as f:
        f.write(report)

if __name__ == "__main__":
    asyncio.run(main())
