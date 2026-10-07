"""Fixed-art 2.5D character: hierarchical bones, eyelids, and prop constraints.

All rendering uses QImage/QPainter. No video, generated frame sequence, NumPy,
decoder subprocess, or background Qt object is required by a rig character.
Coordinates are in the existing 640x360 pet canvas; textures are sampled at 2x.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from pathlib import Path
import weakref

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QTransform


def smooth(value: float) -> float:
    value = min(1., max(0., value))
    return value * value * (3 - 2 * value)


def gate(progress: float) -> float:
    return smooth(progress / .18) * smooth((1 - progress) / .18)


def rotate(point, angle):
    radians = math.radians(angle)
    cosine, sine = math.cos(radians), math.sin(radians)
    return (cosine * point[0] - sine * point[1],
            sine * point[0] + cosine * point[1])


def add(a, b):
    return a[0] + b[0], a[1] + b[1]


def subtract(a, b):
    return a[0] - b[0], a[1] - b[1]


def solve_ik(bone, target, bend):
    """Reach a target with two fixed-length bones; clamp only unreachable goals."""
    shoulder, elbow, wrist = bone
    l1, l2 = math.dist(shoulder, elbow), math.dist(elbow, wrist)
    vector = subtract(target, shoulder)
    original_distance = math.hypot(*vector)
    distance = min(l1 + l2 - 1e-8, max(abs(l1 - l2) + 1e-8, original_distance))
    heading = math.atan2(vector[1], vector[0])
    offset = math.acos(max(-1., min(1., (l1 * l1 + distance * distance - l2 * l2) / (2 * l1 * distance))))
    first = heading + bend * offset
    joint = add(shoulder, (math.cos(first) * l1, math.sin(first) * l1))
    endpoint = add(shoulder, (math.cos(heading) * distance, math.sin(heading) * distance))
    second = math.atan2(endpoint[1] - joint[1], endpoint[0] - joint[0])
    rest_first = math.atan2(elbow[1] - shoulder[1], elbow[0] - shoulder[0])
    rest_second = math.atan2(wrist[1] - elbow[1], wrist[0] - elbow[0])
    normalise = lambda v: math.atan2(math.sin(v), math.cos(v))
    upper = normalise(first - rest_first)
    lower = normalise(second - rest_second - upper)
    return (math.degrees(upper), math.degrees(lower)), (shoulder, joint, endpoint)


def bone_points(bone, angles):
    shoulder, elbow, wrist = bone
    joint = add(shoulder, rotate(subtract(elbow, shoulder), angles[0]))
    endpoint = add(joint, rotate(subtract(wrist, elbow), sum(angles)))
    return shoulder, joint, endpoint


@dataclass
class Prop:
    name: str
    point: tuple[float, float]
    height: float = 35.
    angle: float = 0.
    anchor: tuple[float, float] = (.5, .5)
    behind_hands: bool = True
    opacity: float = 1.


@dataclass
class Pose:
    angles: dict = field(default_factory=lambda: {k: (0., 0.) for k in ("la", "ra", "ll", "rl")})
    head_angle: float = 0.
    head_y: float = 0.
    root_y: float = 0.
    tail_angle: float = 0.
    wing_angle: float = 0.
    emotion: str = "neutral"
    emotion_weight: float = 0.
    eye_l_open: float = 1.
    eye_r_open: float = 1.
    props: list[Prop] = field(default_factory=list)
    contacts: dict = field(default_factory=dict)
    effect: str | None = None
    effect_weight: float = 0.


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
        p = min(1., max(0., seconds / action["seconds"]))
        e = gate(p)
        phase = math.tau * p
        kind = action["kind"]
        variant = int(action.get("variant") or 0) % 3
        wave = math.sin(phase * (1 + variant % 2)) * e
        state = Pose(emotion=action.get("emotion") or "neutral", emotion_weight=e)
        state.tail_angle = 3 * math.sin(phase) * e
        state.wing_angle = 2 * math.sin(phase) * e
        blink = smooth((p - .58) / .025) * smooth((.69 - p) / .025)
        state.eye_l_open = state.eye_r_open = 1 - blink
        state.head_y = .5 * math.sin(phase) * e

        def arms(left, right):
            state.angles["la"] = tuple(a * e for a in left)
            state.angles["ra"] = tuple(a * e for a in right)

        def reach(key, target):
            wrist = self.bones[key][-1]
            target = (wrist[0] + (target[0] - wrist[0]) * e,
                      wrist[1] + (target[1] - wrist[1]) * e)
            angles, points = solve_ik(self.bones[key], target, 1 if key.startswith("l") else -1)
            state.angles[key] = angles
            return points[-1]

        if kind in {"walk", "run", "pace", "float", "drag"}:
            stride = 8 if kind == "run" else 4
            state.angles["ll"] = (stride * wave, 5 * abs(wave))
            state.angles["rl"] = (-stride * wave, -5 * abs(wave))
            arms((12 * wave, -5), (-12 * wave, 5))
            if kind in {"float", "drag"}:
                state.root_y = -8 * e
                state.wing_angle = 7 * wave
                arms((35 + 10 * wave, 10), (-35 + 10 * wave, -10))
        elif kind == "wave":
            arms((0, 0), (-95, 22 * math.sin(phase * 3)))
            state.head_angle = 3 * e
        elif kind == "stretch":
            arms((100, -20), (-100, 20))
            state.head_y -= 2 * e
        elif kind in {"jump", "startled"}:
            arms((48 + 15 * wave, 5), (-48 - 15 * wave, -5))
            state.root_y = -16 * math.sin(math.pi * p) ** 2 * e
            state.wing_angle = 9 * wave
        elif kind in {"shy", "heart", "tickle", "cuddle"}:
            arms((-65, -18 - 10 * wave), (65, 18 + 10 * wave))
            state.head_angle = 3 * e
        elif kind == "angry":
            arms((-22, -42), (22, 42))
            state.head_angle = -3 * wave
        elif kind == "sad":
            arms((18, -8), (-18, 8))
            state.head_angle = 5 * e
            state.head_y += 2 * e
        elif kind == "sleep":
            arms((-20, -15), (20, 15))
            state.eye_l_open = state.eye_r_open = 1 - e
            state.head_angle = 5 * e
        elif kind in {"yawn", "rubeyes", "think", "wink", "nod", "bow", "squat"}:
            if kind in {"yawn", "rubeyes"}:
                reach("ra", (326, 183 if kind == "rubeyes" else 204))
            elif kind == "think":
                reach("ra", (321, 208))
                state.head_angle = -4 * e
            elif kind == "wink":
                state.eye_l_open = 1 - e
            elif kind == "nod":
                state.head_y += 4 * math.sin(math.pi * p * 2) ** 2 * e
                state.head_angle = 3 * wave
            else:
                arms((-32, -18), (32, 18))
                state.root_y = 5 * e
                state.angles["ll"] = (-8 * e, 12 * e)
                state.angles["rl"] = (8 * e, -12 * e)
        elif kind in {"dance", "display"}:
            arms((26 * wave, -15 - 8 * wave), (26 * wave, 15 + 8 * wave))
            state.head_angle = (7 if kind == "display" else 4) * wave
            state.angles["ll"] = (4 * wave, 0)
            state.angles["rl"] = (4 * wave, 0)
        elif kind == "tail":
            state.tail_angle = 12 * math.sin(phase * 2) * e
        elif kind == "kick":
            state.angles["rl"] = (-18 * wave, -15 * e)
            arms((15 * wave, 0), (15 * wave, 0))
        elif kind in {"type", "write", "board", "desk", "sew"}:
            if kind == "type":
                reach("la", (280, 243 + 2 * math.sin(phase * 6)))
                reach("ra", (316, 242 + 2 * math.cos(phase * 6)))
                state.props.append(Prop("laptop", (297, 268), 48, opacity=e))
            elif kind == "write":
                center = (297., 267.)
                page = (309 + 3 * math.sin(phase * 3), 245 + 1.5 * math.sin(phase * 6))
                support = (267., 262.)
                angle, height = -24., 27.
                offset = rotate((0., height * (.975 - .66)), angle)
                hand = reach("ra", subtract(page, offset))
                left = reach("la", support)
                state.props.extend((Prop("notebook", center, 47, opacity=e),
                                    Prop("pen", hand, height, angle, (.5, .66), False, e)))
                state.contacts.update(pen_tip=add(hand, offset), page=page,
                                      left_hand=left, book_support=support)
            else:
                reach("la", (278, 258))
                reach("ra", (312, 252 + 3 * wave))
        elif kind in {"eat", "eat-token"}:
            reach("la", (275, 260))
            rise = math.sin(math.pi * p) ** 2
            hand = reach("ra", (324, 248 - 44 * rise))
            if kind == "eat":
                state.props.append(Prop("chopsticks", hand, 25, -18, (.5, .85), False, e))
            state.head_y += 1.5 * e
        elif kind in {"juggle", "magic", "ghost", "bubbles", "leaves", "animals"}:
            arms((25 + 15 * wave, 15), (-25 + 15 * wave, -15))
            if kind == "juggle":
                for offset in (0., 1 / 3, 2 / 3):
                    q = (p * 2 + offset) % 1
                    state.props.append(Prop("ball", (250 + 95 * q, 239 - 65 * math.sin(math.pi * q)),
                                            13, opacity=e))
            state.effect = "spark" if kind == "magic" else kind
            state.effect_weight = e
        elif kind in {"cube", "game", "flute", "violin", "gift", "present", "lion", "horse", "swing", "snow", "tree", "toycar"}:
            arms((-62, -20 - 7 * wave), (62, 20 + 7 * wave))
            if kind in {"horse", "swing", "toycar"}:
                state.angles["ll"] = (-6 * e, 8 * e)
                state.angles["rl"] = (6 * e, -8 * e)
                state.root_y = 3 * e
        elif kind != "idle":
            # Single-hand inspection, grooming and instrument actions.
            rise = math.sin(math.pi * p) ** 2
            reach("ra", (332 - 14 * rise, 241 - 25 * rise + 2 * wave))
            state.head_angle = -3 * e

        prop = action.get("prop")
        if prop and kind != "write":
            hand = bone_points(self.bones["ra"], state.angles["ra"])[-1]
            if kind in {"cube", "game", "sew", "gift", "present", "cuddle"}:
                layer = self.layers["prop_" + prop]
                height = min(34., 62 / layer["size"][0])
                width = layer["size"][0] * height
                center = (298., 253.)
                reach("la", (center[0] - width * .4, center[1] + height * .18))
                reach("ra", (center[0] + width * .4, center[1] + height * .18))
                state.props.append(Prop(prop, center, height, opacity=e))
            elif kind == "flute":
                reach("la", (286, 208))
                reach("ra", (323, 214))
                state.props.append(Prop(prop, (307, 211), 14, opacity=e))
            elif kind == "violin":
                reach("la", (297, 229))
                hand = reach("ra", (324, 230 + 5 * wave))
                state.props.extend((Prop(prop, (311, 227), 43, -20, opacity=e),
                                    Prop("bow", hand, 46, -28, (.6, .7), False, e)))
            elif kind == "eat":
                state.props.append(Prop(prop, (298, 267), 34, opacity=e))
            elif kind in {"desk", "board", "horse", "swing", "toycar", "snow", "tree", "lion"}:
                point = (298, 293) if kind not in {"snow", "tree", "lion"} else (400, 282)
                state.props.append(Prop(prop, point, 58, opacity=e))
            else:
                anchor = {"balloon": (.5, .95), "kite": (.5, .9), "lantern": (.5, .05),
                          "fan": (.5, .8), "brush": (.6, .45)}.get(kind, (.5, .8))
                state.props.append(Prop(prop, hand, 38, 6 * wave, anchor, False, e))
        state.contacts["tail_root"] = self.tail_root
        state.contacts.setdefault("left_hand", bone_points(self.bones["la"], state.angles["la"])[-1])
        state.contacts["right_hand"] = bone_points(self.bones["ra"], state.angles["ra"])[-1]
        parameters = parameters or {}
        for key in ("eye_l_open", "eye_r_open"):
            if key in parameters:
                setattr(state, key, max(0., min(1., float(parameters[key]))))
        state.head_angle += 3 * max(-1., min(1., float(parameters.get("look_x", 0))))
        state.head_y += 2 * max(-1., min(1., float(parameters.get("look_y", 0))))
        state.tail_angle += max(-15., min(15., float(parameters.get("tail_angle", 0))))
        state.angles["tail"] = (state.tail_angle, 3 * math.sin(phase - .35) * e)
        return state

    def _draw_layer(self, painter, name):
        layer = self.layers[name]
        painter.drawImage(QRectF(*layer["origin"], *layer["size"]), self.images[name])

    def _draw_bone(self, painter, key, angles):
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
            painter.rotate(sum(angles))
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
        self._draw_bone(painter, "ll", state.angles["ll"])
        self._draw_bone(painter, "rl", state.angles["rl"])
        self._draw_layer(painter, "body")
        painter.save()
        painter.translate(self.neck[0], self.neck[1] + state.head_y)
        painter.rotate(state.head_angle)
        painter.translate(-self.neck[0], -self.neck[1])
        emotion = "head_" + state.emotion
        if emotion in self.images and state.emotion != "neutral" and state.emotion_weight > 0:
            # Add premultiplied images in a private head buffer. Drawing the two
            # outlines source-over would thicken their antialiased alpha edges.
            head = QImage(image.size(), image.format())
            head.fill(Qt.GlobalColor.transparent)
            hp = QPainter(head)
            hp.scale(factor, factor)
            hp.setOpacity(1 - state.emotion_weight)
            self._draw_layer(hp, "head_neutral")
            hp.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            hp.setOpacity(state.emotion_weight)
            self._draw_layer(hp, emotion)
            hp.end()
            painter.drawImage(QRectF(0, 0, *self.canvas), head)
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
