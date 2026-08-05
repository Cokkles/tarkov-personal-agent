from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from tarkov_agent.config import AppSettings
from tarkov_agent.desktop.client import DesktopApiClient
from tarkov_agent.desktop.service import EmbeddedServiceManager
from tarkov_agent.domain.desktop import DesktopStatus
from tarkov_agent.domain.models import MarkerCommand, RaidRecord

LOGGER = logging.getLogger(__name__)

MARKERS: tuple[tuple[str, str, str], ...] = (
    ("PMC Heard", "audio", "Possible PMC audio cue"),
    ("Player Seen", "contact", "Visual player contact"),
    ("Fight Started", "combat", "Committed engagement"),
    ("Route Changed", "decision", "Meaningful route change"),
    ("Important Loot", "loot", "Important loot acquired or observed"),
    ("Mistake", "review", "Immediate mistake recognition"),
    ("Good Decision", "review", "Immediate positive decision recognition"),
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


class StartRaidDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Start Raid")
        form = QFormLayout(self)
        self.map_name = QLineEdit()
        self.map_name.setPlaceholderText("Customs")
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
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def payload(self) -> dict[str, str | None]:
        return {
            "map_name": self.map_name.text().strip() or None,
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
        self.result.addItems(
            ["Survived", "KIA", "Run Through", "Missing in Action", ""]
        )
        form.addRow("Result", self.result)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def selected_result(self) -> str | None:
        return self.result.currentText().strip() or None


class DesktopWindow(QMainWindow):
    def __init__(
        self,
        settings: AppSettings,
        client: DesktopApiClient,
        service: EmbeddedServiceManager,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.client = client
        self.service = service
        self.pool = QThreadPool.globalInstance()
        self._status_request_active = False
        self._allow_close = False
        self._tray_notice_shown = False
        self._status: DesktopStatus | None = None
        self._marker_buttons: list[QPushButton] = []
        self._build_window()
        self._build_tray()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(
            int(self.settings.desktop.poll_interval_seconds * 1000)
        )
        self.poll_timer.timeout.connect(self.refresh_status)
        self.poll_timer.start()

    def _build_window(self) -> None:
        self.setWindowTitle("Tarkov Personal Agent")
        self.resize(1040, 760)
        self.setMinimumSize(820, 620)
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(14)

        title = QLabel("TARKOV PERSONAL AGENT")
        title.setObjectName("title")
        subtitle = QLabel(
            "Local raid companion · evidence · coaching · media"
        )
        subtitle.setObjectName("subtitle")
        root.addWidget(title)
        root.addWidget(subtitle)

        service_group = QGroupBox("Service")
        service_layout = QHBoxLayout(service_group)
        self.service_label = QLabel("Checking local service…")
        self.service_label.setObjectName("serviceStatus")
        service_layout.addWidget(self.service_label, 1)
        self.start_service_button = QPushButton("Start Service")
        self.start_service_button.clicked.connect(self.start_service)
        self.stop_service_button = QPushButton("Stop Service")
        self.stop_service_button.clicked.connect(self.stop_service)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_status)
        service_layout.addWidget(self.start_service_button)
        service_layout.addWidget(self.stop_service_button)
        service_layout.addWidget(self.refresh_button)
        root.addWidget(service_group)

        status_group = QGroupBox("Current Status")
        status_grid = QGridLayout(status_group)
        self.lifecycle_value = self._status_pair(
            status_grid, 0, 0, "Lifecycle"
        )
        self.active_raid_value = self._status_pair(
            status_grid, 0, 2, "Active raid"
        )
        self.obs_value = self._status_pair(status_grid, 1, 0, "OBS")
        self.queue_value = self._status_pair(
            status_grid, 1, 2, "Review queue"
        )
        self.ppe_value = self._status_pair(status_grid, 2, 0, "PPE")
        self.rules_value = self._status_pair(
            status_grid, 2, 2, "Automatic log rules"
        )
        root.addWidget(status_group)

        controls_group = QGroupBox("Raid Controls")
        controls = QHBoxLayout(controls_group)
        self.start_raid_button = QPushButton("Start Raid")
        self.start_raid_button.clicked.connect(self.start_raid)
        self.end_raid_button = QPushButton("End Raid")
        self.end_raid_button.clicked.connect(self.end_raid)
        self.abort_raid_button = QPushButton("Abort Raid")
        self.abort_raid_button.setObjectName("dangerButton")
        self.abort_raid_button.clicked.connect(self.abort_raid)
        controls.addWidget(self.start_raid_button)
        controls.addWidget(self.end_raid_button)
        controls.addWidget(self.abort_raid_button)
        root.addWidget(controls_group)

        marker_group = QGroupBox("Live Markers")
        marker_grid = QGridLayout(marker_group)
        for index, (label, category, details) in enumerate(MARKERS):
            button = QPushButton(label)
            button.clicked.connect(
                lambda checked=False, marker_label=label,
                marker_category=category, marker_details=details: (
                    self.add_marker(
                        marker_label,
                        marker_category,
                        marker_details,
                    )
                )
            )
            marker_grid.addWidget(button, index // 4, index % 4)
            self._marker_buttons.append(button)
        root.addWidget(marker_group)

        navigation_group = QGroupBox("Open Workspace")
        navigation = QGridLayout(navigation_group)
        destinations = (
            ("Raid Review", "/"),
            ("PPE", "/ppe"),
            ("Source of Truth", "/truth"),
            ("Recommendations", "/recommendations"),
            ("Media", "/media"),
            ("API Docs", "/docs"),
        )
        for index, (label, path) in enumerate(destinations):
            button = QPushButton(label)
            button.clicked.connect(
                lambda checked=False, target=path: self.open_page(target)
            )
            navigation.addWidget(button, index // 3, index % 3)
        root.addWidget(navigation_group)

        self.activity = QTextEdit()
        self.activity.setReadOnly(True)
        self.activity.setMaximumHeight(110)
        self.activity.setPlaceholderText("Desktop activity and errors appear here.")
        root.addWidget(self.activity)
        self.statusBar().showMessage(
            f"Config: {self.service.config_path}"
        )
        self._set_online(False)
        self.setStyleSheet(_STYLE)

    def _build_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if not self.settings.desktop.minimize_to_tray:
            return
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self.style().standardIcon(
            QStyle.StandardPixmap.SP_ComputerIcon
        )
        self.setWindowIcon(icon)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("Tarkov Personal Agent")
        menu = QMenu()
        show_action = QAction("Show", menu)
        show_action.triggered.connect(self.show_from_tray)
        open_action = QAction("Open Raid Review", menu)
        open_action.triggered.connect(lambda: self.open_page("/"))
        start_action = QAction("Start Service", menu)
        start_action.triggered.connect(self.start_service)
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(show_action)
        menu.addAction(open_action)
        menu.addAction(start_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        self.tray = tray

    @staticmethod
    def _status_pair(
        layout: QGridLayout,
        row: int,
        column: int,
        label: str,
    ) -> QLabel:
        name = QLabel(label)
        name.setObjectName("statusName")
        value = QLabel("—")
        value.setObjectName("statusValue")
        layout.addWidget(name, row, column)
        layout.addWidget(value, row, column + 1)
        return value

    def auto_start(self) -> None:
        if self.settings.desktop.auto_start_service:
            self.start_service()
        else:
            self.refresh_status()

    def start_service(self) -> None:
        self._append_activity("Starting or connecting to the local service…")
        self._run_task(
            self.service.start,
            self._service_started,
            "Starting service…",
        )

    def stop_service(self) -> None:
        if not self.service.owns_service:
            self._append_activity(
                "This desktop session does not own the running service."
            )
            return
        self._run_task(
            self.service.stop,
            self._service_stopped,
            "Stopping service…",
        )

    def refresh_status(self) -> None:
        if self._status_request_active:
            return
        self._status_request_active = True
        worker = ApiWorker(self.client.status)
        worker.signals.result.connect(self._status_received)
        worker.signals.error.connect(self._status_failed)
        worker.signals.finished.connect(self._status_finished)
        self.pool.start(worker)

    def start_raid(self) -> None:
        dialog = StartRaidDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        payload = dialog.payload()
        self._run_task(
            lambda: self.client.start_raid(
                map_name=payload["map_name"],
                character_type=payload["character_type"],
                primary_objective=payload["primary_objective"],
                secondary_objective=payload["secondary_objective"],
            ),
            self._raid_started,
            "Starting raid…",
        )

    def end_raid(self) -> None:
        dialog = EndRaidDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._run_task(
            lambda: self.client.end_raid(result=dialog.selected_result()),
            self._raid_ended,
            "Ending raid and finalizing recording…",
        )

    def abort_raid(self) -> None:
        answer = QMessageBox.question(
            self,
            "Abort Raid",
            "Abort the active raid record? OBS recording will also be stopped.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._run_task(
            lambda: self.client.abort_raid(
                reason="Aborted from Desktop Companion"
            ),
            self._raid_aborted,
            "Aborting raid…",
        )

    def add_marker(self, label: str, category: str, details: str) -> None:
        command = MarkerCommand(
            label=label,
            category=category,
            details=details,
        )
        self._run_task(
            lambda: self.client.add_marker(command),
            lambda _: self._marker_added(label),
            f"Adding marker: {label}",
        )

    def open_page(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl(f"{self.client.base_url}{path}"))

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_application(self) -> None:
        self._allow_close = True
        if (
            self.settings.desktop.stop_service_on_exit
            and self.service.owns_service
        ):
            self.service.stop()
        tray = self.tray
        if tray is not None:
            tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            event.accept()
            return
        if self.tray is not None and self.tray.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_notice_shown:
                self.tray.showMessage(
                    "Tarkov Personal Agent",
                    "The companion is still running in the system tray.",
                    QSystemTrayIcon.MessageIcon.Information,
                    3000,
                )
                self._tray_notice_shown = True
            return
        self.quit_application()
        event.accept()

    def _tray_activated(
        self,
        reason: QSystemTrayIcon.ActivationReason,
    ) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        }:
            self.show_from_tray()

    def _run_task(
        self,
        task: Callable[[], object],
        on_result: Callable[[object], None],
        message: str,
    ) -> None:
        self.statusBar().showMessage(message)
        worker = ApiWorker(task)
        worker.signals.result.connect(on_result)
        worker.signals.error.connect(self._task_failed)
        worker.signals.finished.connect(
            lambda: self.statusBar().showMessage("Ready")
        )
        self.pool.start(worker)

    @Slot(object)
    def _status_received(self, value: object) -> None:
        status = DesktopStatus.model_validate(value)
        self._status = status
        self._set_online(True)
        self.lifecycle_value.setText(status.lifecycle_state.replace("_", " ").title())
        if status.active_raid is None:
            self.active_raid_value.setText("None")
        else:
            map_name = status.active_raid.map_name or "Unknown map"
            character = status.active_raid.character_type or "Unknown"
            self.active_raid_value.setText(f"{map_name} · {character}")
        if not status.obs.enabled:
            self.obs_value.setText("Disabled")
        elif status.obs.error:
            self.obs_value.setText("Connection error")
            self.obs_value.setToolTip(status.obs.error)
        elif status.obs.recording_active:
            self.obs_value.setText("Recording")
        elif status.obs.connected:
            self.obs_value.setText("Connected")
        else:
            self.obs_value.setText("Disconnected")
        self.queue_value.setText(str(status.review_queue_count))
        self.ppe_value.setText(
            f"Profile v{status.ppe_profile_version}"
            if status.ppe_profile_version is not None
            else ("Ready" if status.ppe_enabled else "Disabled")
        )
        self.rules_value.setText(str(status.automatic_log_rules))
        active = status.active_raid is not None
        self.start_raid_button.setEnabled(not active)
        self.end_raid_button.setEnabled(active)
        self.abort_raid_button.setEnabled(active)
        for button in self._marker_buttons:
            button.setEnabled(active)
        self.start_service_button.setEnabled(False)
        self.stop_service_button.setEnabled(self.service.owns_service)

    @Slot(str)
    def _status_failed(self, message: str) -> None:
        self._set_online(False)
        self.service_label.setToolTip(message)

    @Slot()
    def _status_finished(self) -> None:
        self._status_request_active = False

    def _set_online(self, online: bool) -> None:
        self.service_label.setText(
            "● Local service online" if online else "● Local service offline"
        )
        self.service_label.setProperty("online", online)
        self.service_label.style().unpolish(self.service_label)
        self.service_label.style().polish(self.service_label)
        self.start_service_button.setEnabled(not online)
        self.stop_service_button.setEnabled(
            online and self.service.owns_service
        )
        if not online:
            self.lifecycle_value.setText("Offline")
            self.active_raid_value.setText("—")
            self.obs_value.setText("—")
            self.queue_value.setText("—")
            self.ppe_value.setText("—")
            self.rules_value.setText("—")
            self.start_raid_button.setEnabled(False)
            self.end_raid_button.setEnabled(False)
            self.abort_raid_button.setEnabled(False)
            for button in self._marker_buttons:
                button.setEnabled(False)

    @Slot(object)
    def _service_started(self, owned: object) -> None:
        message = (
            "Embedded local service started."
            if bool(owned)
            else "Connected to an already running local service."
        )
        self._append_activity(message)
        self.refresh_status()

    @Slot(object)
    def _service_stopped(self, _: object) -> None:
        self._append_activity("Embedded local service stopped.")
        self._set_online(False)

    @Slot(object)
    def _raid_started(self, value: object) -> None:
        raid = RaidRecord.model_validate(value)
        self._append_activity(f"Raid started: {raid.map_name or raid.id}")
        self.refresh_status()

    @Slot(object)
    def _raid_ended(self, value: object) -> None:
        raid = RaidRecord.model_validate(value)
        self._append_activity(
            f"Raid ended and queued for review: {raid.result or raid.id}"
        )
        self.refresh_status()

    @Slot(object)
    def _raid_aborted(self, value: object) -> None:
        raid = RaidRecord.model_validate(value)
        self._append_activity(f"Raid aborted: {raid.id}")
        self.refresh_status()

    def _marker_added(self, label: str) -> None:
        self._append_activity(f"Marker added: {label}")

    @Slot(str)
    def _task_failed(self, message: str) -> None:
        self._append_activity(f"Error: {message}")
        QMessageBox.warning(self, "Tarkov Personal Agent", message)
        self.refresh_status()

    def _append_activity(self, message: str) -> None:
        self.activity.append(message)


_STYLE = """
QWidget {
    background: #0b1015;
    color: #e7edf4;
    font-family: "Segoe UI";
    font-size: 10.5pt;
}
QMainWindow, QDialog { background: #0b1015; }
QLabel#title {
    color: #f1f5f9;
    font-size: 22pt;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#subtitle { color: #8394a5; font-size: 10pt; }
QGroupBox {
    border: 1px solid #293541;
    border-radius: 10px;
    margin-top: 10px;
    padding: 13px 10px 10px 10px;
    background: #111820;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #a9b8c6;
}
QPushButton {
    background: #1a2a38;
    border: 1px solid #36516a;
    border-radius: 7px;
    padding: 9px 13px;
    font-weight: 600;
}
QPushButton:hover { background: #24415a; border-color: #4f83ad; }
QPushButton:pressed { background: #162532; }
QPushButton:disabled { color: #586776; background: #111820; border-color: #27313a; }
QPushButton#dangerButton { border-color: #7c3d45; background: #351d22; }
QPushButton#dangerButton:hover { background: #51262e; }
QLabel#serviceStatus[online="true"] { color: #70d69a; font-weight: 700; }
QLabel#serviceStatus[online="false"] { color: #ef8f8f; font-weight: 700; }
QLabel#statusName { color: #7f91a2; }
QLabel#statusValue { color: #edf4fa; font-weight: 650; }
QLineEdit, QComboBox, QTextEdit {
    background: #0c1218;
    border: 1px solid #32404d;
    border-radius: 6px;
    padding: 7px;
    selection-background-color: #356d9e;
}
QStatusBar { color: #7f91a2; }
"""


def run_desktop(settings: AppSettings, *, config_path: Path) -> int:
    application = QApplication([])
    application.setApplicationName("Tarkov Personal Agent")
    application.setOrganizationName("Tarkov Personal Agent")
    if settings.desktop.minimize_to_tray:
        application.setQuitOnLastWindowClosed(False)
    client = DesktopApiClient(settings)
    service = EmbeddedServiceManager(
        settings,
        client,
        config_path=config_path,
    )
    window = DesktopWindow(settings, client, service)
    window.show()
    QTimer.singleShot(100, window.auto_start)
    return application.exec()
