"""Deterministic joint-space performances and physical support for the Qilin rig.

The generic IK solver is separate from the motion policy: animation never sends
a resting hand on a straight line through its shoulder's folded singularity.
Each performance approaches a safe pose, holds it, and settles back to rest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math


def smooth(value: float) -> float:
    """Quintic easing with zero velocity and acceleration at both joins."""
    value = min(1., max(0., value))
    return value ** 3 * (10 + value * (-15 + 6 * value))


def gate(progress: float) -> float:
    return smooth(progress / .22) * smooth((1 - progress) / .22)


def activity(progress: float, start=.28, end=.72) -> float:
    return smooth((progress - start) / .07) * smooth((end - progress) / .07)


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
    """Reach with two fixed-length bones; preserve the public geometric contract."""
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


def safe_arm(key, angles):
    """Keep the authored shoulder branch and anatomical elbow bend direction."""
    side = 1 if key == "la" else -1
    upper, lower = angles[0] * side, angles[1] * side
    return side * min(135., max(-65., upper)), side * min(0., max(-132., lower))


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
    foot_angles: dict = field(default_factory=lambda: {"ll": 0., "rl": 0.})
    planted_feet: tuple[str, ...] = ("ll", "rl")
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


def build_pose(model, action: dict, seconds: float, parameters: dict | None = None) -> Pose:
    p = min(1., max(0., seconds / action["seconds"]))
    e, work = gate(p), activity(p)
    kind, prop = action["kind"], action.get("prop")
    phase = math.tau * p
    state = Pose(emotion=action.get("emotion") or "neutral", emotion_weight=e)
    # Small downward breathing lets near-extended legs keep their ground reach.
    breath = .24 * (1 - math.cos(phase)) * e
    state.root_y = breath
    state.head_y = -.18 * (1 - math.cos(phase)) * e
    state.tail_angle = 1.3 * math.sin(phase - .2) * e
    state.wing_angle = .8 * math.sin(phase - .35) * e
    blink = smooth((p - .59) / .03) * smooth((.70 - p) / .04)
    state.eye_l_open = state.eye_r_open = 1 - blink

    def arms(left, right):
        for key, goal in (("la", left), ("ra", right)):
            state.angles[key] = tuple(a * e for a in safe_arm(key, goal))

    def hand(key):
        return bone_points(model.bones[key], state.angles[key])[-1]

    def reach(key, target):
        goal, _ = solve_ik(model.bones[key], target, 1 if key == "la" else -1)
        # Interpolate the safe joint pose, never a hand line crossing the shoulder.
        state.angles[key] = tuple(a * e for a in safe_arm(key, goal))
        return hand(key)

    def held(name, key="ra", height=38., angle=0., anchor=(.5, .8)):
        item = Prop(name, hand(key), height, angle, anchor, False, e)
        state.props.append(item)
        state.contacts[name + "_grip"] = item.point
        return item

    def two_hands(name):
        layer = model.layers["prop_" + name]
        height = min(34., 62 / layer["size"][0])
        width = layer["size"][0] * height
        center = (298., 253.)
        reach("la", (center[0] - width * .4, center[1] + height * .18))
        right = reach("ra", (center[0] + width * .4, center[1] + height * .18))
        # The object travels with its gripping hand throughout preparation/return.
        point = subtract(right, (width * .4, height * .18))
        state.props.append(Prop(name, point, height, opacity=e))
        state.contacts[name + "_grip"] = right
        state.contacts[name + "_support"] = add(point, (-width * .4, height * .18))

    if kind in {"walk", "run", "pace"}:
        swing = math.sin(phase * (2 if kind == "run" else 1)) * e
        arms((7 * swing, -6), (7 * swing, 6))
    elif kind in {"float", "drag"}:
        state.root_y = -8 * e
        arms((42, -16), (-42, 16))
        state.wing_angle = 3 * math.sin(phase * 2) * e
    elif kind == "wave":
        arms((0, 0), (-85, 32 + 9 * math.sin(phase * 2) * work))
        state.head_angle = 2 * e
    elif kind == "stretch":
        arms((100, -24), (-100, 24))
        state.head_y -= 1.5 * e
    elif kind in {"jump", "startled"}:
        arms((40, -18), (-40, 18))
        air = math.sin(math.pi * min(1., max(0., (p - .24) / .48))) ** 2
        prepare = smooth(p / .16) * smooth((.26 - p) / .1)
        land = smooth((p - .69) / .1) * smooth((.94 - p) / .15)
        state.root_y = 2 * prepare - (14 if kind == "jump" else 6) * air + 2 * land
    elif kind in {"shy", "heart", "tickle", "cuddle"}:
        arms((-28, -50), (28, 50))
        state.head_angle = 2 * e
    elif kind == "angry":
        arms((-20, -42), (20, 42))
        state.head_angle = -3 * e
    elif kind == "sad":
        arms((12, -8), (-12, 8))
        state.head_angle = 4 * e
        state.head_y += 1.2 * e
    elif kind == "sleep":
        arms((-15, -16), (15, 16))
        state.eye_l_open = state.eye_r_open = 1 - e
        state.head_angle = 4 * e
    elif kind in {"yawn", "rubeyes", "think", "wink", "nod", "bow", "squat"}:
        if kind in {"yawn", "rubeyes", "think"}:
            if kind == "think" and action.get("folder") == "turn":
                state.head_angle = 4 * math.sin(phase) * work
            else:
                reach("ra", (350, 182) if kind == "rubeyes" else (348, 217))
                state.head_angle = -2 * e
            if kind == "rubeyes":
                # One small rub at the cheek, without circling the upper arm.
                upper, lower = state.angles["ra"]
                state.angles["ra"] = (upper, lower + 1.5 * math.sin(phase * 2) * work)
        elif kind == "wink":
            state.eye_l_open = 1 - e
        elif kind == "nod":
            nod = smooth((p - .22) / .18) * smooth((.72 - p) / .2)
            state.head_angle = 3 * nod
            state.head_y += 1.5 * nod
        else:
            arms((-26, -22), (26, 22))
            state.root_y = (4 if kind == "squat" else 2.5) * e + breath
            state.head_angle = 4 * e if kind == "bow" else 0.
    elif kind in {"dance", "display"}:
        sway = math.sin(phase) * work
        arms((16 * sway, -20), (16 * sway, 20))
        state.head_angle = (3 if kind == "display" else 2) * sway
        state.root_y += .6 * (1 - math.cos(phase * 2)) * work
    elif kind == "tail":
        # Two intentional taps; the rest of the body does not oscillate with them.
        tap = smooth((p - .23) / .1) * smooth((.45 - p) / .12)
        tap += smooth((p - .55) / .1) * smooth((.79 - p) / .14)
        state.tail_angle = 6 * tap
    elif kind == "kick":
        arms((8, -8), (-8, 8))
    elif kind in {"type", "write", "board", "desk", "sew"}:
        stroke = math.sin(phase * 3) * work
        if kind == "type":
            reach("la", (280, 245 + .8 * stroke))
            reach("ra", (316, 244 - .8 * stroke))
            state.props.append(Prop("laptop", (297, 268), 48, opacity=e))
        elif kind == "write":
            center = (297., 267.)
            page = (309 + 2 * stroke, 245 + .6 * math.sin(phase * 6) * work)
            support = (267., 262.)
            angle, height = -24., 27.
            offset = rotate((0., height * (.975 - .66)), angle)
            right = reach("ra", subtract(page, offset))
            left = reach("la", support)
            state.props.extend((Prop("notebook", center, 47, opacity=e),
                                Prop("pen", right, height, angle, (.5, .66), False, e)))
            state.contacts.update(pen_tip=add(right, offset), page=page,
                                  left_hand=left, book_support=support)
        else:
            reach("la", (278, 258))
            reach("ra", (314, 252 + stroke))
    elif kind in {"eat", "eat-token"}:
        reach("la", (275, 260))
        reach("ra", (348, 217) if kind == "eat" else (343, 233))
        state.head_angle = -1.5 * e
        if kind == "eat":
            held("chopsticks", height=42, angle=-35, anchor=(.5, .86))
    elif kind in {"juggle", "magic", "ghost", "bubbles", "leaves", "animals"}:
        arms((18, -18), (-18, 18))
        if kind == "juggle":
            for offset in (0., 1 / 3, 2 / 3):
                q = (p * 2 + offset) % 1
                state.props.append(Prop("ball", (250 + 95 * q, 239 - 65 * math.sin(math.pi * q)),
                                        13, opacity=e))
        state.effect = "spark" if kind == "magic" else kind
        state.effect_weight = e
    elif kind in {"cube", "game", "flute", "violin", "gift", "present", "lion", "horse", "swing", "snow", "tree", "toycar"}:
        arms((-26, -48), (26, 48))
        if kind in {"horse", "swing", "toycar"}:
            state.root_y = 3 * e + breath
    elif kind != "idle":
        # Grooming and inspection use an outer approach with a stable hold.
        target = (348, 224) if kind in {"flower", "fan", "brush", "mirror", "balloon"} else (333, 243)
        reach("ra", target)
        state.head_angle = -2 * e
        if kind in {"fan", "brush"}:
            upper, lower = state.angles["ra"]
            state.angles["ra"] = (upper, lower + 3 * math.sin(phase * 2) * work)

    if prop and kind not in {"write", "juggle"}:
        if kind in {"cube", "game", "sew", "gift", "present", "cuddle"}:
            two_hands(prop)
        elif kind == "flute":
            left = reach("la", (281, 245))
            right = reach("ra", (348, 211))
            # This fixed diagonal texture has two grip points along its shaft.
            ratio = model.layers["prop_" + prop]["size"][0]
            local = (.66 * ratio, -.66)
            vector = subtract(right, left)
            height = math.hypot(*vector) / math.hypot(*local)
            angle = math.degrees(math.atan2(vector[1], vector[0]) - math.atan2(local[1], local[0]))
            state.props.append(Prop(prop, left, height, angle, (.18, .82), True, e))
            state.contacts.update(flute_left=left, flute_right=right)
        elif kind == "violin":
            left = reach("la", (280, 247))
            reach("ra", (334, 247 + math.sin(phase * 2) * work))
            state.props.append(Prop(prop, left, 43, -20, (.22, .72), True, e))
            held("bow", height=46, angle=-28, anchor=(.6, .7))
        elif kind == "eat":
            held(prop, "la", 34., anchor=(.18, .45)).behind_hands = True
        elif kind in {"desk", "board", "horse", "swing", "toycar", "snow", "tree", "lion"}:
            point = (298, 293 - state.root_y) if kind not in {"snow", "tree", "lion"} else (400, 282 - state.root_y)
            state.props.append(Prop(prop, point, 58, opacity=e))
        else:
            anchor = {"balloon": (.5, .95), "kite": (.5, .9), "lantern": (.5, .05),
                      "fan": (.5, .8), "brush": (.6, .45)}.get(kind, (.5, .8))
            held(prop, height=50 if kind == "eat-token" else 38,
                 angle=-28 if kind == "eat-token" else 0., anchor=anchor)

    # Ground targets are in canvas/world space, solved against the moving pelvis.
    planted = []
    for key, contact in (("ll", "left_foot"), ("rl", "right_foot")):
        ankle = model.bones[key][-1]
        target = ankle
        lifted = False
        if kind in {"walk", "run", "pace"}:
            stride = math.sin(phase * (2 if kind == "run" else 1)) * e
            lift = max(0., stride if key == "ll" else -stride)
            target = add(ankle, ((2 if key == "ll" else -2) * lift ** 2,
                                 -(4 if kind == "run" else 2.5) * lift ** 2))
            lifted = lift > 1e-7
            state.foot_angles[key] = (-3 if key == "ll" else 3) * lift
        elif kind == "kick" and key == "rl":
            lift = smooth((p - .22) / .15) * smooth((.72 - p) / .2)
            target = add(ankle, (6 * lift, -5 * lift))
            lifted = lift > 1e-7
            state.foot_angles[key] = -8 * lift
        if kind in {"float", "drag"}:
            state.angles[key] = ((-5 if key == "ll" else 5) * e, (8 if key == "ll" else -8) * e)
            lifted = True
        elif kind in {"jump", "startled"} and state.root_y < 0:
            # Curl grows with the jump height, so takeoff/landing cannot switch
            # the knee abruptly to a fully posed airborne leg.
            curl = smooth(-state.root_y / (14 if kind == "jump" else 6))
            state.angles[key] = ((-5 if key == "ll" else 5) * curl,
                                 (8 if key == "ll" else -8) * curl)
            lifted = True
        elif e > 0:
            angles, _ = solve_ik(model.bones[key], subtract(target, (0., state.root_y)), 1)
            state.angles[key] = angles
        state.contacts[contact] = add(bone_points(model.bones[key], state.angles[key])[-1], (0., state.root_y))
        if not lifted:
            planted.append(key)
    state.planted_feet = tuple(planted)
    state.contacts["tail_root"] = model.tail_root
    state.contacts.setdefault("left_hand", hand("la"))
    state.contacts["right_hand"] = hand("ra")
    parameters = parameters or {}
    for key in ("eye_l_open", "eye_r_open"):
        if key in parameters:
            setattr(state, key, max(0., min(1., float(parameters[key]))))
    state.head_angle += 3 * max(-1., min(1., float(parameters.get("look_x", 0))))
    state.head_y += 2 * max(-1., min(1., float(parameters.get("look_y", 0))))
    state.tail_angle += max(-15., min(15., float(parameters.get("tail_angle", 0))))
    state.angles["tail"] = (state.tail_angle, -.4 * state.tail_angle)
    return state
