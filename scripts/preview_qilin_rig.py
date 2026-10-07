"""Exercise real PetWindow actions and save native window evidence, in isolation."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication
from pet.config import Config
from pet.library import MovieLibrary
from pet.window import PetWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--speed", type=float, default=1.)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--name")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows" if sys.platform == "win32" else "offscreen")
    app = QApplication([])
    config = Config(base=args.out / "isolated-config")
    config.data.update({"character": "qilin", "scale": .85, "no_move": True,
                        "lock_position": True, "collision_enabled": False,
                        "self_talk_enabled": False, "proactive_enabled": False,
                        "click_talk_enabled": False, "voice_chime_enabled": False,
                        "animation_gap_seconds": 60, "predictive_prewarm_enabled": False,
                        "dynamic_island": {"enabled": False}, "playback_speed": args.speed})
    lib = MovieLibrary(character_id="qilin", asset_dir=args.character / "videos", prewarm_enabled=False)
    pet = PetWindow(lib, config)
    pet.move(100, 100)
    pet.show()
    pet.facing = "left"
    selected = ["待机呼吸休闲", "点击回应-傲娇生气", "轻快记录", "原地小憩沉眠",
                "超大伸懒腰", "被鼠标拖拽悬空反馈", "用龙尾拍打地面", "写代码",
                "螃蟹走路", "优雅国风舞", "小幅度原地360度旋转展示", "瑞麟现世"]
    names = [args.name] if args.name else (lib.names() if args.full else selected)[args.start:]
    records = []
    try:
        for offset, name in enumerate(names):
            index = args.start + offset
            clip = lib.movie(name)
            clip.set_playback_speed(args.speed)
            phases = {0, round((clip.frameCount() - 1) * .2),
                      round((clip.frameCount() - 1) * .4),
                      round((clip.frameCount() - 1) * .625),
                      round((clip.frameCount() - 1) * .8)}
            samples, intervals, errors = [], [], []
            clock = [None]
            last_frame = [-1]
            loop = QEventLoop()
            timed_out = []
            timer = QTimer()
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: (timed_out.append(True), loop.quit()))

            def frame(n):
                last_frame[0] = n
                now = time.perf_counter()
                if clock[0] is not None and n > 0:
                    intervals.append((now - clock[0]) * 1000)
                clock[0] = now
                if n in phases and pet.anim == name and clip.currentFrameNumber() == n:
                    phases.remove(n)
                    pet._rebuild_frame()
                    pet.update()
                    target = args.out / f"{index:03d}-{n:03d}.png"
                    assert pet.grab().save(str(target))
                    samples.append({"path": str(target), "frame": n,
                                    "position": [pet.x(), pet.y()],
                                    "dpr": pet.devicePixelRatioF(), "scale": pet.scale,
                                    "binary_mask_empty": pet.mask().isEmpty()})
                if n == clip.frameCount() - 1:
                    loop.quit()

            # Observe newly-created clips before the window's final-frame slot.
            clip.frameChanged.connect(frame)
            clip.errorOccurred.connect(errors.append)
            pet._cancel_animation_gap()
            assert pet._switch(name)
            pet.playback_speed = args.speed
            clip.set_playback_speed(args.speed)
            timer.start(max(8000, int(clip.duration() * 1000 + 5000)))
            loop.exec()
            timer.stop()
            clip.frameChanged.disconnect(frame)
            clip.errorOccurred.disconnect(errors.append)
            clip.stop()
            record = {"name": name, "frames": clip.frameCount(), "errors": errors,
                      "timed_out": bool(timed_out), "samples": samples,
                      "median_interval_ms": statistics.median(intervals) if intervals else None,
                      "max_interval_ms": max(intervals) if intervals else None}
            record.update(last_observed_frame=last_frame[0], running=clip._running,
                          active_timer=clip._timer.isActive(), current_frame=clip.currentFrameNumber(),
                          active_animation=pet.anim, visible=pet.isVisible(),
                          hidden_paused=pet._hidden_paused)
            records.append(record)
            (args.out / "records.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps({"index": index, "name": name, "samples": len(samples),
                              "timeout": bool(timed_out), "errors": errors}, ensure_ascii=False), flush=True)
            if timed_out or errors:
                return 1
        print(json.dumps({"actions": len(records), "renderer": lib.media_type,
                          "platform": app.platformName(), "speed": args.speed}, ensure_ascii=False), flush=True)
        return 0
    finally:
        pet.close()
        lib.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
