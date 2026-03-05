#!/usr/bin/env python3
"""Generate per-subject diagnostics: BPM traces, error histograms, lag correlation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True, type=Path)
    p.add_argument("--output-dir", default=None, type=Path)
    p.add_argument("--max-lag-seconds", type=float, default=8.0)
    return p.parse_args()


def load_timeseries(path: Path) -> dict[str, np.ndarray]:
    cols: dict[str, list[float]] = {"time_s": [], "estimated_bpm": [], "ground_truth_bpm": [], "error_bpm": []}
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            cols["time_s"].append(float(row["time_s"]))
            for k in ("estimated_bpm", "ground_truth_bpm", "error_bpm"):
                v = row[k].strip()
                cols[k].append(np.nan if v == "" else float(v))
    return {k: np.array(v, dtype=np.float64) for k, v in cols.items()}


def valid_pair(est: np.ndarray, gt: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    m = np.isfinite(est) & np.isfinite(gt)
    return est[m], gt[m]


def lag_corr(est: np.ndarray, gt: np.ndarray, fs: float, max_lag_s: float) -> tuple[np.ndarray, np.ndarray]:
    max_lag = int(round(max_lag_s * fs))
    lags = np.arange(-max_lag, max_lag + 1, dtype=int)
    corr = np.full(lags.shape, np.nan, dtype=np.float64)
    for i, lag in enumerate(lags):
        if lag < 0:
            a = est[:lag]
            b = gt[-lag:]
        elif lag > 0:
            a = est[lag:]
            b = gt[:-lag]
        else:
            a = est
            b = gt
        va, vb = valid_pair(a, b)
        if va.size >= 5 and np.std(va) > 1e-8 and np.std(vb) > 1e-8:
            corr[i] = float(np.corrcoef(va, vb)[0, 1])
    return lags / fs, corr


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir
    if not run_dir.exists():
        raise FileNotFoundError(run_dir)
    out_dir = args.output_dir or (Path("outputs/plots") / run_dir.name / "diagnostics")
    out_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(run_dir.glob("*_timeseries.csv"))
    if not files:
        raise FileNotFoundError(f"No *_timeseries.csv in {run_dir}")

    fig1, ax1 = plt.subplots(figsize=(11, 4.5))
    fig2, ax2 = plt.subplots(figsize=(11, 4.5))
    fig3, ax3 = plt.subplots(figsize=(11, 4.5))

    for f in files:
        method = f.name.replace("_timeseries.csv", "")
        d = load_timeseries(f)
        t = d["time_s"]
        est = d["estimated_bpm"]
        gt = d["ground_truth_bpm"]
        err = d["error_bpm"]

        ax1.plot(t, est, linewidth=1.0, label=f"{method.upper()} estimate")
        if method == files[0].name.replace("_timeseries.csv", ""):
            ax1.plot(t, gt, linewidth=1.2, color="black", alpha=0.8, label="Ground truth")

        v = err[np.isfinite(err)]
        if v.size:
            ax2.hist(v, bins=35, alpha=0.35, density=True, label=method.upper())

        dt = np.median(np.diff(t)) if t.size >= 2 else (1.0 / 30.0)
        fs = 1.0 / max(dt, 1e-6)
        lags_s, c = lag_corr(est, gt, fs=fs, max_lag_s=args.max_lag_seconds)
        ax3.plot(lags_s, c, linewidth=1.0, label=method.upper())

    ax1.set_title("Estimated BPM vs Ground Truth")
    ax1.set_xlabel("Time (s)")
    ax1.set_ylabel("BPM")
    ax1.legend(loc="best")
    fig1.tight_layout()
    fig1.savefig(out_dir / "diagnostic_bpm_vs_gt.png", dpi=220)
    plt.close(fig1)

    ax2.set_title("Error Distribution (Estimated - Ground Truth)")
    ax2.set_xlabel("Error (BPM)")
    ax2.set_ylabel("Density")
    ax2.legend(loc="best")
    fig2.tight_layout()
    fig2.savefig(out_dir / "diagnostic_error_hist.png", dpi=220)
    plt.close(fig2)

    ax3.axvline(0.0, color="#666666", linestyle="--", linewidth=0.8)
    ax3.set_title("Lag Correlation (Estimate vs Ground Truth)")
    ax3.set_xlabel("Lag (s)")
    ax3.set_ylabel("Pearson correlation")
    ax3.set_ylim(-1.0, 1.0)
    ax3.legend(loc="best")
    fig3.tight_layout()
    fig3.savefig(out_dir / "diagnostic_lag_correlation.png", dpi=220)
    plt.close(fig3)

    print(f"Wrote diagnostics to: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
