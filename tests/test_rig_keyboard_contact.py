"""Typing hands must meet the visible keyboard, not a floating contact label."""
from pathlib import Path
import math

import pytest
from PySide6.QtWidgets import QApplication

from pet.rig_model import RigModel, bone_points

MODEL = Path(__file__).resolve().parents[1] / 'assets/characters/qilin/rig/model.json'


@pytest.fixture(scope='module')
def model():
    app = QApplication.instance() or QApplication([])
    yield RigModel(MODEL)
    assert app is not None


def fingertip(model, pose, key):
    rest = model.layers[key + '_lower']['touch_point']
    bone = model.bones[key]
    return bone_points((bone[0], bone[1], rest), pose.angles[key])[-1]


def prop_point(layer, prop, uv):
    local = ((uv[0] - prop.anchor[0]) * layer['size'][0] * prop.height,
             (uv[1] - prop.anchor[1]) * layer['size'][1] * prop.height)
    angle = math.radians(prop.angle)
    return (prop.point[0] + local[0] * math.cos(angle) - local[1] * math.sin(angle),
            prop.point[1] + local[0] * math.sin(angle) + local[1] * math.cos(angle))


def keyboard_uv(corners, u, v):
    return tuple((1-v) * ((1-u) * corners[0][i] + u * corners[1][i])
                 + v * ((1-u) * corners[3][i] + u * corners[2][i]) for i in (0, 1))


@pytest.mark.parametrize('name', ['写代码', '工作状态-忙碌点按'])
def test_typing_fingertips_meet_keyboard_for_both_actions(model, name):
    layer = model.layers['prop_laptop']
    assert layer['render_style'] == 'laptop-mesh-1'
    corners = layer['keyboard']['corners']
    action = model.actions[name]
    for i in range(23, 78):
        pose = model.pose(action, action['seconds'] * i / 100)
        laptop = next(prop for prop in pose.props if prop.name == 'laptop')
        for key, uv in layer['keyboard']['hand_positions'].items():
            surface = prop_point(layer, laptop, keyboard_uv(corners, *uv))
            painted_tip = fingertip(model, pose, key)
            assert math.dist(painted_tip, surface) < 1.0, (name, i, key)
            assert math.dist(painted_tip, pose.contacts[key + '_key_touch']) < 1e-7
        # Both hands must be separated across the keyboard, not stacked together.
        assert fingertip(model, pose, 'ra')[0] - fingertip(model, pose, 'la')[0] > 25


def test_authored_contact_points_are_on_visible_finger_skin(model):
    for key in ('la', 'ra'):
        layer = model.layers[key + '_lower']
        x, y = layer['touch_point']
        image = model.images[key + '_lower']
        px = round((x - layer['origin'][0]) / layer['size'][0] * image.width())
        py = round((y - layer['origin'][1]) / layer['size'][1] * image.height())
        color = image.pixelColor(px, py)
        assert color.alpha() > 240
        assert color.red() > 230 and color.green() > 140 and color.blue() > 110


def test_fingers_remain_visible_over_the_keyboard_in_rendered_pixels(model):
    action = model.actions['写代码']
    pose = model.pose(action, action['seconds'] * .5)
    frame = model.render(action, action['seconds'] * .5)
    for key in ('la', 'ra'):
        x, y = fingertip(model, pose, key)
        color = frame.pixelColor(round(x * model.sampling),
                                 round((y + pose.root_y) * model.sampling))
        assert color.alpha() > 240
        assert color.red() > 230 and color.green() > 140 and color.blue() > 110


def test_keyboard_and_stand_stay_fixed_while_the_pet_breathes(model):
    layer = model.layers['prop_laptop']
    assert len(layer['stand']) == 3
    positions = []
    action = model.actions['写代码']
    floors = []
    for key, name in (('ll', 'l_foot'), ('rl', 'r_foot')):
        foot, art = model.layers[name], model.images[name]
        last = max(y for y in range(art.height())
                   if any(art.pixelColor(x, y).alpha() >= 128 for x in range(art.width())))
        floors.append(model.bones[key][-1][1] + foot['origin'][1]
                      + (last + .5) * foot['size'][1] / art.height())
    for i in range(101):
        pose = model.pose(action, action['seconds'] * i / 100)
        laptop = next(prop for prop in pose.props if prop.name == 'laptop')
        positions.append((laptop.point[0], laptop.point[1] + pose.root_y))
        for leg in layer['stand'][1:]:
            bottom = prop_point(layer, laptop, leg[2])
            assert abs(bottom[1] + pose.root_y - max(floors)) < .5
    assert max(math.dist(a, b) for a in positions for b in positions) < 1e-7
    pose = model.pose(action, action['seconds'] * .5)
    laptop = next(prop for prop in pose.props if prop.name == 'laptop')
    frame = model.render(action, action['seconds'] * .5)
    for leg in layer['stand'][1:]:
        uv = ((leg[2][0] + leg[3][0]) / 2, leg[2][1] - .015)
        x, y = prop_point(layer, laptop, uv)
        color = frame.pixelColor(round(x * model.sampling),
                                 round((y + pose.root_y) * model.sampling))
        assert color.alpha() > 200 and color.red() > 190
