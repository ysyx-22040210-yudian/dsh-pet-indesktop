"""GUI-thread adapter from a live parameter rig to the pet clip contract."""
from __future__ import annotations

import math
import time

from PySide6.QtCore import QObject, QTimer, Qt, Signal
from PySide6.QtGui import QImage, QPixmap

from .rig_model import RigModel


class RigClip(QObject):
    frameChanged = Signal(int)
    finished = Signal()
    errorOccurred = Signal(str)

    def __init__(self, model: RigModel, action: dict, parent: QObject | None = None):
        super().__init__(parent)
        self.model = model
        self.action = action
        self.path = model.path
        self.playback_speed = 1.
        self._parameters = {}
        self.render_revision = 0
        self._frame = 0
        self._image = QImage()
        self._running = False
        self._closed = False
        self._generation = 0
        self._started = 0.
        self._soft_parked = False
        self.decode_throttle_divisor = 1
        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.setInterval(max(4, round(1000 / model.fps)))
        self._timer.timeout.connect(self._tick)

    def frameCount(self):
        return max(2, math.ceil(self.action["seconds"] * self.model.fps) + 1)

    def duration(self):
        return self.action["seconds"] / self.playback_speed

    def currentFrameNumber(self):
        return self._frame

    def currentTimeSeconds(self):
        return self._frame / (self.frameCount() - 1) * self.duration()

    def _source_time(self):
        return self._frame / (self.frameCount() - 1) * self.action["seconds"]

    def currentImage(self):
        if self._image.isNull() and not self._closed:
            self._image = self.model.render(self.action, self._source_time(), self._parameters)
        return self._image

    def currentPixmap(self):
        return QPixmap.fromImage(self.currentImage())

    def jumpToFrame(self, frame_index):
        if self._closed:
            return False
        self._generation += 1
        self._frame = max(0, min(self.frameCount() - 1, int(frame_index)))
        self._image = QImage()
        if self._running:
            self._started = time.monotonic() - self._source_time() / self.playback_speed
        self.frameChanged.emit(self._frame)
        return True

    def start(self):
        if self._closed:
            return False
        if self._running:
            return True
        if self._frame == self.frameCount() - 1:
            self._frame = 0
            self._image = QImage()
        self._generation += 1
        self._running = True
        self._started = time.monotonic() - self._source_time() / self.playback_speed
        self._timer.start()
        self.frameChanged.emit(self._frame)
        return True

    def stop(self):
        self._generation += 1
        self._running = False
        self._timer.stop()

    def _tick(self):
        if not self._running or self._closed:
            return
        generation = self._generation
        seconds = (time.monotonic() - self._started) * self.playback_speed
        progress = min(1., max(0., seconds / self.action["seconds"]))
        frame = min(self.frameCount() - 1, int(progress * (self.frameCount() - 1)))
        if frame != self._frame:
            self._frame = frame
            self._image = QImage()
            self.frameChanged.emit(frame)
        # PetWindow may restart or switch synchronously on the final frame.
        if generation == self._generation and self._running and progress >= 1:
            self.stop()
            self.finished.emit()

    def set_playback_speed(self, speed):
        source_time = (time.monotonic() - self._started) * self.playback_speed if self._running else self._source_time()
        self.playback_speed = max(.1, min(20., float(speed)))
        if self._running:
            self._started = time.monotonic() - source_time / self.playback_speed

    def set_parameter(self, name, value):
        if name not in {"eye_l_open", "eye_r_open", "look_x", "look_y", "tail_angle"}:
            raise ValueError(f"Unknown rig parameter: {name}")
        value = float(value)
        if not math.isfinite(value):
            raise ValueError("Rig parameter must be finite")
        self._parameters[name] = value
        self.render_revision += 1
        self._image = QImage()
        self.frameChanged.emit(self._frame)

    def clear_display_frame(self):
        self._image = QImage()

    def set_throttle_fps(self, fps):
        interval = 1000 / min(self.model.fps, float(fps)) if fps and fps > 0 else 1000 / self.model.fps
        self._timer.setInterval(max(4, round(interval)))

    def set_decode_throttle(self, divisor):
        self.decode_throttle_divisor = max(1, int(divisor))
        self.set_throttle_fps(self.model.fps / self.decode_throttle_divisor)

    def warm_meta(self):
        return

    def warm_first_frame(self):
        # Fixed textures are already resident. This method deliberately never
        # paints, touches QPixmap or mutates display slots on warm worker threads.
        return

    def cleanup(self):
        self.stop()
        self._closed = True
        self._image = QImage()
