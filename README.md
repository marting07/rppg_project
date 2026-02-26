# rPPG Pulse Estimation Method Comparison

This project compares three remote photoplethysmography (rPPG) methods for pulse estimation from webcam video:

- Green channel method
- CHROM (chrominance-based method)
- JBSS-style windowed ICA + component selection method

The implementation goal is educational and research-focused: keep the core methods manually implemented (no specialized rPPG library abstractions) so each step is explainable in a paper.

## Project Goal

Build a clear, reproducible comparison study that:

- explains how each method works mathematically and algorithmically,
- references the original researchers/papers,
- evaluates behavior under the same capture conditions,
- produces publication-ready figures and tables.

## References

- Verkruysse, W., Svaasand, L. O., & Nelson, J. S. (2008). *Remote plethysmographic imaging using ambient light*. Optics Express, 16(26), 21434-21445.
- de Haan, G., & Jeanne, V. (2013). *Robust pulse rate from chrominance-based rPPG*. IEEE Transactions on Biomedical Engineering, 60(10), 2878-2886.
- Bousefsaf, F., Maaoui, C., & Pruski, A. (2013). *Continuous wavelet filtering on webcam photoplethysmographic signals to remotely assess the instantaneous heart rate*. Biomedical Signal Processing and Control, 8(6), 568-574. (context for signal processing choices)

The JBSS implementation is a full manual windowed pipeline with multi-component ICA, component ranking/tracking, and continuous signal reconstruction.

## Quick Start

1. Create a virtual environment and install dependencies:

```bash
make venv
make install
```

2. Run the app:

```bash
make run
```

## Virtual Environment Management

- `make venv`: create `.venv` using Python venv
- `make install`: install dependencies from `requirements.txt`
- `make run`: start the app
- `make test`: run unit tests
- `make evaluate VIDEO=/abs/path/video.mp4 SCENARIO=still METHODS=all [GT=/abs/path/gt.csv] [RUN_ID=my_run]`: run offline evaluation
- `make plots RUN_DIR=outputs/data/<run_id>`: generate paper figures from one evaluation run
- `make corpus-manifest CORPUS=ubfc_rppg_v1 CORPUS_ROOT=data/public/UBFC-rPPG/DATASET_2 [MANIFEST_OUT=outputs/data/corpus_manifests/custom.csv]`: build public corpus manifest
- `make corpus-batch MANIFEST=outputs/data/corpus_manifests/ubfc_rppg_v1_manifest.csv METHODS=all SCENARIO=still [AGG_OUT=outputs/data/aggregate/custom.csv]`: run all corpus rows and write aggregate paper tables
- `make corpus-download CORPUS=ubfc_rppg_v1 UBFC_URL="https://<direct-download-link>"` or `make corpus-download CORPUS=all URLS_JSON=/abs/path/dataset_urls.json`: download/place public corpus files
  - UBFC Google Drive folder URLs are supported directly.
- `make corpus-latex [LATEX_IN=/abs/path/method_means.csv] [LATEX_OUT=/abs/path/table.tex]`: export aggregate metrics to LaTeX table
- `make corpus-render [LATEX_TEX=/abs/path/table.tex] [RENDER_OUT=/abs/path/table.pdf|.png]`: render LaTeX table into PDF/PNG for quick viewing
- `make freeze`: regenerate `requirements.txt` from current `.venv`
- `make clean-venv`: remove `.venv`

## Current Structure

```text
main.py
rppg_methods/
utils/
configs/
docs/
scripts/
tests/
```

## Reproducible Paper Workflow

1. Acquire the selected public corpus (UBFC-rPPG baseline) and place it under `data/public/UBFC-rPPG/DATASET_2`.
2. Build manifest:

```bash
make corpus-manifest CORPUS=ubfc_rppg_v1 CORPUS_ROOT=data/public/UBFC-rPPG/DATASET_2
```

3. Run evaluator in batch from manifest:

```bash
make corpus-batch MANIFEST=outputs/data/corpus_manifests/ubfc_rppg_v1_manifest.csv METHODS=all SCENARIO=still
```

4. Optional: run one subject manually:

```bash
make evaluate VIDEO=/absolute/path/subject1/vid.avi SCENARIO=still METHODS=all GT=/absolute/path/subject1/ground_truth.txt RUN_ID=ubfc_subject1
```

5. Generate figures:

```bash
make plots RUN_DIR=outputs/data/still_run_01
```

6. Use generated artifacts in:
- `outputs/data/<run_id>/summary.csv`
- `outputs/plots/<run_id>/`
- `outputs/data/aggregate/manifest_aggregate_summary_method_means.csv`
7. Export paper table:

```bash
make corpus-latex
```

8. Render to PDF/PNG:

```bash
make corpus-render RENDER_OUT=outputs/data/aggregate/manifest_aggregate_summary_method_means.pdf
```

## Documentation Index

- Methods and equations: `docs/methods.md`
- Experimental protocol: `docs/experimental_protocol.md`
- Public corpus plan: `docs/public_corpus.md`
- Ongoing implementation tracker: `docs/improvement_tracker.md`
