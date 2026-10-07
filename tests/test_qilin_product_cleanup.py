"""Public configuration and Qt seams for the qilin product migration."""
import json

import pytest
from PySide6.QtWidgets import QApplication

from pet.chat.models import ChatSettings, ProviderConfig
from pet.chat.themes import CHAT_UI_STYLE_LABELS
from pet.config import Config, DEFAULT_MENU_EASTER_EGG
from pet.context_menus.registry import MenuActionRegistry
from pet.modern_settings_dialog import ModernSettingsDialog, SettingRow


def test_new_install_has_no_vendor_endpoint_or_model(tmp_path):
    cfg = Config(base=tmp_path)
    provider = cfg.chat_settings().active_config
    assert provider.name == '自定义接口'
    assert provider.base_url == provider.model == ''
    assert ProviderConfig('new').base_url == ''
    assert ChatSettings.defaults().active_config.model == ''
    assert all('DeepSeek' not in text for text in CHAT_UI_STYLE_LABELS.values())


@pytest.mark.parametrize('old_path', [
    'assets/big_blue_fat_fish',
    'D:/old-install/_internal/assets/big_blue_fat_fish',
])
def test_load_migrates_old_vendor_and_builtin_assets_without_losing_custom_data(tmp_path, old_path):
    cfg = Config(base=tmp_path)
    raw = {
        'chat': {'active_provider': 'old', 'providers': {
            'old': {'name': 'DeepSeek', 'base_url': 'https://api.deepseek.com', 'model': 'deepseek-v4-flash'},
            'custom': {'name': '我的服务', 'base_url': 'http://localhost:1234/v1', 'model': 'local'},
        }},
        'harness_autostart': True, 'click_show_balance': True,
        'balance_refresh_minutes': 5, 'agent_cost_enabled': True,
        'agent_link': {'dsh': True, 'claude': True},
        'self_talk_image_dir': old_path,
        'menu_easter_egg': {'title': '厉害了我的鲸', 'avatar': old_path + '/ojingjing.jpg', 'image_dir': old_path},
        'lock_position': True,
    }
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    cfg.path.write_text(json.dumps(raw), encoding='utf-8')
    cfg = Config(base=tmp_path)
    assert set(cfg.chat_settings().providers) == {'custom'}
    assert cfg.chat_settings().active_provider == 'custom'
    assert cfg.get('agent_link')['claude'] is True
    assert not cfg.get('agent_link').get('dsh', False)
    assert not cfg.get('harness_autostart', False)
    assert not cfg.get('click_show_balance', False)
    assert cfg.get('balance_refresh_minutes', 0) == 0
    assert not cfg.get('agent_cost_enabled', False)
    assert cfg.get('self_talk_image_dir') == 'assets/qilin_memes'
    assert cfg.get('menu_easter_egg')['avatar'] == DEFAULT_MENU_EASTER_EGG['avatar']
    assert cfg.get('menu_easter_egg')['title'] == '麒麟表情包'
    assert cfg.get('lock_position') is True
    cfg.save()
    assert Config(base=tmp_path).chat_settings().active_provider == 'custom'


def test_custom_image_directory_and_caption_survive_migration(tmp_path):
    cfg = Config(base=tmp_path)
    cfg.set('self_talk_image_dir', 'E:/my-pictures')
    cfg.set('menu_easter_egg', {'title': '我的图片', 'image_dir': 'E:/my-pictures', 'avatar': 'E:/my-pictures/a.png'})
    cfg.save()
    reloaded = Config(base=tmp_path)
    assert reloaded.get('self_talk_image_dir') == 'E:/my-pictures'
    assert reloaded.get('menu_easter_egg')['title'] == '我的图片'


def test_persisted_brand_captions_and_old_default_phrase_migrate(tmp_path):
    cfg = Config(base=tmp_path)
    raw = {
        'self_talk_texts': ['欧鲸鲸……', '使用 DeepSeek', '我的提醒'],
        'menu_easter_egg': {'title': 'DeepSeek 表情包'},
        'character_aliases': {'qilin': 'DeepSeek 小助手', 'custom': '小朋友'},
    }
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    cfg.path.write_text(json.dumps(raw), encoding='utf-8')
    cfg = Config(base=tmp_path)
    assert cfg.get('self_talk_texts') == ['瑞麟给你加油。', '麒麟来陪你啦。', '我的提醒']
    assert cfg.get('menu_easter_egg')['title'] == '麒麟表情包'
    assert cfg.character_alias('qilin') == ''
    assert cfg.character_alias('custom') == '小朋友'


