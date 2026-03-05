# Public Corpus Plan

This project uses a single public corpus for the paper experiments.

## Selected Corpus

- **UBFC-rPPG (Dataset 2)** is the official corpus for this study.

Rationale:

- widely used in rPPG research,
- contains video plus physiological reference signals,
- supports fully reproducible experiments in this repository.

## Local Folder Convention

Expected UBFC root:

`data/public/UBFC-rPPG/DATASET_2`

Expected per-subject files:

- `subjectXX/vid.avi`
- `subjectXX/ground_truth.*`

## Dataset Download Script

Download and place UBFC data with:

```bash
make corpus-download UBFC_URL="https://<direct-download-link>"
```

UBFC Google Drive folder link is supported directly:

```bash
make corpus-download UBFC_URL="https://drive.google.com/drive/folders/1o0XU4gTIo46YfwaWjIgbtCncc-oF44Xk?usp=sharing"
```

Optional JSON format:

```json
{
  "ubfc_rppg_v1": "https://.../ubfc.zip"
}
```

Notes:

- Files are normalized under `data/public/...` so manifest generation works directly.
- Google Drive URLs are handled via `gdown` (installed through `requirements.txt`).

## Manifest Generation

Generate a machine-readable run manifest:

```bash
make corpus-manifest CORPUS=ubfc_rppg_v1 CORPUS_ROOT=data/public/UBFC-rPPG/DATASET_2
```

This writes:

- `outputs/data/corpus_manifests/ubfc_rppg_v1_manifest.csv`

## Running Evaluation from Manifest Rows

Use each row's `video_path` and `ground_truth_path` with evaluator:

```bash
make evaluate VIDEO=/abs/path/to/vid.avi GT=/abs/path/to/ground_truth.txt SCENARIO=still METHODS=all
```

`scripts/offline_evaluate.py` supports:

- CSV ground truth (`time_s,bpm`)
- UBFC text-style numeric ground-truth files

## Batch Evaluation and Paper Table

Run all manifest rows and produce aggregate paper tables:

```bash
make corpus-batch MANIFEST=outputs/data/corpus_manifests/ubfc_rppg_v1_manifest.csv METHODS=all SCENARIO=still
```

Outputs:

- `outputs/data/aggregate/manifest_aggregate_summary.csv`
- `outputs/data/aggregate/manifest_aggregate_summary_method_means.csv`
- `outputs/data/aggregate/manifest_aggregate_summary_runs.csv`

## LaTeX Table Export

Generate a paper-ready LaTeX table:

```bash
make corpus-latex
```

Render to PDF/PNG:

```bash
make corpus-render RENDER_OUT=outputs/data/aggregate/manifest_aggregate_summary_method_means.pdf
make corpus-render RENDER_OUT=outputs/data/aggregate/manifest_aggregate_summary_method_means.png
```
