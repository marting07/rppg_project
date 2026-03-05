# Method Pseudocode

## Green Method

```text
Initialize GreenMethod(fs, buffer_size)
For each frame:
  roi <- forehead_region(frame)
  if roi is empty: continue
  g_mean <- mean(roi.green_channel)
  append g_mean to signal_buffer
  if buffer has enough samples:
    estimate bpm using shared FFT pipeline
```

## CHROM Method

```text
Initialize ChromMethod(fs, buffer_size)
Maintain rolling RGB buffers
For each frame:
  roi <- forehead_region(frame)
  if roi is empty: continue
  r, g, b <- mean RGB channels from roi
  x <- 3r - 2g
  y <- 1.5r + g - 1.5b
  alpha <- std(x_window) / std(y_window)
  s <- x - alpha * y
  append s to signal_buffer
  if buffer has enough samples:
    estimate bpm using shared FFT pipeline
```

## POS Method

```text
Initialize POSMethod(fs, buffer_size, window_size)
Maintain rolling R, G, B buffers
For each frame:
  roi <- forehead_region(frame)
  if roi is empty: continue
  r, g, b <- robust mean RGB from roi
  append r, g, b to rolling buffers
  if window is not full: continue
  C <- last window of [R, G, B]
  Cn <- C / mean(C) - 1
  s1 <- Cn.G - Cn.B
  s2 <- -2*Cn.R + Cn.G + Cn.B
  alpha <- std(s1) / std(s2)
  s <- normalize(s1 + alpha*s2)
  append s[-1] to signal_buffer
  if signal_buffer has enough samples:
    estimate bpm using shared FFT pipeline
```

## SSR/2SR-Style Method

```text
Initialize SSRMethod(fs, buffer_size)
Maintain previous 2D color subspace basis U_prev
For each frame:
  roi <- forehead_region(frame)
  if roi is empty: continue
  skin_pixels <- YCrCb skin mask from roi (fallback all pixels)
  X <- normalize RGB of skin_pixels
  C <- covariance(X)
  U <- top-2 eigenvectors of C
  if U_prev is missing:
    U_prev <- U
    continue
  A <- transpose(U_prev) * U
  r <- atan2(A01 - A10, A00 + A11)
  append smoothed r to signal_buffer
  U_prev <- U
  if signal_buffer has enough samples:
    estimate bpm using shared FFT pipeline
```
