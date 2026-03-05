# Method Math-to-Code Guide

This guide maps each method's equations to the exact implementation blocks in the repository.

## Shared Signal-to-BPM Stage (all methods)

Equations:

- Normalization: `x_n(t) = x(t) - mean(x)`
- Band-pass filtering: `x_f(t) = BPF(x_n(t), 0.75, 4.0 Hz)`
- Frequency peak: `f* = argmax_{f in [0.75, 4.0]} |FFT(x_f)|`
- BPM conversion: `BPM = 60 * f*`

Code mapping:

- Shared pipeline methods are in `RPPGMethod`:
  - `normalize_signal`
  - `filter_signal`
  - `estimate_hr_bpm`
- File: `rppg_methods/base.py`

## Green Method

Equation:

- `s_t = mean(G_t)`

Code mapping:

- `GreenMethod.update`
- File: `rppg_methods/green.py`

## CHROM Method

Equations:

- `x_t = 3R_t - 2G_t`
- `y_t = 1.5R_t + G_t - 1.5B_t`
- `alpha = std(x) / std(y)`
- `s_t = x_t - alpha * y_t`

Code mapping:

- `ChromMethod.update`
- File: `rppg_methods/chrom.py`

## POS Method

Equations:

- `C_n = C / mean(C) - 1`
- `s1 = G_n - B_n`
- `s2 = -2R_n + G_n + B_n`
- `alpha = std(s1) / std(s2)`
- `s = s1 + alpha * s2`

Code mapping:

- `POSMethod.update`
- File: `rppg_methods/pos.py`

## SSR/2SR-Style Method

Equations:

- `X_t = normalize(RGB_skin_pixels_t)`
- `C_t = cov(X_t)`
- `U_t = eigvecs_top2(C_t)`
- `A_t = U_{t-1}^T U_t`
- `r_t = atan2(A_t[0,1]-A_t[1,0], A_t[0,0]+A_t[1,1])`

Code mapping:

- `SSRMethod.update`
- `SSRMethod._compute_skin_subspace_basis`
- File: `rppg_methods/ssr.py`
