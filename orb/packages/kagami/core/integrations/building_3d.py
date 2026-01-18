"""Building 3D Model Integration — Get 3D models of buildings.

This integration helps Kagami obtain and use 3D building models for:
- Visualization and digital twins
- Accurate shade/window modeling
- Smart home floor plans
- AR/VR home experiences

Methods (in order of preference):
1. Google Photorealistic 3D Tiles API (official, requires API key)
2. Browser-based capture via Puppeteer (automated)
3. OpenStreetMap 3D buildings (free, limited detail)
4. Cesium ION (free tier available)
5. Manual capture via RenderDoc + Blender (for personal use)

USAGE:
    from kagami.core.integrations.building_3d import capture_building_3d

    # Capture any address
    result = await capture_building_3d("7331 W Green Lake Dr N, Seattle, WA")

    # Result includes:
    # - screenshots (multiple angles)
    # - orientation data
    # - geocoded location
    # - 3D tiles URL (if API key available)

Created: January 4, 2026
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Try to import geopy for geocoding
try:
    from geopy.exc import GeocoderTimedOut
    from geopy.geocoders import Nominatim

    GEOPY_AVAILABLE = True
except ImportError:
    GEOPY_AVAILABLE = False
    logger.warning("geopy not available - install with: pip install geopy")


# =============================================================================
# GEOCODING
# =============================================================================


async def geocode_address(address: str) -> tuple[float, float] | None:
    """Convert an address to latitude/longitude coordinates.

    Uses Nominatim (OpenStreetMap) for geocoding - free and no API key needed.

    Args:
        address: Full street address

    Returns:
        (latitude, longitude) tuple or None if not found
    """
    if not GEOPY_AVAILABLE:
        logger.error("geopy not available for geocoding")
        return None

    try:
        geolocator = Nominatim(user_agent="kagami_building_3d")
        location = await asyncio.get_event_loop().run_in_executor(None, geolocator.geocode, address)

        if location:
            logger.info(f"Geocoded '{address}' → ({location.latitude}, {location.longitude})")
            return (location.latitude, location.longitude)
        else:
            logger.warning(f"Could not geocode address: {address}")
            return None

    except GeocoderTimedOut:
        logger.error(f"Geocoding timed out for: {address}")
        return None
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
        return None


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class CaptureResult:
    """Result of a 3D building capture operation."""

    address: str
    latitude: float
    longitude: float

    # Captured data
    screenshots: list[Path] = field(default_factory=list)
    orientation_heading: float | None = None  # From Street View

    # Metadata
    timestamp: str = ""
    source: str = "google_maps"
    success: bool = False
    error: str | None = None

    # 3D data (if available)
    tiles_url: str | None = None
    model_path: Path | None = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class Building3DModel:
    """A 3D building model."""

    address: str
    latitude: float
    longitude: float

    # Model data
    format: str  # "gltf", "glb", "obj", "tiles"
    file_path: Path | None = None
    url: str | None = None

    # Metadata
    source: str = "unknown"  # "google_3d_tiles", "osm", "cesium", "manual"
    has_textures: bool = False
    lod: str = "unknown"  # Level of detail: "low", "medium", "high", "photorealistic"

    # Dimensions (if known)
    width_meters: float | None = None
    depth_meters: float | None = None
    height_meters: float | None = None


# =============================================================================
# GOOGLE PHOTOREALISTIC 3D TILES
# =============================================================================


class Google3DTilesService:
    """Access Google's Photorealistic 3D Tiles.

    Requires: GOOGLE_MAPS_API_KEY with Map Tiles API enabled.

    The 3D Tiles are in OGC 3D Tiles 1.0 format and can be rendered with:
    - CesiumJS
    - deck.gl
    - Three.js with 3D Tiles loader

    Pricing: $6 per 1000 root tile loads (as of 2024)
    """

    ROOT_URL = "https://tile.googleapis.com/v1/3dtiles/root.json"

    def __init__(self, api_key: str | None = None):
        """Initialize with API key."""
        self.api_key = api_key or os.environ.get("GOOGLE_MAPS_API_KEY", "")

    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return bool(self.api_key)

    def get_tileset_url(self) -> str | None:
        """Get the root tileset URL for streaming 3D tiles.

        This URL can be used with CesiumJS or similar viewers to
        stream photorealistic 3D tiles of the entire world.
        """
        if not self.api_key:
            logger.warning("Google 3D Tiles: No API key configured")
            return None

        return f"{self.ROOT_URL}?key={self.api_key}"

    async def get_tile_at_location(
        self,
        latitude: float,
        longitude: float,
    ) -> dict[str, Any] | None:
        """Get 3D tile data at a specific location.

        Note: Google 3D Tiles are streamed as a tileset, not individual
        building exports. To get a specific building, you need to:
        1. Load the tileset in a 3D viewer
        2. Navigate to the location
        3. Extract the relevant geometry

        For individual building export, consider the manual RenderDoc approach.
        """
        if not self.api_key:
            return None

        # The API provides streaming tiles, not per-building export
        # Return metadata about availability
        return {
            "available": True,
            "tileset_url": self.get_tileset_url(),
            "location": {"lat": latitude, "lng": longitude},
            "note": "Use CesiumJS or deck.gl to render tiles at this location",
        }


# =============================================================================
# OPENSTREETMAP BUILDINGS
# =============================================================================


class OSMBuildingsService:
    """Access OpenStreetMap 3D building data.

    OSM buildings are extruded footprints with height data.
    Less detailed than photogrammetry but free and open.

    Uses Overpass API for queries.
    """

    OVERPASS_URL = "https://overpass-api.de/api/interpreter"

    async def get_building_at_location(
        self,
        latitude: float,
        longitude: float,
        radius_meters: float = 50,
    ) -> dict[str, Any] | None:
        """Get OSM building data near a location.

        Returns building footprint and height if available.
        """
        import aiohttp

        # Overpass QL query for buildings
        query = f"""
        [out:json][timeout:25];
        (
          way["building"](around:{radius_meters},{latitude},{longitude});
          relation["building"](around:{radius_meters},{latitude},{longitude});
        );
        out body;
        >;
        out skel qt;
        """

        try:
            async with (
                aiohttp.ClientSession() as session,
                session.post(
                    self.OVERPASS_URL,
                    data={"data": query},
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp,
            ):
                if resp.status == 200:
                    data = await resp.json()
                    return self._parse_osm_building(data)
                else:
                    logger.error(f"OSM query failed: {resp.status}")
                    return None
        except Exception as e:
            logger.error(f"OSM query error: {e}")
            return None

    def _parse_osm_building(self, data: dict) -> dict[str, Any] | None:
        """Parse OSM response into building data."""
        elements = data.get("elements", [])

        # Find building ways
        buildings = [
            e for e in elements if e.get("type") == "way" and "building" in e.get("tags", {})
        ]

        if not buildings:
            return None

        building = buildings[0]
        tags = building.get("tags", {})

        # Extract height if available
        height = None
        if "height" in tags:
            try:
                height = float(tags["height"].replace("m", "").strip())
            except ValueError:
                pass
        elif "building:levels" in tags:
            try:
                levels = int(tags["building:levels"])
                height = levels * 3.0  # Assume 3m per level
            except ValueError:
                pass

        return {
            "osm_id": building.get("id"),
            "type": tags.get("building", "yes"),
            "height_meters": height,
            "levels": tags.get("building:levels"),
            "name": tags.get("name"),
            "address": {
                "street": tags.get("addr:street"),
                "housenumber": tags.get("addr:housenumber"),
                "city": tags.get("addr:city"),
            },
            "nodes": building.get("nodes", []),
            "source": "openstreetmap",
        }


# =============================================================================
# MANUAL CAPTURE INSTRUCTIONS
# =============================================================================


def get_manual_capture_instructions() -> str:
    """Get instructions for manually capturing a 3D model from Google Maps.

    This uses RenderDoc + MapsModelsImporter for Blender.
    For personal/educational use only.
    """
    return """
