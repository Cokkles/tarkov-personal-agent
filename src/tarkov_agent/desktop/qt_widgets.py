from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from tarkov_agent.desktop.qt_common import MARKERS


class OperationsCenterWidgetsMixin:
    @staticmethod
    def _apply_shadow(widget: QWidget, *, blur: int = 24, y_offset: int = 5) -> None:
        effect = QGraphicsDropShadowEffect(widget)
        effect.setBlurRadius(blur)
        effect.setOffset(0, y_offset)
        effect.setColor(QColor(0, 0, 0, 118))
        widget.setGraphicsEffect(effect)

    @staticmethod
    def _scroll_page() -> tuple[QWidget, QVBoxLayout]:
        body = QWidget()
        body.setObjectName("scrollBody")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 10, 10, 10)
        body_layout.setSpacing(14)

        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        scroll.setAutoFillBackground(False)
        scroll.viewport().setObjectName("scrollViewport")
        scroll.viewport().setAutoFillBackground(False)
        viewport_palette = scroll.viewport().palette()
        viewport_palette.setColor(QPalette.ColorRole.Base, QColor(0, 0, 0, 0))
        viewport_palette.setColor(QPalette.ColorRole.Window, QColor(0, 0, 0, 0))
        scroll.viewport().setPalette(viewport_palette)

        page = QWidget()
        page.setObjectName("pageRoot")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        return page, body_layout

    @staticmethod
    def _panel(title: str, name: str = "panel") -> QFrame:
        frame = QFrame()
        frame.setObjectName(name)
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 11, 12, 12)
        layout.setSpacing(9)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("panelDivider")
        layout.addWidget(line)
        OperationsCenterWidgetsMixin._apply_shadow(frame)
        return frame

    @staticmethod
    def _feature_card(title: str, description: str, status: str, state: str) -> QFrame:
        frame = QFrame()
        frame.setObjectName("featureCard")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(14, 13, 14, 13)
        layout.setSpacing(8)
        top = QHBoxLayout()
        heading = QLabel(title)
        heading.setObjectName("featureTitle")
        badge = QLabel(status.upper())
        badge.setObjectName("featureStatus")
        badge.setProperty("status", state)
        top.addWidget(heading)
        top.addStretch(1)
        top.addWidget(badge)
        layout.addLayout(top)
        body = QLabel(description)
        body.setObjectName("featureDescription")
        body.setWordWrap(True)
        layout.addWidget(body)
        layout.addStretch(1)
        OperationsCenterWidgetsMixin._apply_shadow(frame, blur=18, y_offset=4)
        return frame

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("microLabel")
        return label

    @staticmethod
    def _metric(title: str, *, value: bool = True) -> QFrame:
        frame = QFrame()
        frame.setObjectName("metricBlock")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 8, 10, 9)
        layout.addWidget(OperationsCenterWidgetsMixin._caption(title))
        if value:
            label = QLabel("—")
            label.setObjectName("metricValue")
            label.setWordWrap(True)
            layout.addWidget(label)
        return frame

    @staticmethod
    def _connection(layout: object, name: str) -> QLabel:
        assert isinstance(layout, QVBoxLayout)
        row = QHBoxLayout()
        label = QLabel(name)
        label.setObjectName("connectionName")
        value = QLabel("• —")
        value.setObjectName("connectionValue")
        row.addWidget(label)
        row.addStretch(1)
        row.addWidget(value)
        layout.addLayout(row)
        return value

    @staticmethod
    def _detail(layout: QHBoxLayout, title: str, value: str = "—") -> QLabel:
        box = QVBoxLayout()
        box.addWidget(OperationsCenterWidgetsMixin._caption(title))
        label = QLabel(value)
        label.setObjectName("detailValue")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.addWidget(label)
        layout.addLayout(box, 1)
        return label

    @staticmethod
    def _action(
        title: str,
        subtitle: str,
        name: str,
        callback: Callable[[], None],
    ) -> QPushButton:
        button = QPushButton(f"{title}\n{subtitle}")
        button.setObjectName(name)
        button.setMinimumHeight(70)
        button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        button.clicked.connect(callback)
        return button

    @staticmethod
    def _table(columns: list[str]) -> QTableWidget:
        table = QTableWidget(0, len(columns))
        table.setHorizontalHeaderLabels(columns)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        table.setMinimumHeight(170)
        return table

    @staticmethod
    def _status_card(layout: QHBoxLayout, title: str, value: str = "—") -> QLabel:
        frame = QFrame()
        frame.setObjectName("statusCard")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        inner = QVBoxLayout(frame)
        inner.setContentsMargins(12, 10, 12, 10)
        inner.addWidget(OperationsCenterWidgetsMixin._caption(title))
        label = QLabel(value)
        label.setObjectName("statusCardValue")
        inner.addWidget(label)
        layout.addWidget(frame, 1)
        return label

    @staticmethod
    def _summary(
        grid: QGridLayout,
        row: int,
        column: int,
        title: str,
        value: str = "—",
        *,
        span: int = 1,
    ) -> QLabel:
        frame = QFrame()
        frame.setObjectName("summaryTile")
        frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.addWidget(OperationsCenterWidgetsMixin._caption(title))
        label = QLabel(value)
        label.setObjectName("summaryValue")
        label.setWordWrap(True)
        layout.addWidget(label)
        grid.addWidget(frame, row, column, 1, span)
        return label

    @staticmethod
    def _page_heading(layout: QVBoxLayout, title: str, subtitle: str) -> None:
        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        description = QLabel(subtitle)
        description.setObjectName("pageSubtitle")
        description.setWordWrap(True)
        layout.addWidget(heading)
        layout.addWidget(description)

    def _marker_buttons_into(self, grid: QGridLayout) -> None:
        for index, (marker_type, icon, label) in enumerate(MARKERS):
            button = QPushButton(f"{icon}  {label}")
            button.setObjectName("markerButton")
            button.setToolTip(f"Stable marker ID: {marker_type.value}")
            button.clicked.connect(
                lambda checked=False, selected=marker_type: self.add_marker(selected)
            )
            grid.addWidget(button, index // 4, index % 4)
            self._marker_buttons.append(button)
