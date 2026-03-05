"""Entry point for the rPPG live subject verification application.

This application provides a simple graphical user interface (GUI)
implemented with PySide6. It captures video from the default camera,
detects a face using a Haar cascade classifier, extracts the
forehead region of interest (ROI), and processes it using one of
several rPPG methods (Green, CHROM, POS, SSR) to estimate the user's
heart rate. The current heart rate and the filtered photoplethysmogram
(PPG) waveform are displayed in the UI.

To run the application install the required dependencies:
    pip install opencv-python PySide6 numpy scipy

Then execute this script:
    python main.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

import cv2  # type: ignore
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets  # type: ignore
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas  # type: ignore
from matplotlib.figure import Figure

from rppg_methods.green import GreenMethod
from rppg_methods.chrom import ChromMethod
from rppg_methods.pos import POSMethod
from rppg_methods.ssr import SSRMethod
from utils.roi import FaceDetector, extract_forehead_roi

if TYPE_CHECKING:
    from rppg_methods.base import RPPGMethod


@dataclass
class MethodEntry:
    """Data structure to hold method display name and instance."""

    name: str
    instance: RPPGMethod


class RPPGApp(QtWidgets.QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Remote PPG Live Subject Verification")
        self.resize(800, 600)

        # Initialize video capture
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Unable to open default camera")
        fps = self.cap.get(cv2.CAP_PROP_FPS)
        # Fall back to 30 Hz if FPS cannot be read
        self.fs = fps if fps and fps > 1.0 else 30.0

        # Initialize methods
        self.methods: list[MethodEntry] = [
            MethodEntry("Green", GreenMethod(fs=self.fs, buffer_size=int(self.fs * 10))),
            MethodEntry("CHROM", ChromMethod(fs=self.fs, buffer_size=int(self.fs * 10))),
            MethodEntry("POS", POSMethod(fs=self.fs, buffer_size=int(self.fs * 10))),
            MethodEntry("SSR", SSRMethod(fs=self.fs, buffer_size=int(self.fs * 10))),
        ]
        self.current_method: MethodEntry = self.methods[0]

        # Face detector
        self.face_detector = FaceDetector()

        # UI Elements
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        layout = QtWidgets.QVBoxLayout(central)

        # Video display label
        self.video_label = QtWidgets.QLabel()
        self.video_label.setFixedSize(640, 480)
        self.video_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.video_label)

        # Controls layout
        controls = QtWidgets.QHBoxLayout()
        layout.addLayout(controls)

        # Method selection combo box
        self.method_combo = QtWidgets.QComboBox()
        for entry in self.methods:
            self.method_combo.addItem(entry.name)
        self.method_combo.currentIndexChanged.connect(self.on_method_changed)
        controls.addWidget(QtWidgets.QLabel("Method:"))
        controls.addWidget(self.method_combo)

        # Heart rate label
        self.hr_label = QtWidgets.QLabel("Heart Rate: -- BPM")
        controls.addWidget(self.hr_label)

        # Plot figure
        self.figure = Figure(figsize=(5, 2))
        self.canvas = FigureCanvas(self.figure)
        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel("Samples")
        self.ax.set_ylabel("Amplitude")
        self.line, = self.ax.plot([], [])
        layout.addWidget(self.canvas)

        # Timer for updating frames
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(int(1000 / self.fs))

    def on_method_changed(self, index: int) -> None:
        self.current_method = self.methods[index]
        # Reset method state
        self.current_method.instance.reset()
        # Reset HR label
        self.hr_label.setText("Heart Rate: -- BPM")

    def update_frame(self) -> None:
        ret, frame = self.cap.read()
        if not ret:
            return
        # Flip the frame horizontally for a mirror view
        frame = cv2.flip(frame, 1)
        roi = None
        roi_box = None
        # Detect face
        faces = self.face_detector.detect_faces(frame)
        if faces:
            # Choose the largest face
            face = max(faces, key=lambda b: b[2] * b[3])
            roi, roi_box = extract_forehead_roi(frame, face)
            # Draw bounding boxes
            x, y, w, h = face
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)
            if roi_box:
                rx, ry, rw, rh = roi_box
                cv2.rectangle(frame, (rx, ry), (rx + rw, ry + rh), (0, 255, 0), 2)
        # Update method only when a valid ROI is available.
        if roi is not None and roi.size > 0:
            self.current_method.instance.update(roi)
        hr = self.current_method.instance.get_hr()
        if hr is not None:
            self.hr_label.setText(f"Heart Rate: {hr:.1f} BPM")
        # Update plot
        signal = self.current_method.instance.get_ppg_signal()
        if signal.size > 0:
            self.line.set_data(np.arange(len(signal)), signal)
            self.ax.set_xlim(0, len(signal))
            # Auto-scale y-axis
            min_val = float(np.min(signal))
            max_val = float(np.max(signal))
            if min_val == max_val:
                max_val = min_val + 1e-3
            self.ax.set_ylim(min_val, max_val)
        else:
            self.line.set_data([], [])
        self.canvas.draw_idle()
        # Convert frame to QImage and display
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qimg = QtGui.QImage(
            rgb_frame.data, w, h, bytes_per_line, QtGui.QImage.Format_RGB888
        )
        pixmap = QtGui.QPixmap.fromImage(qimg)
        self.video_label.setPixmap(pixmap)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Release the camera on window close."""
        if self.cap.isOpened():
            self.cap.release()
        super().closeEvent(event)


def main() -> int:
    app = QtWidgets.QApplication(sys.argv)
    window = RPPGApp()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
