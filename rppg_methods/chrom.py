"""Implementation of the chrominance-based rPPG method (CHROM).

This algorithm leverages a linear combination of the color channels
to amplify the photoplethysmographic signal while suppressing
motion artifacts. Specifically it computes two orthogonal
chrominance signals and combines them such that variations due to
illumination changes are minimized.

References
----------
de Haan, G., & Jeanne, V. (2013). Robust pulse rate from
chrominance-based rPPG. IEEE Transactions on Biomedical Engineering,
60(10), 2878–2886.
"""

from __future__ import annotations

import numpy as np

from .base import RPPGMethod


class ChromMethod(RPPGMethod):
    """Chrominance-based rPPG implementation."""

    def __init__(self, fs: float = 30.0, buffer_size: int = 300) -> None:
        super().__init__(fs=fs, buffer_size=buffer_size)
        # Maintain two intermediate signals
        self.x_buffer: list[float] = []
        self.y_buffer: list[float] = []

    def reset(self) -> None:
        super().reset()
        self.x_buffer.clear()
        self.y_buffer.clear()

    def update(self, roi_frame: np.ndarray) -> None:
        """Compute the CHROM signal from the ROI and update buffers."""
        if roi_frame is None or roi_frame.size == 0:
            return
        # Extract mean color channels; OpenCV uses BGR ordering
        b = float(np.mean(roi_frame[:, :, 0].astype(np.float64)))
        g = float(np.mean(roi_frame[:, :, 1].astype(np.float64)))
        r = float(np.mean(roi_frame[:, :, 2].astype(np.float64)))
        # Compute orthogonal chrominance components as per CHROM paper
        x = 3.0 * r - 2.0 * g
        y = 1.5 * r + g - 1.5 * b
        self.x_buffer.append(x)
        self.y_buffer.append(y)
        # Maintain same length as base signal buffer
        if len(self.x_buffer) > self.buffer_size:
            excess = len(self.x_buffer) - self.buffer_size
            self.x_buffer = self.x_buffer[excess:]
            self.y_buffer = self.y_buffer[excess:]
        # Compute alpha scaling between x and y to minimize illumination
        x_arr = np.array(self.x_buffer, dtype=np.float64)
        y_arr = np.array(self.y_buffer, dtype=np.float64)
        if x_arr.size == 0 or y_arr.size == 0:
            return
        std_x = np.std(x_arr)
        std_y = np.std(y_arr)
        if std_y == 0:
            alpha = 0.0
        else:
            alpha = std_x / std_y
        s = x - alpha * y
        self._append_value(s)
        hr = self._compute_hr_from_buffer()
        if hr is not None:
            self.last_hr = hr