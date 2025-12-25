#!/usr/bin/env python3
"""
Generate QR codes for Jacoby Family Christmas 2025 gifts.
Correct URLs: https://awktavian.github.io/art/gifts/{name}
"""

import os
import sys

try:
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, CircleModuleDrawer
    from qrcode.image.styles.colormasks import RadialGradiantColorMask
except ImportError:
    print("Installing required packages...")
    os.system(f"{sys.executable} -m pip install qrcode[pil] pillow")
    import qrcode
    from qrcode.image.styledpil import StyledPilImage
    from qrcode.image.styles.moduledrawers import RoundedModuleDrawer, CircleModuleDrawer
    from qrcode.image.styles.colormasks import RadialGradiantColorMask

from PIL import Image

# Ensure qr directory exists
os.makedirs("qr", exist_ok=True)

# Family members with CORRECT URLs
family = {
    "robert": {
        "url": "https://awktavian.github.io/art/gifts/robert",
        "colors": ((0, 128, 128), (0, 200, 200), (255, 255, 255)),  # Cyan/teal theme
    },
    "katie": {
        "url": "https://awktavian.github.io/art/gifts/katie",
        "colors": ((101, 67, 33), (139, 90, 43), (255, 248, 220)),  # Leather/book theme
    },
    "kristi": {
        "url": "https://awktavian.github.io/art/gifts/kristi",
        "colors": ((184, 134, 11), (218, 165, 32), (255, 255, 255)),  # Brass/gold theme
    },
    "becky": {
        "url": "https://awktavian.github.io/art/gifts/becky",
        "colors": ((180, 83, 9), (217, 119, 6), (255, 255, 255)),  # Copper/orange theme
    },
}


def generate_qr(name: str, url: str, colors: tuple) -> None:
    """Generate a styled QR code for a family member."""
    print(f"Generating QR for {name}: {url}")

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )

    qr.add_data(url)
    qr.make(fit=True)

    # Create styled image
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=RoundedModuleDrawer(),
        color_mask=RadialGradiantColorMask(
            back_color=colors[2],
            center_color=colors[0],
            edge_color=colors[1],
        ),
    )

    # Save
    filename = f"qr/{name}-qr.png"
    img.save(filename)
    print(f"  Saved: {filename}")


def main():
    print("=" * 50)
    print("Generating Jacoby Family Christmas QR Codes")
    print("=" * 50)

    for name, config in family.items():
        generate_qr(name, config["url"], config["colors"])

    print("\n✅ All QR codes generated successfully!")
    print("\nURLs encoded:")
    for name, config in family.items():
        print(f"  {name}: {config['url']}")


if __name__ == "__main__":
    main()
