from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThreadPool, QTimer, Qt
from PySide6.QtGui import QAction, QColor, QFont, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from tarkov_agent import __version__
from tarkov_agent.config import AppSettings
from tarkov_agent.desktop.client import DesktopApiClient
from tarkov_agent.desktop.qt_common import BackgroundWidget, NAVIGATION
from tarkov_agent.desktop.qt_pages import OperationsCenterPagesMixin
from tarkov_agent.desktop.qt_runtime import OperationsCenterRuntimeMixin
from tarkov_agent.desktop.qt_theme import STYLE
from tarkov_agent.desktop.qt_widgets import OperationsCenterWidgetsMixin
from tarkov_agent.desktop.service import EmbeddedServiceManager
from tarkov_agent.domain.desktop import DesktopStatus


class DesktopWindow(
    OperationsCenterPagesMixin,
    OperationsCenterWidgetsMixin,
    OperationsCenterRuntimeMixin,
    QMainWindow,
):
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
        self._status: DesktopStatus | None = None
        self._status_request_active = False
        self._secondary_request_active = False
        self._timeline_request_active = False
        self._active_raid_id: str | None = None
        self._timeline: list[dict[str, object]] = []
        self._seen_timeline_ids: set[str] = set()
        self._timeline_initialized = False
        self._marker_buttons: list[QPushButton] = []
        self._nav_buttons: dict[str, QPushButton] = {}
        self._page_indices: dict[str, int] = {}
        self._allow_close = False
        self._tray_notice_shown = False
        self._last_lifecycle: str | None = None
        self._last_obs: str | None = None
        self._last_ppe: int | None = None
        self._last_rules: int | None = None
        self._last_finalization_token: str | None = None
        self._build_window()
        self._build_tray()
        self._configure_timers()

    def _build_window(self) -> None:
        self.setWindowTitle("Tarkov Personal Agent — Operations Center")
        self.resize(1480, 920)
        self.setMinimumSize(1040, 700)
        central = BackgroundWidget()
        self.setCentralWidget(central)
        shell = QHBoxLayout(central)
        shell.setContentsMargins(0, 0, 0, 0)
        shell.setSpacing(0)
        shell.addWidget(self._sidebar())

        content = QWidget()
        content.setObjectName("contentShell")
        content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(22, 18, 22, 14)
        layout.setSpacing(14)
        layout.addWidget(self._topbar())
        self.pages = QStackedWidget()
        self.pages.setObjectName("pages")
        self.pages.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._add_page("dashboard", self._dashboard_page())
        self._add_page("live", self._live_page())
        self._add_page("markers", self._markers_page())
        self._add_page("reviews", self._reviews_page())
        self._add_page(
            "ppe",
            self._feature_page(
                "PERSONAL PLAYSTYLE ENGINE",
                "Profile dimensions, evidence, confidence, and long-term trends.",
                "/ppe",
            ),
        )
        self._add_page(
            "media",
            self._feature_page(
                "MEDIA INTELLIGENCE",
                "Recordings, clips, screenshots, evidence packages, and exports.",
                "/media",
            ),
        )
        self._add_page(
            "tasks",
            self._feature_page(
                "TASKS & OBJECTIVES",
                "Quest, hideout, and session planning will be connected in a later sprint.",
                None,
            ),
        )
        self._add_page(
            "maps",
            self._feature_page(
                "MAP INTELLIGENCE",
                "Routes, locations, heatmaps, and encounter overlays are planned here.",
                None,
            ),
        )
        self._add_page("settings", self._settings_page())
        layout.addWidget(self.pages, 1)
        layout.addWidget(self._footer())
        shell.addWidget(content, 1)
        self.setStyleSheet(STYLE)
        self._set_online(False)
        self._navigate("dashboard")

    def _sidebar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(238)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 18, 14, 14)
        layout.setSpacing(7)
        brand = QHBoxLayout()
        logo = QLabel("◔")
        logo.setObjectName("brandLogo")
        names = QVBoxLayout()
        title = QLabel("TARKOV")
        title.setObjectName("brandTitle")
        subtitle = QLabel("PERSONAL AGENT")
        subtitle.setObjectName("brandSubtitle")
        names.addWidget(title)
        names.addWidget(subtitle)
        brand.addWidget(logo)
        brand.addLayout(names, 1)
        layout.addLayout(brand)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for label, icon, key in NAVIGATION:
            button = QPushButton(f"{icon}    {label.upper()}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(
                lambda checked=False, page=key: self._navigate(page)
            )
            group.addButton(button)
            self._nav_buttons[key] = button
            layout.addWidget(button)
        layout.addStretch(1)
        status = QFrame()
        status.setObjectName("sidebarStatus")
        status_layout = QVBoxLayout(status)
        status_layout.addWidget(self._caption("AGENT STATUS"))
        self.sidebar_online = QLabel("● Offline")
        self.sidebar_online.setObjectName("sidebarOnline")
        status_layout.addWidget(self.sidebar_online)
        status_layout.addWidget(self._caption("SESSION"))
        self.sidebar_session = QLabel("No active raid")
        self.sidebar_session.setObjectName("sidebarSession")
        status_layout.addWidget(self.sidebar_session)
        layout.addWidget(status)
        return frame

    def _topbar(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("topbar")
        layout = QHBoxLayout(frame)
        self.service_dot = QLabel("●")
        self.service_dot.setObjectName("serviceDot")
        self.service_label = QLabel("SERVICE OFFLINE")
        self.service_label.setObjectName("serviceText")
        api = QLabel(f"API: {self.client.base_url}")
        api.setObjectName("topbarMuted")
        app_version = QLabel(f"APP v{__version__}")
        app_version.setObjectName("topbarMuted")
        self.version_label = QLabel("SERVICE v—")
        self.version_label.setObjectName("topbarMuted")
        phase = QLabel("PHASE 6 · LOCAL INTELLIGENCE")
        phase.setObjectName("phaseBadge")
        refresh = QPushButton("REFRESH")
        refresh.setObjectName("ghostButton")
        refresh.clicked.connect(self.refresh_all)
        for widget in (
            self.service_dot,
            self.service_label,
            api,
            app_version,
            self.version_label,
        ):
            layout.addWidget(widget)
        layout.addStretch(1)
        layout.addWidget(phase)
        layout.addWidget(refresh)
        return frame

    def _configure_timers(self) -> None:
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(
            int(self.settings.desktop.poll_interval_seconds * 1000)
        )
        self.poll_timer.timeout.connect(self.refresh_status)
        self.poll_timer.start()
        self.secondary_timer = QTimer(self)
        self.secondary_timer.setInterval(5000)
        self.secondary_timer.timeout.connect(self.refresh_secondary)
        self.secondary_timer.start()
        self.clock_timer = QTimer(self)
        self.clock_timer.setInterval(1000)
        self.clock_timer.timeout.connect(self._update_clock)
        self.clock_timer.start()
        self._update_clock()

    def _add_page(self, key: str, page: QWidget) -> None:
        self._page_indices[key] = self.pages.addWidget(page)

    def _navigate(self, key: str) -> None:
        index = self._page_indices.get(key)
        if index is None:
            return
        self.pages.setCurrentIndex(index)
        for name, button in self._nav_buttons.items():
            button.setChecked(name == key)
        if key == "reviews":
            self._load_reviews()

    def _build_tray(self) -> None:
        self.tray: QSystemTrayIcon | None = None
        if (
            not self.settings.desktop.minimize_to_tray
            or not QSystemTrayIcon.isSystemTrayAvailable()
        ):
            return
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
        self.setWindowIcon(icon)
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("Tarkov Personal Agent")
        menu = QMenu()
        show = QAction("Show Operations Center", menu)
        show.triggered.connect(self.show_from_tray)
        reviews = QAction("Open Reviews", menu)
        reviews.triggered.connect(lambda: self._show_page("reviews"))
        quit_action = QAction("Quit", menu)
        quit_action.triggered.connect(self.quit_application)
        menu.addAction(show)
        menu.addAction(reviews)
        menu.addSeparator()
        menu.addAction(quit_action)
        tray.setContextMenu(menu)
        tray.activated.connect(self._tray_activated)
        tray.show()
        self.tray = tray


def _operations_palette() -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#070b0e"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#e5e9e4"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#0a1115"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#111a1e"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#11191d"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#e8eadf"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#e5e9e4"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#1d292d"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#e5e9e4"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#f0aca7"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#b5d47b"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#536744"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#f0f3eb"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor("#748084"))
    return palette


def run_desktop(settings: AppSettings, *, config_path: Path) -> int:
    application = QApplication([])
    application.setApplicationName("Tarkov Personal Agent")
    application.setOrganizationName("Tarkov Personal Agent")
    application.setStyle("Fusion")
    application.setPalette(_operations_palette())
    application.setFont(QFont("Segoe UI", 10))
    if settings.desktop.minimize_to_tray:
        application.setQuitOnLastWindowClosed(False)
    client = DesktopApiClient(settings)
    service = EmbeddedServiceManager(settings, client, config_path=config_path)
    window = DesktopWindow(settings, client, service)
    window.show()
    QTimer.singleShot(100, window.auto_start)
    return application.exec()
