"""Removed desktop-island UI must not reappear or overwrite legacy preferences."""
from copy import deepcopy

import pytest
from PySide6.QtWidgets import QApplication

from pet.config import Config
from pet.modern_settings_dialog import ModernSettingsDialog, SettingRow


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize("include_ai", [False, True])
def test_removed_island_has_no_page_controls_or_search_results(app, tmp_path, include_ai):
    cfg = Config(base=tmp_path)
    cfg.set("dynamic_island", {**cfg.get("dynamic_island"), "enabled": True})
    cfg.set("spawn_inherit_dynamic_island", True)
    dialog = ModernSettingsDialog(cfg, include_ai=include_ai)
    try:
        labels = [dialog.sidebar.item(i).text() for i in range(dialog.sidebar.count())]
        assert "桌面组件" not in labels
        assert "灵动岛" not in labels
        assert not hasattr(dialog, "island_enabled_check")
        assert not hasattr(dialog, "spawn_inherit_dynamic_island_check")
        rows = dialog.findChildren(SettingRow)
        assert not any("dynamic_island" in row.objectName() for row in rows)
        dialog._search_settings("灵动岛")
        assert not any("灵动岛" in row.label.text() for row in rows if row.isVisible())
    finally:
        dialog.close()
        app.processEvents()


def test_unrelated_settings_save_preserves_legacy_island_preferences(app, tmp_path):
    cfg = Config(base=tmp_path)
    cfg.set("dynamic_island", {
        **cfg.get("dynamic_island"), "enabled": True,
        "custom_text": "旧版内容", "x": 123, "y": 234,
    })
    cfg.set("spawn_inherit_dynamic_island", True)
    expected = deepcopy(cfg.get("dynamic_island"))
    dialog = ModernSettingsDialog(cfg, include_ai=False)
    try:
        dialog.lock_position_check.setChecked(True)
        dialog._write_config()
        cfg.save()
        reloaded = Config(base=tmp_path)
        assert reloaded.get("dynamic_island") == expected
        assert reloaded.get("spawn_inherit_dynamic_island") is True
        assert reloaded.get("lock_position") is True
    finally:
        dialog.close()
        app.processEvents()
