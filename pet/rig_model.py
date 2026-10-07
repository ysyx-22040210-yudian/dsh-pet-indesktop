"""Fixed-art 2.5D character: hierarchical bones, eyelids, and prop constraints.

All rendering uses QImage/QPainter. No video, generated frame sequence, NumPy,
decoder subprocess, or background Qt object is required by a rig character.
Coordinates are in the existing 640x360 pet canvas; textures are sampled at 2x.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import weakref

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QTransform

from .rig_motion import (
    Pose as Pose, Prop as Prop, add as add, bone_points as bone_points,
    gate as gate, rotate as rotate, smooth as smooth,
    solve_ik as solve_ik, subtract as subtract, build_pose,
)


_MODELS: weakref.WeakValueDictionary = weakref.WeakValueDictionary()


def load_rig_model(path: Path) -> RigModel:
    path = path.resolve()
    stat = path.stat()
    key = (path, stat.st_mtime_ns, stat.st_size)
    model = _MODELS.get(key)
    if model is None:
        model = _MODELS[key] = RigModel(path)
    return model


class RigModel:
    SUPPORTED_KINDS = frozenset({
        "idle", "think", "walk", "float", "run", "jump", "shy", "angry", "tickle",
        "wave", "drag", "type", "write", "eat-token", "sad", "pace", "inspect",
        "present", "juggle", "board", "eat", "dance", "flower", "animals", "cube",
        "sleep", "desk", "toycar", "squat", "magic", "balloon", "flute", "yawn",
        "bow", "snow", "display", "violin", "startled", "top", "gift", "fan",
        "cuddle", "lantern", "kite", "brush", "mirror", "watergun", "game",
        "bubbles", "tail", "sew", "lion", "swing", "ghost", "leaves", "tree",
        "stretch", "kick", "horse", "wink", "heart", "nod", "rubeyes",
    })

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("schema") != "qilin-rig2d-1":
            raise ValueError("Unsupported rig schema")
        self.canvas = tuple(data["canvas"])
        if self.canvas != (640, 360):
            raise ValueError("Rig must use the pet canvas")
        self.fps = int(data["fps"])
        self.sampling = int(data.get("sampling", 2))
        if not 1 <= self.fps <= 60 or self.sampling not in (1, 2):
            raise ValueError("Invalid rig sampling")
        self.bones = {k: tuple(tuple(p) for p in v) for k, v in data["bones"].items()}
        self.neck = tuple(data["neck"])
        self.tail_root = tuple(data["tail_root"])
        self.wing_root = tuple(data["wing_root"])
        self.eye_rects = data["eye_rects"]
        self.layers = data["layers"]
        self.actions = data["actions"]
        self.images = {}
        for name, layer in self.layers.items():
            image_path = (self.path.parent / layer["file"]).resolve()
            if not image_path.is_relative_to(self.path.parent.resolve()):
                raise ValueError("Rig texture outside model package")
            image = QImage(str(image_path))
            if image.isNull():
                raise ValueError(f"Missing rig texture: {name}")
            self.images[name] = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
        for name, action in self.actions.items():
            if action["kind"] not in self.SUPPORTED_KINDS:
                raise ValueError(f"Unknown rig action: {name}")
            if not math.isfinite(action["seconds"]) or action["seconds"] <= 0:
                raise ValueError(f"Invalid action duration: {name}")
            prop = action.get("prop")
            if prop and "prop_" + prop not in self.layers:
                raise ValueError(f"Missing action prop: {name}")

    def pose(self, action: dict, seconds: float, parameters: dict | None = None) -> Pose:
        return build_pose(self, action, seconds, parameters)

    def _draw_layer(self, painter, name):
        layer = self.layers[name]
        painter.drawImage(QRectF(*layer["origin"], *layer["size"]), self.images[name])

    def _draw_bone(self, painter, key, angles, foot_angle=0.):
        shoulder, elbow, _ = self.bones[key]
        points = bone_points(self.bones[key], angles)
        for name, old, new, angle in ((key + "_upper", shoulder, shoulder, angles[0]),
                                      (key + "_lower", elbow, points[1], sum(angles))):
            painter.save()
            painter.translate(*new)
            painter.rotate(angle)
            painter.translate(-old[0], -old[1])
            self._draw_layer(painter, name)
            painter.restore()
        if key in {"ll", "rl"}:
            painter.save()
            painter.translate(*points[2])
            painter.rotate(foot_angle)
            self._draw_layer(painter, key[0] + "_foot")
            painter.restore()

    def _draw_prop(self, painter, prop):
        if prop.opacity <= 0:
            return
        name = "prop_" + prop.name
        layer = self.layers[name]
        painter.save()
        painter.setOpacity(prop.opacity)
        painter.translate(*prop.point)
        painter.rotate(prop.angle)
        painter.scale(prop.height, prop.height)
        painter.translate(-prop.anchor[0] * layer["size"][0], -prop.anchor[1] * layer["size"][1])
        self._draw_layer(painter, name)
        painter.restore()

    def render(self, action: str | dict, seconds: float, parameters: dict | None = None) -> QImage:
        if isinstance(action, str):
            action = self.actions[action]
        state = self.pose(action, seconds, parameters)
        factor = self.sampling
        image = QImage(self.canvas[0] * factor, self.canvas[1] * factor,
                       QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        painter.scale(factor, factor)
        painter.translate(0, state.root_y)
        self._draw_bone(painter, "tail", state.angles["tail"])
        for name, root, angle in (("wing", self.wing_root, state.wing_angle),):
            painter.save()
            painter.translate(*root)
            painter.rotate(angle)
            self._draw_layer(painter, name)
            painter.restore()
        self._draw_bone(painter, "ll", state.angles["ll"], state.foot_angles["ll"])
        self._draw_bone(painter, "rl", state.angles["rl"], state.foot_angles["rl"])
        self._draw_layer(painter, "body")
        painter.save()
        painter.translate(self.neck[0], self.neck[1] + state.head_y)
        painter.rotate(state.head_angle)
        painter.translate(-self.neck[0], -self.neck[1])
        emotion = "head_" + state.emotion
        if emotion in self.images and state.emotion != "neutral" and state.emotion_weight > 0:
            # QPainter global opacity in Plus mode blends the *result* with the
            # destination, rather than scaling only the source. Weight each
            # texture on transparent first, then add at full opacity. A local
            # head buffer also avoids allocating two full-canvas intermediates.
            neutral = self.images["head_neutral"]
            head = QImage(neutral.size(), image.format())
            head.fill(Qt.GlobalColor.transparent)
            hp = QPainter(head)
            hp.setOpacity(1 - state.emotion_weight)
            hp.drawImage(0, 0, neutral)
            weighted = QImage(head.size(), head.format())
            weighted.fill(Qt.GlobalColor.transparent)
            wp = QPainter(weighted)
            wp.setOpacity(state.emotion_weight)
            wp.drawImage(weighted.rect(), self.images[emotion])
            wp.end()
            hp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            hp.setOpacity(1.)
            hp.drawImage(0, 0, weighted)
            hp.end()
            layer = self.layers["head_neutral"]
            painter.drawImage(QRectF(*layer["origin"], *layer["size"]), head)
        else:
            self._draw_layer(painter, "head_neutral")
        for opened, rect in zip((state.eye_l_open, state.eye_r_open), self.eye_rects):
            if opened >= 1:
                continue
            painter.save()
            x, y, width, height = rect
            painter.setClipRect(QRectF(x, y, width, height * (1 - opened)))
            self._draw_layer(painter, "head_blink")
            painter.restore()
        painter.restore()
        for prop in state.props:
            if prop.behind_hands:
                self._draw_prop(painter, prop)
        for key in ("la", "ra"):
            self._draw_bone(painter, key, state.angles[key])
        for prop in state.props:
            if not prop.behind_hands:
                self._draw_prop(painter, prop)
        if state.effect and state.effect_weight > 0:
            painter.save()
            painter.setOpacity(state.effect_weight)
            painter.setPen(QPen(QColor(250, 183, 86, 160), 1.2))
            p = seconds / action["seconds"]
            for i in range(7):
                q = (p + i / 7) % 1
                point = QPointF(290 + 98 * math.cos(math.tau * (q + i / 7)), 166 - 70 * q)
                painter.drawEllipse(point, 2 + 2 * math.sin(math.pi * q), 2 + 2 * math.sin(math.pi * q))
            painter.restore()
        painter.end()
        return image

    def source_size(self):
        return self.canvas[0] * self.sampling, self.canvas[1] * self.sampling

    def local_transform(self, point, angle) -> QTransform:
        """Editable bone pivot transform for authoring/inspection tools."""
        transform = QTransform()
        transform.translate(*point)
        transform.rotate(angle)
        return transform
