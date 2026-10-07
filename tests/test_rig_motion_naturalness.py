"""Physical trajectory regressions for the fixed Qilin puppet."""
from pathlib import Path
import math
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QApplication

from pet.rig_model import RigModel, bone_points

MODEL = Path(__file__).resolve().parents[1] / 'assets/characters/qilin/rig/model.json'


@pytest.fixture(scope='module')
def model():
    app = QApplication.instance() or QApplication([])
    rig = RigModel(MODEL)
    yield rig
    assert app is not None


def test_all_action_joint_trajectories_have_no_flip_or_violent_turn(model):
    failures = []
    for name, action in model.actions.items():
        poses = [model.pose(action, i / 60) for i in range(round(action['seconds'] * 60) + 1)]
        for key in ('la', 'ra', 'll', 'rl', 'tail'):
            for segment in (0, 1):
                speed = max(abs(b.angles[key][segment] - a.angles[key][segment]) * 60
                            for a, b in zip(poses, poses[1:]))
                if speed > 320:
                    failures.append((name, key, segment, round(speed)))
    assert not failures, failures


def test_elbows_never_bend_backwards_or_fold_closed(model):
    failures = []
    for name, action in model.actions.items():
        for i in range(61):
            pose = model.pose(action, action['seconds'] * i / 60)
            if not (-132.001 <= pose.angles['la'][1] <= .001
                    and -.001 <= pose.angles['ra'][1] <= 132.001):
                failures.append((name, i, pose.angles['la'], pose.angles['ra']))
                break
    assert not failures, failures


@pytest.mark.parametrize('name', ['凭空生花', '吃糖葫芦', '收红包', '工作状态-思考冒泡'])
def test_holding_actions_have_a_readable_pause_without_arm_circling(model, name):
    action = model.actions[name]
    poses = [model.pose(action, action['seconds'] * p) for p in (.4, .45, .5, .55)]
    hands = [bone_points(model.bones['ra'], pose.angles['ra'])[-1] for pose in poses]
    assert max(math.dist(a, b) for a in hands for b in hands) < 1.0
    assert max(p.angles['ra'][0] for p in poses) - min(p.angles['ra'][0] for p in poses) < 1.0


@pytest.mark.parametrize('name', ['待机呼吸休闲', '凭空生花', '吃糖葫芦', '轻快记录', '国风屈膝礼仪'])
def test_standing_actions_keep_both_supporting_feet_on_the_ground(model, name):
    action = model.actions[name]
    for i in range(41):
        pose = model.pose(action, action['seconds'] * i / 40)
        for key, contact in (('ll', 'left_foot'), ('rl', 'right_foot')):
            assert contact in pose.contacts
            assert math.dist(pose.contacts[contact], model.bones[key][-1]) < .1
            # Check the actual painted ankle after the pelvis transform, rather
            # than accepting a constant contact label as evidence of support.
            ankle = bone_points(model.bones[key], pose.angles[key])[-1]
            world = (ankle[0], ankle[1] + pose.root_y)
            assert math.dist(world, pose.contacts[contact]) < 1e-7
            assert pose.foot_angles[key] == pytest.approx(0.)
            assert key in pose.planted_feet


def test_preparation_and_settle_join_with_low_velocity(model):
    for name in ('凭空生花', '工作状态-思考冒泡', '轻快记录'):
        action = model.actions[name]
        for start in (0, action['seconds'] - 1 / 60):
            a = model.pose(action, start)
            b = model.pose(action, start + 1 / 60)
            assert max(abs(b.angles[key][j] - a.angles[key][j])
                       for key in ('la', 'ra') for j in (0, 1)) < .1


def test_writing_tools_stay_on_page_while_the_body_breathes(model):
    action = model.actions['轻快记录']
    for i in range(25, 76):
        pose = model.pose(action, action['seconds'] * i / 100)
        assert math.dist(pose.contacts['pen_tip'], pose.contacts['page']) < .05
        assert math.dist(pose.contacts['left_hand'], pose.contacts['book_support']) < .05


def test_expression_mix_keeps_head_opaque_and_does_not_tint_hair(model, monkeypatch):
    state = model.pose(model.actions['待机呼吸休闲'], 0)
    frames = []
    for weight in (0., .5, 1.):
        pose = replace(state, emotion='happy', emotion_weight=weight)
        monkeypatch.setattr(model, 'pose', lambda *_args, pose=pose: pose)
        frames.append(model.render('待机呼吸休闲', 0))
    for x, y in ((300, 90), (310, 110), (340, 90)):
        colors = [frame.pixelColor(x * 2, y * 2).getRgb() for frame in frames]
        assert min(colors[0][3], colors[2][3]) >= 250
        assert colors[1][3] >= min(colors[0][3], colors[2][3]) - 2
        for channel in range(3):
            expected = (colors[0][channel] + colors[2][channel]) / 2
            assert abs(colors[1][channel] - expected) <= 2


def test_all_declared_supports_match_actual_painted_bone_chain(model):
    for name, action in model.actions.items():
        for i in range(81):
            pose = model.pose(action, action['seconds'] * i / 80)
            for key in pose.planted_feet:
                ankle = bone_points(model.bones[key], pose.angles[key])[-1]
                world = (ankle[0], ankle[1] + pose.root_y)
                assert math.dist(world, model.bones[key][-1]) < .02, (name, i, key)
                assert pose.foot_angles[key] == pytest.approx(0.), (name, i, key)


def test_carried_props_follow_actual_gripping_hands_during_entire_action(model):
    for name in ('凭空生花', '吃糖葫芦', '摇扇纳凉', '照镜子', '收红包'):
        action = model.actions[name]
        for i in range(81):
            pose = model.pose(action, action['seconds'] * i / 80)
            item = next(p for p in pose.props if p.name == action['prop'])
            right = bone_points(model.bones['ra'], pose.angles['ra'])[-1]
            if action['kind'] == 'present':
                ratio = model.layers['prop_' + item.name]['size'][0]
                grip = (item.point[0] + ratio * item.height * .4,
                        item.point[1] + item.height * .18)
            else:
                grip = item.point
            assert math.dist(grip, right) < 1e-7
