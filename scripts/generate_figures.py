#!/usr/bin/env python3
"""Generate paper-oriented figures from offline evaluation outputs."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path, help="Path like outputs/data/<run_id>")
    parser.add_argument("--plot-dir", default=None, type=Path, help="Default: outputs/plots/<run_id>")
    return parser.parse_args()


def load_timeseries(path: Path) -> dict[str, np.ndarray]:
    columns: dict[str, list[float]] = {
        "time_s": [],
        "raw_signal": [],
        "filtered_signal": [],
        "estimated_bpm": [],
        "selection_confidence": [],
        "ground_truth_bpm": [],
        "error_bpm": [],
    }
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            columns["time_s"].append(float(row["time_s"]))
            for key in ("raw_signal", "filtered_signal", "estimated_bpm", "selection_confidence", "ground_truth_bpm", "error_bpm"):
                value = row[key].strip()
                columns[key].append(np.nan if value == "" else float(value))
    return {k: np.array(v, dtype=np.float64) for k, v in columns.items()}


def mask_gt_to_estimate_support(est: np.ndarray, gt: np.ndarray) -> np.ndarray:
    masked = gt.copy()
    masked[~np.isfinite(est)] = np.nan
    return masked


def save_method_overview(method: str, data: dict[str, np.ndarray], out_path: Path) -> None:
    t = data["time_s"]
    raw = data["raw_signal"]
    filtered = data["filtered_signal"]
    est = data["estimated_bpm"]
    conf = data["selection_confidence"]
    gt = mask_gt_to_estimate_support(est, data["ground_truth_bpm"])

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle(f"{method.upper()} Method Overview", fontsize=14)

    axes[0, 0].plot(t, raw, linewidth=0.9)
    axes[0, 0].set_title("Raw Signal")
    axes[0, 0].set_xlabel("Time (s)")
    axes[0, 0].set_ylabel("Amplitude")

    axes[0, 1].plot(t, filtered, linewidth=0.9, color="#d55e00")
    axes[0, 1].set_title("Filtered Signal")
    axes[0, 1].set_xlabel("Time (s)")
    axes[0, 1].set_ylabel("Amplitude")

    valid_filtered = filtered[np.isfinite(filtered)]
    if valid_filtered.size > 0:
        f = np.fft.rfftfreq(valid_filtered.size, d=np.mean(np.diff(t)))
        mag = np.abs(np.fft.rfft(valid_filtered))
        band = (f >= 0.75) & (f <= 4.0)
        axes[1, 0].plot(f, mag, linewidth=0.9, color="#009e73")
        if np.any(band):
            peak_f = f[band][np.argmax(mag[band])]
            axes[1, 0].axvline(peak_f, color="#cc79a7", linestyle="--", linewidth=1.0)
        axes[1, 0].set_xlim(0.5, 4.5)
    axes[1, 0].set_title("Power Spectrum")
    axes[1, 0].set_xlabel("Frequency (Hz)")
    axes[1, 0].set_ylabel("Magnitude")

    axes[1, 1].plot(t, est, label="Estimated BPM", linewidth=0.9)
    if np.any(np.isfinite(gt)):
        axes[1, 1].plot(t, gt, label="Ground Truth BPM", linewidth=0.9)
    axes[1, 1].set_title("BPM Over Time")
    axes[1, 1].set_xlabel("Time (s)")
    axes[1, 1].set_ylabel("BPM")
    if np.any(np.isfinite(conf)):
        ax2 = axes[1, 1].twinx()
        ax2.plot(t, conf, color="#444444", linewidth=0.8, alpha=0.6, label="Confidence")
        ax2.set_ylabel("Confidence")
        ax2.set_ylim(0.0, 1.0)
    axes[1, 1].legend(loc="best")

    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def save_error_boxplot(errors_by_method: dict[str, np.ndarray], out_path: Path) -> None:
    labels = []
    data = []
    for method, values in errors_by_method.items():
        abs_values = np.abs(values[np.isfinite(values)])
        if abs_values.size:
            labels.append(method.upper())
            data.append(abs_values)
    if not data:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot(data, tick_labels=labels)
    ax.set_title("Absolute Error Distribution")
    ax.set_ylabel("|Error| (BPM)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def save_bland_altman(estimated_by_method: dict[str, np.ndarray], gt_by_method: dict[str, np.ndarray], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    colors = ["#0072b2", "#d55e00", "#009e73", "#cc79a7"]
    color_idx = 0
    plotted = False
    for method, est in estimated_by_method.items():
        gt = gt_by_method[method]
        valid = np.isfinite(est) & np.isfinite(gt)
        if np.sum(valid) < 2:
            continue
        mean_v = (est[valid] + gt[valid]) / 2.0
        diff = est[valid] - gt[valid]
        bias = np.mean(diff)
        sd = np.std(diff)
        color = colors[color_idx % len(colors)]
        color_idx += 1
        ax.scatter(mean_v, diff, s=10, alpha=0.5, label=f"{method.upper()} points", color=color)
        ax.axhline(bias, color=color, linestyle="-", linewidth=1.0)
        ax.axhline(bias + 1.96 * sd, color=color, linestyle="--", linewidth=0.8)
        ax.axhline(bias - 1.96 * sd, color=color, linestyle="--", linewidth=0.8)
        plotted = True
    if not plotted:
        plt.close(fig)
        return
    ax.set_title("Bland-Altman (Estimated vs Ground Truth)")
    ax.set_xlabel("Mean BPM")
    ax.set_ylabel("Difference BPM (Estimated - Ground Truth)")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def save_failure_rate(errors_by_method: dict[str, np.ndarray], out_path: Path, threshold: float = 10.0) -> None:
    labels: list[str] = []
    rates: list[float] = []
    for method, errors in errors_by_method.items():
        valid = errors[np.isfinite(errors)]
        if valid.size == 0:
            continue
        labels.append(method.upper())
        rates.append(float(np.mean(np.abs(valid) > threshold)))
    if not rates:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.bar(labels, rates, color=["#0072b2", "#d55e00", "#009e73"][: len(labels)])
    ax.set_title(f"Failure Rate (|Error| > {threshold:.0f} BPM)")
    ax.set_ylabel("Rate")
    ax.set_ylim(0.0, 1.0)
    fig.tight_layout()
    fig.savefig(out_path, dpi=220)
    plt.close(fig)


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir
    if not run_dir.exists():
        raise FileNotFoundError(f"Run directory not found: {run_dir}")

    run_id = run_dir.name
    plot_dir = args.plot_dir or Path("outputs/plots") / run_id
    plot_dir.mkdir(parents=True, exist_ok=True)

    timeseries_files = sorted(run_dir.glob("*_timeseries.csv"))
    if not timeseries_files:
        raise FileNotFoundError(f"No *_timeseries.csv found in {run_dir}")

    errors_by_method: dict[str, np.ndarray] = {}
    estimated_by_method: dict[str, np.ndarray] = {}
    gt_by_method: dict[str, np.ndarray] = {}

    for csv_path in timeseries_files:
        method = csv_path.name.replace("_timeseries.csv", "")
        data = load_timeseries(csv_path)
        save_method_overview(method, data, plot_dir / f"{method}_overview.png")
        errors_by_method[method] = data["error_bpm"]
        estimated_by_method[method] = data["estimated_bpm"]
        gt_by_method[method] = data["ground_truth_bpm"]

    save_error_boxplot(errors_by_method, plot_dir / "comparison_error_boxplot.png")
    save_bland_altman(estimated_by_method, gt_by_method, plot_dir / "comparison_bland_altman.png")
    save_failure_rate(errors_by_method, plot_dir / "comparison_failure_rate.png")

    print(f"Wrote figures to: {plot_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
