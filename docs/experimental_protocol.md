# Experimental Protocol

This protocol defines the comparison setup for Green, CHROM, and simplified JBSS implementations.

## Goals

- Compare pulse estimation accuracy under controlled scenario changes.
- Keep all non-method parameters fixed for fair evaluation.
- Produce reproducible outputs for paper figures and tables.

## Fixed Parameters

Source: `configs/experiment_protocol.json`

- Fallback frame rate: 30 Hz
- Buffer length: 10 seconds
- Minimum signal before HR estimation: 4 seconds
- Physiological band: 0.75-4.0 Hz (45-240 BPM)
- Metrics: MAE, RMSE, Pearson correlation

## Scenarios

1. Still Subject
- Subject keeps head and body as still as possible.

2. Head Motion
- Subject performs intentional left-right/up-down movements.

3. Lighting Variation
- Ambient lighting changes over time.

4. Distance Variation
- Subject moves closer/farther while remaining visible.

## Data Requirements

- Recorded video per scenario.
- Optional ground-truth CSV with columns:
  - `time_s`
  - `bpm`

## Output Artifacts

The evaluator writes:

- Per-method time-series CSV
  - Includes `selection_confidence` when method exposes component confidence (JBSS)
- Per-method summary CSV
- Run metadata JSON

The plotting script writes:

- Raw/filtered signal plots
- PSD plot with in-band peak
- BPM vs time (and ground truth if available)
- Comparison plots (error boxplot, Bland-Altman, failure rates)

## Reproducibility Rules

- Keep config file versioned in git.
- Use explicit `run-id` for stable output folders.
- Keep method implementation manual and transparent.
