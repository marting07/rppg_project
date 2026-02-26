# rPPG Improvement Tracker

This file tracks implementation progress for the five agreed improvement areas.

Legend:

- `[ ]` pending
- `[~]` in progress
- `[x]` completed

## 1) Method fidelity and explainability

Status: `[x]`

Tasks:

- [x] Split method workflow into explicit stages (`signal_extraction`, `normalization`, `filtering`, `hr_estimation`) in code structure.
- [x] Add clear equations and algorithm flow notes in method docs.
- [x] Link each method implementation block to primary literature references.
- [x] Mark simplified JBSS behavior explicitly in code and docs.

## 2) Scientific comparison protocol

Status: `[x]`

Tasks:

- [x] Define fixed experimental scenarios (still, motion, lighting, distance).
- [x] Standardize comparison parameters (window, frequency band, BPM range).
- [x] Define required metrics (MAE, RMSE, Pearson correlation).
- [x] Add protocol configuration file for reproducible experiments.

## 3) Data and reproducibility pipeline

Status: `[x]`

Tasks:

- [x] Add offline evaluation runner for recorded videos.
- [x] Export per-frame and per-window signals to CSV.
- [x] Save structured run metadata (method, fs, config, timestamp).
- [x] Support deterministic outputs for repeated runs.

## 4) Figure generation for paper

Status: `[x]`

Tasks:

- [x] Generate per-method signal plots (raw, filtered, PSD, BPM vs time).
- [x] Generate comparison plots (error boxplot, Bland-Altman, failure rate).
- [x] Save plots in publication-friendly format and naming.
- [x] Document how to regenerate all figures from commands.

## 5) Code quality and publication readiness

Status: `[x]`

Tasks:

- [x] Add tests for short-buffer filtering behavior.
- [x] Add tests for no-face / empty ROI handling.
- [x] Add synthetic-signal tests for deterministic HR estimation.
- [x] Add publication docs (`docs/methods.md`, `docs/experimental_protocol.md`).

## Execution Task List

- [x] T1 Create tracking document and folder layout.
- [x] T2 Refactor method pipeline and add explanatory docs.
- [x] T3 Add protocol config and experiment definitions.
- [x] T4 Implement offline evaluator and structured outputs.
- [x] T5 Implement figure generation scripts.
- [x] T6 Add tests and publication docs.
- [x] T7 Update README and tracker to final state.

## Validation Notes

- `python3 -m py_compile` passed for updated source files.
- `python3 -m unittest discover -s tests -p "test_*.py"` is currently blocked in this shell due to missing installed dependencies (`scipy`, `cv2`).
- Run `make install` then `make test` in project `.venv` to execute the test suite end-to-end.
- JBSS upgrade files (`rppg_methods/jbss.py`, evaluator, figures, tests) pass static syntax check.

## JBSS Production Upgrade (Non-Educational Implementation)

Status: `[x]`

### Iteration 1: Algorithm fidelity

- [x] Define explicit JBSS processing stages and state model.
- [x] Add overlapping temporal windows.
- [x] Add configurable window length.
- [x] Add configurable overlap ratio and hop size.
- [x] Add RGB temporal normalization per channel.
- [x] Add linear detrending per channel.
- [x] Add common-mode suppression for motion/illumination robustness.
- [x] Add frame-wise normalization after common-mode suppression.
- [x] Replace single-component ICA with deterministic multi-component FastICA.
- [x] Add warm-start unmixing matrix initialization for temporal continuity.

### Iteration 2: Component selection and tracking

- [x] Add CCA-like periodicity scoring over physiological lag range.
- [x] Add spectral quality scoring in physiological frequency band.
- [x] Combine periodicity + spectral into ranking function.
- [x] Add temporal tracking score based on component-vector continuity.
- [x] Build weighted composite score for component selection.
- [x] Compute confidence from winner margin over runner-up.
- [x] Persist selected component state for next window.

### Iteration 3: Signal reconstruction

- [x] Reconstruct selected component per window.
- [x] Normalize reconstructed component amplitude.
- [x] Emit frame-rate pulse stream via pending-sample queue.
- [x] Add overlap boundary blending logic for continuity.
- [x] Integrate reconstructed samples into base HR estimation pipeline.
- [x] Expose selection confidence through public method.

### Iteration 4: Validation and integration

- [x] Ensure deterministic behavior with fixed initialization strategy.
- [x] Keep compatibility with existing app update/get_hr flow.
- [x] Keep compatibility with offline evaluator interface.
- [x] Update method docs to reflect production-style JBSS implementation.
- [x] Keep existing synthetic determinism test coverage applicable.
- [x] Verify static syntax correctness with `py_compile`.

### Iteration 5: Paper readiness artifacts

- [x] Remove "educational approximation" framing in method code.
- [x] Add publication-style method description in `docs/methods.md`.
- [x] Keep protocol/evaluation scripts compatible with updated JBSS class.

## Public Corpus Integration

Status: `[x]`

- [x] Select initial public corpus baseline (UBFC-rPPG v1).
- [x] Add public corpus config file (`configs/public_corpus.json`).
- [x] Add public corpus execution documentation (`docs/public_corpus.md`).
- [x] Add manifest generation script for selected corpus.
- [x] Add `make corpus-manifest` command for reproducible indexing.
- [x] Extend evaluator to parse UBFC-style text ground truth in addition to CSV.
- [x] Update README workflow to public-corpus-first process.
- [x] Add batch manifest runner for end-to-end corpus execution.
- [x] Add aggregate paper-table generation (method-level means).
- [x] Add LaTeX exporter for method-level aggregate table.
- [x] Add PDF/PNG renderer for generated LaTeX table.
