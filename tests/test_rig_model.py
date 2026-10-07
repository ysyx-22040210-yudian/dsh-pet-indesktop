"""Real layered model, contact constraints, and GUI playback lifecycle."""
from pathlib import Path
import math

import pytest
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from pet.rig_model import RigModel, solve_ik
from pet.rig_clip import RigClip
from pet.library import MovieLibrary

MODEL = Path(__file__).resolve().parents[1] / "assets/characters/qilin/rig/model.json"


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def model(app):
    return RigModel(MODEL)


def test_model_covers_requested_actions_without_video(model):
    assert len(model.actions) == 105
    assert "左转奔跑" not in model.actions
    for action in model.actions.values():
        assert action["kind"] in model.SUPPORTED_KINDS
        if action.get("prop"):
            assert "prop_" + action["prop"] in model.layers
    assert model.canvas == (640, 360)


def test_every_action_enters_and_leaves_same_pose(model):
    reference = model.render("待机呼吸休闲", 0)
    for name, action in model.actions.items():
        assert model.render(name, 0) == reference, name
        assert model.render(name, action["seconds"]) == reference, name


@pytest.mark.parametrize("target", [(270, 230), (330, 232), (1000, -300), (323, 212)])
def test_two_bone_ik_preserves_lengths_and_reachable_target(model, target):
    bone = model.bones["ra"]
    angles, points = solve_ik(bone, target, -1)
    assert all(math.isfinite(a) for a in angles)
    for i in (0, 1):
        assert math.dist(points[i], points[i + 1]) == pytest.approx(
            math.dist(bone[i], bone[i + 1]), abs=1e-8,
        )
    distance = math.dist(bone[0], target)
    lengths = [math.dist(bone[i], bone[i + 1]) for i in (0, 1)]
    if abs(lengths[0] - lengths[1]) < distance < sum(lengths):
        assert math.dist(points[-1], target) < 1e-7


def test_writing_pen_tip_and_supporting_hand_contact(model):
    action = model.actions["轻快记录"]
    for fraction in (.23, .4, .55, .72):
        pose = model.pose(action, action["seconds"] * fraction)
        assert math.dist(pose.contacts["pen_tip"], pose.contacts["page"]) < .02
        assert math.dist(pose.contacts["left_hand"], pose.contacts["book_support"]) < .02


def test_tail_root_remains_at_pelvis(model):
    action = model.actions["用龙尾拍打地面"]
    roots = [model.pose(action, action["seconds"] * p).contacts["tail_root"]
             for p in (0, .15, .3, .5, .7, .9, 1)]
    assert all(math.dist(roots[0], point) < 1e-9 for point in roots)


def test_closed_eyes_cover_iris_and_can_be_controlled_independently(model):
    name = "待机呼吸休闲"
    opened = model.render(name, 0)
    closed = model.render(name, 0, {"eye_l_open": 0, "eye_r_open": 0})
    wink = model.render(name, 0, {"eye_l_open": 0, "eye_r_open": 1})
    for index, rect in enumerate(model.eye_rects):
        x, y, w, h = rect
        region = (round(x * 2), round(y * 2), round(w * 2), round(h * 2))
        assert opened.copy(*region) != closed.copy(*region)
        assert wink.copy(*region) == (closed if index == 0 else opened).copy(*region)
        # Measure the amber iris area rather than mistaking a dark closed lash
        # for an unclosed eye. Small lash highlights may also be amber.
        amber = []
        for image in (opened, closed):
            count = 0
            for py in range(int((y + h * .45) * 2), int((y + h * .85) * 2)):
                for px in range(int((x + w * .32) * 2), int((x + w * .68) * 2)):
                    color = image.pixelColor(px, py)
                    r, g, b = color.red(), color.green(), color.blue()
                    count += r > 130 and g > 60 and b < 100 and r > g * 1.15
            amber.append(count)
        assert amber[0] > 100
        assert amber[1] < amber[0] * .05


def test_clip_restart_finish_stop_and_cleanup_use_real_event_loop(model, app):
    action = dict(model.actions["点击回应-傲娇生气"], seconds=.12)
    clip = RigClip(model, action)
    ended = []
    clip.finished.connect(lambda: ended.append(clip.currentFrameNumber()))
    loop = QEventLoop()
    clip.finished.connect(loop.quit)
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    try:
        for _ in range(2):
            clip.jumpToFrame(0)
            assert clip.start()
            timeout.start(6000)
            loop.exec()
            timeout.stop()
            assert ended[-1] == clip.frameCount() - 1
        assert len(ended) == 2
        clip.start()
        clip.stop()
        assert not clip._timer.isActive()
        clip.cleanup()
        assert clip.start() is False
    finally:
        timeout.stop()
        clip.cleanup()


def test_last_frame_switch_does_not_emit_stale_finished(model, app):
    clip = RigClip(model, dict(model.actions["待机呼吸休闲"], seconds=.12))
    ended = []
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)

    def on_frame(n):
        if n == clip.frameCount() - 1:
            clip.stop()
            clip.jumpToFrame(0)
            loop.quit()

    clip.frameChanged.connect(on_frame)
    clip.finished.connect(lambda: ended.append(True))
    try:
        clip.start()
        timeout.start(6000)
        loop.exec()
        assert clip.currentFrameNumber() == 0
        assert not ended
    finally:
        timeout.stop()
        clip.cleanup()


def test_library_selects_model_and_never_spawns_decode_warmers(model, app, monkeypatch):
    import pet.library as library_module
    lib = MovieLibrary(character_id="qilin", asset_dir=MODEL.parent.parent / "videos")
    monkeypatch.setattr(library_module.threading, "Thread",
                        lambda *a, **k: pytest.fail("model spawned media warmer"))
    try:
        assert lib.media_type == "rig2d"
        assert isinstance(lib.movie("待机呼吸休闲"), RigClip)
        lib.schedule_high_priority_warm()
        lib.schedule_low_priority_warm()
        lib.warm_predicted("轻快记录")
        assert not lib._low_warm_timer.isActive()
        assert not lib.representative_image("轻快记录").isNull()
    finally:
        lib.shutdown()


def test_paused_pet_repaints_live_parameters_at_same_frame(model, app, tmp_path):
    from pet.config import Config
    from pet.window import PetWindow
    config = Config(base=tmp_path)
    config.data.update({"character": "qilin", "scale": .85, "no_move": True,
                        "collision_enabled": False, "self_talk_enabled": False,
                        "proactive_enabled": False, "voice_chime_enabled": False,
                        "dynamic_island": {"enabled": False}})
    lib = MovieLibrary(character_id="qilin", asset_dir=MODEL.parent.parent / "videos")
    window = PetWindow(lib, config)
    try:
        window.show()
        window.movie.stop()
        window.movie.jumpToFrame(0)
        window._rebuild_frame()
        before = window._frame_pixmap.toImage().copy()
        window.movie.set_parameter("eye_l_open", 0)
        window.movie.set_parameter("eye_r_open", 0)
        window._rebuild_frame()
        assert window.movie.currentFrameNumber() == 0
        assert window._frame_pixmap.toImage() != before
        assert window._frame_pixmap.devicePixelRatio() == window.devicePixelRatioF()
    finally:
        window.close()
        lib.shutdown()


def test_rig_character_is_discoverable_without_any_webm(model, monkeypatch):
    from pet import catalog
    monkeypatch.setattr(catalog, "CHARACTERS", {})
    monkeypatch.setattr(catalog, "external_character_dirs", lambda: [MODEL.parent.parent.parent])
    assert "qilin" in catalog.list_available_characters()
