"""Base classes and common utilities for remote photoplethysmography methods.

Each rPPG method should inherit from ``RPPGMethod`` and implement
``update`` to process a new ROI frame, ``reset`` to clear any
internal state between video sessions, and optionally ``get_hr``
and ``get_ppg_signal`` for downstream display or analysis.
"""

from __future__ import annotations

import numpy as np
from typing import Optional

from utils.bandpass_filter import bandpass_filter


class RPPGMethod:
    """Abstract base class for rPPG methods.

    Parameters
    ----------
    fs : float
        Sampling frequency (frame rate) of the video in Hertz.
    buffer_size : int
        Number of samples to retain for heart rate estimation. The
        buffer should be long enough to capture several cardiac
        cycles; a typical buffer corresponds to 8–12 seconds of
        video.
    """

    def __init__(self, fs: float = 30.0, buffer_size: int = 300) -> None:
        self.fs = fs
        self.buffer_size = buffer_size
        self.signal_buffer: list[float] = []
        self.times: list[float] = []
        self.last_hr: Optional[float] = None

    def reset(self) -> None:
        """Clear the internal signal buffer and reset heart rate."""
        self.signal_buffer.clear()
        self.times.clear()
        self.last_hr = None

    def update(self, roi_frame: np.ndarray) -> None:
        """Process a new ROI frame and update the internal buffer.

        Subclasses must override this method to extract the per‑frame
        photoplethysmographic value (e.g. mean green intensity or a
        chrominance combination) from the ROI.

        Parameters
        ----------
        roi_frame : np.ndarray
            The cropped BGR image corresponding to the subject's
            forehead.
        """
        raise NotImplementedError

    def _append_value(self, value: float) -> None:
        """Append a raw value to the signal buffer and trim if necessary."""
        self.signal_buffer.append(value)
        # Maintain buffer length
        if len(self.signal_buffer) > self.buffer_size:
            # Remove oldest values
            excess = len(self.signal_buffer) - self.buffer_size
            self.signal_buffer = self.signal_buffer[excess:]

    def _compute_hr_from_buffer(self) -> Optional[float]:
        """Estimate heart rate from the current signal buffer.

        The signal buffer is band‑pass filtered and transformed to
        the frequency domain via an FFT. The frequency with the
        maximum magnitude within the physiological heart rate band
        (0.75–4 Hz) is selected and converted to beats per minute.

        Returns
        -------
        float or None
            Estimated heart rate in BPM if a peak is found,
            otherwise ``None``.
        """
        signal = np.array(self.signal_buffer, dtype=np.float64)
        if signal.size < int(self.fs * 4):
            # Require at least 4 seconds of data to estimate HR
            return None
        # Remove mean to reduce DC component
        detrended = signal - np.mean(signal)
        # Apply band‑pass filter
        filtered = bandpass_filter(detrended, fs=self.fs, low=0.75, high=4.0)
        # Compute FFT and corresponding frequencies
        n = len(filtered)
        freqs = np.fft.rfftfreq(n, d=1.0 / self.fs)
        fft_mag = np.abs(np.fft.rfft(filtered))
        # Restrict to physiological band
        mask = (freqs >= 0.75) & (freqs <= 4.0)
        if not np.any(mask):
            return None
        # Find frequency with maximum magnitude
        peak_freq = freqs[mask][np.argmax(fft_mag[mask])]
        hr = float(peak_freq * 60.0)
        return hr

    def get_hr(self) -> Optional[float]:
        """Return the most recent heart rate estimation.

        This method should be called after ``update`` has been
        invoked on successive frames. The result is cached to avoid
        recomputing the FFT on every frame.
        """
        return self.last_hr

    def get_ppg_signal(self) -> np.ndarray:
        """Return the current filtered PPG signal for plotting."""
        signal = np.array(self.signal_buffer, dtype=np.float64)
        if signal.size == 0:
            return signal
        detrended = signal - np.mean(signal)
        filtered = bandpass_filter(detrended, fs=self.fs, low=0.75, high=4.0)
        return filtered
