"""Image preprocessing for OMR.

Prepares score images for optimal recognition:
- Binarization (adaptive thresholding)
- Deskew correction
- Noise removal
- Contrast enhancement
- Staff line detection hints
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class PreprocessResult:
    """Result of image preprocessing.

    Attributes:
        image: Processed PIL Image.
        binary: Binarized numpy array.
        skew_angle: Detected skew angle in degrees.
        staff_line_spacing: Estimated staff line spacing in pixels.
        contrast_enhanced: Whether contrast was enhanced.
    """

    image: Image.Image
    binary: np.ndarray
    skew_angle: float
    staff_line_spacing: float | None
    contrast_enhanced: bool


class ImagePreprocessor:
    """Preprocess score images for OMR.

    Applies standard image processing techniques to improve
    recognition accuracy on scanned/photographed sheet music.

    Example:
        >>> preprocessor = ImagePreprocessor()
        >>> result = preprocessor.process(image)
        >>> print(f"Skew: {result.skew_angle:.2f}°")
    """

    def __init__(
        self,
        binarize: bool = True,
        deskew: bool = True,
        denoise: bool = True,
        enhance_contrast: bool = True,
    ) -> None:
        """Initialize preprocessor with options.

        Args:
            binarize: Apply adaptive binarization.
            deskew: Correct rotation/skew.
            denoise: Remove noise artifacts.
            enhance_contrast: Enhance contrast for faded scans.
        """
        self.binarize = binarize
        self.deskew = deskew
        self.denoise = denoise
        self.enhance_contrast = enhance_contrast

    def process(self, image: Image.Image) -> PreprocessResult:
        """Process an image for OMR.

        Args:
            image: Input PIL Image (can be RGB or grayscale).

        Returns:
            PreprocessResult with processed image and metadata.
        """
        from PIL import Image, ImageFilter

        # Convert to grayscale if needed
        if image.mode != "L":
            gray = image.convert("L")
        else:
            gray = image.copy()

        # Convert to numpy for processing
        arr = np.array(gray)
        skew_angle = 0.0
        contrast_enhanced = False

        # Enhance contrast for faded scans
        if self.enhance_contrast:
            arr, contrast_enhanced = self._enhance_contrast(arr)
            gray = Image.fromarray(arr)

        # Deskew correction
        if self.deskew:
            skew_angle = self._detect_skew(arr)
            if abs(skew_angle) > 0.1:
                gray = gray.rotate(skew_angle, resample=Image.BICUBIC, expand=False, fillcolor=255)
                arr = np.array(gray)
                logger.debug(f"Corrected skew: {skew_angle:.2f}°")

        # Denoise
        if self.denoise:
            gray = gray.filter(ImageFilter.MedianFilter(size=3))
            arr = np.array(gray)

        # Binarize using adaptive thresholding
        binary = arr
        if self.binarize:
            binary = self._adaptive_binarize(arr)

        # Estimate staff line spacing
        staff_spacing = self._estimate_staff_spacing(binary)

        # Convert binary back to PIL for output
        output_image = Image.fromarray(binary if self.binarize else arr)

        return PreprocessResult(
            image=output_image,
            binary=binary,
            skew_angle=skew_angle,
            staff_line_spacing=staff_spacing,
            contrast_enhanced=contrast_enhanced,
        )

    def _enhance_contrast(self, arr: np.ndarray) -> tuple[np.ndarray, bool]:
        """Enhance contrast using histogram equalization.

        Args:
            arr: Input grayscale array.

        Returns:
            Tuple of (enhanced array, whether enhancement was applied).
        """
        # Check if image needs enhancement
        std_dev = np.std(arr)
        if std_dev > 50:  # Already good contrast
            return arr, False

        # Apply CLAHE-like local contrast enhancement
        # Simple version: stretch histogram
        p2, p98 = np.percentile(arr, (2, 98))
        if p98 - p2 < 100:  # Low contrast
            arr = np.clip((arr - p2) * 255.0 / (p98 - p2 + 1), 0, 255).astype(np.uint8)
            return arr, True

        return arr, False

    def _detect_skew(self, arr: np.ndarray) -> float:
        """Detect skew angle using projection profile.

        Uses horizontal projection profiles at different angles
        to find the angle with maximum variance (strongest staff lines).

        Args:
            arr: Binarized or grayscale array.

        Returns:
            Skew angle in degrees.
        """
        # Binarize if needed
        if arr.max() > 1:
            threshold = np.mean(arr)
            binary = (arr < threshold).astype(np.uint8)
        else:
            binary = arr

        best_angle = 0.0
        best_variance = 0.0

        # Search in small range (-2 to 2 degrees)
        for angle_10 in range(-20, 21):
            angle = angle_10 / 10.0
            rotated = self._rotate_array(binary, angle)

            # Horizontal projection
            projection = np.sum(rotated, axis=1)
            variance = np.var(projection)

            if variance > best_variance:
                best_variance = variance
                best_angle = angle

        return best_angle

    def _rotate_array(self, arr: np.ndarray, angle: float) -> np.ndarray:
        """Rotate array by angle degrees.

        Args:
            arr: Input array.
            angle: Rotation angle in degrees.

        Returns:
            Rotated array.
        """
        from PIL import Image

        img = Image.fromarray((arr * 255).astype(np.uint8))
        rotated = img.rotate(angle, resample=Image.BILINEAR, fillcolor=0)
        return np.array(rotated) / 255.0

    def _adaptive_binarize(
        self, arr: np.ndarray, block_size: int = 51, c: float = 10
    ) -> np.ndarray:
        """Adaptive binarization using local mean.

        Args:
            arr: Input grayscale array.
            block_size: Size of local neighborhood.
            c: Constant subtracted from local mean.

        Returns:
            Binarized array (0 = black, 255 = white).
        """
        from scipy.ndimage import uniform_filter

        # Compute local mean
        local_mean = uniform_filter(arr.astype(np.float64), size=block_size)

        # Threshold: pixel < (local_mean - c) => black
        binary = np.where(arr < (local_mean - c), 0, 255).astype(np.uint8)

        return binary

    def _estimate_staff_spacing(self, binary: np.ndarray) -> float | None:
        """Estimate staff line spacing using run-length analysis.

        Looks for repeating patterns in horizontal projections
        that correspond to staff lines.

        Args:
            binary: Binarized array.

        Returns:
            Estimated spacing in pixels, or None if not detected.
        """
        # Horizontal projection (sum of black pixels per row)
        if binary.max() > 1:
            projection = np.sum(binary < 128, axis=1)
        else:
            projection = np.sum(binary, axis=1)

        # Find peaks (staff lines)
        threshold = np.max(projection) * 0.5
        peaks = []
        in_peak = False
        peak_start = 0

        for i, val in enumerate(projection):
            if val > threshold and not in_peak:
                in_peak = True
                peak_start = i
            elif val <= threshold and in_peak:
                in_peak = False
                peaks.append((peak_start + i) // 2)

        if len(peaks) < 5:
            return None

        # Calculate spacing between consecutive peaks
        spacings = [peaks[i + 1] - peaks[i] for i in range(len(peaks) - 1)]

        # Filter outliers and get median
        spacings = [s for s in spacings if 3 < s < 50]  # Reasonable range
        if not spacings:
            return None

        return float(np.median(spacings))


class StaffDetector:
    """Detect staff lines and systems in a score image.

    Uses morphological operations and projection analysis
    to identify staff line positions and group them into systems.
    """

    def __init__(self) -> None:
        """Initialize the staff detector."""
        pass

    def detect_staff_lines(self, binary: np.ndarray) -> list[list[int]]:
        """Detect horizontal staff lines.

        Args:
            binary: Binarized score image.

        Returns:
            List of staff groups, each containing 5 line y-positions.
        """
        # Horizontal projection
        projection = np.sum(binary < 128, axis=1)

        # Find peaks
        threshold = np.mean(projection) + np.std(projection)
        peaks = []

        for i in range(1, len(projection) - 1):
            if (
                projection[i] > threshold
                and projection[i] >= projection[i - 1]
                and projection[i] >= projection[i + 1]
            ):
                peaks.append(i)

        # Group into staves (5 lines each)
        staves = []
        current_staff = []
        last_peak = -100

        for peak in peaks:
            if peak - last_peak > 50:  # New staff
                if len(current_staff) >= 5:
                    staves.append(current_staff[:5])
                current_staff = [peak]
            else:
                current_staff.append(peak)
            last_peak = peak

        if len(current_staff) >= 5:
            staves.append(current_staff[:5])

        return staves

    def detect_systems(self, staff_lines: list[list[int]], page_height: int) -> list[list[int]]:
        """Group staves into systems.

        A system is a group of staves that are played simultaneously
        (e.g., all instruments in an orchestral score).

        Args:
            staff_lines: List of staff line positions.
            page_height: Height of the page in pixels.

        Returns:
            List of systems, each containing indices of staves.
        """
        if not staff_lines:
            return []

        # Calculate gaps between staves
        staff_centers = [sum(staff) / 5 for staff in staff_lines]
        gaps = [staff_centers[i + 1] - staff_centers[i] for i in range(len(staff_centers) - 1)]

        if not gaps:
            return [[0]]

        # Large gap indicates system break
        median_gap = np.median(gaps)
        system_break_threshold = median_gap * 1.5

        systems = []
        current_system = [0]

        for i, gap in enumerate(gaps):
            if gap > system_break_threshold:
                systems.append(current_system)
                current_system = [i + 1]
            else:
                current_system.append(i + 1)

        if current_system:
            systems.append(current_system)

        return systems
