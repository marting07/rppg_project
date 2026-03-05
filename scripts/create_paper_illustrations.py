#!/usr/bin/env python3
"""Create illustrative paper figures combining video frame samples and BPM signals."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import cv2  # type: ignore
import matplotlib.pyplot as plt
import numpy as np


DEFAULT_METHODS = ("green", "chrom", "pos", "ssr")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, help="Run folder name inside outputs/data/")
    parser.add_argument("--video", required=True, type=Path, help="Video path used for the run.")
    parser.add_argument("--data-root", default=Path("outputs/data"), type=Path)
    parser.add_argument("--output-dir", default=Path("outputs/paper/figures"), type=Path)
    parser.add_argument("--samples", type=int, default=5, help="Number of time sample frames.")
    parser.add_argument("--methods", default="green,chrom,pos,ssr", help="Comma-separated method names.")
    return parser.parse_args()


def load_timeseries(csv_path: Path) -> dict[str, np.ndarray]:
    cols: dict[str, list[float]] = {
        "time_s": [],
        "estimated_bpm": [],
        "ground_truth_bpm": [],
        "error_bpm": [],
    }
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cols["time_s"].append(float(row["time_s"]))
            for k in ("estimated_bpm", "ground_truth_bpm", "error_bpm"):
                v = row[k].strip()
                cols[k].append(np.nan if v == "" else float(v))
    return {k: np.array(v, dtype=np.float64) for k, v in cols.items()}


def choose_sample_times(t: np.ndarray, n_samples: int) -> np.ndarray:
    if t.size == 0:
        return np.array([], dtype=np.float64)
    if t.size <= n_samples:
        return t
    idx = np.linspace(0, t.size - 1, n_samples, dtype=int)
    return t[idx]


def mask_gt_to_estimate_support(est: np.ndarray, gt: np.ndarray) -> np.ndarray:
    masked = gt.copy()
    masked[~np.isfinite(est)] = np.nan
    return masked


def overlap_sample_times(data: dict[str, np.ndarray], n_samples: int) -> np.ndarray:
    t = data["time_s"]
    est = data["estimated_bpm"]
    gt = data["ground_truth_bpm"]
    overlap = np.isfinite(est) & np.isfinite(gt)
    if np.any(overlap):
        return choose_sample_times(t[overlap], n_samples)
    if np.any(np.isfinite(est)):
        return choose_sample_times(t[np.isfinite(est)], n_samples)
    return choose_sample_times(t, n_samples)


def extract_frame_at_time(cap: cv2.VideoCapture, time_s: float) -> np.ndarray:
    cap.set(cv2.CAP_PROP_POS_MSEC, max(0.0, time_s) * 1000.0)
    ok, frame = cap.read()
    if not ok:
        return np.zeros((240, 320, 3), dtype=np.uint8)
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return frame


def make_frame_strip(frames: list[np.ndarray], times: np.ndarray) -> tuple[plt.Figure, list[plt.Axes]]:
    fig, axes = plt.subplots(1, len(frames), figsize=(3.2 * len(frames), 2.7))
    if len(frames) == 1:
        axes = [axes]  # type: ignore[list-item]
    for i, (ax, fr) in enumerate(zip(axes, frames)):
        ax.imshow(fr)
        ax.set_title(f"t={times[i]:.1f}s", fontsize=9)
        ax.axis("off")
    return fig, axes  # type: ignore[return-value]


def create_method_figure(
    method: str,
    data: dict[str, np.ndarray],
    sample_times: np.ndarray,
    frames: list[np.ndarray],
    output_path: Path,
) -> None:
    fig = plt.figure(figsize=(14, 6))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.3], hspace=0.25)
    ax_strip = fig.add_subplot(gs[0, 0])
    ax_sig = fig.add_subplot(gs[1, 0])

    strip = np.hstack([cv2.resize(fr, (260, 180)) for fr in frames]) if frames else np.zeros((180, 260, 3), dtype=np.uint8)
    ax_strip.imshow(strip)
    ax_strip.axis("off")
    label_text = " | ".join([f"{t:.1f}s" for t in sample_times]) if sample_times.size else "no samples"
    ax_strip.set_title(f"{method.upper()} frame samples: {label_text}", fontsize=10)

    t = data["time_s"]
    est = data["estimated_bpm"]
    gt = mask_gt_to_estimate_support(est, data["ground_truth_bpm"])
    ax_sig.plot(t, est, label=f"{method.upper()} BPM", linewidth=1.0, color="#1f77b4")
    if np.any(np.isfinite(gt)):
        ax_sig.plot(t, gt, label="Ground truth BPM", linewidth=0.9, color="#d62728", alpha=0.85)
    for ts in sample_times:
        ax_sig.axvline(ts, color="#777777", linestyle="--", linewidth=0.8, alpha=0.7)
    ax_sig.set_xlabel("Time (s)")
    ax_sig.set_ylabel("BPM")
    ax_sig.set_title(f"{method.upper()} pulse estimate over time")
    ax_sig.legend(loc="best")
    ax_sig.grid(alpha=0.2)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def create_comparison_figure(
    series: dict[str, dict[str, np.ndarray]],
    methods: tuple[str, ...],
    sample_times: np.ndarray,
    frames: list[np.ndarray],
    output_path: Path,
) -> None:
    fig = plt.figure(figsize=(14, 6))
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.3], hspace=0.25)
    ax_strip = fig.add_subplot(gs[0, 0])
    ax_sig = fig.add_subplot(gs[1, 0])
    strip = np.hstack([cv2.resize(fr, (260, 180)) for fr in frames]) if frames else np.zeros((180, 260, 3), dtype=np.uint8)
    ax_strip.imshow(strip)
    ax_strip.axis("off")
    ax_strip.set_title("Video frame samples used for method comparison", fontsize=10)

    palette = {
        "green": "#2ca02c",
        "chrom": "#ff7f0e",
        "pos": "#1f77b4",
        "ssr": "#8c564b",
    }
    gt_plotted = False
    for method in methods:
        d = series[method]
        color = palette.get(method, "#333333")
        ax_sig.plot(d["time_s"], d["estimated_bpm"], label=f"{method.upper()} BPM", linewidth=1.0, color=color)
        gt = mask_gt_to_estimate_support(d["estimated_bpm"], d["ground_truth_bpm"])
        if (not gt_plotted) and np.any(np.isfinite(gt)):
            ax_sig.plot(d["time_s"], gt, label="Ground truth BPM", linewidth=1.0, color="#d62728", alpha=0.85)
            gt_plotted = True
    for ts in sample_times:
        ax_sig.axvline(ts, color="#777777", linestyle="--", linewidth=0.8, alpha=0.7)
    ax_sig.set_xlabel("Time (s)")
    ax_sig.set_ylabel("BPM")
    ax_sig.set_title("Method BPM comparison on the same video")
    ax_sig.legend(loc="best")
    ax_sig.grid(alpha=0.2)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def create_snapshot_sequence(
    series: dict[str, dict[str, np.ndarray]],
    methods: tuple[str, ...],
    sample_times: np.ndarray,
    frames: list[np.ndarray],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, (ts, fr) in enumerate(zip(sample_times, frames)):
        fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(8.6, 3.6))
        ax0.imshow(fr)
        ax0.axis("off")
        ax0.set_title(f"Frame sample t={ts:.2f}s")
        rows = []
        for method in methods:
            d = series[method]
            idx = int(np.argmin(np.abs(d["time_s"] - ts)))
            est = d["estimated_bpm"][idx]
            gt = d["ground_truth_bpm"][idx]
            rows.append((method.upper(), est, gt))
        ax1.axis("off")
        lines = ["BPM snapshot values", ""]
        for m, est, gt in rows:
            est_txt = "--" if not np.isfinite(est) else f"{est:.2f}"
            gt_txt = "--" if not np.isfinite(gt) else f"{gt:.2f}"
            lines.append(f"{m:5s}  est={est_txt:>8s}  gt={gt_txt:>8s}")
        ax1.text(0.0, 0.95, "\n".join(lines), va="top", family="monospace", fontsize=10)
        fig.savefig(output_dir / f"sequence_sample_{i+1:02d}.png", dpi=220, bbox_inches="tight")
        plt.close(fig)


def main() -> int:
    args = parse_args()
    methods = tuple([m.strip() for m in args.methods.split(",") if m.strip()]) or DEFAULT_METHODS
    run_dir = args.data_root / args.run_id
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")
    if not args.video.exists():
        raise FileNotFoundError(f"Video not found: {args.video}")

    series: dict[str, dict[str, np.ndarray]] = {}
    for method in methods:
        csv_path = run_dir / f"{method}_timeseries.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing timeseries CSV: {csv_path}")
        series[method] = load_timeseries(csv_path)

    sample_times = overlap_sample_times(series[methods[0]], args.samples)

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open video: {args.video}")
    frames = [extract_frame_at_time(cap, float(t)) for t in sample_times]
    cap.release()

    out_base = args.output_dir / args.run_id
    for method in methods:
        create_method_figure(
            method=method,
            data=series[method],
            sample_times=sample_times,
            frames=frames,
            output_path=out_base / f"{method}_bpm_with_frames.png",
        )
    create_comparison_figure(
        series=series,
        methods=methods,
        sample_times=sample_times,
        frames=frames,
        output_path=out_base / "method_comparison_bpm_with_frames.png",
    )
    create_snapshot_sequence(
        series=series,
        methods=methods,
        sample_times=sample_times,
        frames=frames,
        output_dir=out_base / "sequence_samples",
    )
    print(f"Wrote paper illustrations to: {out_base}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
