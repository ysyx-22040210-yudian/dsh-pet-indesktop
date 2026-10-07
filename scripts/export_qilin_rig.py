"""Compile existing editable artwork into a fixed 2.5D rig, not video frames.

Authoring-only dependencies: Pillow, NumPy and OpenCV. The desktop renderer
uses only Qt. Input is the existing qilin-pet production directory; approved
notebook/pen artwork is taken from this repository's postprocess assets.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image


def compile_model(source: Path, installed: Path, output: Path) -> None:
    module_path = source / "joint-motion-v1/rig.py"
    spec = importlib.util.spec_from_file_location("qilin_authoring_rig", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.W, module.H = 1280, 720
    module.S *= 2
    module.TX *= 2
    module.TY *= 2
    rig = module.Rig()
    repo = Path(__file__).resolve().parents[1]
    rows = json.loads((source / "joint-motion-v1/actions.json").read_text(encoding="utf-8"))
    by_name = {row["name"]: row for row in rows}
    aliases = {"瑞麟现世": "蓝鲸现世",
               "工作状态-垂头叹气冒汗（失败反馈）": "工作状态-垂头叹气冒汗"}
    actions = {}
    videos = installed / "videos"
    for path in sorted(videos.rglob("*.webm")):
        row = by_name[aliases.get(path.stem, path.stem)]
        actions[path.stem] = {key: row.get(key) for key in
                              ("kind", "emotion", "prop", "variant", "seconds", "effect")}
        actions[path.stem]["folder"] = path.parent.relative_to(videos).as_posix()
        if path.stem == "瑞麟现世":
            actions[path.stem]["prop"] = None
    output.mkdir(parents=True, exist_ok=True)
    layers = {}

    def save(name, pixels, origin=(0, 0), factor=2):
        """Export a cropped native texture with its measured model coordinates."""
        pixels = pixels.copy()
        pixels[pixels[:, :, 3] < 8 / 255] = 0
        alpha = pixels[:, :, 3]
        ys, xs = np.where(alpha > .001)
        assert len(xs), name
        x0, y0 = max(0, xs.min() - 2), max(0, ys.min() - 2)
        x1, y1 = min(alpha.shape[1], xs.max() + 3), min(alpha.shape[0], ys.max() + 3)
        rgba = module.straight(pixels[y0:y1, x0:x1])
        # Filter alpha in premultiplied space; resampling never imports hidden RGB.
        premult = module.premultiply(rgba)
        premult = cv2.GaussianBlur(premult, (3, 3), .38)
        rgba = module.straight(premult)
        path = output / (name + ".png")
        Image.fromarray(rgba).save(path)
        layers[name] = {"file": path.name,
                        "origin": [(origin[0] + x0) / factor, (origin[1] + y0) / factor],
                        "size": [(x1 - x0) / factor, (y1 - y0) / factor],
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    save("body", rig.plate)
    save("head_neutral", rig.head)
    # A reviewed fixed closed-eye texture replaces the old atlas's mismatched
    # facial skin. Only eye regions are registered; all hair/body pixels remain
    # the approved master. This is a model texture, never an action frame stack.
    closed_source = repo / "packaging/rig_sources/qilin-closed-eyes.png"
    closed_rgba = np.array(Image.open(closed_source).convert("RGBA"))
    transform = np.array([[module.S, 0, module.TX], [0, module.S, module.TY]], np.float32)
    closed = cv2.warpAffine(module.premultiply(closed_rgba), transform, (module.W, module.H))
    yy, xx = np.mgrid[:module.H, :module.W]
    mx, my = (xx - module.TX) / module.S, (yy - module.TY) / module.S
    eye_mask = np.zeros((module.H, module.W), np.float32)
    for x0, y0, x1, y1 in ((357, 417, 519, 576), (598, 453, 768, 592)):
        weight = module.smooth((mx - x0) / 12) * module.smooth((x1 - mx) / 12)
        weight *= module.smooth((my - y0) / 12) * module.smooth((y1 - my) / 12)
        eye_mask = np.maximum(eye_mask, weight)
    eye_mask = eye_mask[:, :, None]
    for name, (texture, mask) in rig.expressions.items():
        head = rig.head * (1 - mask) + texture * mask
        if name in ("blink", "happy"):
            head = head * (1 - eye_mask) + closed * eye_mask
        save("head_" + name, head)
    # Keep all original limb texels at 2x model resolution. Two rounded,
    # overlapping joint caps keep shoulders/elbows/knees closed during rotation.
    bones = {}
    for key, limb in rig.limbs.items():
        bones[key] = [point.tolist() for point in
                      (limb.pivot / 2, limb.joint / 2, limb.end / 2)]
        yy, xx = np.mgrid[:limb.tex.shape[0], :limb.tex.shape[1]]
        points = np.stack((xx + limb.left, yy + limb.top), -1)
        along = (points - limb.joint) @ limb.axis
        radius = 18 if key.endswith("a") else 10
        cap = np.sum((points - limb.joint) ** 2, -1) < radius ** 2
        upper = (along <= 0) | cap
        lower = (along >= 0) | cap
        save(key + "_upper", limb.tex * upper[:, :, None], (limb.left, limb.top))
        save(key + "_lower", limb.tex * lower[:, :, None], (limb.left, limb.top))
    for side, foot in rig.feet.items():
        # Feet use a local coordinate system around the ankle.
        anchor = foot.anchor * np.array((foot.tex.shape[1], foot.tex.shape[0]))
        save(side + "_foot", foot.tex, -anchor, factor=1 / module.S * 2)
    tail_sprite, tail_pivot = rig.accessories["tail"]
    # Reject clothing pixels at the attachment: the tail starts behind the hip.
    tail = tail_sprite.tex.copy()
    th, tw = tail.shape[:2]
    tail[:int(th * .20), :int(tw * .42)] = 0
    anchor = tail_sprite.anchor * np.array((tw, th))
    tail_factor = 1 / module.S * 2
    tail_origin = tail_pivot / 2 * tail_factor - anchor
    bones["tail"] = [[349.4, 277.], [400., 293.], [414., 250.]]
    yy, xx = np.mgrid[:th, :tw]
    gx, gy = (xx + tail_origin[0]) / tail_factor, (yy + tail_origin[1]) / tail_factor
    cap = (gx - 400) ** 2 + (gy - 293) ** 2 < 9 ** 2
    upper, lower = (gx <= 400) | cap, (gx >= 400) | cap
    save("tail_upper", tail * upper[:, :, None], tail_origin, factor=tail_factor)
    save("tail_lower", tail * lower[:, :, None], tail_origin, factor=tail_factor)
    wing, wing_pivot = rig.accessories["wing"]
    anchor = wing.anchor * np.array((wing.tex.shape[1], wing.tex.shape[0]))
    save("wing", wing.tex, -anchor, factor=1 / module.S * 2)
    wanted_props = {a["prop"] for a in actions.values() if a.get("prop")}
    wanted_props.update({"laptop", "chopsticks", "ball", "bow"})
    for name, sprite in rig.props.items():
        if name not in wanted_props:
            continue
        height = sprite.tex.shape[0]
        save("prop_" + name, sprite.tex, factor=height)

    for name, filename in (("notebook", "qilin-notebook-20261007.png"),
                           ("pen", "qilin-note-pen-20261007.png")):
        rgba = np.array(Image.open(repo / "packaging/character_postprocess/assets" / filename).convert("RGBA"))
        ys, xs = np.where(rgba[:, :, 3] > 8)
        rgba = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        # Normalise props to logical height 1. Grip/tip use this cropped artwork.
        save("prop_" + name, module.premultiply(rgba), factor=rgba.shape[0])

    # Contact landmarks are measured on the fixed fingertip art, not the wrist.
    layers["la_lower"]["touch_point"] = [230.54, 252.44]
    layers["ra_lower"]["touch_point"] = [364.3, 257.96]
    layers["prop_laptop"].update({
        "render_style": "laptop-mesh-1",
        "placement": {"point": [298., 248.], "height": 55.},
        "lid": [[.075, .07], [.91, .07], [.91, .60], [.075, .60]],
        "stand": [
            [[.01, .96], [.99, .96], [.99, 1.03], [.01, 1.03]],
            [[.025, 1.03], [.105, 1.03], [.10, 1.994], [.035, 1.994]],
            [[.89, 1.03], [.97, 1.03], [.96, 1.994], [.90, 1.994]],
        ],
        "keyboard": {
            "corners": [[.075, .64], [.91, .64], [.995, .95], [.01, .95]],
            "hand_positions": {"la": [.28, .32], "ra": [.72, .32]},
        },
    })
    model = {"schema": "qilin-rig2d-1", "motion_revision": "natural-rig-2", "canvas": [640, 360], "fps": 30,
             "sampling": 2, "neck": (rig.neck / 2).tolist(), "bones": bones,
             "tail_root": bones["tail"][0], "wing_root": (wing_pivot / 2).tolist(),
             "eye_rects": [[module.TX / 2 + x * module.S / 2,
                             module.TY / 2 + y * module.S / 2,
                             w * module.S / 2, h * module.S / 2]
                            for x, y, w, h in ((357, 417, 162, 159), (598, 453, 170, 139))],
             "layers": layers, "actions": actions,
             "authoring": {"method": "Fixed native art, hierarchical two-bone rig and Qt parameters",
                           "rig_source_sha256": hashlib.sha256(module_path.read_bytes()).hexdigest(),
                           "master_sha256": hashlib.sha256(module.MASTER.read_bytes()).hexdigest(),
                           "closed_eye_source_sha256": hashlib.sha256(closed_source.read_bytes()).hexdigest(),
                           "reference": "Chibi proportions and independent eye/blink parameters; no third-party model assets"}}
    (output / "model.json").write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = json.loads((videos / "manifest.json").read_text(encoding="utf-8"))
    manifest.update({"version": "3.0.2-keyboard-contact", "name": "麒麟", "renderer": "rig2d", "rig": "../rig/model.json", "fps": 30,
                     "description": "固定麒麟分层模型：实时骨骼、眼睑参数及道具接触约束。"})
    manifest["production"] = {"runtime": "Qt QPainter rig2d; no video decoding for this character",
                              "actions": len(actions), "layers": len(layers),
                              "sampling": 2, "limitations": "2.5D front/three-quarter pose; no complete 3D back view"}
    target = output.parent / "videos"
    target.mkdir(exist_ok=True)
    (target / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output.parent / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"actions": len(actions), "layers": len(layers), "model": str(output / "model.json")}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    compile_model(options.source, options.installed, options.output)