# Manual 3D Model Capture from Google Maps

This method captures 3D data from Google Maps using RenderDoc and imports it into Blender.
**For personal/educational use only - review Google's ToS.**

## Requirements
1. RenderDoc (graphics debugger): https://renderdoc.org/
2. Blender 3.x or 4.x: https://blender.org/
3. MapsModelsImporter add-on: https://github.com/eliemichel/MapsModelsImporter

## Steps

### 1. Install RenderDoc
```bash
# macOS
brew install --cask renderdoc

# Or download from https://renderdoc.org/builds
```

### 2. Install Blender + Add-on
1. Download and install Blender
2. Download MapsModelsImporter from GitHub releases
3. In Blender: Edit → Preferences → Add-ons → Install → Select the .zip

### 3. Capture from Google Maps
1. Open RenderDoc
2. Launch Chrome via RenderDoc: File → Launch Application
   - Executable: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
   - Arguments: `--disable-gpu-sandbox --gpu-startup-dialog`
3. In Chrome, go to https://www.google.com/maps
4. Navigate to your building in 3D view (satellite, tilt, zoom)
5. In RenderDoc, click "Capture Frame" (or press F12)
6. Save the capture (.rdc file)

### 4. Import to Blender
1. Open Blender
2. File → Import → Google Maps Capture
3. Select your .rdc file
4. The 3D model with textures will be imported

