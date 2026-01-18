#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Tool Time University - IMSCC Package Builder
# Creates a Canvas-compatible Common Cartridge import package
# ═══════════════════════════════════════════════════════════════════════════════

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPORT_DIR="${SCRIPT_DIR}/canvas-export"
OUTPUT_FILE="${SCRIPT_DIR}/tool-time-university.imscc"

echo "═══════════════════════════════════════════════════════════════════"
echo "  Tool Time University - IMSCC Package Builder"
echo "  MORE POWER to your Canvas course imports!"
echo "═══════════════════════════════════════════════════════════════════"
echo ""

# Check if canvas-export directory exists
if [ ! -d "${EXPORT_DIR}" ]; then
    echo "ERROR: canvas-export directory not found!"
    echo "Expected location: ${EXPORT_DIR}"
    exit 1
fi

# Check for required files
REQUIRED_FILES=(
    "imsmanifest.xml"
    "course_settings/course_settings.xml"
    "course_settings/assignment_groups.xml"
    "outcomes.xml"
)

echo "Checking required files..."
for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "${EXPORT_DIR}/${file}" ]; then
        echo "ERROR: Required file missing: ${file}"
        exit 1
    fi
    echo "  ✓ ${file}"
done

# Remove old package if exists
if [ -f "${OUTPUT_FILE}" ]; then
    echo ""
    echo "Removing existing package..."
    rm "${OUTPUT_FILE}"
fi

# Create the IMSCC package (which is just a zip file with .imscc extension)
echo ""
echo "Building IMSCC package..."
cd "${EXPORT_DIR}"

# Create zip with proper structure
# IMSCC requires imsmanifest.xml at the root
zip -r "${OUTPUT_FILE}" . \
    -x "*.DS_Store" \
    -x "__MACOSX/*" \
    -x "*.git*" \
    -x "*.sh"

echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo "  Package created successfully!"
echo "  Output: ${OUTPUT_FILE}"
echo ""
echo "  Package contents:"
unzip -l "${OUTPUT_FILE}" | head -30
echo "  ... (and more)"
echo ""
echo "  To import into Canvas:"
echo "  1. Go to your Canvas course"
echo "  2. Settings → Import Course Content"
echo "  3. Select 'Common Cartridge 1.x Package'"
echo "  4. Upload: tool-time-university.imscc"
echo "  5. Select content to import"
echo ""
echo "  DOES EVERYBODY KNOW WHAT TIME IT IS?"
echo "  TOOL TIME!"
echo "═══════════════════════════════════════════════════════════════════"
