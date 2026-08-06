from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover
    QWebEngineView = None  # type: ignore[assignment,misc]


class OperationsCenterPagesMixin:
    def _dashboard_page(self) -> QWidget:
        page, layout = self._scroll_page()
        hero = self._panel("CURRENT STATUS", "heroPanel")
        grid = QGridLayout()
        lifecycle = self._metric("LIFECYCLE")
        self.lifecycle_value = lifecycle.findChild(QLabel, "metricValue")
        raid = self._metric("ACTIVE RAID")
        self.active_raid_value = raid.findChild(QLabel, "metricValue")
        connections = self._metric("CONNECTIONS", value=False)
        connection_layout = connections.layout()
        self.obs_value = self._connection(connection_layout, "OBS")
        self.ppe_value = self._connection(connection_layout, "PPE")
        self.rules_value = self._connection(connection_layout, "AUTO LOG RULES")
        grid.addWidget(lifecycle, 0, 0)
        grid.addWidget(raid, 0, 1)
        grid.addWidget(connections, 0, 2)
        hero.layout().addLayout(grid)
        details = QHBoxLayout()
        self.raid_id_value = self._detail(details, "RAID ID")
        self.raid_timer_value = self._detail(details, "SESSION TIME", "00:00:00")
        self.raid_objective_value = self._detail(details, "PRIMARY OBJECTIVE")
        hero.layout().addLayout(details)
        layout.addWidget(hero)

        controls = QHBoxLayout()
        self.start_raid_button = self._action("▷  START RAID", "Begin a new raid", "primaryAction", self.start_raid)
        self.end_raid_button = self._action("□  END RAID", "Complete current raid", "warningAction", self.end_raid)
        self.abort_raid_button = self._action("△  ABORT RAID", "Cancel current raid record", "dangerAction", self.abort_raid)
        controls.addWidget(self.start_raid_button)
        controls.addWidget(self.end_raid_button)
        controls.addWidget(self.abort_raid_button)
        layout.addLayout(controls)

        lower = QHBoxLayout()
        markers = self._panel("LIVE MARKERS")
        self.dashboard_markers = self._table(["TIME", "MARKER", "TYPE", "SOURCE"])
        markers.layout().addWidget(self.dashboard_markers)
        self.marker_count = QLabel("0 marker events")
        self.marker_count.setObjectName("mutedText")
        markers.layout().addWidget(self.marker_count)
        lower.addWidget(markers, 3)
        side = QVBoxLayout()
        activity = self._panel("ACTIVITY LOG")
        self.activity_table = self._table(["TIME", "EVENT"])
        activity.layout().addWidget(self.activity_table)
        side.addWidget(activity, 3)
        recent = self._panel("RECENT REVIEWS")
        self.recent_table = self._table(["MAP", "RESULT", "STATUS"])
        recent.layout().addWidget(self.recent_table)
        open_reviews = QPushButton("VIEW ALL REVIEWS  →")
        open_reviews.setObjectName("smallButton")
        open_reviews.clicked.connect(lambda: self._navigate("reviews"))
        recent.layout().addWidget(open_reviews, 0, Qt.AlignmentFlag.AlignRight)
        side.addWidget(recent, 2)
        lower.addLayout(side, 2)
        layout.addLayout(lower, 1)

        cards = QHBoxLayout()
        self.obs_card = self._status_card(cards, "OBS")
        self.ppe_card = self._status_card(cards, "PPE")
        self.queue_card = self._status_card(cards, "REVIEW QUEUE", "0 pending")
        self.media_card = self._status_card(cards, "MEDIA")
        layout.addLayout(cards)
        return page

    def _live_page(self) -> QWidget:
        page, layout = self._scroll_page()
        self._page_heading(layout, "LIVE RAID", "Active raid status, objectives, quick markers, and the event timeline.")
        summary = self._panel("RAID OVERVIEW")
        grid = QGridLayout()
        self.live_map = self._summary(grid, 0, 0, "MAP")
        self.live_character = self._summary(grid, 0, 1, "CHARACTER")
        self.live_timer = self._summary(grid, 0, 2, "SESSION", "00:00:00")
        self.live_objective = self._summary(grid, 1, 0, "PRIMARY OBJECTIVE", span=2)
        self.live_recording = self._summary(grid, 1, 2, "RECORDING")
        summary.layout().addLayout(grid)
        layout.addWidget(summary)
        actions = self._panel("QUICK MARKERS")
        marker_grid = QGridLayout()
        self._marker_buttons_into(marker_grid)
        actions.layout().addLayout(marker_grid)
        layout.addWidget(actions)
        timeline = self._panel("RAID EVENT TIMELINE")
        self.live_timeline = self._table(["TIME", "EVENT", "TYPE", "SOURCE"])
        self.live_timeline.setProperty("allEvents", True)
        timeline.layout().addWidget(self.live_timeline)
        layout.addWidget(timeline, 1)
        return page

    def _markers_page(self) -> QWidget:
        page, layout = self._scroll_page()
        self._page_heading(layout, "MARKERS", "Record moments from the desktop or Stream Deck and verify every trigger.")
        actions = self._panel("MARKER ACTIONS")
        grid = QGridLayout()
        self._marker_buttons_into(grid)
        actions.layout().addLayout(grid)
        layout.addWidget(actions)
        history = self._panel("CURRENT RAID MARKER HISTORY")
        self.markers_table = self._table(["TIME", "MARKER", "TYPE", "SOURCE"])
        history.layout().addWidget(self.markers_table)
        layout.addWidget(history, 1)
        return page

    def _reviews_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        self._page_heading(titles, "REVIEWS", "Complete raid review, encounter notes, evidence validation, and finalization inside the app.")
        header.addLayout(titles)
        header.addStretch(1)
        reload_button = QPushButton("RELOAD")
        reload_button.setObjectName("smallButton")
        reload_button.clicked.connect(self._load_reviews)
        browser_button = QPushButton("OPEN IN BROWSER")
        browser_button.setObjectName("smallButton")
        browser_button.clicked.connect(lambda: self.open_page("/"))
        header.addWidget(reload_button)
        header.addWidget(browser_button)
        layout.addLayout(header)
        if QWebEngineView is not None:
            self.review_web = QWebEngineView()
            self.review_web.setObjectName("reviewWeb")
            layout.addWidget(self.review_web, 1)
        else:
            self.review_web = None
            fallback = self._panel("REVIEW WORKSPACE UNAVAILABLE")
            message = QLabel("Qt WebEngine is not installed. Use Open in Browser or reinstall the desktop extra.")
            message.setWordWrap(True)
            fallback.layout().addWidget(message)
            layout.addWidget(fallback, 1)
        return page

    def _feature_page(self, title: str, description: str, path: str | None) -> QWidget:
        page, layout = self._scroll_page()
        self._page_heading(layout, title, description)
        panel = self._panel("OPERATIONS CENTER MODULE")
        message = QLabel("The permanent page shell is ready. Its dedicated native workflow will be connected as the intelligence pipeline expands.")
        message.setObjectName("featureBody")
        message.setWordWrap(True)
        panel.layout().addWidget(message)
        if path is not None:
            button = QPushButton("OPEN CURRENT WORKSPACE")
            button.setObjectName("primaryCompact")
            button.clicked.connect(lambda: self.open_page(path))
            panel.layout().addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(panel)
        layout.addStretch(1)
        return page

    def _settings_page(self) -> QWidget:
        page, layout = self._scroll_page()
        self._page_heading(layout, "SETTINGS", "Local service controls, API details, and configuration access.")
        panel = self._panel("LOCAL SERVICE")
        row = QHBoxLayout()
        self.settings_service = QLabel("Offline")
        self.start_service_button = QPushButton("START SERVICE")
        self.start_service_button.setObjectName("primaryCompact")
        self.start_service_button.clicked.connect(self.start_service)
        self.stop_service_button = QPushButton("STOP SERVICE")
        self.stop_service_button.setObjectName("smallButton")
        self.stop_service_button.clicked.connect(self.stop_service)
        row.addWidget(self.settings_service)
        row.addStretch(1)
        row.addWidget(self.start_service_button)
        row.addWidget(self.stop_service_button)
        panel.layout().addLayout(row)
        layout.addWidget(panel)
        info = self._panel("CONNECTION DETAILS")
        form = QFormLayout()
        form.addRow("API address", QLabel(self.client.base_url))
        form.addRow("Configuration", QLabel(str(self.service.config_path)))
        form.addRow("Polling", QLabel(f"{self.settings.desktop.poll_interval_seconds:g} seconds"))
        info.layout().addLayout(form)
        layout.addWidget(info)
        layout.addStretch(1)
        return page

    def _footer(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("footer")
        layout = QHBoxLayout(frame)
        self.footer_message = QLabel("Operations Center ready")
        self.footer_message.setObjectName("footerMuted")
        self.footer_clock = QLabel("—")
        self.footer_clock.setObjectName("footerClock")
        layout.addWidget(self.footer_message)
        layout.addStretch(1)
        layout.addWidget(self.footer_clock)
        return frame
