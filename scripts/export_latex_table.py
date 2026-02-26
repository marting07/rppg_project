#!/usr/bin/env python3
"""Export aggregate metrics CSV into a paper-ready LaTeX table."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        default=Path("outputs/data/aggregate/manifest_aggregate_summary_method_means.csv"),
        type=Path,
    )
    parser.add_argument(
        "--output",
        default=Path("outputs/data/aggregate/manifest_aggregate_summary_method_means.tex"),
        type=Path,
    )
    parser.add_argument("--caption", default="Comparison of rPPG methods on UBFC-rPPG.")
    parser.add_argument("--label", default="tab:ubfc_method_comparison")
    return parser.parse_args()


def to_float(value: str) -> float | None:
    s = value.strip()
    if not s:
        return None
    return float(s)


def fmt(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:.3f}"


def highlight_best(rows: list[dict], key: str, lower_is_better: bool) -> None:
    values = [(idx, row[key]) for idx, row in enumerate(rows) if row[key] is not None]
    if not values:
        return
    best_idx, _ = min(values, key=lambda x: x[1]) if lower_is_better else max(values, key=lambda x: x[1])
    rows[best_idx][f"{key}_best"] = True


def main() -> int:
    args = parse_args()
    if not args.input.exists():
        raise FileNotFoundError(f"Input CSV not found: {args.input}")

    rows: list[dict] = []
    with args.input.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            rows.append(
                {
                    "method": row.get("method", "").upper(),
                    "subjects": row.get("subjects", ""),
                    "mae": to_float(row.get("mean_mae", "")),
                    "rmse": to_float(row.get("mean_rmse", "")),
                    "corr": to_float(row.get("mean_pearson_correlation", "")),
                    "fail": to_float(row.get("mean_failure_rate_gt_10bpm", "")),
                    "mae_best": False,
                    "rmse_best": False,
                    "corr_best": False,
                    "fail_best": False,
                }
            )

    if not rows:
        raise RuntimeError(f"No data rows in: {args.input}")

    highlight_best(rows, "mae", lower_is_better=True)
    highlight_best(rows, "rmse", lower_is_better=True)
    highlight_best(rows, "corr", lower_is_better=False)
    highlight_best(rows, "fail", lower_is_better=True)

    def cell(row: dict, key: str) -> str:
        value = fmt(row[key])
        return f"\\textbf{{{value}}}" if row.get(f"{key}_best", False) else value

    lines: list[str] = []
    lines.append("\\begin{table}[t]")
    lines.append("\\centering")
    lines.append("\\small")
    lines.append("\\begin{tabular}{lccccc}")
    lines.append("\\hline")
    lines.append("Method & Subjects & MAE $\\downarrow$ & RMSE $\\downarrow$ & Corr $\\uparrow$ & FailRate $\\downarrow$\\\\")
    lines.append("\\hline")
    for row in rows:
        lines.append(
            f"{row['method']} & {row['subjects']} & {cell(row, 'mae')} & {cell(row, 'rmse')} & {cell(row, 'corr')} & {cell(row, 'fail')}\\\\"
        )
    lines.append("\\hline")
    lines.append("\\end{tabular}")
    lines.append(f"\\caption{{{args.caption}}}")
    lines.append(f"\\label{{{args.label}}}")
    lines.append("\\end{table}")
    lines.append("")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote LaTeX table to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
