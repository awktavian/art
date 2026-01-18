# Hardware Documentation Skill

**Purpose:** Repeatable, auditable hardware product documentation workflow with single source of truth architecture.

## When to Use This Skill

- Creating or updating hardware BOM (Bill of Materials)
- Generating assembly documentation
- Building test coverage matrices
- Integrating FMEA (Failure Mode and Effects Analysis)
- Processing CAD files for documentation
- Running validation audits

## Core Principles

### 1. Single Source of Truth (SSOT)

All documentation derives from structured YAML/JSON files:

```
bom/
├── core.yaml          # Master BOM - ALL components, suppliers, tests
├── assemblies.yaml    # Assembly procedures (or embedded in core.yaml)
└── alternatives.yaml  # Alternative sourcing options

fmea/
└── core.yaml          # Failure modes linked to BOM components

tests/
└── coverage.yaml      # Test specifications linked to BOM
```

### 2. Traceability Chain

```
Requirements → Components → Tests → FMEA → Validation
     ↑              ↑          ↑        ↑
     └──────────────┴──────────┴────────┴── All linked by IDs
```

Every component has:
- `part_id` - unique identifier
- `test_coverage[]` - array of test IDs
- `fmea_links[]` - failure modes this component can exhibit

### 3. Output Generation Pipeline

```
YAML Source → Generator → Multiple Formats
                ├── HTML (interactive, searchable)
                ├── Markdown (git-friendly, docs)
                ├── CSV (spreadsheet, cost analysis)
                ├── PDF (print, shipping)
                └── IPC-2581 (manufacturing)
```

## BOM Structure (core.yaml)

```yaml
project: "kagami-orb"
version: "2.0.0"
revision: "B"

metadata:
  created: "2026-01-11"
  author: "Kagami"

components:
  - part_id: "LED-SK6812-001"
    designation: "U1-U24"
    quantity: 24
    value: "SK6812 RGBW LED"
    package: "5050"

    # Primary supplier
    supplier: "AliExpress"
    supplier_part_number: "SK6812-MINI-E"
    unit_cost: "$0.25"
    lead_time: "15-30 days"

    # Alternatives (CRITICAL for supply chain resilience)
    alternatives:
      - supplier: "Adafruit"
        part_number: "2862"
        unit_cost: "$0.50"
        lead_time: "In stock"

    # Technical specs
    attributes:
      protocol: "1-wire @ 800kHz"
      power_max: "60mA @ 5V"
      color_depth: "8-bit per channel"

    # Test linkage (CRITICAL)
    test_coverage:
      - test_id: "V-LED-001"
        description: "LED burn-in test"
        category: "reliability"
        criticality: "high"

    # FMEA linkage
    fmea_links:
      - fmea_id: "FM-V-001"
        failure_mode: "LED does not illuminate"

assemblies:
  - assembly_id: "ASM-LED-RING-001"
    name: "24-LED RGBW Ring"
    components_used:
      - part_id: "LED-SK6812-001"
        quantity: 24

    difficulty_level: "intermediate"
    manufacturing_time_minutes: 45

    steps:
      - step_num: 1
        description: "Prepare LED ring PCB"
        tools_required: ["soldering_iron", "flux", "solder"]
        parts_involved: ["LED-SK6812-001"]
        time_minutes: 5

        callouts:
          - type: "esd_warning"
            text: "LEDs are ESD sensitive. Use grounded workstation."
          - type: "tip"
            text: "Pre-tin pads for faster assembly."

        image_placeholders:
          - id: "ASM-LED-001-S1-A"
            description: "LED ring PCB with pads highlighted"
            dimensions: "800x600"
```

## Assembly Documentation Standards

### Hybrid Approach (IKEA + iFixit + ISO 9001)

**Layer 1: User-Facing Guide (IKEA + iFixit)**
- 3D illustrations > photos (consistent perspective)
- Minimal text (numbered steps only)
- Difficulty rating (1-5 scale)
- Time estimates per step
- Tool icons (not text lists)

**Layer 2: Work Instructions (ISO 9001)**
- Formal procedure with sign-off checkpoints
- Success criteria per step
- Rework instructions if step fails
- Inspector verification points

**Layer 3: Acceptance Criteria (IPC-A-610)**
- Photo examples: Acceptable / Marginal / Defective
- Solder joint standards
- Assembly tolerances

### Callout Types

| Type | Icon | Color | Use Case |
|------|------|-------|----------|
| `warning` | ⚠️ | Orange | General caution |
| `critical` | 🔴 | Red | Safety-critical step |
| `tip` | 💡 | Blue | Helpful hint |
| `esd_warning` | ⚡ | Red | ESD-sensitive component |
| `time_estimate` | ⏱️ | Green | Duration callout |

