#!/usr/bin/env python3
"""Client Apps Demo — Multi-Platform Kagami Clients.

This example PROVES that Kagami client apps exist by checking
the actual source code files on disk.

WHAT THIS EXAMPLE PROVES:
=========================
1. Desktop client (Tauri + Rust + JS) source exists
2. Hub client (Raspberry Pi + Rust) source exists
3. Watch client (SwiftUI) source exists
4. Vision client (visionOS) source exists
5. Key files for each platform are present

Created: December 31, 2025
Colony: Spark (e₁) — The Igniter
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add examples/common to path
sys.path.insert(0, str(Path(__file__).parent))

from common.output import (
    print_header,
    print_section,
    print_success,
    print_error,
    print_warning,
    print_metrics,
    print_footer,
    print_separator,
)
from common.metrics import Timer, MetricsCollector


# Project root
PROJECT_ROOT = Path(__file__).parent.parent


# =============================================================================
# SECTION 1: VERIFY DESKTOP CLIENT EXISTS
# =============================================================================


def section_1_desktop():
    """Verify Desktop client source exists."""
    print_section(1, "Desktop Client (Tauri)")

    desktop_path = PROJECT_ROOT / "apps" / "desktop" / "kagami-client"

    if not desktop_path.exists():
        print_error(f"Desktop client not found at {desktop_path}")
        return False

    print("   ✅ Desktop client found at: apps/desktop/kagami-client/")
    print()

    # Check key files
    key_files = [
        ("src-tauri/src/main.rs", "Rust backend entry"),
        ("src-tauri/src/realtime.rs", "WebSocket state sync"),
        ("src-tauri/Cargo.toml", "Rust dependencies"),
        ("src/js/ambient.js", "Ambient display animations"),
        ("src/js/context.js", "System context provider"),
        ("package.json", "JS dependencies"),
    ]

    files_found = 0
    print("   Key files:")
    for rel_path, description in key_files:
        full_path = desktop_path / rel_path
        exists = full_path.exists()
        status = "✅" if exists else "❌"
        print(f"      {status} {rel_path} — {description}")
        if exists:
            files_found += 1

    # Count total files
    if desktop_path.exists():
        total_files = sum(1 for _ in desktop_path.rglob("*") if _.is_file())
        print()
        print(f"   Total files: {total_files}")

    print()
    if files_found >= 4:
        print_success("Desktop client verified", f"{files_found}/{len(key_files)} key files")
        return True
    else:
        print_warning("Desktop client incomplete", f"{files_found}/{len(key_files)} key files")
        return False


# =============================================================================
# SECTION 2: VERIFY HUB CLIENT EXISTS
# =============================================================================


def section_2_hub():
    """Verify Hub client source exists."""
    print_separator()
    print_section(2, "Hub Client (Raspberry Pi)")

    hub_path = PROJECT_ROOT / "apps" / "hub" / "kagami-hub"

    if not hub_path.exists():
        print_error(f"Hub client not found at {hub_path}")
        return False

    print("   ✅ Hub client found at: apps/hub/kagami-hub/")
    print()

    # Check key files
    key_files = [
        ("src/main.rs", "Rust entry point"),
        ("src/voice_pipeline.rs", "STT + TTS integration"),
        ("src/led_ring.rs", "NeoPixel animations"),
        ("src/wake_word.rs", "Porcupine wake word"),
        ("src/realtime.rs", "WebSocket client"),
        ("Cargo.toml", "Rust dependencies"),
    ]

    files_found = 0
    print("   Key files:")
    for rel_path, description in key_files:
        full_path = hub_path / rel_path
        exists = full_path.exists()
        status = "✅" if exists else "❌"
        print(f"      {status} {rel_path} — {description}")
        if exists:
            files_found += 1

    # Show README if exists
    readme = hub_path / "README.md"
    if readme.exists():
        print()
        print("   README.md excerpt:")
        with open(readme) as f:
            lines = f.readlines()[:5]
            for line in lines:
                print(f"      {line.rstrip()}")

    print()
    if files_found >= 4:
        print_success("Hub client verified", f"{files_found}/{len(key_files)} key files")
        return True
    else:
        print_warning("Hub client incomplete", f"{files_found}/{len(key_files)} key files")
        return False


# =============================================================================
# SECTION 3: VERIFY WATCH CLIENT EXISTS
# =============================================================================


def section_3_watch():
    """Verify Watch client source exists."""
    print_separator()
    print_section(3, "Watch Client (Apple Watch)")

    watch_path = PROJECT_ROOT / "apps" / "watch" / "kagami-watch"

    if not watch_path.exists():
        print_error(f"Watch client not found at {watch_path}")
        return False

    print("   ✅ Watch client found at: apps/watch/kagami-watch/")
    print()

    # Check key files
    key_files = [
        ("KagamiWatch/KagamiWatchApp.swift", "App entry point"),
        ("KagamiWatch/ContentView.swift", "Main interface"),
        ("KagamiWatch/Complications/ColonyComplication.swift", "Watch face widgets"),
        ("KagamiWatch/Services/KagamiAPIService.swift", "API communication"),
        ("Package.swift", "Swift package manifest"),
    ]

    files_found = 0
    print("   Key files:")
    for rel_path, description in key_files:
        full_path = watch_path / rel_path
        exists = full_path.exists()
        status = "✅" if exists else "❌"
        print(f"      {status} {rel_path} — {description}")
        if exists:
            files_found += 1

    print()
    if files_found >= 3:
        print_success("Watch client verified", f"{files_found}/{len(key_files)} key files")
        return True
    else:
        print_warning("Watch client incomplete", f"{files_found}/{len(key_files)} key files")
        return False


# =============================================================================
# SECTION 4: VERIFY VISION CLIENT EXISTS
# =============================================================================


def section_4_vision():
    """Verify Vision client source exists."""
    print_separator()
    print_section(4, "Vision Client (Vision Pro)")

    vision_path = PROJECT_ROOT / "apps" / "vision" / "kagami-vision"

    if not vision_path.exists():
        print_error(f"Vision client not found at {vision_path}")
        return False

    print("   ✅ Vision client found at: apps/vision/kagami-vision/")
    print()

    # Check key files
    key_files = [
        ("KagamiVision/KagamiVisionApp.swift", "App entry point"),
        ("KagamiVision/ContentView.swift", "Main interface"),
        ("KagamiVision/Spaces/KagamiPresenceView.swift", "Spatial presence view"),
        ("KagamiVision/Spaces/CommandPaletteView.swift", "Voice + gesture input"),
        ("KagamiVision/Services/GazeTrackingService.swift", "Gaze tracking"),
        ("Package.swift", "Swift package manifest"),
    ]

    files_found = 0
    print("   Key files:")
    for rel_path, description in key_files:
        full_path = vision_path / rel_path
        exists = full_path.exists()
        status = "✅" if exists else "❌"
        print(f"      {status} {rel_path} — {description}")
        if exists:
            files_found += 1

    print()
    if files_found >= 3:
        print_success("Vision client verified", f"{files_found}/{len(key_files)} key files")
        return True
    else:
        print_warning("Vision client incomplete", f"{files_found}/{len(key_files)} key files")
        return False


# =============================================================================
# SECTION 5: VERIFY ADDITIONAL CLIENTS
# =============================================================================


def section_5_additional():
    """Verify additional client platforms."""
    print_separator()
    print_section(5, "Additional Clients")

    clients = [
        ("apps/android/kagami-android", "Android", "KagamiApp.kt"),
        ("apps/ios/kagami-ios", "iOS", "KagamiIOSApp.swift"),
    ]

    verified = 0
    for path, name, key_file in clients:
        client_path = PROJECT_ROOT / path
        if client_path.exists():
            key_path = list(client_path.rglob(key_file))
            if key_path:
                print(f"   ✅ {name} client: {path}/")
                print(f"      Entry point: {key_file}")
                verified += 1
            else:
                print(f"   ⚠️ {name} client exists but missing {key_file}")
        else:
            print(f"   ❌ {name} client not found at {path}")

    print()
    print_success("Additional clients", f"{verified}/{len(clients)} verified")
    return verified


# =============================================================================
# SECTION 6: LINE COUNT SUMMARY
# =============================================================================


def section_6_summary():
    """Count lines of code across all clients."""
    print_separator()
    print_section(6, "Client Code Summary")

    clients = {
        "Desktop (Rust + JS)": [
            "apps/desktop/kagami-client/src-tauri/src/*.rs",
            "apps/desktop/kagami-client/src/js/*.js",
        ],
        "Hub (Rust)": ["apps/hub/kagami-hub/src/*.rs"],
        "Watch (Swift)": ["apps/watch/kagami-watch/KagamiWatch/**/*.swift"],
        "Vision (Swift)": ["apps/vision/kagami-vision/KagamiVision/**/*.swift"],
        "Android (Kotlin)": ["apps/android/kagami-android/**/*.kt"],
        "iOS (Swift)": ["apps/ios/kagami-ios/**/*.swift"],
    }

    print("   Lines of code by platform:")
    total_lines = 0

    for name, patterns in clients.items():
        lines = 0
        for pattern in patterns:
            for f in PROJECT_ROOT.glob(pattern):
                if f.is_file():
                    try:
                        lines += sum(1 for _ in open(f))
                    except Exception:
                        pass
        print(f"      {name}: {lines:,} lines")
        total_lines += lines

    print()
    print(f"   Total client code: {total_lines:,} lines")

    print()
    print_success("Code summary complete")


# =============================================================================
# MAIN
# =============================================================================


def main():
    """Run Client Apps demonstration."""
    print_header("CLIENT APPS DEMO", "📱")

    MetricsCollector("client_apps_demo")

    with Timer() as total_timer:
        # Verify each platform
        desktop_ok = section_1_desktop()
        hub_ok = section_2_hub()
        watch_ok = section_3_watch()
        vision_ok = section_4_vision()
        additional = section_5_additional()

        # Summary
        section_6_summary()

    platforms_verified = sum([desktop_ok, hub_ok, watch_ok, vision_ok]) + additional

    print_metrics(
        {
            "Total time": f"{total_timer.elapsed:.2f}s",
            "Platforms verified": f"{platforms_verified}/6",
            "Desktop": "✅" if desktop_ok else "❌",
            "Hub": "✅" if hub_ok else "❌",
            "Watch": "✅" if watch_ok else "❌",
            "Vision": "✅" if vision_ok else "❌",
            "Android/iOS": f"{additional}/2",
        }
    )

    if platforms_verified >= 4:
        print_footer(
            message="Client Apps VERIFIED — Real source code exists!",
            next_steps=[
                f"{platforms_verified} client platforms have real code",
                "See apps/ directory for source",
                "Run smarthome_demo.py to test backend",
            ],
        )
    else:
        print_footer(
            message="Some client apps missing",
            next_steps=[
                "Check apps/ directory structure",
                "Some platforms may be in development",
            ],
        )


if __name__ == "__main__":
    main()