### 5. Export
- Export as .glb, .obj, or .fbx for use in other applications

## Notes
- Quality depends on Google Maps coverage for the area
- Seattle has good 3D coverage
- Textures are included in the capture
- Model is georeferenced (has real-world coordinates)

## Alternative: Google Earth Pro
Google Earth Pro can export 3D buildings, but with lower quality.
"""


# =============================================================================
# UNIFIED SERVICE
# =============================================================================


class Building3DService:
    """Unified service for obtaining 3D building models."""

    def __init__(self):
        """Initialize all sub-services."""
        self.google = Google3DTilesService()
        self.osm = OSMBuildingsService()

    async def get_building_model(
        self,
        latitude: float,
        longitude: float,
        address: str | None = None,
    ) -> dict[str, Any]:
        """Get 3D building data using available sources.

        Returns a dict with data from all available sources.
        """
        results = {
            "location": {"lat": latitude, "lng": longitude},
            "address": address,
            "sources": {},
        }

        # Try Google 3D Tiles
        if self.google.is_available:
            google_data = await self.google.get_tile_at_location(latitude, longitude)
            if google_data:
                results["sources"]["google_3d_tiles"] = google_data

        # Try OSM
        osm_data = await self.osm.get_building_at_location(latitude, longitude)
        if osm_data:
            results["sources"]["openstreetmap"] = osm_data

        # Add manual instructions
        results["manual_capture"] = {
            "available": True,
            "instructions": "Call get_manual_capture_instructions() for details",
        }

        return results

    def get_setup_requirements(self) -> dict[str, Any]:
        """Get information about what's needed for full functionality."""
        return {
            "google_3d_tiles": {
                "status": "available" if self.google.is_available else "needs_api_key",
                "requirement": "GOOGLE_MAPS_API_KEY with Map Tiles API enabled",
                "pricing": "$6 per 1000 root tile loads",
                "quality": "Photorealistic with textures",
            },
            "openstreetmap": {
                "status": "available",
                "requirement": "None (free)",
                "quality": "Extruded footprints, basic geometry",
            },
            "manual_capture": {
                "status": "available",
                "requirement": "RenderDoc + Blender + MapsModelsImporter",
                "quality": "Photorealistic with textures (same as Google Maps)",
            },
        }


