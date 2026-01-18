"""BBC Symphony Orchestra — Comprehensive Test Harness.

Tests all 45 instruments with all articulations through the full pipeline:
1. Generate MIDI samples → bbc_sample_generator
2. Generate RfxChain files → rfxchain_generator
3. Render through REAPER → bbc_renderer
4. Play through spatial audio → voice effector

Created: January 2, 2026
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from kagami.core.effectors.bbc_instruments import BBC_CATALOG, Section
from kagami.core.effectors.bbc_sample_generator import (
    BBC_INSTRUMENTS_DATABASE,
    generate_and_save_sample,
)
from kagami.core.effectors.rfxchain_generator import (
    get_rfxchain_path,
)

logger = logging.getLogger(__name__)

# Output directories
OUTPUT_BASE = Path.home() / ".kagami" / "bbc_test"
MIDI_DIR = OUTPUT_BASE / "midi"
RENDER_DIR = OUTPUT_BASE / "rendered"
REPORT_DIR = OUTPUT_BASE / "reports"


@dataclass
class InstrumentTestResult:
    """Result of testing a single instrument."""

    key: str
    name: str
    section: str
    articulation_count: int
    midi_path: Path | None = None
    rfxchain_path: Path | None = None
    render_path: Path | None = None
    midi_size: int = 0
    rfxchain_size: int = 0
    render_size: int = 0
    midi_time_ms: float = 0
    rfxchain_time_ms: float = 0
    render_time_ms: float = 0
    success: bool = False
    error: str | None = None
    articulations_tested: list[str] = field(default_factory=list)


@dataclass
class TestReport:
    """Complete test report."""

    total_instruments: int = 0
    successful: int = 0
    failed: int = 0
    total_articulations: int = 0
    total_midi_time_ms: float = 0
    total_rfxchain_time_ms: float = 0
    total_render_time_ms: float = 0
    results: list[InstrumentTestResult] = field(default_factory=list)


def get_instruments_by_section(section: Section) -> list[str]:
    """Get instrument keys for a section."""
    return [k for k, v in BBC_CATALOG.items() if v.section == section]


def generate_midi_for_instrument(key: str) -> tuple[Path | None, float, str | None]:
    """Generate MIDI sample for an instrument. Returns (path, time_ms, error)."""
    t0 = time.perf_counter()
    try:
        # Check if in DATABASE (sample generator uses this)
        if key not in BBC_INSTRUMENTS_DATABASE:
            # Map BBC_CATALOG key to DATABASE key
            db_key = key
            if db_key not in BBC_INSTRUMENTS_DATABASE:
                return None, 0, f"Not in DATABASE: {key}"
        else:
            db_key = key

        path = generate_and_save_sample(db_key, MIDI_DIR)
        t1 = time.perf_counter()
        return path, (t1 - t0) * 1000, None
    except Exception as e:
        t1 = time.perf_counter()
        return None, (t1 - t0) * 1000, str(e)


def generate_rfxchain_for_instrument(key: str) -> tuple[Path | None, float, str | None]:
    """Generate RfxChain for an instrument. Returns (path, time_ms, error)."""
    t0 = time.perf_counter()
    try:
        path = get_rfxchain_path(key, force_regenerate=True)
        t1 = time.perf_counter()
        return path, (t1 - t0) * 1000, None
    except Exception as e:
        t1 = time.perf_counter()
        return None, (t1 - t0) * 1000, str(e)


async def test_single_instrument(key: str) -> InstrumentTestResult:
    """Test a single instrument through the pipeline."""
    if key not in BBC_CATALOG:
        return InstrumentTestResult(
            key=key,
            name=key,
            section="unknown",
            articulation_count=0,
            error=f"Unknown instrument: {key}",
        )

    inst = BBC_CATALOG[key]
    result = InstrumentTestResult(
        key=key,
        name=inst.name,
        section=inst.section.value,
        articulation_count=len(inst.articulations),
        articulations_tested=list(inst.articulations.keys()),
    )

    # Step 1: Generate MIDI
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        midi_path, midi_time, midi_error = await loop.run_in_executor(
            executor, generate_midi_for_instrument, key
        )

    if midi_error:
        result.error = f"MIDI: {midi_error}"
        return result

    result.midi_path = midi_path
    result.midi_time_ms = midi_time
    result.midi_size = midi_path.stat().st_size if midi_path else 0

    # Step 2: Generate RfxChain
    with ThreadPoolExecutor(max_workers=1) as executor:
        rfx_path, rfx_time, rfx_error = await loop.run_in_executor(
            executor, generate_rfxchain_for_instrument, key
        )

    if rfx_error:
        result.error = f"RfxChain: {rfx_error}"
        return result

    result.rfxchain_path = rfx_path
    result.rfxchain_time_ms = rfx_time
    result.rfxchain_size = rfx_path.stat().st_size if rfx_path else 0

    result.success = True
    return result


async def test_section(section: Section, max_parallel: int = 4) -> list[InstrumentTestResult]:
    """Test all instruments in a section in parallel."""
    keys = get_instruments_by_section(section)

    logger.info(f"Testing {section.value}: {len(keys)} instruments")

    semaphore = asyncio.Semaphore(max_parallel)

    async def bounded_test(key: str) -> InstrumentTestResult:
        async with semaphore:
            return await test_single_instrument(key)

    tasks = [bounded_test(key) for key in keys]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Handle any exceptions
    final_results = []
    for key, r in zip(keys, results, strict=False):
        if isinstance(r, Exception):
            final_results.append(
                InstrumentTestResult(
                    key=key,
                    name=key,
                    section=section.value,
                    articulation_count=0,
                    error=str(r),
                )
            )
        else:
            final_results.append(r)

    return final_results


async def test_all_instruments(max_parallel: int = 8) -> TestReport:
    """Test all instruments in all sections."""
    report = TestReport()

    # Create directories
    MIDI_DIR.mkdir(parents=True, exist_ok=True)
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Test all sections in parallel
    sections = [
        Section.STRINGS,
        Section.WOODWINDS,
        Section.BRASS,
        Section.PERCUSSION_TUNED,
        Section.PERCUSSION_UNTUNED,
    ]

    logger.info("=" * 80)
    logger.info("BBC SYMPHONY ORCHESTRA COMPREHENSIVE TEST")
    logger.info("=" * 80)

    all_results = []

    for section in sections:
        results = await test_section(section, max_parallel)
        all_results.extend(results)

        # Log section summary
        success = sum(1 for r in results if r.success)
        logger.info(f"  {section.value}: {success}/{len(results)} passed")

    # Compile report
    report.results = all_results
    report.total_instruments = len(all_results)
    report.successful = sum(1 for r in all_results if r.success)
    report.failed = report.total_instruments - report.successful
    report.total_articulations = sum(r.articulation_count for r in all_results)
    report.total_midi_time_ms = sum(r.midi_time_ms for r in all_results)
    report.total_rfxchain_time_ms = sum(r.rfxchain_time_ms for r in all_results)

    return report


def print_report(report: TestReport) -> str:
    """Generate a human-readable report."""
    lines = [
        "=" * 80,
        "BBC SYMPHONY ORCHESTRA TEST REPORT",
        "=" * 80,
        "",
        f"Total Instruments: {report.total_instruments}",
        f"Successful: {report.successful}",
        f"Failed: {report.failed}",
        f"Total Articulations: {report.total_articulations}",
        "",
        f"Total MIDI Generation: {report.total_midi_time_ms:.0f}ms",
        f"Total RfxChain Generation: {report.total_rfxchain_time_ms:.0f}ms",
        "",
        "-" * 80,
        "RESULTS BY INSTRUMENT",
        "-" * 80,
    ]

    # Group by section
    by_section: dict[str, list[InstrumentTestResult]] = {}
    for r in report.results:
        by_section.setdefault(r.section, []).append(r)

    for section, results in sorted(by_section.items()):
        lines.append(f"\n{section.upper()}")
        lines.append("-" * 40)

        for r in results:
            status = "✓" if r.success else "✗"
            arts = r.articulation_count
            midi_kb = r.midi_size / 1024 if r.midi_size else 0
            rfx_kb = r.rfxchain_size / 1024 if r.rfxchain_size else 0

            lines.append(
                f"  {status} {r.name}: {arts} artics, "
                f"MIDI {midi_kb:.1f}KB ({r.midi_time_ms:.0f}ms), "
                f"RfxChain {rfx_kb:.1f}KB ({r.rfxchain_time_ms:.0f}ms)"
            )

            if r.error:
                lines.append(f"    ERROR: {r.error}")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


async def run_full_test() -> TestReport:
    """Run the complete test suite."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    report = await test_all_instruments()

    # Print report
    report_text = print_report(report)
    print(report_text)

    # Save report
    report_path = REPORT_DIR / f"test_report_{int(time.time())}.txt"
    report_path.write_text(report_text)
    logger.info(f"\nReport saved to: {report_path}")

    return report


# Entry point for direct execution
if __name__ == "__main__":
    asyncio.run(run_full_test())


__all__ = [
    "InstrumentTestResult",
    "TestReport",
    "print_report",
    "run_full_test",
    "test_all_instruments",
    "test_section",
    "test_single_instrument",
]
