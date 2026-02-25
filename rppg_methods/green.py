"""Implementation of the basic green channel rPPG method.

This method tracks the average intensity of the green channel
within the forehead region across successive frames. Because
hemoglobin absorbs more green light than red or blue, the green
channel tends to exhibit the strongest pulsatile component
correlated with the cardiac cycle. A band‑pass filter and FFT
analysis are applied in the base class to derive the heart rate.

References
----------
Verkruysse, W., Svaasand, L. O., & Nelson, J. S. (2008). Remote
plethysmographic imaging using ambient light. Optics Express, 16(26),
21434–21445.
"""

from __future__ import annotations

import numpy as np

from .base import RPPGMethod


class GreenMethod(RPPGMethod):
    """Simple rPPG method using mean green channel intensity."""

    def __init__(self, fs: float = 30.0, buffer_size: int = 300) -> None:
        super().__init__(fs=fs, buffer_size=buffer_size)

    def update(self, roi_frame: np.ndarray) -> None:
        """Extract mean green intensity from the ROI and update buffer."""
        if roi_frame is None or roi_frame.size == 0:
            return
        # OpenCV loads images in BGR order; index 1 is green
        green_values = roi_frame[:, :, 1].astype(np.float64)
        mean_green = float(np.mean(green_values))
        self._append_value(mean_green)
        # Update heart rate estimation periodically
        hr = self._compute_hr_from_buffer()
        if hr is not None:
            self.last_hr = hr