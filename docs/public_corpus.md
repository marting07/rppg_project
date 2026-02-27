# Public Corpus Plan

This project now starts with a public corpus baseline so results are publishable even without large in-house recordings.

## Selected Baseline Corpus

- **UBFC-rPPG (Dataset 2)** is the first integrated corpus.
- Why first:
  - widely used in rPPG papers,
  - video + physiological signal availability,
  - practical setup for immediate reproducible experiments.

## Planned Expansion

- **COHFACE**: cross-dataset generalization check (**pending access approval**).
- **PURE**: request was denied (**excluded from current paper scope**).

These are tracked in `configs/public_corpus.json`.

## Local Folder Convention

Expected UBFC root:

`data/public/UBFC-rPPG/DATASET_2`

Expected per-subject files:

- `subjectXX/vid.avi`
- `subjectXX/ground_truth.*`

## Dataset Download Script

You can download and place corpora with:

```bash
make corpus-download CORPUS=ubfc_rppg_v1 UBFC_URL="https://<direct-download-link>"
```

UBFC Google Drive folder link is supported directly:

```bash
make corpus-download CORPUS=ubfc_rppg_v1 UBFC_URL="https://drive.google.com/drive/folders/1o0XU4gTIo46YfwaWjIgbtCncc-oF44Xk?usp=sharing"
```

Multiple corpora:

```bash
make corpus-download CORPUS=all URLS_JSON=/absolute/path/dataset_urls.json
```

`dataset_urls.json` format:

```json
{
  "ubfc_rppg_v1": "https://.../ubfc.zip",
  "cohface": "https://.../cohface.zip",
  "pure": "https://.../pure.zip"
}
```

Notes:

- Some datasets require account approval; if no direct URL is passed, the script prints the official access page.
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

Use each row's `video_path` and `ground_truth_path` with existing evaluator:

```bash
make evaluate VIDEO=/abs/path/to/vid.avi GT=/abs/path/to/ground_truth.txt SCENARIO=still METHODS=all
```

`scripts/offline_evaluate.py` now supports:

- CSV ground truth (`time_s,bpm`)
- UBFC text-style numeric ground-truth files

## Batch Evaluation and Paper Table

Run all manifest rows in one command and produce aggregate paper tables:

```bash
make corpus-batch MANIFEST=outputs/data/corpus_manifests/ubfc_rppg_v1_manifest.csv METHODS=all SCENARIO=still
```

Outputs:

- `outputs/data/aggregate/manifest_aggregate_summary.csv`
  - one row per subject per method
- `outputs/data/aggregate/manifest_aggregate_summary_method_means.csv`
  - method-level mean metrics table for paper insertion
- `outputs/data/aggregate/manifest_aggregate_summary_runs.csv`
  - run success/failure diagnostics

## LaTeX Table Export

Generate a paper-ready LaTeX table from aggregate method means:

```bash
make corpus-latex
```

Default input/output:

- input: `outputs/data/aggregate/manifest_aggregate_summary_method_means.csv`
- output: `outputs/data/aggregate/manifest_aggregate_summary_method_means.tex`

Custom paths:

```bash
make corpus-latex LATEX_IN=/abs/path/method_means.csv LATEX_OUT=/abs/path/table.tex
```

Render LaTeX table into viewable artifact:

```bash
make corpus-render RENDER_OUT=outputs/data/aggregate/manifest_aggregate_summary_method_means.pdf
make corpus-render RENDER_OUT=outputs/data/aggregate/manifest_aggregate_summary_method_means.png
```

Requirements:

- PDF output: `pdflatex` installed.
- PNG output: `pdflatex` + (`pdftoppm` or `magick`) installed.
