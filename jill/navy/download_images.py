#!/usr/bin/env python3
"""Download and create placeholder images for Jill's Navy gallery."""

import json
import urllib.request
import os
from pathlib import Path

# Create placeholder images for products that need them
IMAGES_DIR = Path(__file__).parent / "images"
GALLERY_FILE = Path(__file__).parent / "data" / "gallery.json"

def create_placeholder(filename: str, text: str = "Navy"):
    """Create a simple placeholder file marker."""
    filepath = IMAGES_DIR / filename
    if filepath.exists():
        print(f"  ✓ {filename} already exists")
        return
    
    # Create a marker file
    filepath.write_text(f"PLACEHOLDER: {text}")
    print(f"  → Created placeholder: {filename}")

def main():
    """Download or create placeholders for all images."""
    print("=" * 60)
    print("JILL'S NAVY GALLERY — Image Setup")
    print("=" * 60)
    
    # Load gallery
    with open(GALLERY_FILE) as f:
        gallery = json.load(f)
    
    # Ensure images dir exists
    IMAGES_DIR.mkdir(exist_ok=True)
    
    # Check each product
    for product in gallery["products"]:
        filename = product["local_image"]
        filepath = IMAGES_DIR / filename
        
        if filepath.exists() and filepath.stat().st_size > 1000:
            print(f"✓ {filename} (exists, {filepath.stat().st_size / 1024:.1f}KB)")
        else:
            print(f"⚠ {filename} needs image")
            create_placeholder(filename, product["name"])
    
    print("\n" + "=" * 60)
    print("Summary:")
    existing = [f for f in IMAGES_DIR.glob("*.jpg") if f.stat().st_size > 1000]
    print(f"  Real images: {len(existing)}")
    print(f"  Total products: {len(gallery['products'])}")
    print("=" * 60)

if __name__ == "__main__":
    main()
