"""Optional deployment logo shared by application windows and the system tray."""
from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtGui import QIcon, QPixmap


def load_application_logo(root: Path | None = None) -> QIcon:
    """Load branding/logo.png on the GUI thread; return an empty icon on failure.

    Frozen deployments resolve from the executable directory, independent of
    the launch working directory. Source runs can provide the same layout in
    their working directory. No profile or persistent setting is needed.
    """
    if root is None:
        root = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path.cwd()
    path = Path(root) / "branding" / "logo.png"
    if not path.is_file():
        return QIcon()
    pixmap = QPixmap(str(path))
    return QIcon(pixmap) if not pixmap.isNull() else QIcon()
