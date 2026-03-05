# rPPG Methods (Manual Implementations)

This document explains the manually implemented methods and how they map to the shared processing pipeline.

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

## 3) POS Method

Extraction equations (windowed channel-normalized RGB traces):

- `C_n = C / mean(C) - 1`
- `s1 = G_n - B_n`
- `s2 = -2R_n + G_n + B_n`
- `alpha = std(s1) / std(s2)`
- `s = s1 + alpha * s2`

Interpretation:

- POS projects normalized color traces onto a plane orthogonal to the skin-tone direction.
- Adaptive `alpha` balances the projected axes to suppress common illumination changes.

Primary reference:

- Wang, W., den Brinker, A. C., Stuijk, S., & de Haan, G. (2017). *Algorithmic Principles of Remote PPG*. IEEE Transactions on Biomedical Engineering, 64(7), 1479-1491.

## 4) SSR/2SR-Style Subspace Rotation

Per-frame equations (skin pixels):

- `X_t = normalize(RGB_skin_pixels_t)`
- `C_t = cov(X_t)`
- `U_t = eigvecs_top2(C_t)`
- `r_t = atan2(a12 - a21, a11 + a22)` where `A = U_{t-1}^T U_t`

Interpretation:

- The pulse is encoded as temporal rotation of the skin-color subspace.
- Signed rotation between consecutive 2D subspaces yields a 1D pulsatile stream.

Primary reference:

- Wang, W., Stuijk, S., & de Haan, G. (2015). *A Novel Algorithm for Remote Photoplethysmography: Spatial Subspace Rotation*. IEEE Transactions on Biomedical Engineering, 63(9), 1974-1984.
