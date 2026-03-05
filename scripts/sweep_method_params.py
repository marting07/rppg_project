#!/usr/bin/env python3
"""Grid-search HR estimator parameters for one method on a manifest subset."""

from __future__ import annotations

import argparse
import csv
import itertools
import subprocess
import sys
from pathlib import Path


def parse_floats(text: str) -> list[float]:
    return [float(x.strip()) for x in text.split(",") if x.strip()]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--method", required=True, choices=["green", "chrom", "pos", "ssr"])
    p.add_argument("--scenario", default="still")
    p.add_argument("--output-dir", default=Path("outputs/data"), type=Path)
    p.add_argument("--aggregate-root", default=Path("outputs/data/aggregate/sweeps"), type=Path)
    p.add_argument("--welch-window-seconds", default="5.0,6.0,8.0")
    p.add_argument("--min-hr-confidence", default="1.1,1.3,1.5")
    p.add_argument("--hr-smoothing-alpha", default="0.2,0.3,0.45")
    p.add_argument("--max-hr-jump-bpm-per-s", default="8.0,12.0,18.0")
    return p.parse_args()


def load_method_means(path: Path, method: str) -> dict[str, float]:
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("method") == method:
                return {
                    "mean_mae": float(row["mean_mae"]),
                    "mean_rmse": float(row["mean_rmse"]),
                    "mean_pearson_correlation": float(row["mean_pearson_correlation"]),
                    "mean_failure_rate_gt_10bpm": float(row["mean_failure_rate_gt_10bpm"]),
                }
    raise RuntimeError(f"Method row not found: {method} in {path}")


def score(metrics: dict[str, float]) -> float:
    return metrics["mean_mae"] + 0.35 * metrics["mean_rmse"] + 8.0 * metrics["mean_failure_rate_gt_10bpm"] - 4.0 * metrics["mean_pearson_correlation"]


def main() -> int:
    args = parse_args()
    if not args.manifest.exists():
        raise FileNotFoundError(args.manifest)

    windows = parse_floats(args.welch_window_seconds)
    confs = parse_floats(args.min_hr_confidence)
    alphas = parse_floats(args.hr_smoothing_alpha)
    jumps = parse_floats(args.max_hr_jump_bpm_per_s)

    args.aggregate_root.mkdir(parents=True, exist_ok=True)
    results_path = args.aggregate_root / f"{args.method}_sweep_results.csv"

    rows: list[dict[str, str]] = []
    best_row: dict[str, str] | None = None
    best_score: float | None = None

    for idx, (win_s, conf, alpha, jump) in enumerate(itertools.product(windows, confs, alphas, jumps), start=1):
        agg_out = args.aggregate_root / f"{args.method}_sweep_{idx:03d}.csv"
        cmd = [
            sys.executable,
            "scripts/run_manifest_batch.py",
            "--manifest",
            str(args.manifest),
            "--methods",
            args.method,
            "--scenario",
            args.scenario,
            "--output-dir",
            str(args.output_dir),
            "--aggregate-out",
            str(agg_out),
            "--welch-window-seconds",
            str(win_s),
            "--min-hr-confidence",
            str(conf),
            "--hr-smoothing-alpha",
            str(alpha),
            "--max-hr-jump-bpm-per-s",
            str(jump),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            rows.append(
                {
                    "method": args.method,
                    "welch_window_seconds": str(win_s),
                    "min_hr_confidence": str(conf),
                    "hr_smoothing_alpha": str(alpha),
                    "max_hr_jump_bpm_per_s": str(jump),
                    "status": "failed",
                    "score": "",
                    "mean_mae": "",
                    "mean_rmse": "",
                    "mean_pearson_correlation": "",
                    "mean_failure_rate_gt_10bpm": "",
                    "error": (proc.stderr or proc.stdout).replace("\n", " ").strip(),
                }
            )
            continue

        means_path = agg_out.with_name(agg_out.stem + "_method_means.csv")
        metrics = load_method_means(means_path, args.method)
        run_score = score(metrics)
        row = {
            "method": args.method,
            "welch_window_seconds": f"{win_s}",
            "min_hr_confidence": f"{conf}",
            "hr_smoothing_alpha": f"{alpha}",
            "max_hr_jump_bpm_per_s": f"{jump}",
            "status": "ok",
            "score": f"{run_score:.6f}",
            "mean_mae": f"{metrics['mean_mae']:.6f}",
            "mean_rmse": f"{metrics['mean_rmse']:.6f}",
            "mean_pearson_correlation": f"{metrics['mean_pearson_correlation']:.6f}",
            "mean_failure_rate_gt_10bpm": f"{metrics['mean_failure_rate_gt_10bpm']:.6f}",
            "error": "",
        }
        rows.append(row)

        if best_score is None or run_score < best_score:
            best_score = run_score
            best_row = row

    with results_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "welch_window_seconds",
                "min_hr_confidence",
                "hr_smoothing_alpha",
                "max_hr_jump_bpm_per_s",
                "status",
                "score",
                "mean_mae",
                "mean_rmse",
                "mean_pearson_correlation",
                "mean_failure_rate_gt_10bpm",
                "error",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote sweep results: {results_path}")
    if best_row is not None:
        print("Best parameters:")
        print(best_row)
    else:
        print("No successful runs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
