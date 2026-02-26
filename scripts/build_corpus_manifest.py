#!/usr/bin/env python3
"""Build local corpus manifests for public datasets."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True, choices=["ubfc_rppg_v1"])
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument(
        "--output",
        default=Path("outputs/data/corpus_manifests/ubfc_rppg_v1_manifest.csv"),
        type=Path,
    )
    return parser.parse_args()


def build_ubfc_manifest(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    subjects = sorted(root.glob("subject*"))
    for subject_dir in subjects:
        if not subject_dir.is_dir():
            continue
        video_path = subject_dir / "vid.avi"
        if not video_path.exists():
            continue
        gt_candidates = sorted(subject_dir.glob("ground_truth.*"))
        gt_path = gt_candidates[0] if gt_candidates else None
        rows.append(
            {
                "corpus_id": "ubfc_rppg_v1",
                "subject_id": subject_dir.name,
                "scenario_id": "ubfc_default",
                "video_path": str(video_path.resolve()),
                "ground_truth_path": "" if gt_path is None else str(gt_path.resolve()),
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    root = args.root
    if not root.exists():
        raise FileNotFoundError(f"Corpus root not found: {root}")

    if args.corpus == "ubfc_rppg_v1":
        rows = build_ubfc_manifest(root)
    else:
        raise ValueError(f"Unsupported corpus: {args.corpus}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "corpus_id",
                "subject_id",
                "scenario_id",
                "video_path",
                "ground_truth_path",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
