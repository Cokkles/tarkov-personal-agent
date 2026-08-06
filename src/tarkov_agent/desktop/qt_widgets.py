from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel,
    QPushButton, QScrollArea, QSizePolicy, QTableWidget, QVBoxLayout, QWidget,
)

from tarkov_agent.desktop.qt_common import MARKERS


class OperationsCenterWidgetsMixin:
    @staticmethod
    def _scroll_page() -> tuple[QWidget, QVBoxLayout]:
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 8, 0)
        body_layout.setSpacing(14)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(body)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)
        return page, body_layout

    @staticmethod
    def _panel(title: str, name: str = "panel") -> QFrame:
        frame = QFrame()
        frame.setObjectName(name)
        layout = QVBoxLayout(frame)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setObjectName("panelDivider")
        layout.addWidget(line)
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
        layout = QVBoxLayout(frame)
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
    def _action(title: str, subtitle: str, name: str, callback: Callable[[], None]) -> QPushButton:
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
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.setMinimumHeight(170)
        return table

    @staticmethod
    def _status_card(layout: QHBoxLayout, title: str, value: str = "—") -> QLabel:
        frame = QFrame()
        frame.setObjectName("statusCard")
        inner = QVBoxLayout(frame)
        inner.addWidget(OperationsCenterWidgetsMixin._caption(title))
        label = QLabel(value)
        label.setObjectName("statusCardValue")
        inner.addWidget(label)
        layout.addWidget(frame, 1)
        return label

    @staticmethod
    def _summary(grid: QGridLayout, row: int, column: int, title: str, value: str = "—", *, span: int = 1) -> QLabel:
        frame = QFrame()
        frame.setObjectName("summaryTile")
        layout = QVBoxLayout(frame)
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
            button.clicked.connect(lambda checked=False, selected=marker_type: self.add_marker(selected))
            grid.addWidget(button, index // 4, index % 4)
            self._marker_buttons.append(button)
