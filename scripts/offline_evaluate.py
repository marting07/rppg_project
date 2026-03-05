#!/usr/bin/env python3
"""Offline evaluator for manual rPPG method comparison."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import cv2  # type: ignore
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rppg_methods import ChromMethod, GreenMethod, POSMethod, SSRMethod
from rppg_methods.base import RPPGMethod
from utils.roi import FaceDetector, extract_named_face_rois

METHOD_FACTORY: dict[str, Callable[[float, int], RPPGMethod]] = {
    "green": lambda fs, buf: GreenMethod(fs=fs, buffer_size=buf),
    "chrom": lambda fs, buf: ChromMethod(fs=fs, buffer_size=buf),
    "pos": lambda fs, buf: POSMethod(fs=fs, buffer_size=buf),
    "ssr": lambda fs, buf: SSRMethod(fs=fs, buffer_size=buf),
}


@dataclass
class GroundTruth:
    times_s: np.ndarray
    bpm: np.ndarray
    bvp: np.ndarray | None = None
    source: str = "bpm_row"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--protocol", default=Path("configs/experiment_protocol.json"), type=Path)
    parser.add_argument("--scenario", default="still")
    parser.add_argument("--methods", default="all", help="comma list or 'all'")
    parser.add_argument("--ground-truth", type=Path, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--output-dir", default=Path("outputs/data"), type=Path)
    parser.add_argument("--welch-window-seconds", type=float, default=None)
    parser.add_argument("--welch-overlap-ratio", type=float, default=None)
    parser.add_argument("--min-hr-confidence", type=float, default=None)
    parser.add_argument("--hr-smoothing-alpha", type=float, default=None)
    parser.add_argument("--max-hr-jump-bpm-per-s", type=float, default=None)
    parser.add_argument(
        "--ground-truth-mode",
        choices=["auto", "bpm_row", "bvp_derived"],
        default="bpm_row",
        help="How to build ground-truth BPM when UBFC text includes BVP row.",
    )
    parser.add_argument("--max-lag-seconds", type=float, default=2.0, help="Per-method lag search window for alignment.")
    parser.add_argument(
        "--roi-fusion-mode",
        choices=["single", "multi_snr"],
        default="multi_snr",
        help="single: forehead only. multi_snr: forehead+cheeks fused by confidence weights.",
    )
    parser.add_argument(
        "--roi-snr-exponent",
        type=float,
        default=1.0,
        help="Exponent applied to confidence weights in multi_snr mode.",
    )
    return parser.parse_args()


def load_protocol(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _parse_numeric_tokens(text: str) -> list[float]:
    matches = re.findall(r"[-+]?(?:\d*\.\d+|\d+)(?:[eE][-+]?\d+)?", text)
    return [float(m) for m in matches]


def _is_monotonic_non_decreasing(values: np.ndarray) -> bool:
    if values.size < 2:
        return False
    return bool(np.all(np.diff(values) >= -1e-9))


def _looks_like_bpm(values: np.ndarray) -> bool:
    if values.size < 2:
        return False
    finite = values[np.isfinite(values)]
    if finite.size < 2:
        return False
    q05, q95 = np.percentile(finite, [5, 95])
    return q05 >= 35.0 and q95 <= 220.0


def _select_bpm_time_bvp_rows(
    per_line_values: list[np.ndarray],
    fs: float,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    if not per_line_values:
        return None, None, None

    # UBFC ground_truth.txt is typically [BVP, BPM, timestamps] with equal lengths.
    if len(per_line_values) >= 3:
        row0, row1, row2 = per_line_values[0], per_line_values[1], per_line_values[2]
        if row0.size == row1.size == row2.size and _looks_like_bpm(row1) and _is_monotonic_non_decreasing(row2):
            return row1.astype(np.float64), row2.astype(np.float64), row0.astype(np.float64)

    bpm_candidates = [row for row in per_line_values if _looks_like_bpm(row)]
    if not bpm_candidates:
        return None, None, None
    bpm = max(bpm_candidates, key=lambda row: row.size).astype(np.float64)

    time_candidates = [
        row
        for row in per_line_values
        if row.size == bpm.size and _is_monotonic_non_decreasing(row) and float(row[0]) <= 1.0 and float(row[-1]) > 5.0
    ]
    if time_candidates:
        times = max(time_candidates, key=lambda row: row[-1]).astype(np.float64)
    else:
        times = np.arange(bpm.size, dtype=np.float64) / fs
    return bpm, times, None


def _derive_bpm_from_bvp(
    bvp: np.ndarray,
    times_s: np.ndarray,
    min_window_seconds: float = 4.0,
    analysis_window_seconds: float = 8.0,
) -> np.ndarray:
    n = bvp.size
    out = np.full(n, np.nan, dtype=np.float64)
    if n < 8 or times_s.size != n:
        return out
    for i in range(n):
        t_end = float(times_s[i])
        t_start = t_end - analysis_window_seconds
        start = int(np.searchsorted(times_s, t_start, side="left"))
        seg = bvp[start : i + 1]
        seg_t = times_s[start : i + 1]
        if seg.size < 8:
            continue
        duration = float(seg_t[-1] - seg_t[0])
        if duration < min_window_seconds:
            continue
        dt = np.diff(seg_t)
        dt = dt[np.isfinite(dt) & (dt > 1e-6)]
        if dt.size == 0:
            continue
        fs_seg = float(1.0 / np.median(dt))
        if fs_seg <= 1.0:
            continue
        x = seg.astype(np.float64) - float(np.mean(seg))
        x = x * np.hanning(x.size)
        spec = np.abs(np.fft.rfft(x))
        freqs = np.fft.rfftfreq(x.size, d=1.0 / fs_seg)
        band = (freqs >= 0.75) & (freqs <= 3.0)
        if not np.any(band):
            continue
        peak_idx = int(np.argmax(spec[band]))
        peak_f = float(freqs[band][peak_idx])
        out[i] = peak_f * 60.0
    return out


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
        return GroundTruth(times_s=np.array(times, dtype=np.float64), bpm=np.array(bpm, dtype=np.float64), source="csv_bpm")

    raw = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return None
    if fs is None or fs <= 0:
        fs = 30.0

    per_line_values = [np.array(_parse_numeric_tokens(line), dtype=np.float64) for line in lines]
    bpm, times, bvp = _select_bpm_time_bvp_rows(per_line_values, fs=fs)
    if bpm is None or times is None or bpm.size < 2 or times.size != bpm.size:
        return None

    return GroundTruth(times_s=times, bpm=bpm, bvp=bvp, source="ubfc_bpm_row")


def select_ground_truth_mode(gt: GroundTruth | None, mode: str) -> GroundTruth | None:
    if gt is None:
        return None
    if gt.bvp is None or gt.bvp.size != gt.times_s.size:
        return gt
    if mode == "bpm_row":
        return gt
    if mode in {"auto", "bvp_derived"}:
        derived = _derive_bpm_from_bvp(gt.bvp, gt.times_s)
        return GroundTruth(times_s=gt.times_s.copy(), bpm=derived, bvp=gt.bvp.copy(), source="ubfc_bvp_derived")
    return gt


def deterministic_run_id(video: Path, scenario: str, methods: list[str], protocol_path: Path) -> str:
    payload = f"{video.resolve()}|{scenario}|{','.join(methods)}|{protocol_path.resolve()}"
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]
    return f"run_{digest}"


def interpolate_ground_truth(gt: GroundTruth | None, t_s: float) -> float | None:
    if gt is None:
        return None
    finite = np.isfinite(gt.bpm)
    if not np.any(finite):
        return None
    t_valid = gt.times_s[finite]
    y_valid = gt.bpm[finite]
    if t_valid.size == 1:
        return float(y_valid[0]) if abs(t_s - t_valid[0]) < 1e-6 else None
    if t_s < t_valid[0] or t_s > t_valid[-1]:
        return None
    return float(np.interp(t_s, t_valid, y_valid))


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


def _shift_series(values: np.ndarray, lag_samples: int) -> np.ndarray:
    n = values.size
    out = np.full(n, np.nan, dtype=np.float64)
    for i in range(n):
        j = i - lag_samples
        if 0 <= j < n:
            out[i] = values[j]
    return out


def optimize_lag_samples(est: np.ndarray, gt: np.ndarray, max_lag_samples: int) -> int:
    if est.size < 8 or gt.size != est.size or max_lag_samples <= 0:
        return 0
    best_lag = 0
    best_corr = -2.0
    for lag in range(-max_lag_samples, max_lag_samples + 1):
        gt_shifted = _shift_series(gt, lag)
        mask = np.isfinite(est) & np.isfinite(gt_shifted)
        if int(np.sum(mask)) < 8:
            continue
        e = est[mask]
        g = gt_shifted[mask]
        if np.std(e) < 1e-8 or np.std(g) < 1e-8:
            continue
        corr = float(np.corrcoef(e, g)[0, 1])
        if np.isfinite(corr) and corr > best_corr:
            best_corr = corr
            best_lag = lag
    return int(best_lag)


def apply_lag_alignment(rows: list[dict[str, str]], fs: float, max_lag_seconds: float) -> float:
    if not rows or fs <= 0:
        return 0.0
    est = np.array([np.nan if not r["estimated_bpm"] else float(r["estimated_bpm"]) for r in rows], dtype=np.float64)
    gt = np.array([np.nan if not r["ground_truth_bpm"] else float(r["ground_truth_bpm"]) for r in rows], dtype=np.float64)
    lag_samples = optimize_lag_samples(est, gt, max_lag_samples=int(round(max_lag_seconds * fs)))
    gt_shifted = _shift_series(gt, lag_samples)
    lag_s = float(lag_samples / fs)
    for i, row in enumerate(rows):
        g = gt_shifted[i]
        if np.isfinite(g):
            row["ground_truth_bpm"] = f"{float(g):.6f}"
            est_v = row["estimated_bpm"]
            row["error_bpm"] = f"{(float(est_v) - float(g)):.6f}" if est_v else ""
            gt_t = float(row["ground_truth_time_s"]) + lag_s
            row["ground_truth_time_s"] = f"{max(0.0, gt_t):.6f}"
        else:
            row["ground_truth_bpm"] = ""
            row["error_bpm"] = ""
    return lag_s


def compute_roi_quality(
    roi: np.ndarray,
    prev_gray_small: np.ndarray | None,
) -> tuple[bool, float, float, float, np.ndarray]:
    if roi.size == 0:
        return False, 0.0, 1.0, 1.0, np.zeros((24, 24), dtype=np.uint8)

    roi_u8 = roi.astype(np.uint8)
    total_px = roi_u8.shape[0] * roi_u8.shape[1]
    if total_px < 200:
        gray_small = cv2.resize(cv2.cvtColor(roi_u8, cv2.COLOR_BGR2GRAY), (24, 24), interpolation=cv2.INTER_AREA)
        return False, 0.0, 1.0, 1.0, gray_small

    clipped = np.any((roi_u8 <= 5) | (roi_u8 >= 250), axis=2)
    saturation_ratio = float(np.mean(clipped))

    ycrcb = cv2.cvtColor(roi_u8, cv2.COLOR_BGR2YCrCb)
    cr = ycrcb[:, :, 1]
    cb = ycrcb[:, :, 2]
    skin_mask = (cr >= 120) & (cr <= 180) & (cb >= 80) & (cb <= 140)
    skin_ratio = float(np.mean(skin_mask))

    gray_small = cv2.resize(cv2.cvtColor(roi_u8, cv2.COLOR_BGR2GRAY), (24, 24), interpolation=cv2.INTER_AREA)
    if prev_gray_small is None or prev_gray_small.shape != gray_small.shape:
        motion_score = 0.0
    else:
        motion_score = float(np.mean(np.abs(gray_small.astype(np.float64) - prev_gray_small.astype(np.float64))) / 255.0)

    is_good = (skin_ratio >= 0.25) and (saturation_ratio <= 0.12) and (motion_score <= 0.10)
    return is_good, skin_ratio, saturation_ratio, motion_score, gray_small


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

    roi_names = ["forehead"] if args.roi_fusion_mode == "single" else ["forehead", "left_cheek", "right_cheek"]
    methods: dict[str, dict[str, RPPGMethod]] = {
        name: {roi_name: METHOD_FACTORY[name](fs, buffer_size) for roi_name in roi_names} for name in requested_methods
    }
    for per_roi_methods in methods.values():
        for method in per_roi_methods.values():
            if args.welch_window_seconds is not None and hasattr(method, "welch_window_seconds"):
                method.welch_window_seconds = float(args.welch_window_seconds)  # type: ignore[attr-defined]
            if args.welch_overlap_ratio is not None and hasattr(method, "welch_overlap_ratio"):
                method.welch_overlap_ratio = float(np.clip(args.welch_overlap_ratio, 0.0, 0.95))  # type: ignore[attr-defined]
            if args.min_hr_confidence is not None and hasattr(method, "min_hr_confidence"):
                method.min_hr_confidence = float(args.min_hr_confidence)  # type: ignore[attr-defined]
            if args.hr_smoothing_alpha is not None and hasattr(method, "hr_smoothing_alpha"):
                method.hr_smoothing_alpha = float(np.clip(args.hr_smoothing_alpha, 0.0, 1.0))  # type: ignore[attr-defined]
            if args.max_hr_jump_bpm_per_s is not None and hasattr(method, "max_hr_jump_bpm_per_s"):
                method.max_hr_jump_bpm_per_s = float(args.max_hr_jump_bpm_per_s)  # type: ignore[attr-defined]
    face_detector = FaceDetector()
    gt_loaded = load_ground_truth(args.ground_truth, fs=fs)
    gt = select_ground_truth_mode(gt_loaded, mode=args.ground_truth_mode)

    records: dict[str, list[dict[str, str]]] = {name: [] for name in requested_methods}
    frame_idx = 0
    detected_face_count = 0
    roi_quality_pass_count = 0
    prev_gray_small: dict[str, np.ndarray | None] = {name: None for name in roi_names}

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        time_s = frame_idx / fs
        faces = face_detector.detect_faces(frame)
        face_detected = False
        frame_skin_ratios: list[float] = []
        frame_saturation_ratios: list[float] = []
        frame_motion_scores: list[float] = []
        valid_rois: dict[str, np.ndarray] = {}
        if faces:
            face_detected = True
            detected_face_count += 1
            face = max(faces, key=lambda b: b[2] * b[3])
            named_rois = extract_named_face_rois(frame, face, include_cheeks=(args.roi_fusion_mode != "single"))
            for roi_name in roi_names:
                roi, _ = named_rois.get(roi_name, (None, None))  # type: ignore[assignment]
                if roi is None or roi.size == 0:
                    continue
                roi_good, skin_ratio, saturation_ratio, motion_score, gray_small = compute_roi_quality(roi, prev_gray_small[roi_name])
                prev_gray_small[roi_name] = gray_small
                frame_skin_ratios.append(float(skin_ratio))
                frame_saturation_ratios.append(float(saturation_ratio))
                frame_motion_scores.append(float(motion_score))
                if roi_good:
                    valid_rois[roi_name] = roi

        roi_good = len(valid_rois) > 0
        if roi_good:
            roi_quality_pass_count += 1
        skin_ratio = float(np.mean(frame_skin_ratios)) if frame_skin_ratios else np.nan
        saturation_ratio = float(np.mean(frame_saturation_ratios)) if frame_saturation_ratios else np.nan
        motion_score = float(np.mean(frame_motion_scores)) if frame_motion_scores else np.nan

        for method_name, method_rois in methods.items():
            region_candidates: list[tuple[str, float, float, float | None, float | None, float | None]] = []
            latency_ref: RPPGMethod | None = None
            for roi_name in roi_names:
                method = method_rois[roi_name]
                if latency_ref is None:
                    latency_ref = method
                previous_len = len(method.signal_buffer)
                roi = valid_rois.get(roi_name)
                if roi is not None and roi.size > 0:
                    method.update(roi)
                est_bpm = method.get_hr()
                confidence = method.get_confidence() if hasattr(method, "get_confidence") else None
                raw_value = method.signal_buffer[-1] if len(method.signal_buffer) > previous_len else None
                filtered_signal = method.get_ppg_signal()
                filtered_value = float(filtered_signal[-1]) if filtered_signal.size else None
                if est_bpm is not None:
                    conf = float(confidence) if confidence is not None and np.isfinite(confidence) else 1.0
                    region_candidates.append((roi_name, float(est_bpm), conf, raw_value, filtered_value, confidence))

            best_raw: float | None = None
            best_filtered: float | None = None
            best_conf: float | None = None
            fused_bpm: float | None = None
            if region_candidates:
                exp = float(max(0.0, args.roi_snr_exponent))
                weights = np.array([max(1e-6, c[2]) ** exp for c in region_candidates], dtype=np.float64)
                bpm_values = np.array([c[1] for c in region_candidates], dtype=np.float64)
                fused_bpm = float(np.sum(weights * bpm_values) / np.sum(weights))
                best_idx = int(np.argmax(weights))
                best_raw = None if region_candidates[best_idx][3] is None else float(region_candidates[best_idx][3])  # type: ignore[arg-type]
                best_filtered = (
                    None if region_candidates[best_idx][4] is None else float(region_candidates[best_idx][4])  # type: ignore[arg-type]
                )
                best_conf = float(region_candidates[best_idx][5]) if region_candidates[best_idx][5] is not None else None

            gt_delay_s = float(getattr(latency_ref, "latency_seconds", 0.0)) if latency_ref is not None else 0.0
            gt_time_s = max(0.0, time_s - gt_delay_s)
            gt_bpm = interpolate_ground_truth(gt, gt_time_s)
            error = (fused_bpm - gt_bpm) if (fused_bpm is not None and gt_bpm is not None) else None

            records[method_name].append(
                {
                    "frame_idx": str(frame_idx),
                    "time_s": f"{time_s:.6f}",
                    "ground_truth_time_s": f"{gt_time_s:.6f}",
                    "face_detected": "1" if face_detected else "0",
                    "roi_quality_pass": "1" if roi_good else "0",
                    "roi_skin_ratio": "" if not np.isfinite(skin_ratio) else f"{skin_ratio:.6f}",
                    "roi_saturation_ratio": "" if not np.isfinite(saturation_ratio) else f"{saturation_ratio:.6f}",
                    "roi_motion_score": "" if not np.isfinite(motion_score) else f"{motion_score:.6f}",
                    "raw_signal": "" if best_raw is None else f"{best_raw:.8f}",
                    "filtered_signal": "" if best_filtered is None else f"{best_filtered:.8f}",
                    "estimated_bpm": "" if fused_bpm is None else f"{fused_bpm:.6f}",
                    "selection_confidence": "" if best_conf is None else f"{float(best_conf):.6f}",
                    "ground_truth_bpm": "" if gt_bpm is None else f"{gt_bpm:.6f}",
                    "error_bpm": "" if error is None else f"{error:.6f}",
                }
            )
        frame_idx += 1

    cap.release()

    summary_rows: list[dict[str, str]] = []
    lag_by_method_s: dict[str, float] = {}
    for method_name, rows in records.items():
        lag_s = apply_lag_alignment(rows, fs=fs, max_lag_seconds=float(max(0.0, args.max_lag_seconds)))
        lag_by_method_s[method_name] = lag_s
        out_csv = run_dir / f"{method_name}_timeseries.csv"
        with out_csv.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "frame_idx",
                    "time_s",
                    "ground_truth_time_s",
                    "face_detected",
                    "roi_quality_pass",
                    "roi_skin_ratio",
                    "roi_saturation_ratio",
                    "roi_motion_score",
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
                "roi_quality_accept_ratio": f"{(roi_quality_pass_count / frame_idx) if frame_idx else 0.0:.6f}",
                "valid_hr_points": str(sum(1 for r in rows if r["estimated_bpm"])),
                "mae": "" if metrics["mae"] is None else f"{metrics['mae']:.6f}",
                "rmse": "" if metrics["rmse"] is None else f"{metrics['rmse']:.6f}",
                "pearson_correlation": "" if metrics["pearson_correlation"] is None else f"{metrics['pearson_correlation']:.6f}",
                "failure_rate_gt_10bpm": "" if metrics["failure_rate_gt_10bpm"] is None else f"{metrics['failure_rate_gt_10bpm']:.6f}",
                "optimized_lag_seconds": f"{lag_s:.6f}",
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
                "roi_quality_accept_ratio",
                "valid_hr_points",
                "mae",
                "rmse",
                "pearson_correlation",
                "failure_rate_gt_10bpm",
                "optimized_lag_seconds",
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
        "welch_window_seconds": args.welch_window_seconds,
        "welch_overlap_ratio": args.welch_overlap_ratio,
        "min_hr_confidence": args.min_hr_confidence,
        "hr_smoothing_alpha": args.hr_smoothing_alpha,
        "max_hr_jump_bpm_per_s": args.max_hr_jump_bpm_per_s,
        "roi_quality_acceptance_ratio": (roi_quality_pass_count / frame_idx) if frame_idx else 0.0,
        "ground_truth": None if args.ground_truth is None else str(args.ground_truth.resolve()),
        "ground_truth_mode": args.ground_truth_mode,
        "ground_truth_source": None if gt is None else gt.source,
        "lag_by_method_seconds": lag_by_method_s,
        "max_lag_seconds": args.max_lag_seconds,
        "roi_fusion_mode": args.roi_fusion_mode,
        "roi_snr_exponent": args.roi_snr_exponent,
        "roi_names": roi_names,
    }
    metadata_path = run_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(f"Wrote evaluation outputs to: {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
