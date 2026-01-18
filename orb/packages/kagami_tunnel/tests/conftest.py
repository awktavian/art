"""Pytest configuration for kagami_tunnel tests.

Ensures the local package is properly imported during development.
"""

import sys
from pathlib import Path

# Add the kagami_tunnel package directory to sys.path
# This ensures local development imports work correctly
package_dir = Path(__file__).parent.parent
if str(package_dir) not in sys.path:
    sys.path.insert(0, str(package_dir))
