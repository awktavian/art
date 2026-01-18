"""Export utilities for Kagami examples.

Provides JSON and CSV export for metrics and results.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def export_json(
    data: dict[str, Any] | list[Any],
    path: str | Path,
    indent: int = 2,
    add_metadata: bool = True,
) -> Path:
    """Export data to JSON file.

    Args:
        data: Data to export
        path: Output file path
        indent: JSON indentation
        add_metadata: Whether to add export metadata

    Returns:
        Path to the exported file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if add_metadata and isinstance(data, dict):
        data = {
            "_metadata": {
                "exported_at": datetime.now().isoformat(),
                "source": "kagami_examples",
            },
            **data,
        }

    with open(path, "w") as f:
        json.dump(data, f, indent=indent, default=str)

    return path


def export_csv(
    rows: list[dict[str, Any]],
    path: str | Path,
    fieldnames: list[str] | None = None,
) -> Path:
    """Export data to CSV file.

    Args:
        rows: List of dictionaries to export
        path: Output file path
        fieldnames: Column names (auto-detected if None)

    Returns:
        Path to the exported file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        # Write empty file with header if fieldnames provided
        if fieldnames:
            with open(path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
        return path

    # Auto-detect fieldnames from first row
    if fieldnames is None:
        fieldnames = list(rows[0].keys())

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return path


def export_metrics(
    metrics: dict[str, Any],
    base_path: str | Path,
    name: str = "metrics",
    formats: list[str] | None = None,
) -> dict[str, Path]:
    """Export metrics to multiple formats.

    Args:
        metrics: Metrics dictionary
        base_path: Base directory for output
        name: Base filename (without extension)
        formats: List of formats to export (json, csv, txt)

    Returns:
        Dictionary mapping format to output path
    """
    formats = formats or ["json"]
    base_path = Path(base_path)
    results = {}

    if "json" in formats:
        json_path = base_path / f"{name}.json"
        export_json(metrics, json_path)
        results["json"] = json_path

    if "csv" in formats:
        csv_path = base_path / f"{name}.csv"
        # Flatten metrics for CSV
        flat_metrics = [{"metric": k, "value": v} for k, v in metrics.items()]
        export_csv(flat_metrics, csv_path, fieldnames=["metric", "value"])
        results["csv"] = csv_path

    if "txt" in formats:
        txt_path = base_path / f"{name}.txt"
        with open(txt_path, "w") as f:
            f.write("Kagami Metrics Export\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n")
            f.write("=" * 40 + "\n\n")
            for key, value in metrics.items():
                f.write(f"{key}: {value}\n")
        results["txt"] = txt_path

    return results


class ResultsExporter:
    """Helper class for exporting example results.

    Usage:
        exporter = ResultsExporter("my_example")
        exporter.add_result("test_1", {"score": 95})
        exporter.add_result("test_2", {"score": 87})
        exporter.export_all("/tmp/results")
    """

    def __init__(self, name: str):
        self.name = name
        self.results: list[dict[str, Any]] = []
        self.metadata: dict[str, Any] = {
            "name": name,
            "started_at": datetime.now().isoformat(),
        }

    def add_result(self, label: str, data: dict[str, Any]) -> None:
        """Add a result to the collection."""
        self.results.append(
            {
                "label": label,
                "timestamp": datetime.now().isoformat(),
                **data,
            }
        )

    def add_metadata(self, key: str, value: Any) -> None:
        """Add metadata about the export."""
        self.metadata[key] = value

    def export_all(
        self,
        base_path: str | Path,
        formats: list[str] | None = None,
    ) -> dict[str, Path]:
        """Export all results to files.

        Args:
            base_path: Base directory for output
            formats: List of formats (json, csv)

        Returns:
            Dictionary mapping format to output path
        """
        formats = formats or ["json"]
        base_path = Path(base_path)
        base_path.mkdir(parents=True, exist_ok=True)

        self.metadata["completed_at"] = datetime.now().isoformat()
        self.metadata["result_count"] = len(self.results)

        exported = {}

        if "json" in formats:
            json_path = base_path / f"{self.name}_results.json"
            export_json(
                {
                    "metadata": self.metadata,
                    "results": self.results,
                },
                json_path,
                add_metadata=False,
            )
            exported["json"] = json_path

        if "csv" in formats and self.results:
            csv_path = base_path / f"{self.name}_results.csv"
            export_csv(self.results, csv_path)
            exported["csv"] = csv_path

        return exported
