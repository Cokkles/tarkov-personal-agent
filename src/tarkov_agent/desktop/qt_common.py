from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Qt, Signal, Slot
from PySide6.QtGui import (
    QBrush,
    QColor,
    QLinearGradient,
    QPainter,
    QPixmap,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from tarkov_agent.domain.models import MarkerType

LOGGER = logging.getLogger(__name__)

MARKERS: tuple[tuple[MarkerType, str, str], ...] = (
    (MarkerType.PMC_HEARD, "◉", "PMC HEARD"),
    (MarkerType.PLAYER_SEEN, "◈", "PLAYER SEEN"),
    (MarkerType.FIGHT_STARTED, "✥", "FIGHT STARTED"),
    (MarkerType.ROUTE_CHANGED, "↗", "ROUTE CHANGED"),
    (MarkerType.IMPORTANT_LOOT, "▣", "IMPORTANT LOOT"),
    (MarkerType.MISTAKE, "△", "MISTAKE"),
    (MarkerType.GOOD_DECISION, "✓", "GOOD DECISION"),
)

NAVIGATION: tuple[tuple[str, str, str], ...] = (
    ("Dashboard", "⌂", "dashboard"),
    ("Live Raid", "◉", "live"),
    ("Markers", "✥", "markers"),
    ("Reviews", "▤", "reviews"),
    ("PPE", "◌", "ppe"),
    ("Media", "▦", "media"),
    ("Tasks", "☑", "tasks"),
    ("Maps", "◇", "maps"),
    ("Settings", "⚙", "settings"),
)


class WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class ApiWorker(QRunnable):
    def __init__(self, task: Callable[[], object]) -> None:
        super().__init__()
        self.task = task
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.task()
        except Exception as exc:
            LOGGER.exception("Desktop background task failed")
            self.signals.error.emit(str(exc))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class BackgroundWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        path = Path(__file__).with_name("assets") / "operations_center_background.jpg"
        self._background = QPixmap(str(path))
        self.setAutoFillBackground(False)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#06090c"))
        if not self._background.isNull():
            pixmap = self._background.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(
                (self.width() - pixmap.width()) // 2,
                (self.height() - pixmap.height()) // 2,
                pixmap,
            )

        tactical_glow = QRadialGradient(
            self.width() * 0.77,
            self.height() * 0.34,
            max(self.width(), self.height()) * 0.62,
        )
        tactical_glow.setColorAt(0.0, QColor(126, 116, 76, 34))
        tactical_glow.setColorAt(0.48, QColor(61, 76, 60, 18))
        tactical_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), QBrush(tactical_glow))

        horizontal = QLinearGradient(0, 0, self.width(), 0)
        horizontal.setColorAt(0.0, QColor(4, 9, 12, 244))
        horizontal.setColorAt(0.42, QColor(4, 9, 12, 208))
        horizontal.setColorAt(0.76, QColor(4, 9, 12, 128))
        horizontal.setColorAt(1.0, QColor(4, 9, 12, 72))
        painter.fillRect(self.rect(), QBrush(horizontal))

        vertical = QLinearGradient(0, 0, 0, self.height())
        vertical.setColorAt(0.0, QColor(0, 0, 0, 18))
        vertical.setColorAt(0.58, QColor(0, 0, 0, 36))
        vertical.setColorAt(1.0, QColor(0, 0, 0, 92))
        painter.fillRect(self.rect(), QBrush(vertical))
        painter.end()
        super().paintEvent(event)  # type: ignore[arg-type]


class StartRaidDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start Raid")
        self.setMinimumWidth(430)
        form = QFormLayout(self)
        self.map_name = QComboBox()
        self.map_name.setEditable(True)
        self.map_name.addItems([
            "Customs", "Factory", "Ground Zero", "Interchange", "Lighthouse",
            "Reserve", "Shoreline", "Streets of Tarkov", "The Lab", "Woods",
        ])
        self.map_name.setCurrentText("")
        self.character_type = QComboBox()
        self.character_type.addItems(["Scav", "PMC"])
        self.primary_objective = QLineEdit()
        self.primary_objective.setPlaceholderText("Primary goal for this raid")
        self.secondary_objective = QLineEdit()
        self.secondary_objective.setPlaceholderText("Optional secondary goal")
        form.addRow("Map", self.map_name)
        form.addRow("Character", self.character_type)
        form.addRow("Primary objective", self.primary_objective)
        form.addRow("Secondary objective", self.secondary_objective)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def payload(self) -> dict[str, str | None]:
        return {
            "map_name": self.map_name.currentText().strip() or None,
            "character_type": self.character_type.currentText(),
            "primary_objective": self.primary_objective.text().strip() or None,
            "secondary_objective": self.secondary_objective.text().strip() or None,
        }


class EndRaidDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("End Raid")
        form = QFormLayout(self)
        self.result = QComboBox()
        self.result.setEditable(True)
        self.result.addItems(["Survived", "KIA", "Run Through", "Missing in Action", ""])
        form.addRow("Result", self.result)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selected_result(self) -> str | None:
        return self.result.currentText().strip() or None