def test_qilin_build_migrates_retired_character_in_existing_child_slot(tmp_path, monkeypatch):
    from pet import catalog

    monkeypatch.setattr(catalog, '_DEPLOYED_CHARACTER', 'qilin')
    cfg = Config(base=tmp_path, instance_id='slot-1')
    cfg.path.parent.mkdir(parents=True, exist_ok=True)
    cfg.path.write_text(json.dumps({'version': 4, 'character': 'shenshen', 'scale': 0.85, 'lock_position': True}), encoding='utf-8')
    migrated = Config(base=tmp_path, instance_id='slot-1')
    assert migrated.get('character') == 'qilin'
    assert migrated.get('scale') == 0.85
    assert migrated.get('lock_position') is True
    migrated.save()
    assert Config(base=tmp_path, instance_id='slot-1').get('character') == 'qilin'


def test_unconfigured_chat_returns_setup_message_without_network(monkeypatch):
    from threading import Event
    from pet.chat.providers import OpenAICompatibleProvider, ProviderError, test_connection

    def forbidden(*args, **kwargs):
        pytest.fail('An unconfigured provider must never send a request')

    monkeypatch.setattr('urllib.request.urlopen', forbidden)
    cfg = ProviderConfig('new')
    ok, message = test_connection(cfg)
    assert not ok and '接口地址' in message
    with pytest.raises(ProviderError, match='接口地址'):
        list(OpenAICompatibleProvider().stream([], cfg, Event()))
    from pet.vision import VisionError, _post_vision_request
    with pytest.raises(VisionError, match='接口地址'):
        _post_vision_request(b'jpeg', '', '', cfg)


@pytest.mark.parametrize('include_ai', [False, True])
def test_settings_and_registry_offer_no_retired_service_controls(tmp_path, include_ai):
    app = QApplication.instance() or QApplication([])
    cfg = Config(base=tmp_path)
    dialog = ModernSettingsDialog(cfg, include_ai=include_ai)
    try:
        ids = {r.objectName().removeprefix('settingRow_') for r in dialog.findChildren(SettingRow)}
        assert not ids.intersection({'harness_autostart', 'agent_cost', 'click_balance', 'balance_refresh', 'balance_tier_mode'})
        assert not {'balance', 'harness', 'deepseek_web', 'agent_cost'}.intersection(MenuActionRegistry()._specs)
        dialog._write_config()
    finally:
        dialog.close()
        app.processEvents()


def test_chat_header_uses_qilin_name(tmp_path):
    from pet.chat.widgets import ChatWindow

    app = QApplication.instance() or QApplication([])
    window = ChatWindow(Config(base=tmp_path), 'qilin')
    try:
        assert window.brand_label.text() == '麒麟 AI'
    finally:
        window.close()
        app.processEvents()


def test_delayed_retired_install_signal_cannot_restart_service(tmp_path):
    from threading import Thread
    from PySide6.QtCore import QEventLoop, QTimer
    from pet.agent_link import AgentLinkManager

    app = QApplication.instance() or QApplication([])
    cfg = Config(base=tmp_path)

    class Window:
        def __init__(self):
            self.bubbles = []

        def show_bubble(self, text, **kwargs):
            self.bubbles.append(text)

    window = Window()
    manager = AgentLinkManager(window, cfg)
    manager._install_pending['dsh'] = 7
    loop = QEventLoop()
    manager.install_finished.connect(lambda *_: loop.quit())
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    timeout.start(5000)
    worker = Thread(target=lambda: manager.install_finished.emit('dsh', True, 'done', 7))
    try:
        worker.start()
        loop.exec()
        worker.join(timeout=5)
        assert not worker.is_alive()
        assert 'dsh' not in manager._install_pending
        assert not cfg.get('agent_link')['dsh']
        assert not manager.monitors['dsh']._running
        assert not manager.set_enabled('dsh', True)
        assert not window.bubbles
    finally:
        timeout.stop()
        manager.shutdown()
        app.processEvents()
