"""Implementation of a JBSS-style rPPG method with windowed ICA + selection.

Pipeline summary:
1) Windowed RGB traces with overlap.
2) Preprocessing: temporal normalization, detrending, common-mode removal.
3) Multi-component FastICA extraction.
4) CCA-like periodicity and spectral quality scoring per component.
5) Temporal component tracking across windows for stability.
6) Overlap-add reconstruction of pulse signal and frame-rate output stream.
"""

from __future__ import annotations

import numpy as np

from .base import RPPGMethod


class JBSSMethod(RPPGMethod):
    """JBSS-style manual implementation with deterministic multi-ICA windows."""

    def __init__(
        self,
        fs: float = 30.0,
        buffer_size: int = 300,
        window_seconds: float = 6.0,
        overlap_ratio: float = 0.5,
        n_components: int = 3,
    ) -> None:
        super().__init__(fs=fs, buffer_size=buffer_size)
        self.r_buffer: list[float] = []
        self.g_buffer: list[float] = []
        self.b_buffer: list[float] = []
        self.window_size = max(1, int(round(window_seconds * fs)))
        self.overlap_ratio = float(np.clip(overlap_ratio, 0.0, 0.95))
        self.hop_size = max(1, int(round(self.window_size * (1.0 - self.overlap_ratio))))
        self.n_components = max(1, min(3, n_components))

        self._window_count = 0
        self._pending_pulse: list[float] = []
        self._last_selected_w: np.ndarray | None = None
        self._last_unmixing: np.ndarray | None = None
        self.last_confidence: float | None = None

    def reset(self) -> None:
        super().reset()
        self.r_buffer.clear()
        self.g_buffer.clear()
        self.b_buffer.clear()
        self._window_count = 0
        self._pending_pulse.clear()
        self._last_selected_w = None
        self._last_unmixing = None
        self.last_confidence = None

    def update(self, roi_frame: np.ndarray) -> None:
        """Run JBSS-style extraction and emit one pulse sample per frame."""
        if roi_frame is None or roi_frame.size == 0:
            return
        b = float(np.mean(roi_frame[:, :, 0].astype(np.float64)))
        g = float(np.mean(roi_frame[:, :, 1].astype(np.float64)))
        r = float(np.mean(roi_frame[:, :, 2].astype(np.float64)))
        self.r_buffer.append(r)
        self.g_buffer.append(g)
        self.b_buffer.append(b)
        if len(self.r_buffer) > self.buffer_size:
            excess = len(self.r_buffer) - self.buffer_size
            self.r_buffer = self.r_buffer[excess:]
            self.g_buffer = self.g_buffer[excess:]
            self.b_buffer = self.b_buffer[excess:]
        self._process_new_window_if_ready()
        if self._pending_pulse:
            self.update_from_value(self._pending_pulse.pop(0))

    def get_confidence(self) -> float | None:
        """Return last component-selection confidence for reporting."""
        return self.last_confidence

    def _process_new_window_if_ready(self) -> None:
        n = len(self.r_buffer)
        if n < self.window_size:
            return
        if (n - self.window_size) % self.hop_size != 0:
            return

        X = np.array([self.r_buffer[-self.window_size :], self.g_buffer[-self.window_size :], self.b_buffer[-self.window_size :]], dtype=np.float64).T
        X_prep = self._preprocess_window(X)
        S, W = self._fastica_multi(X_prep, self.n_components)
        if S.size == 0:
            return

        selected_idx, confidence = self._select_component(S, W)
        selected = S[:, selected_idx]
        selected = selected - np.mean(selected)
        std = np.std(selected)
        if std > 1e-8:
            selected = selected / std

        overlap = self.window_size - self.hop_size
        if self._window_count == 0 or overlap <= 0:
            segment = selected[-self.hop_size :]
        else:
            # Raised-cosine taper at the overlap boundary reduces discontinuities.
            prev_tail = np.array(self._pending_pulse[-overlap:], dtype=np.float64) if len(self._pending_pulse) >= overlap else None
            head = selected[:overlap]
            if prev_tail is not None and prev_tail.size == overlap:
                w = np.linspace(0.0, 1.0, overlap, endpoint=False)
                blended = (1.0 - w) * prev_tail + w * head
                self._pending_pulse[-overlap:] = blended.tolist()
            segment = selected[-self.hop_size :]

        self._pending_pulse.extend(segment.tolist())
        self.last_confidence = confidence
        self._window_count += 1

    def _preprocess_window(self, X: np.ndarray) -> np.ndarray:
        Xn = X.copy().astype(np.float64)
        for col in range(Xn.shape[1]):
            c = Xn[:, col]
            c = c - np.mean(c)
            t = np.arange(c.size, dtype=np.float64)
            slope, intercept = np.polyfit(t, c, 1)
            c = c - (slope * t + intercept)
            c_std = np.std(c)
            if c_std > 1e-8:
                c = c / c_std
            Xn[:, col] = c

        # Remove common-mode illumination component.
        common = np.mean(Xn, axis=1, keepdims=True)
        Xn = Xn - common
        row_norm = np.linalg.norm(Xn, axis=1, keepdims=True)
        row_norm[row_norm < 1e-8] = 1.0
        Xn = Xn / row_norm
        return Xn

    def _fastica_multi(self, X: np.ndarray, n_components: int) -> tuple[np.ndarray, np.ndarray]:
        if X.size == 0:
            return np.array([], dtype=np.float64), np.array([], dtype=np.float64)

        X_centered = X - np.mean(X, axis=0)
        cov = np.cov(X_centered, rowvar=False)
        d, E = np.linalg.eigh(cov)
        idx = np.argsort(d)[::-1]
        d = d[idx]
        E = E[:, idx]
        D_inv = np.diag(1.0 / np.sqrt(d + 1e-10))
        whitening = E @ D_inv @ E.T
        X_white = X_centered @ whitening

        n_features = X_white.shape[1]
        W = np.zeros((n_components, n_features), dtype=np.float64)
        init_order = [np.array([1.0, 0.0, 0.0], dtype=np.float64), np.array([0.0, 1.0, 0.0], dtype=np.float64), np.array([0.0, 0.0, 1.0], dtype=np.float64)]
        if self._last_unmixing is not None and self._last_unmixing.shape == W.shape:
            init_order = [self._last_unmixing[i].copy() for i in range(n_components)]

        for comp in range(n_components):
            w = init_order[comp] if comp < len(init_order) else np.ones(n_features, dtype=np.float64)
            if np.linalg.norm(w) < 1e-10:
                w = np.ones(n_features, dtype=np.float64)
            w = w / np.linalg.norm(w)
            for _ in range(200):
                u = X_white @ w
                g = np.tanh(u)
                g_der = 1.0 - g ** 2
                w_new = (X_white.T @ g) / X_white.shape[0] - np.mean(g_der) * w
                if comp > 0:
                    w_new -= W[:comp].T @ (W[:comp] @ w_new)
                norm = np.linalg.norm(w_new)
                if norm < 1e-10:
                    break
                w_new /= norm
                if np.abs(np.abs(np.dot(w_new, w)) - 1.0) < 1e-6:
                    w = w_new
                    break
                w = w_new
            W[comp] = w

        S = X_white @ W.T
        self._last_unmixing = W.copy()
        return S, W

    def _select_component(self, S: np.ndarray, W: np.ndarray) -> tuple[int, float]:
        lag_min = max(1, int(self.fs / 4.0))
        lag_max = min(S.shape[0] // 2, max(lag_min + 1, int(self.fs / 0.75)))
        scores: list[float] = []
        for idx in range(S.shape[1]):
            s = S[:, idx]
            periodicity = self._cca_like_periodicity(s, lag_min, lag_max)
            spectral = self._spectral_quality(s)
            tracking = self._tracking_score(W[idx])
            score = 0.45 * periodicity + 0.35 * spectral + 0.20 * tracking
            scores.append(score)

        best = int(np.argmax(scores))
        sorted_scores = np.sort(np.array(scores, dtype=np.float64))
        if sorted_scores.size == 1:
            confidence = 1.0
        else:
            gap = sorted_scores[-1] - sorted_scores[-2]
            confidence = float(np.clip(gap / (abs(sorted_scores[-1]) + 1e-8), 0.0, 1.0))
        self._last_selected_w = W[best].copy()
        return best, confidence

    def _cca_like_periodicity(self, s: np.ndarray, lag_min: int, lag_max: int) -> float:
        s0 = s - np.mean(s)
        std = np.std(s0)
        if std < 1e-8:
            return 0.0
        s0 /= std
        best = 0.0
        for lag in range(lag_min, lag_max + 1):
            if lag >= s0.size:
                break
            a = s0[:-lag]
            b = s0[lag:]
            if a.size < 3:
                continue
            corr = np.corrcoef(a, b)[0, 1]
            if np.isfinite(corr):
                best = max(best, abs(float(corr)))
        return float(np.clip(best, 0.0, 1.0))

    def _spectral_quality(self, s: np.ndarray) -> float:
        s0 = s - np.mean(s)
        n = s0.size
        if n < 8:
            return 0.0
        fft_mag = np.abs(np.fft.rfft(s0))
        freqs = np.fft.rfftfreq(n, d=1.0 / self.fs)
        band = (freqs >= 0.75) & (freqs <= 4.0)
        if not np.any(band):
            return 0.0
        band_mag = fft_mag[band]
        peak = float(np.max(band_mag))
        baseline = float(np.mean(band_mag) + 1e-8)
        snr_like = (peak / baseline) - 1.0
        return float(np.clip(np.tanh(max(0.0, snr_like)), 0.0, 1.0))

    def _tracking_score(self, w: np.ndarray) -> float:
        if self._last_selected_w is None:
            return 0.5
        denom = (np.linalg.norm(w) * np.linalg.norm(self._last_selected_w)) + 1e-8
        score = abs(float(np.dot(w, self._last_selected_w) / denom))
        return float(np.clip(score, 0.0, 1.0))
