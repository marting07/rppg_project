#!/usr/bin/env python3
"""Run offline evaluation for all rows in a corpus manifest and aggregate results."""

from __future__ import annotations

import argparse
import csv
import hashlib
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--protocol", default=Path("configs/experiment_protocol.json"), type=Path)
    parser.add_argument("--methods", default="all")
    parser.add_argument("--scenario", default="still")
    parser.add_argument("--output-dir", default=Path("outputs/data"), type=Path)
    parser.add_argument(
        "--aggregate-out",
        default=Path("outputs/data/aggregate/manifest_aggregate_summary.csv"),
        type=Path,
    )
    parser.add_argument("--welch-window-seconds", type=float, default=None)
    parser.add_argument("--welch-overlap-ratio", type=float, default=None)
    parser.add_argument("--min-hr-confidence", type=float, default=None)
    parser.add_argument("--hr-smoothing-alpha", type=float, default=None)
    parser.add_argument("--max-hr-jump-bpm-per-s", type=float, default=None)
    parser.add_argument("--ground-truth-mode", choices=["auto", "bpm_row", "bvp_derived"], default="bpm_row")
    parser.add_argument("--max-lag-seconds", type=float, default=2.0)
    parser.add_argument("--roi-fusion-mode", choices=["single", "multi_snr"], default="multi_snr")
    parser.add_argument("--roi-snr-exponent", type=float, default=1.0)
    return parser.parse_args()


def stable_run_id(corpus_id: str, subject_id: str, video_path: str, methods: str, profile: str) -> str:
    payload = f"{corpus_id}|{subject_id}|{video_path}|{methods}|{profile}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return f"{corpus_id}_{subject_id}_{digest}"


def run_one(
    python_exec: str,
    row: dict[str, str],
    args: argparse.Namespace,
) -> tuple[str, str | None]:
    corpus_id = row.get("corpus_id", "unknown")
    subject_id = row.get("subject_id", "unknown")
    video_path = row.get("video_path", "").strip()
    gt_path = row.get("ground_truth_path", "").strip()
    if not video_path:
        return "", f"missing video path for {corpus_id}/{subject_id}"

    profile = (
        f"gt={args.ground_truth_mode};lag={args.max_lag_seconds};"
        f"roi={args.roi_fusion_mode};snr_exp={args.roi_snr_exponent}"
    )
    run_id = stable_run_id(corpus_id, subject_id, video_path, args.methods, profile)
    cmd = [
        python_exec,
        "scripts/offline_evaluate.py",
        "--video",
        video_path,
        "--protocol",
        str(args.protocol),
        "--scenario",
        args.scenario,
        "--methods",
        args.methods,
        "--run-id",
        run_id,
        "--output-dir",
        str(args.output_dir),
    ]
    if gt_path:
        cmd.extend(["--ground-truth", gt_path])
    if args.welch_window_seconds is not None:
        cmd.extend(["--welch-window-seconds", str(args.welch_window_seconds)])
    if args.welch_overlap_ratio is not None:
        cmd.extend(["--welch-overlap-ratio", str(args.welch_overlap_ratio)])
    if args.min_hr_confidence is not None:
        cmd.extend(["--min-hr-confidence", str(args.min_hr_confidence)])
    if args.hr_smoothing_alpha is not None:
        cmd.extend(["--hr-smoothing-alpha", str(args.hr_smoothing_alpha)])
    if args.max_hr_jump_bpm_per_s is not None:
        cmd.extend(["--max-hr-jump-bpm-per-s", str(args.max_hr_jump_bpm_per_s)])
    cmd.extend(["--ground-truth-mode", str(args.ground_truth_mode)])
    cmd.extend(["--max-lag-seconds", str(args.max_lag_seconds)])
    cmd.extend(["--roi-fusion-mode", str(args.roi_fusion_mode)])
    cmd.extend(["--roi-snr-exponent", str(args.roi_snr_exponent)])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        err = (result.stderr or result.stdout).strip()
        return run_id, err
    return run_id, None


def load_summary(summary_csv: Path) -> list[dict[str, str]]:
    with summary_csv.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def aggregate_metrics(rows: list[dict[str, str]], metric: str) -> str:
    values = [float(r[metric]) for r in rows if r.get(metric, "").strip()]
    if not values:
        return ""
    return f"{sum(values) / len(values):.6f}"