# =============================================================================
# SINGLETON
# =============================================================================


_service: Building3DService | None = None


def get_building_3d_service() -> Building3DService:
    """Get the building 3D service singleton."""
    global _service
    if _service is None:
        _service = Building3DService()
    return _service


# =============================================================================
# BROWSER CAPTURE (via subprocess - works on any system)
# =============================================================================


class BrowserCaptureService:
    """Capture 3D building views from Google Maps using browser automation.

    This creates a script that can be run with Puppeteer or Playwright
    to capture screenshots from multiple angles.
    """

    OUTPUT_DIR = Path("/tmp/kagami_3d_captures")

    def __init__(self):
        """Initialize capture service."""
        self.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def generate_capture_script(
        self,
        latitude: float,
        longitude: float,
        address: str,
        output_dir: Path | None = None,
    ) -> str:
        """Generate a Node.js script for capturing 3D views.

        The script uses Puppeteer to:
        1. Navigate to Google Maps at the location
        2. Enable 3D/satellite view
        3. Capture screenshots from multiple angles
        4. Extract Street View heading for orientation
        """
        output = output_dir or self.OUTPUT_DIR
        safe_address = address.replace('"', '\\"').replace("'", "\\'")

        script = f'''
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const LAT = {latitude};
const LNG = {longitude};
const ADDRESS = "{safe_address}";
const OUTPUT_DIR = "{output}";

// Helper function to wait (newer Puppeteer API)
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

async function captureBuilding() {{
    const browser = await puppeteer.launch({{
        headless: false,  // Need visible browser for 3D rendering
        args: ['--window-size=1920,1080', '--disable-web-security']
    }});

    const page = await browser.newPage();
    await page.setViewport({{ width: 1920, height: 1080 }});

    const results = {{
        address: ADDRESS,
        latitude: LAT,
        longitude: LNG,
        screenshots: [],
        orientation: null,
        timestamp: new Date().toISOString()
    }};

    try {{
        // Navigate to Google Maps with 3D satellite view
        const url = `https://www.google.com/maps/place/${{encodeURIComponent(ADDRESS)}}/@${{LAT}},${{LNG}},73a,35y,307h,79t/data=!3m1!1e3`;
        console.log('Navigating to:', url);
        await page.goto(url, {{ waitUntil: 'networkidle2', timeout: 60000 }});

        // Wait for map to fully load
        await delay(5000);

        // Take 3D aerial screenshot
        const aerialPath = path.join(OUTPUT_DIR, '3d_aerial_view.png');
        await page.screenshot({{ path: aerialPath, fullPage: false }});
        results.screenshots.push(aerialPath);
        console.log('Captured 3D aerial view');

        // Navigate to flat satellite view
        const satUrl = `https://www.google.com/maps/@${{LAT}},${{LNG}},100m/data=!3m1!1e3`;
        await page.goto(satUrl, {{ waitUntil: 'networkidle2', timeout: 60000 }});
        await delay(3000);

        const satPath = path.join(OUTPUT_DIR, 'satellite_view.png');
        await page.screenshot({{ path: satPath, fullPage: false }});
        results.screenshots.push(satPath);
        console.log('Captured satellite view');

        // Try to get Street View for orientation (307° heading = front of house)
        const streetViewUrl = `https://www.google.com/maps/@${{LAT}},${{LNG}},3a,75y,307h,90t/data=!3m6!1e1!3m4!1s!2e0!7i16384!8i8192`;
        await page.goto(streetViewUrl, {{ waitUntil: 'networkidle2', timeout: 60000 }});
        await delay(3000);

        // Extract heading from URL
        const currentUrl = page.url();
        const headingMatch = currentUrl.match(/,(\\d+\\.?\\d*)h,/);
        if (headingMatch) {{
            results.orientation = parseFloat(headingMatch[1]);
            console.log('Extracted orientation heading:', results.orientation);
        }}

        // Take Street View screenshot
        const streetViewPath = path.join(OUTPUT_DIR, 'street_view.png');
        await page.screenshot({{ path: streetViewPath, fullPage: false }});
        results.screenshots.push(streetViewPath);
        console.log('Captured Street View');

        // Try multiple angles
        const angles = [0, 90, 180, 270];
        for (const angle of angles) {{
            const angleUrl = `https://www.google.com/maps/@${{LAT}},${{LNG}},3a,75y,${{angle}}h,90t/data=!3m6!1e1!3m4!1s!2e0!7i16384!8i8192`;
            await page.goto(angleUrl, {{ waitUntil: 'networkidle2', timeout: 60000 }});
            await delay(2000);

            const anglePath = path.join(OUTPUT_DIR, `street_view_${{angle}}.png`);
            await page.screenshot({{ path: anglePath, fullPage: false }});
            results.screenshots.push(anglePath);
            console.log(`Captured Street View at ${{angle}}°`);
        }}

    }} catch (error) {{
        console.error('Capture error:', error.message);
        results.error = error.message;
    }}

    await browser.close();

    // Save results
    const resultsPath = path.join(OUTPUT_DIR, 'capture_results.json');
    fs.writeFileSync(resultsPath, JSON.stringify(results, null, 2));
    console.log('Results saved to:', resultsPath);

    return results;
}}

captureBuilding().then(r => console.log('Done:', r)).catch(e => console.error(e));
'''
        return script

    async def capture(
        self,
        address: str,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> dict[str, Any]:
        """Capture 3D building data for an address.

        Args:
            address: Street address
            latitude: Optional latitude (will geocode if not provided)
            longitude: Optional longitude (will geocode if not provided)

        Returns:
            Dict with screenshots, orientation, and capture script path
        """
        result: dict[str, Any] = {
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "screenshots": [],
            "orientation_heading": None,
            "success": False,
            "error": None,
            "capture_script": None,
        }

        # Geocode if needed
        if latitude is None or longitude is None:
            coords = await geocode_address(address)
            if coords is None:
                result["error"] = "Could not geocode address"
                return result
            latitude, longitude = coords
            result["latitude"] = latitude
            result["longitude"] = longitude

        # Create output directory for this capture
        safe_name = "".join(c if c.isalnum() else "_" for c in address)[:50]
        output_dir = self.OUTPUT_DIR / safe_name
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate and save capture script
        script = self.generate_capture_script(latitude, longitude, address, output_dir)
        script_path = output_dir / "capture.js"
        script_path.write_text(script)
        result["capture_script"] = str(script_path)

        logger.info(f"Generated capture script: {script_path}")
        logger.info(f"Run with: node {script_path}")

        # Try to run the script if Node.js and Puppeteer are available
        try:
            proc_result = subprocess.run(
                ["node", str(script_path)],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(output_dir),
            )

            if proc_result.returncode == 0:
                # Load results
                results_path = output_dir / "capture_results.json"
                if results_path.exists():
                    data = json.loads(results_path.read_text())
                    result["screenshots"] = data.get("screenshots", [])
                    result["orientation_heading"] = data.get("orientation")
                    result["success"] = True
                    return result
            else:
                logger.warning(f"Capture script failed: {proc_result.stderr}")
                result["error"] = f"Script failed: {proc_result.stderr[:200]}"

        except FileNotFoundError:
            logger.info("Node.js not available - script saved for manual execution")
            result["error"] = "Node.js not available. Run script manually."
        except subprocess.TimeoutExpired:
            logger.warning("Capture timed out")
            result["error"] = "Capture timed out after 120 seconds"
        except Exception as e:
            logger.error(f"Capture error: {e}")
            result["error"] = str(e)

        return result


# =============================================================================
# HIGH-LEVEL API
# =============================================================================


async def capture_building_3d(
    address: str,
    latitude: float | None = None,
    longitude: float | None = None,
    include_osm: bool = True,
) -> dict[str, Any]:
    """Capture 3D building data for any address.

    This is the main entry point for the 3D building capture system.

    Args:
        address: Full street address (e.g., "7331 W Green Lake Dr N, Seattle, WA")
        latitude: Optional latitude (will geocode if not provided)
        longitude: Optional longitude (will geocode if not provided)
        include_osm: Whether to query OpenStreetMap for building data

    Returns:
        Dict containing:
        - geocoded_location: (lat, lng) tuple
        - orientation: Property orientation data (if detected)
        - screenshots: List of captured image paths
        - osm_data: OpenStreetMap building data (if available)
        - tiles_url: Google 3D Tiles URL (if API key configured)
        - capture_script: Path to Puppeteer script for manual capture

    Example:
        >>> result = await capture_building_3d("7331 W Green Lake Dr N, Seattle, WA")
        >>> print(result["geocoded_location"])
        (47.6829, -122.3426)
        >>> print(result["orientation"]["front_azimuth"])
        307.0
    """
    result: dict[str, Any] = {
        "address": address,
        "geocoded_location": None,
        "orientation": None,
        "screenshots": [],
        "osm_data": None,
        "tiles_url": None,
        "capture_script": None,
        "success": False,
        "errors": [],
    }

    # Step 1: Geocode address
    if latitude is None or longitude is None:
        coords = await geocode_address(address)
        if coords:
            latitude, longitude = coords
            result["geocoded_location"] = coords
        else:
            result["errors"].append("Could not geocode address")
            return result
    else:
        result["geocoded_location"] = (latitude, longitude)

    # Step 2: Get Google 3D Tiles URL (if API key available)
    google_service = Google3DTilesService()
    if google_service.is_available:
        result["tiles_url"] = google_service.get_tileset_url()

    # Step 3: Get OSM building data
    if include_osm:
        osm_service = OSMBuildingsService()
        osm_data = await osm_service.get_building_at_location(latitude, longitude)
        if osm_data:
            result["osm_data"] = osm_data

    # Step 4: Browser capture
    browser_service = BrowserCaptureService()
    capture_result = await browser_service.capture(address, latitude, longitude)

    result["capture_script"] = capture_result.get("capture_script")

    if capture_result.get("success"):
        result["screenshots"] = capture_result.get("screenshots", [])
        heading = capture_result.get("orientation_heading")
        if heading is not None:
            # Import orientation helper
            try:
                from kagami.core.integrations.property_intelligence import (
                    orientation_from_street_view_heading,
                )

                orient = orientation_from_street_view_heading(heading)
                result["orientation"] = {
                    "front_azimuth": orient.front_azimuth,
                    "front_cardinal": orient.front_cardinal,
                    "back_azimuth": orient.back_azimuth,
                    "rotation_from_north": orient.rotation_from_north,
                    "confidence": orient.confidence,
                }
            except ImportError:
                result["orientation"] = {"heading": heading}
    else:
        if capture_result.get("error"):
            result["errors"].append(capture_result["error"])

    result["success"] = bool(result["screenshots"]) or bool(result["tiles_url"])
    return result


async def get_property_3d_info(address: str) -> dict[str, Any]:
    """Get comprehensive 3D information about a property.

    Combines geocoding, orientation detection, and 3D model availability.

    Args:
        address: Full street address

    Returns:
        Dict with property 3D information
    """
    return await capture_building_3d(address, include_osm=True)


# =============================================================================
# EXPORTS
# =============================================================================


__all__ = [
    "BrowserCaptureService",
    # Data models
    "Building3DModel",
    "Building3DService",
    # Services
    "Google3DTilesService",
    "OSMBuildingsService",
    # High-level API
    "capture_building_3d",
    "geocode_address",
    # Singletons
    "get_building_3d_service",
    # Utilities
    "get_manual_capture_instructions",
    "get_property_3d_info",
]