## Test Coverage Matrix

### Required Coverage

Every component MUST have at least one test in these categories:

| Component Type | Required Tests |
|---------------|----------------|
| ICs/Modules | Functional, Thermal |
| Passives | Electrical (tolerance) |
| Connectors | Mechanical (durability) |
| Power Components | Load, Thermal, Protection |
| Sensors | Calibration, Accuracy |

### Gap Detection

```python
# Automated gap detection
for component in bom.components:
    if not component.test_coverage:
        report_gap(f"{component.part_id}: NO TEST COVERAGE")

    if component.criticality == "high" and len(component.test_coverage) < 2:
        report_gap(f"{component.part_id}: HIGH CRITICALITY but <2 tests")
```

## FMEA Integration

### RPN Calculation

```
RPN = Severity × Occurrence × Detection
```

| Score | Severity | Occurrence | Detection |
|-------|----------|------------|-----------|
| 1-3 | Minor | Rare | Easily detected |
| 4-6 | Moderate | Occasional | Usually detected |
| 7-9 | Serious | Frequent | Hard to detect |
| 10 | Safety | Very frequent | Cannot detect |

### Mitigation Linkage

Every FMEA entry MUST link to:
- `mitigation_test` - Test that catches this failure
- `mitigation_step` - Assembly step that addresses it
- `residual_rpn` - RPN after mitigation

## CAD-to-Documentation Flow

### STL Generation

```bash
# Generate STL from OpenSCAD
openscad -o output.stl --export-format binstl input.scad

# Batch export all parts
for f in cad/openscad/*.scad; do
    openscad -o "cad/stl/$(basename $f .scad).stl" "$f"
done
```

### Part Naming Convention

```
{DESIGNATOR}_{COMPONENT_TYPE}_{VARIANT}
Example: U1_LED_SK6812
Example: R1_RES_470R
```

### Exploded View Generation

1. Load assembly STL
2. Identify component centroids
3. Calculate explosion vectors (radial from center)
4. Render at multiple angles (0°, 45°, 90°)
5. Generate interactive HTML viewer (Babylon.js)

## Validation Workflow

### Pre-Release Checklist

```
┌─────────────────────────────────────────────────────────┐
│  HARDWARE DOCUMENTATION QUALITY GATE                     │
├─────────────────────────────────────────────────────────┤
│  BOM Integrity                                          │
│  □ All components have unique part_id                   │
│  □ All components have at least one supplier            │
│  □ All high-criticality parts have alternatives         │
│  □ Total cost calculated and verified                   │
│                                                         │
│  Assembly Completeness                                  │
│  □ Every BOM item appears in at least one assembly step │
│  □ Every assembly step references valid BOM items       │
│  □ Time estimates verified (within 20% of actual)       │
│  □ All tools listed exist and are available             │
│                                                         │
│  Test Coverage                                          │
│  □ No untested components (100% coverage)               │
│  □ High-criticality components have 2+ tests            │
│  □ Test procedures have pass/fail criteria              │
│                                                         │
│  FMEA Coverage                                          │
│  □ All components have FMEA entries                     │
│  □ All FMEA entries link to mitigation tests            │
│  □ No RPN > 100 without documented mitigation           │
│                                                         │
│  CAD Integrity                                          │
│  □ All STL files generated from source                  │
│  □ Part names match BOM designators                     │
│  □ Exploded views current with design                   │
└─────────────────────────────────────────────────────────┘
```

## Commands

### Generate All Documentation

```bash
# From project root
python -m hardware_docs.generate \
    --bom bom/core.yaml \
    --output docs/ \
    --formats html,markdown,csv,pdf
```

### Run Validation Audit

```bash
python -m hardware_docs.validate \
    --bom bom/core.yaml \
    --fmea fmea/core.yaml \
    --assembly assemblies/ \
    --report validation_report.html
```

### Generate Test Matrix

```bash
python -m hardware_docs.test_matrix \
    --bom bom/core.yaml \
    --output docs/test_coverage.html \
    --identify-gaps
```

## Integration with Other Skills

| Skill | Integration |
|-------|-------------|
| `platform-hub` | Firmware test coverage feeds into hardware validation |
| `byzantine-quality` | Run parallel audits on documentation quality |
| `virtuoso` | Apply craft standards to assembly visuals |
| `video-production` | Generate assembly video from shot list |

## Example Projects

- `apps/hub/kagami-orb/` - Full implementation
- `apps/hub/kagami-pico/` - Simpler reference

## References

- IPC-A-610H: Electronics Assembly Acceptability
- IPC-J-STD-001: Soldering Standards
- ISO 9001:2015: Quality Management Work Instructions
- AIAG-VDA FMEA: Failure Mode Analysis Standard
