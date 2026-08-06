from __future__ import annotations

from tarkov_agent import __version__
from tarkov_agent.desktop.qt_theme import STYLE


def test_phase_6_theme_exports_public_style() -> None:
    assert STYLE
    assert "QWidget#pageRoot" in STYLE
    assert "QWidget#scrollViewport" in STYLE
    assert "QFrame#featureCard" in STYLE
    assert "QFrame#pipelinePanel" in STYLE
    assert "QProgressBar#finalizationProgress" in STYLE
    assert "QLabel#pipelineStep" in STYLE
    assert "qlineargradient" in STYLE


def test_phase_6_version() -> None:
    assert __version__ == "0.10.0"
