"""Dense optical flow computation for motion analysis.

Uses Farneback's algorithm for dense optical flow tracking.
Superior to simple frame difference for motion understanding.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def compute_dense_optical_flow(
    frame1: Any, frame2: Any, method: str = "farneback"
) -> dict[str, Any]:
    """Compute dense optical flow between two frames.

    Args:
        frame1: Previous frame (BGR or grayscale)
        frame2: Current frame (BGR or grayscale)
        method: "farneback" (dense) or "lucas-kanade" (sparse)

    Returns:
        Dict with flow field, magnitude, angle, and statistics
    """
    try:
        import cv2
        import numpy as np

        # Convert to grayscale if needed
        if len(frame1.shape) == 3:
            gray1 = cv2.cvtColor(frame1, cv2.COLOR_BGR2GRAY)
        else:
            gray1 = frame1

        if len(frame2.shape) == 3:
            gray2 = cv2.cvtColor(frame2, cv2.COLOR_BGR2GRAY)
        else:
            gray2 = frame2

        if method == "farneback":
            # Dense optical flow (Farneback algorithm)
            flow = cv2.calcOpticalFlowFarneback(  # type: ignore[call-overload]
                prev=gray1,
                next=gray2,
                flow=None,
                pyr_scale=0.5,  # Pyramid scale
                levels=3,  # Number of pyramid levels
                winsize=15,  # Window size
                iterations=3,  # Iterations at each level
                poly_n=5,  # Polynomial expansion size
                poly_sigma=1.2,  # Gaussian sigma for polynomial expansion
                flags=0,
            )

            # flow: [H, W, 2] where flow[y,x] = (dx, dy)

            # Compute magnitude and angle
            magnitude, angle = cv2.cartToPolar(flow[..., 0], flow[..., 1])

            # Statistics
            avg_magnitude = float(np.mean(magnitude))
            max_magnitude = float(np.max(magnitude))
            flow_variance = float(np.var(magnitude))

            # Detect high-motion regions
            high_motion_threshold = avg_magnitude + 2 * np.std(magnitude)
            high_motion_mask = magnitude > high_motion_threshold
            high_motion_percent = 100 * np.sum(high_motion_mask) / magnitude.size

            return {
                "flow": flow,
                "magnitude": magnitude,
                "angle": angle,
                "stats": {
                    "average_magnitude": round(avg_magnitude, 2),
                    "max_magnitude": round(max_magnitude, 2),
                    "variance": round(flow_variance, 2),
                    "high_motion_percent": round(float(high_motion_percent), 2),
                },
                "method": "farneback",
            }

        else:  # lucas-kanade (sparse)
            # Detect features in first frame
            feature_params = {
                "maxCorners": 200,
                "qualityLevel": 0.01,
                "minDistance": 10,
                "blockSize": 7,
            }

            p0 = cv2.goodFeaturesToTrack(gray1, **feature_params)  # type: ignore  # Overload call

            if p0 is None:
                return {"flow": None, "stats": {"tracked_points": 0}}

            # Track features in second frame
            lk_params = {
                "winSize": (15, 15),
                "maxLevel": 2,
                "criteria": (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 0.03),
            }

            p1, status, _err = cv2.calcOpticalFlowPyrLK(  # type: ignore  # Overload call
                gray1, gray2, p0, None, **lk_params
            )

            # Select good points
            if p1 is not None and status is not None:
                good_new = p1[status == 1]
                good_old = p0[status == 1]

                # Compute motion vectors
                motion_vectors = good_new - good_old
                magnitudes = np.linalg.norm(motion_vectors, axis=1)

                return {
                    "points_old": good_old,
                    "points_new": good_new,
                    "motion_vectors": motion_vectors,
                    "stats": {
                        "tracked_points": len(good_new),
                        "average_magnitude": round(float(np.mean(magnitudes)), 2),
                        "max_magnitude": round(float(np.max(magnitudes)), 2),
                    },
                    "method": "lucas-kanade",
                }
            else:
                return {"flow": None, "stats": {"tracked_points": 0}}

    except ImportError:
        logger.debug("OpenCV not available for optical flow")
        return {"error": "opencv_missing", "stats": {"average_magnitude": 0.0}}
    except Exception as e:
        logger.error(f"Optical flow computation failed: {e}")
        return {"error": str(e), "stats": {"average_magnitude": 0.0}}


def visualize_optical_flow(flow_magnitude: Any, flow_angle: Any, method: str = "hsv") -> Any:
    """Create visualization of optical flow field.

    Args:
        flow_magnitude: Magnitude of flow vectors
        flow_angle: Angle of flow vectors (radians)
        method: "hsv" or "arrows"

    Returns:
        RGB visualization image
    """
    try:
        import cv2
        import numpy as np

        if method == "hsv":
            # HSV representation: Hue=direction, Value=magnitude
            h, w = flow_magnitude.shape
            hsv = np.zeros((h, w, 3), dtype=np.uint8)
            hsv[..., 1] = 255  # Saturation = max

            # Hue from angle (0-180 degrees)
            hsv[..., 0] = (flow_angle * 180 / np.pi / 2).astype(np.uint8)

            # Value from magnitude (normalized)
            hsv[..., 2] = cv2.normalize(  # type: ignore  # Overload call
                flow_magnitude, None, 0, 255, cv2.NORM_MINMAX
            ).astype(np.uint8)

            # Convert to RGB
            rgb = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

            return rgb

        else:
            logger.warning(f"Visualization method '{method}' not implemented")
            return None

    except Exception as e:
        logger.error(f"Flow visualization failed: {e}")
        return None


def extract_motion_features(flow_result: dict[str, Any]) -> dict[str, float]:
    """Extract high-level motion features from optical flow.

    Args:
        flow_result: Result from compute_dense_optical_flow()

    Returns:
        Motion feature dict[str, Any] (for world model input)
    """
    if "stats" not in flow_result:
        return {"motion_intensity": 0.0, "motion_complexity": 0.0}

    stats = flow_result["stats"]

    # Motion intensity (how much motion)
    motion_intensity = stats.get("average_magnitude", 0.0)

    # Motion complexity (how varied the motion is)
    motion_complexity = stats.get("variance", 0.0)

    # Motion coverage (what percentage is moving)
    motion_coverage = stats.get("high_motion_percent", 0.0)

    return {
        "motion_intensity": motion_intensity,
        "motion_complexity": motion_complexity,
        "motion_coverage": motion_coverage,
    }
