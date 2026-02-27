# rPPG Project AGENTS

## Objective

Compare pulse estimation methods with manual/non-library method implementations suitable for a paper:
- Green channel
- CHROM
- JBSS-style windowed ICA + component selection

## Key Files

- Entry point: `main.py`
- Methods: `rppg_methods/`
- Evaluation/config: `scripts/`, `configs/`, `tests/`
- Paper docs: `docs/`
- Output artifacts: `outputs/`

## Standard Commands

- `make venv`
- `make install`
- `make test`
- `make run`
- `make evaluate VIDEO=/abs/path/video.mp4 SCENARIO=still METHODS=all [GT=/abs/path/gt.csv] [RUN_ID=my_run]`
- `make plots RUN_DIR=outputs/data/<run_id>`
- `make corpus-manifest CORPUS=ubfc_rppg_v1 CORPUS_ROOT=data/public/UBFC-rPPG/DATASET_2`
- `make corpus-batch MANIFEST=outputs/data/corpus_manifests/ubfc_rppg_v1_manifest.csv METHODS=all SCENARIO=still`

## Corpus Status

- UBFC-rPPG is the active baseline corpus.
- COHFACE is pending approval.
- PURE was excluded (request denied).

## Planning Notes

- Use `docs/improvement_tracker.md` as the authoritative implementation tracker.
- Treat production-ready ICA/JBSS work as iterative: fidelity, component selection, reconstruction, validation, and paper-readiness passes.
