"""Face Quality Scoring.

Scores face images for quality to select best references.

Quality factors:
- Sharpness (Laplacian variance)
- Face size (pixels)
- Pose/frontality
- Lighting uniformity
- Expression (neutral preferred)
"""

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class QualityScore:
    """Quality assessment for a face image."""

    sharpness: float = 0.0
    size_score: float = 0.0
    lighting_score: float = 0.0
    contrast_score: float = 0.0
    overall: float = 0.0
    grade: str = "unknown"

    def calculate_overall(self):
        """Calculate weighted overall score."""
        self.overall = (
            self.sharpness * 0.35
            + self.size_score * 0.25
            + self.lighting_score * 0.20
            + self.contrast_score * 0.20
        )

        if self.overall > 0.75:
            self.grade = "excellent"
        elif self.overall > 0.55:
            self.grade = "good"
        elif self.overall > 0.35:
            self.grade = "fair"
        else:
            self.grade = "poor"


class QualityScorer:
    """Score face image quality."""

    def __init__(
        self,
        ideal_size: int = 256,
        max_sharpness: float = 1000.0,
    ):
        """Initialize scorer.

        Args:
            ideal_size: Ideal face size in pixels
            max_sharpness: Maximum expected sharpness value
        """
        self.ideal_size = ideal_size
        self.max_sharpness = max_sharpness

    def score(self, image: np.ndarray) -> QualityScore:
        """Score a face image.

        Args:
            image: Face image (BGR or grayscale)

        Returns:
            QualityScore with component and overall scores
        """
        score = QualityScore()

        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image

        # Sharpness (Laplacian variance)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        score.sharpness = min(laplacian_var / self.max_sharpness, 1.0)

        # Size score
        height, width = gray.shape[:2]
        avg_size = (height + width) / 2
        score.size_score = min(avg_size / self.ideal_size, 1.0)

        # Lighting uniformity (histogram spread)
        hist = cv2.calcHist([gray], [0], None, [256], [0, 256])
        hist = hist.flatten() / hist.sum()

        # Good lighting has spread histogram, not concentrated
        non_zero_bins = np.sum(hist > 0.001)
        score.lighting_score = min(non_zero_bins / 128.0, 1.0)

        # Contrast score
        min_val, max_val = gray.min(), gray.max()
        score.contrast_score = (max_val - min_val) / 255.0

        # Calculate overall
        score.calculate_overall()

        return score

    def score_batch(self, images: list[np.ndarray]) -> list[QualityScore]:
        """Score multiple images.

        Args:
            images: List of face images

        Returns:
            List of QualityScore objects
        """
        return [self.score(img) for img in images]

    def rank_by_quality(
        self,
        images: list[np.ndarray],
        return_indices: bool = False,
    ) -> list:
        """Rank images by quality.

        Args:
            images: List of face images
            return_indices: If True, return indices instead of images

        Returns:
            Sorted list of (image, score) or (index, score) tuples
        """
        scores = self.score_batch(images)

        if return_indices:
            ranked = [(i, s) for i, s in enumerate(scores)]
        else:
            ranked = [(img, s) for img, s in zip(images, scores, strict=False)]

        ranked.sort(key=lambda x: x[1].overall, reverse=True)
        return ranked


def score_face_quality(image: np.ndarray) -> QualityScore:
    """Convenience function to score a face image.

    Args:
        image: Face image

    Returns:
        QualityScore
    """
    scorer = QualityScorer()
    return scorer.score(image)
