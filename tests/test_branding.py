"""Custom application-logo loading at the deployed/source public seam."""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from pet.branding import load_application_logo


def _app():
    return QApplication.instance() or QApplication([])


def _logo(root: Path):
    path = root / "branding" / "logo.png"
    path.parent.mkdir(parents=True)
    image = QImage(32, 32, QImage.Format.Format_RGBA8888)
    image.fill(QColor("#f54b50"))
    assert image.save(str(path))
    return path


def test_logo_loads_from_deployed_executable_directory(tmp_path, monkeypatch):
    app = _app()
    _logo(tmp_path)
    monkeypatch.setattr("pet.branding.sys.frozen", True, raising=False)
    monkeypatch.setattr("pet.branding.sys.executable", str(tmp_path / "pet.exe"))
    icon = load_application_logo()
    assert not icon.isNull()
    assert icon.pixmap(32, 32).toImage().pixelColor(16, 16) == QColor("#f54b50")
    assert app is not None


def test_source_logo_uses_working_directory(tmp_path, monkeypatch):
    app = _app()
    _logo(tmp_path)
    monkeypatch.setattr("pet.branding.sys.frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)
    icon = load_application_logo()
    assert not icon.isNull()
    assert icon.pixmap(32, 32).toImage().pixelColor(16, 16).alpha() == 255
    assert app is not None


def test_missing_or_invalid_logo_allows_existing_character_icon(tmp_path):
    app = _app()
    assert load_application_logo(tmp_path).isNull()
    path = tmp_path / "branding" / "logo.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"invalid image")
    assert load_application_logo(tmp_path).isNull()
    image = QImage(8, 8, QImage.Format.Format_RGBA8888)
    image.fill(Qt.GlobalColor.transparent)
    assert image.hasAlphaChannel()
    assert app is not None
