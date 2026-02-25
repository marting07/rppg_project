"""Implementation of a joint blind source separation (JBSS) rPPG method.

The JBSS approach combines independent component analysis (ICA) with
canonical correlation analysis (CCA) to separate the true pulse
signal from noise and motion artifacts. Here we implement a simplified
version using a single‑component FastICA on the RGB signals.

Note
----
This implementation is illustrative and does not faithfully reproduce
all details of the JBSS algorithm described in the literature. In
practice JBSS would operate on overlapping temporal windows and apply
CCA across multiple color channels to select the most periodic
component. Nonetheless, the method here demonstrates how ICA can
extract a periodic source from the color traces.
"""

from __future__ import annotations

import numpy as np

from .base import RPPGMethod


class JBSSMethod(RPPGMethod):
    """Simplified JBSS method using a single‑component ICA."""

    def __init__(self, fs: float = 30.0, buffer_size: int = 300) -> None:
        super().__init__(fs=fs, buffer_size=buffer_size)
        self.r_buffer: list[float] = []
        self.g_buffer: list[float] = []
        self.b_buffer: list[float] = []

    def reset(self) -> None:
        super().reset()
        self.r_buffer.clear()
        self.g_buffer.clear()
        self.b_buffer.clear()

    def update(self, roi_frame: np.ndarray) -> None:
        """Collect RGB means and compute ICA periodically."""
        if roi_frame is None or roi_frame.size == 0:
            return
        b = float(np.mean(roi_frame[:, :, 0].astype(np.float64)))
        g = float(np.mean(roi_frame[:, :, 1].astype(np.float64)))
        r = float(np.mean(roi_frame[:, :, 2].astype(np.float64)))
        self.r_buffer.append(r)
        self.g_buffer.append(g)
        self.b_buffer.append(b)
        # Trim to buffer_size
        if len(self.r_buffer) > self.buffer_size:
            excess = len(self.r_buffer) - self.buffer_size
            self.r_buffer = self.r_buffer[excess:]
            self.g_buffer = self.g_buffer[excess:]
            self.b_buffer = self.b_buffer[excess:]
        # Convert to array when enough samples collected
        X = np.array([self.r_buffer, self.g_buffer, self.b_buffer], dtype=np.float64).T
        if X.shape[0] < int(self.fs * 4):
            return
        # Center and whiten
        X_centered = X - np.mean(X, axis=0)
        cov = np.cov(X_centered, rowvar=False)
        # Eigenvalue decomposition
        d, E = np.linalg.eigh(cov)
        # Sort eigenvalues in descending order
        idx = np.argsort(d)[::-1]
        d = d[idx]
        E = E[:, idx]
        # Compute whitening matrix
        D_inv = np.diag(1.0 / np.sqrt(d + 1e-10))
        whitening = E @ D_inv @ E.T
        X_white = X_centered @ whitening
        # FastICA: single component extraction using fixed‑point iteration
        n_components = 1
        n_features = X_white.shape[1]
        # Initialize random weight vector
        w = np.random.rand(n_features)
        w /= np.linalg.norm(w)
        for _ in range(100):
            # g(u) = tanh(u) nonlinearity
            u = X_white @ w
            g = np.tanh(u)
            g_der = 1.0 - g ** 2
            w_new = (X_white.T @ g) / X_white.shape[0] - np.mean(g_der) * w
            # Normalize
            w_new /= np.linalg.norm(w_new)
            # Check convergence
            if np.abs(np.abs(np.dot(w_new, w)) - 1.0) < 1e-6:
                break
            w = w_new
        # Extract component
        s = X_white @ w
        # Append latest sample value
        self._append_value(float(s[-1]))
        hr = self._compute_hr_from_buffer()
        if hr is not None:
            self.last_hr = hr