# rPPG Methods (Manual Implementations)

This document explains the three manually implemented methods and how they map to the shared processing pipeline.

## Shared Pipeline

Each method uses the same downstream stages in `RPPGMethod`:

1. `signal_extraction`: method-specific scalar from each ROI frame
2. `normalization`: remove DC component (`x - mean(x)`)
3. `filtering`: Butterworth bandpass in 0.75-4.0 Hz
4. `hr_estimation`: FFT peak frequency in physiological band, BPM = `f_peak * 60`

## 1) Green Method

Extraction equation:

`s_t = mean(G_t)`

- `G_t` is the green channel in the forehead ROI at frame `t`.
- Motivation: hemoglobin absorption makes green reflectance strongly pulsatile.

Primary reference:

- Verkruysse, W., Svaasand, L. O., & Nelson, J. S. (2008). *Remote plethysmographic imaging using ambient light*. Optics Express, 16(26), 21434-21445.

## 2) CHROM Method

Extraction equations (using frame-wise channel means):

- `x_t = 3R_t - 2G_t`
- `y_t = 1.5R_t + G_t - 1.5B_t`
- `alpha = std(x) / std(y)`
- `s_t = x_t - alpha * y_t`

Interpretation:

- `x_t` and `y_t` form orthogonal chrominance combinations.
- `alpha` rescales components to reduce illumination/motion influence.

Primary reference:

- de Haan, G., & Jeanne, V. (2013). *Robust pulse rate from chrominance-based rPPG*. IEEE Transactions on Biomedical Engineering, 60(10), 2878-2886.

## 3) JBSS-Style Windowed ICA + Selection

The JBSS implementation is now a full manual windowed pipeline with component
selection/tracking and continuous reconstruction.

Per-window equations:

- `X_t = [R_t, G_t, B_t]` (windowed RGB means)
- `X_p = preprocess(X_t)` (detrend, channel normalization, common-mode removal)
- `S = FastICA_multi(X_p)` (multi-component source extraction)
- `score_i = w1 * periodicity_i + w2 * spectral_i + w3 * tracking_i`
- `i* = argmax(score_i)` (selected source)
- `s_t = overlap_add(S[:, i*])` (continuous pulse reconstruction)

Selection details:

- `periodicity_i`: CCA-like delayed self-correlation score in physiological lag range.
- `spectral_i`: in-band peak prominence score in 0.75-4.0 Hz.
- `tracking_i`: continuity score versus previously selected component vector.

Outcome:

- A stable, deterministic, publishable JBSS-style manual method suitable for
  direct comparison against Green and CHROM.
