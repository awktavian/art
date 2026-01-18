"""Face Clustering Pipeline.

Groups extracted faces by person using DBSCAN clustering on face embeddings.

Usage:
    clusterer = FaceClusterer()
    clusters = clusterer.cluster(faces)

    for person_id, person_faces in clusters.items():
        print(f"Person {person_id}: {len(person_faces)} faces")
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

try:
    from sklearn.cluster import DBSCAN
    from sklearn.preprocessing import normalize

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

from kagami_media.face_extractor import ExtractedFace


@dataclass
class PersonCluster:
    """A cluster of faces belonging to the same person."""

    cluster_id: int
    faces: list[ExtractedFace]
    centroid: np.ndarray | None = None

    @property
    def best_face(self) -> ExtractedFace:
        """Return highest quality face in cluster."""
        quality_order = {"excellent": 4, "good": 3, "fair": 2, "poor": 1}
        return max(
            self.faces,
            key=lambda f: (quality_order.get(f.quality_score, 0), f.sharpness, f.face_size),
        )

    @property
    def top_faces(self, n: int = 5) -> list[ExtractedFace]:
        """Return top N highest quality faces."""
        quality_order = {"excellent": 4, "good": 3, "fair": 2, "poor": 1}
        sorted_faces = sorted(
            self.faces,
            key=lambda f: (quality_order.get(f.quality_score, 0), f.sharpness, f.face_size),
            reverse=True,
        )
        return sorted_faces[:n]

    @property
    def source_videos(self) -> set[str]:
        """Get all source videos containing this person."""
        return {f.source_video for f in self.faces}

    @property
    def timestamp_range(self) -> tuple[float, float]:
        """Get min/max timestamps for this person."""
        timestamps = [f.timestamp_seconds for f in self.faces]
        return (min(timestamps), max(timestamps))

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "cluster_id": self.cluster_id,
            "face_count": len(self.faces),
            "source_videos": list(self.source_videos),
            "best_face": self.best_face.to_dict(),
            "all_faces": [f.to_dict() for f in self.faces],
        }


class FaceClusterer:
    """Cluster faces by person using DBSCAN.

    Uses face embeddings to group faces that belong to the same person.
    Works with or without InsightFace embeddings (falls back to image similarity).
    """

    def __init__(
        self,
        eps: float = 0.5,
        min_samples: int = 2,
        metric: str = "cosine",
    ):
        """Initialize clusterer.

        Args:
            eps: DBSCAN epsilon (max distance between samples)
            min_samples: Min samples to form a cluster
            metric: Distance metric ('cosine' or 'euclidean')
        """
        self.eps = eps
        self.min_samples = min_samples
        self.metric = metric

    def cluster(self, faces: list[ExtractedFace]) -> dict[int, PersonCluster]:
        """Cluster faces by person.

        Args:
            faces: List of extracted faces with embeddings

        Returns:
            Dictionary mapping cluster_id to PersonCluster
        """
        if not faces:
            return {}

        if not SKLEARN_AVAILABLE:
            # Fall back to simple clustering by visual similarity
            return self._fallback_cluster(faces)

        # Check if we have embeddings
        embeddings = [f.embedding for f in faces if f.embedding is not None]

        if len(embeddings) < len(faces) * 0.5:
            # Not enough embeddings, use fallback
            return self._fallback_cluster(faces)

        # Use only faces with embeddings
        faces_with_embeddings = [f for f in faces if f.embedding is not None]
        embedding_matrix = np.vstack([f.embedding for f in faces_with_embeddings])

        # Normalize embeddings for cosine similarity
        if self.metric == "cosine":
            embedding_matrix = normalize(embedding_matrix)

        # Run DBSCAN
        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric="euclidean" if self.metric == "cosine" else self.metric,
            n_jobs=-1,
        ).fit(embedding_matrix)

        # Group faces by cluster
        clusters: dict[int, PersonCluster] = {}

        for face, label in zip(faces_with_embeddings, clustering.labels_, strict=False):
            if label == -1:
                # Noise - assign to individual cluster
                noise_id = -1 - len([c for c in clusters if c < 0])
                clusters[noise_id] = PersonCluster(
                    cluster_id=noise_id,
                    faces=[face],
                )
            else:
                if label not in clusters:
                    clusters[label] = PersonCluster(
                        cluster_id=label,
                        faces=[],
                    )
                clusters[label].faces.append(face)

        # Calculate centroids
        for cluster in clusters.values():
            if cluster.cluster_id >= 0:
                embeddings = [f.embedding for f in cluster.faces]
                cluster.centroid = np.mean(embeddings, axis=0)

        return clusters

    def _fallback_cluster(self, faces: list[ExtractedFace]) -> dict[int, PersonCluster]:
        """Simple clustering based on temporal proximity.

        Groups faces that appear close together in time within the same video.
        """
        # Group by video first
        by_video: dict[str, list[ExtractedFace]] = defaultdict(list)
        for face in faces:
            by_video[face.source_video].append(face)

        clusters: dict[int, PersonCluster] = {}
        cluster_id = 0

        for _video, video_faces in by_video.items():
            # Sort by timestamp
            video_faces.sort(key=lambda f: f.timestamp_seconds)

            # Group faces within 5 seconds of each other
            current_cluster = []
            last_timestamp = -999

            for face in video_faces:
                if face.timestamp_seconds - last_timestamp > 5.0:
                    # New cluster
                    if current_cluster:
                        clusters[cluster_id] = PersonCluster(
                            cluster_id=cluster_id,
                            faces=current_cluster,
                        )
                        cluster_id += 1
                    current_cluster = [face]
                else:
                    current_cluster.append(face)
                last_timestamp = face.timestamp_seconds

            # Don't forget last cluster
            if current_cluster:
                clusters[cluster_id] = PersonCluster(
                    cluster_id=cluster_id,
                    faces=current_cluster,
                )
                cluster_id += 1

        return clusters

    def merge_clusters(
        self,
        clusters: dict[int, PersonCluster],
        cluster_ids: list[int],
        new_id: int | None = None,
    ) -> dict[int, PersonCluster]:
        """Merge multiple clusters into one.

        Args:
            clusters: Current clusters
            cluster_ids: IDs of clusters to merge
            new_id: Optional ID for merged cluster

        Returns:
            Updated clusters dictionary
        """
        if len(cluster_ids) < 2:
            return clusters

        # Collect all faces from clusters to merge
        merged_faces = []
        for cid in cluster_ids:
            if cid in clusters:
                merged_faces.extend(clusters[cid].faces)
                del clusters[cid]

        # Create merged cluster
        if new_id is None:
            new_id = min(cluster_ids)

        clusters[new_id] = PersonCluster(
            cluster_id=new_id,
            faces=merged_faces,
        )

        return clusters

    def save_clusters(
        self,
        clusters: dict[int, PersonCluster],
        output_dir: str,
        save_images: bool = True,
    ):
        """Save clusters to directory.

        Args:
            clusters: Clusters to save
            output_dir: Output directory
            save_images: Whether to save face images
        """
        import cv2

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        cluster_data = {}

        for cluster_id, cluster in clusters.items():
            cluster_dir = output_path / f"person_{cluster_id:03d}"
            cluster_dir.mkdir(exist_ok=True)

            if save_images:
                # Save top faces
                for i, face in enumerate(cluster.top_faces):
                    img_path = cluster_dir / f"face_{i:02d}_{face.face_id}.jpg"
                    cv2.imwrite(str(img_path), face.face_image)

            cluster_data[cluster_id] = cluster.to_dict()

        # Save cluster metadata
        meta_path = output_path / "clusters.json"
        with open(meta_path, "w") as f:
            json.dump(
                {
                    "total_clusters": len(clusters),
                    "total_faces": sum(len(c.faces) for c in clusters.values()),
                    "clusters": cluster_data,
                },
                f,
                indent=2,
            )


def cluster_faces(faces: list[ExtractedFace]) -> dict[int, PersonCluster]:
    """Convenience function to cluster faces.

    Args:
        faces: List of extracted faces

    Returns:
        Dictionary mapping cluster_id to PersonCluster
    """
    clusterer = FaceClusterer()
    return clusterer.cluster(faces)
