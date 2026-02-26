#!/usr/bin/env python3
"""Offline evaluator for manual rPPG method comparison."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import cv2  # type: ignore
import numpy as np

from rppg_methods import ChromMethod, GreenMethod, JBSSMethod
from rppg_methods.base import RPPGMethod
from utils.roi import FaceDetector, extract_forehead_roi

METHOD_FACTORY: dict[str, Callable[[float, int], RPPGMethod]] = {
    "green": lambda fs, buf: GreenMethod(fs=fs, buffer_size=buf),
    "chrom": lambda fs, buf: ChromMethod(fs=fs, buffer_size=buf),
    "jbss": lambda fs, buf: JBSSMethod(fs=fs, buffer_size=buf),
}


@dataclass
class GroundTruth:
    times_s: np.ndarray
    bpm: np.ndarray


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--protocol", default=Path("configs/experiment_protocol.json"), type=Path)
    parser.add_argument("--scenario", default="still")
    parser.add_argument("--methods", default="all", help="comma list or 'all'")
    parser.add_argument("--ground-truth", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", default=Path("outputs/data"), type=Path)
    return parser.parse_args()


def load_protocol(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_numeric_tokens(text: str) -> list[float]:
    matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", text)
    return [float(m) for m in matches]


def load_ground_truth(path: Path | None, fs: float | None = None) -> GroundTruth | None:
    if path is None:
        return None

    if path.suffix.lower() == ".csv":
        times: list[float] = []
        bpm: list[float] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                times.append(float(row["time_s"]))
                bpm.append(float(row["bpm"]))
        if not times:
            return None
        return GroundTruth(times_s=np.array(times, dtype=np.float64), bpm=np.array(bpm, dtype=np.float64))

    raw = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return None
    if fs is None or fs <= 0:
        fs = 30.0

    per_line_values = [_parse_numeric_tokens(line) for line in lines]
    candidate = max(per_line_values, key=len)
    if len(per_line_values) >= 2 and len(per_line_values[1]) >= len(candidate):
        candidate = per_line_values[1]
    if len(candidate) < 2:
        return None

    bpm = np.array(candidate, dtype=np.float64)
    times = np.arange(bpm.size, dtype=np.float64) / fs
    return GroundTruth(times_s=times, bpm=bpm)


def deterministic_run_id(video: Path, scenario: str, methods: list[str], protocol_path: Path) -> str:
    payload = f"{video.resolve()}|{scenario}|{','.join(methods)}|{protocol_path.resolve()}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return f"run_{digest}"


def interpolate_ground_truth(gt: GroundTruth | None, t_s: float) -> float | None:
    if gt is None:
        return None
    if gt.times_s.size == 1:
        return float(gt.bpm[0])
    if t_s < gt.times_s[0] or t_s > gt.times_s[-1]:
        return None
    return float(np.interp(t_s, gt.times_s, gt.bpm))


def compute_metrics(errors: np.ndarray, est: np.ndarray, gt: np.ndarray) -> dict[str, float | None]:
    out: dict[str, float | None] = {"mae": None, "rmse": None, "pearson_correlation": None, "failure_rate_gt_10bpm": None}
    if errors.size == 0:
        return out
    out["mae"] = float(np.mean(np.abs(errors)))
    out["rmse"] = float(np.sqrt(np.mean(errors ** 2)))
    out["failure_rate_gt_10bpm"] = float(np.mean(np.abs(errors) > 10.0))
    if est.size >= 2 and gt.size >= 2:
        corr = np.corrcoef(est, gt)[0, 1]
        out["pearson_correlation"] = float(corr) if np.isfinite(corr) else None
    return out


def main() -> int:
    args = parse_args()
    protocol = load_protocol(args.protocol)
    common = protocol["common_parameters"]

    requested_methods = list(METHOD_FACTORY.keys()) if args.methods == "all" else [m.strip() for m in args.methods.split(",") if m.strip()]
    for method_name in requested_methods:
        if method_name not in METHOD_FACTORY:
            raise ValueError(f"Unsupported method: {method_name}")

    run_id = args.run_id or deterministic_run_id(args.video, args.scenario, requested_methods, args.protocol)
    run_dir = args.output_dir / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    fs = fps if fps and fps > 1.0 else float(common["fs_fallback_hz"])
    buffer_size = int(float(common["buffer_seconds"]) * fs)

    methods = {name: METHOD_FACTORY[name](fs, buffer_size) for name in requested_methods}
    face_detector = FaceDetector()
    gt = load_ground_truth(args.ground_truth, fs=fs)

    records: dict[str, list[dict[str, str]]] = {name: [] for name in requested_methods}
    frame_idx = 0
    detected_face_count = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        time_s = frame_idx / fs
        faces = face_detector.detect_faces(frame)
        roi = None
        if faces:
            detected_face_count += 1
            face = max(faces, key=lambda b: b[2] * b[3])
            roi, _ = extract_forehead_roi(frame, face)

        gt_bpm = interpolate_ground_truth(gt, time_s)

        for method_name, method in methods.items():
            previous_len = len(method.signal_buffer)
            if roi is not None and roi.size > 0:
                method.update(roi)
            raw_value = method.signal_buffer[-1] if len(method.signal_buffer) > previous_len else None
            filtered_signal = method.get_ppg_signal()
            filtered_value = float(filtered_signal[-1]) if filtered_signal.size else None
            est_bpm = method.get_hr()
            confidence = None
            if hasattr(method, "get_confidence"):
                confidence = method.get_confidence()  # type: ignore[attr-defined]
            error = (est_bpm - gt_bpm) if (est_bpm is not None and gt_bpm is not None) else None

            records[method_name].append(
                {
                    "frame_idx": str(frame_idx),
                    "time_s": f"{time_s:.6f}",
                    "face_detected": "1" if roi is not None else "0",
                    "raw_signal": "" if raw_value is None else f"{raw_value:.8f}",
                    "filtered_signal": "" if filtered_value is None else f"{filtered_value:.8f}",
                    "estimated_bpm": "" if est_bpm is None else f"{est_bpm:.6f}",
                    "selection_confidence": "" if confidence is None else f"{float(confidence):.6f}",
                    "ground_truth_bpm": "" if gt_bpm is None else f"{gt_bpm:.6f}",
                    "error_bpm": "" if error is None else f"{error:.6f}",
                }
            )
        frame_idx += 1

    cap.release()

    summary_rows: list[dict[str, str]] = []
    for method_name, rows in records.items():
        out_csv = run_dir / f"{method_name}_timeseries.csv"
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "frame_idx",
                    "time_s",
                    "face_detected",
                    "raw_signal",
                    "filtered_signal",
                    "estimated_bpm",
                    "selection_confidence",
                    "ground_truth_bpm",
                    "error_bpm",
                ],
            )
            writer.writeheader()
            writer.writerows(rows)

        errors = np.array([float(r["error_bpm"]) for r in rows if r["error_bpm"]], dtype=np.float64)
        est = np.array([float(r["estimated_bpm"]) for r in rows if r["error_bpm"]], dtype=np.float64)
        gt_arr = np.array([float(r["ground_truth_bpm"]) for r in rows if r["error_bpm"]], dtype=np.float64)
        metrics = compute_metrics(errors, est, gt_arr)

        summary_rows.append(
            {
                "method": method_name,
                "frames": str(frame_idx),
                "face_detected_ratio": f"{(detected_face_count / frame_idx) if frame_idx else 0.0:.6f}",
                "valid_hr_points": str(sum(1 for r in rows if r["estimated_bpm"])),
                "mae": "" if metrics["mae"] is None else f"{metrics['mae']:.6f}",
                "rmse": "" if metrics["rmse"] is None else f"{metrics['rmse']:.6f}",
                "pearson_correlation": "" if metrics["pearson_correlation"] is None else f"{metrics['pearson_correlation']:.6f}",
                "failure_rate_gt_10bpm": "" if metrics["failure_rate_gt_10bpm"] is None else f"{metrics['failure_rate_gt_10bpm']:.6f}",
            }
        )

    summary_csv = run_dir / "summary.csv"
    with summary_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "method",
                "frames",
                "face_detected_ratio",
                "valid_hr_points",
                "mae",
                "rmse",
                "pearson_correlation",
                "failure_rate_gt_10bpm",
            ],
        )
        writer.writeheader()
        writer.writerows(summary_rows)

    metadata = {
        "run_id": run_id,
        "timestamp_utc": datetime.now(tz=timezone.utc).isoformat(),
        "video": str(args.video.resolve()),
        "scenario": args.scenario,
        "methods": requested_methods,
        "protocol": str(args.protocol.resolve()),
        "fs_used_hz": fs,
        "buffer_size_samples": buffer_size,
        "ground_truth": None if args.ground_truth is None else str(args.ground_truth.resolve()),
    }
    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote evaluation outputs to: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