def main() -> int:
    args = parse_args()
    if not args.manifest.exists():
        raise FileNotFoundError(f"Manifest not found: {args.manifest}")

    with args.manifest.open("r", encoding="utf-8", newline="") as f:
        manifest_rows = list(csv.DictReader(f))
    if not manifest_rows:
        raise RuntimeError(f"No rows in manifest: {args.manifest}")

    python_exec = sys.executable
    run_reports: list[dict[str, str]] = []
    method_rows: list[dict[str, str]] = []

    for row in manifest_rows:
        run_id, err = run_one(python_exec, row, args)
        report = {
            "corpus_id": row.get("corpus_id", ""),
            "subject_id": row.get("subject_id", ""),
            "video_path": row.get("video_path", ""),
            "run_id": run_id,
            "status": "failed" if err else "ok",
            "error": "" if err is None else err.replace("\n", " "),
        }
        run_reports.append(report)
        if err is not None:
            continue

        summary_path = args.output_dir / run_id / "summary.csv"
        if not summary_path.exists():
            report["status"] = "failed"
            report["error"] = f"missing summary {summary_path}"
            continue

        for method_row in load_summary(summary_path):
            method_rows.append(
                {
                    "corpus_id": row.get("corpus_id", ""),
                    "subject_id": row.get("subject_id", ""),
                    "run_id": run_id,
                    "method": method_row.get("method", ""),
                    "frames": method_row.get("frames", ""),
                    "face_detected_ratio": method_row.get("face_detected_ratio", ""),
                    "roi_quality_accept_ratio": method_row.get("roi_quality_accept_ratio", ""),
                    "valid_hr_points": method_row.get("valid_hr_points", ""),
                    "mae": method_row.get("mae", ""),
                    "rmse": method_row.get("rmse", ""),
                    "pearson_correlation": method_row.get("pearson_correlation", ""),
                    "failure_rate_gt_10bpm": method_row.get("failure_rate_gt_10bpm", ""),
                }
            )

    args.aggregate_out.parent.mkdir(parents=True, exist_ok=True)
    with args.aggregate_out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "corpus_id",
                "subject_id",
                "run_id",
                "method",
                "frames",
                "face_detected_ratio",
                "roi_quality_accept_ratio",
                "valid_hr_points",
                "mae",
                "rmse",
                "pearson_correlation",
                "failure_rate_gt_10bpm",
            ],
        )
        writer.writeheader()
        writer.writerows(method_rows)

    run_report_path = args.aggregate_out.with_name(args.aggregate_out.stem + "_runs.csv")
    with run_report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["corpus_id", "subject_id", "video_path", "run_id", "status", "error"],
        )
        writer.writeheader()
        writer.writerows(run_reports)

    by_method: dict[str, list[dict[str, str]]] = {}
    for row in method_rows:
        by_method.setdefault(row["method"], []).append(row)
    method_table_path = args.aggregate_out.with_name(args.aggregate_out.stem + "_method_means.csv")
    with method_table_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "subjects",
                "mean_mae",
                "mean_rmse",
                "mean_pearson_correlation",
                "mean_failure_rate_gt_10bpm",
            ],
        )
        writer.writeheader()
        for method, rows in sorted(by_method.items()):
            writer.writerow(
                {
                    "method": method,
                    "subjects": str(len(rows)),
                    "mean_mae": aggregate_metrics(rows, "mae"),
                    "mean_rmse": aggregate_metrics(rows, "rmse"),
                    "mean_pearson_correlation": aggregate_metrics(rows, "pearson_correlation"),
                    "mean_failure_rate_gt_10bpm": aggregate_metrics(rows, "failure_rate_gt_10bpm"),
                }
            )

    ok_count = sum(1 for r in run_reports if r["status"] == "ok")
    fail_count = len(run_reports) - ok_count
    print(f"Batch finished: {ok_count} ok, {fail_count} failed")
    print(f"Per-run aggregate: {args.aggregate_out}")
    print(f"Method means: {method_table_path}")
    print(f"Run report: {run_report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
