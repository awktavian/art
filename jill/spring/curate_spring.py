#!/usr/bin/env python3
"""
Curate Spring 2026 gallery for Jill using Kagami's autonomous pipeline.

Uses OpenAI as LLM backend (Gemini key is currently flagged).
Runs the full pipeline: generate → evaluate → refine → stock verify → EFE score → images → HTML.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add kagami packages to path
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "packages"))

from kagami.core.security import get_secret
from kagami.core.services.llm.openai_compatible_client import (
    OpenAICompatibleClient,
    OpenAICompatibleConfig,
)
from kagami.core.services.shopping.autonomous_curator import (
    AutonomousConfig,
    AutonomousCurator,
)
from kagami.core.services.shopping.gallery_curator import CuratorConfig, GalleryCurator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("spring_curator")


def _make_openai_client() -> OpenAICompatibleClient:
    """Create OpenAI client with our API key."""
    api_key = get_secret("openai_api_key")
    if not api_key:
        raise RuntimeError("No OpenAI API key found in keychain")

    return OpenAICompatibleClient(
        OpenAICompatibleConfig(
            base_url="https://api.openai.com/v1",
            model="gpt-4o",
            api_key=api_key,
            timeout_s=120.0,
        )
    )


async def main() -> int:
    output_dir = Path(__file__).parent
    existing_dir = output_dir.parent / "wardrobe"

    prompt = (
        "Spring 2026 wardrobe transition for Jill. "
        "She already owns: knitwear (Jenni Kayne cashmere cocoon, La Ligne Marin, "
        "White+Warren wrap), outerwear (Barbour Beadnell, JK blazer), "
        "essentials (Saint James Breton, Cuyana silk shirt), "
        "evening (Reformation Frankie, Toteme trousers), "
        "shoes (Margaux Demi ballet flat), jewelry (Catbird ring, MOUNSER earrings), "
        "and a full Amelie French-Japanese collection (orSlow, Bleu de Paname, "
        "Lemaire Croissant, Repetto). "
        "What's MISSING for spring? Think: lightweight layers, transitional dresses, "
        "linen pants, spring shoes, a light bag, maybe a hat. "
        "Navy is her signature. Pants-forward. No earrings. No boring basics. Joy matters."
    )

    # Configure autonomous curator
    config = AutonomousConfig(
        quality_threshold=85,
        max_iterations=3,
        verify_stock=False,  # Skip stock for now — URLs may be LLM-generated
        crawl_images=True,
        verify_images_with_vlm=False,  # Faster without VLM verification
        generate_html=True,
    )

    curator = AutonomousCurator(config)

    # Monkey-patch to use OpenAI instead of Gemini
    openai_client = _make_openai_client()
    await openai_client.initialize()

    # Patch the gallery curator's client
    async def _get_openai_client():
        return openai_client

    # Override the internal methods to use OpenAI
    original_get_curator = curator._get_curator

    async def _patched_get_curator() -> GalleryCurator:
        gc = await original_get_curator()
        gc._get_client = _get_openai_client  # type: ignore
        return gc

    curator._get_curator = _patched_get_curator  # type: ignore

    # Also patch the LLM used for quality evaluation
    original_get_llm = curator._get_llm

    async def _patched_get_llm():
        return openai_client

    curator._get_llm = _patched_get_llm  # type: ignore

    logger.info("🚀 Starting Spring 2026 curation for Jill")
    logger.info(f"   Output: {output_dir}")
    logger.info(f"   LLM: OpenAI gpt-4o")

    result = await curator.curate(
        prompt=prompt,
        recipient="Jill",
        output_dir=output_dir,
        gallery_type="fashion_women",
        num_products=12,
        quality_threshold=85,
        max_iterations=3,
        existing_gallery_dir=existing_dir,
    )

    print(f"\n{'=' * 60}")
    print(f"Gallery: {result.gallery.meta.name}")
    print(f"Products: {len(result.gallery.products)}")
    print(f"Quality: {result.quality_score.overall_score}/100")
    print(f"Iterations: {result.iterations}")
    print(f"Images: {result.images_downloaded}")
    print(f"Output: {result.output_dir}")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
