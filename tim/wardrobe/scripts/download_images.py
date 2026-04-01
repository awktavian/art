#!/usr/bin/env python3
"""
Download product images for The Gentleman Scientist wardrobe gallery.
Reads gallery.json and downloads each product's image_url to images/ directory.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
GALLERY_PATH = PROJECT_DIR / "data" / "gallery.json"
IMAGES_DIR = PROJECT_DIR / "images"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def download_image(url: str, dest: Path, retries: int = 2) -> bool:
    """Download an image from url to dest path. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"  SKIP (exists): {dest.name}")
        return True

    if not url or url.startswith("#"):
        print(f"  SKIP (no URL): {dest.name}")
        return False

    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                if len(data) < 500:
                    print(f"  WARN: {dest.name} — too small ({len(data)} bytes)")
                    return False
                dest.write_bytes(data)
                print(f"  OK: {dest.name} ({len(data):,} bytes)")
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            if attempt < retries:
                print(f"  RETRY ({attempt+1}): {dest.name} — {e}")
                time.sleep(1)
            else:
                print(f"  FAIL: {dest.name} — {e}")
                return False
    return False


def main():
    IMAGES_DIR.mkdir(exist_ok=True)

    with open(GALLERY_PATH) as f:
        data = json.load(f)

    products = data.get("products", [])
    total = len(products)
    success = 0
    skipped = 0
    failed = 0

    print(f"\nDownloading images for {total} products...\n")

    for i, product in enumerate(products, 1):
        name = product.get("name", "unknown")
        brand = product.get("brand", "unknown")
        local = product.get("local_image", "")
        url = product.get("image_url", "")

        print(f"[{i}/{total}] {brand} — {name}")

        if not local:
            print(f"  SKIP (no local_image)")
            skipped += 1
            continue

        dest = IMAGES_DIR / local

        if download_image(url, dest):
            success += 1
        else:
            failed += 1

        # Be polite
        if i < total:
            time.sleep(0.5)

    print(f"\n{'='*50}")
    print(f"Results: {success} downloaded, {skipped} skipped, {failed} failed")
    print(f"Images directory: {IMAGES_DIR}")

    # Generate placeholder SVGs for missing images
    for product in products:
        local = product.get("local_image", "")
        if not local:
            continue
        dest = IMAGES_DIR / local
        if not dest.exists() or dest.stat().st_size < 500:
            brand = product.get("brand", "?")
            svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="450" viewBox="0 0 600 450">
  <rect width="600" height="450" fill="#F0EBE1"/>
  <text x="300" y="200" text-anchor="middle" font-family="Georgia,serif" font-size="24" fill="#8B7D6B" font-style="italic">{brand}</text>
  <text x="300" y="240" text-anchor="middle" font-family="monospace" font-size="12" fill="#B8AD9E">{local.replace('.jpg','')}</text>
</svg>'''
            svg_dest = dest.with_suffix('.svg')
            svg_dest.write_text(svg)
            print(f"  PLACEHOLDER: {svg_dest.name}")


if __name__ == "__main__":
    main()
