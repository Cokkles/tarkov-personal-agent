from __future__ import annotations

_STYLE = """
QWidget {
    color: #e5e9e4;
    font-family: "Segoe UI", "Bahnschrift", sans-serif;
    font-size: 10.5pt;
}
QMainWindow, QDialog { background: #080d10; }
QWidget#contentShell { background: transparent; }
QFrame#sidebar {
    background: rgba(6, 12, 16, 238);
    border-right: 1px solid rgba(83, 101, 98, 90);
}
QFrame#brand { background: transparent; border: none; }
QLabel#brandLogo { color: #d6a928; font-size: 28pt; font-weight: 700; }
QLabel#brandTitle {
    color: #d8d5bf;
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: 2px;
}
QLabel#brandSubtitle {
    color: #a9cf66;
    font-size: 11pt;
    font-weight: 700;
    letter-spacing: 2px;
}
QPushButton#navButton {
    text-align: left;
    background: transparent;
    color: #b9c0c2;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 12px 12px;
    font-weight: 600;
}
QPushButton#navButton:hover {
    color: #eef1e7;
    background: rgba(66, 80, 71, 90);
    border-color: rgba(102, 123, 105, 100);
}
QPushButton#navButton:checked {
    color: #b7df73;
    background: rgba(75, 94, 64, 150);
    border-color: rgba(143, 174, 98, 150);
}
QFrame#sidebarStatus,
QFrame#topbar,
QFrame#panel,
QFrame#heroPanel,
QFrame#statusCard,
QFrame#summaryTile {
    background: rgba(10, 17, 22, 214);
    border: 1px solid rgba(73, 91, 96, 125);
    border-radius: 10px;
}
QFrame#heroPanel {
    background: rgba(10, 17, 22, 226);
    border-color: rgba(96, 111, 96, 145);
}
QFrame#topbar { background: rgba(7, 13, 17, 222); }
QFrame#footer {
    background: rgba(7, 13, 17, 212);
    border-top: 1px solid rgba(73, 91, 96, 85);
    border-radius: 7px;
}
QLabel#serviceDot[online="true"], QLabel#sidebarOnline[online="true"] { color: #9dce69; }
QLabel#serviceDot[online="false"], QLabel#sidebarOnline[online="false"] { color: #d56c66; }
QLabel#serviceText[online="true"] { color: #a9d86f; font-weight: 700; letter-spacing: 1px; }
QLabel#serviceText[online="false"] { color: #df756f; font-weight: 700; letter-spacing: 1px; }
QLabel#sidebarOnline { font-size: 12pt; font-weight: 650; }
QLabel#sidebarSession { color: #9ca8aa; }
QLabel#topbarMuted, QLabel#footerMuted { color: #879497; }
QLabel#footerClock { color: #e5e9e4; font-size: 11pt; }
QLabel#pageTitle {
    color: #e8eadf;
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: 2px;
}
QLabel#pageSubtitle { color: #92a0a3; font-size: 10.5pt; }
QLabel#sectionTitle {
    color: #c7ced0;
    font-size: 12pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#microLabel {
    color: #7f8c8f;
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 1px;
}
QLabel#metricValue {
    color: #c6cbd0;
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#metricValue[state="game_running"],
QLabel#metricValue[state="in_raid"] { color: #a8d969; }
QLabel#detailValue { color: #d2d7d3; font-size: 10.5pt; }
QLabel#connectionName { color: #9ba5a7; }
QLabel#connectionValue { color: #a8d969; }
QLabel#statusCardValue { color: #b6d77a; font-weight: 650; }
QLabel#summaryValue { color: #dce1dc; font-size: 15pt; font-weight: 700; }
QLabel#mutedText, QLabel#featureBody { color: #9ca8aa; font-size: 11pt; }
QFrame#panelDivider { color: rgba(80, 97, 100, 105); }
QFrame#topDivider { color: rgba(91, 105, 106, 100); }
QPushButton {
    background: rgba(31, 43, 47, 220);
    color: #dce2de;
    border: 1px solid rgba(80, 103, 107, 150);
    border-radius: 8px;
    padding: 9px 13px;
    font-weight: 650;
}
QPushButton:hover {
    background: rgba(50, 66, 67, 235);
    border-color: rgba(145, 170, 130, 175);
}
QPushButton:pressed { background: rgba(24, 34, 37, 245); }
QPushButton:disabled {
    color: #5e696b;
    background: rgba(14, 22, 27, 175);
    border-color: rgba(58, 70, 73, 90);
}
QPushButton#primaryAction {
    text-align: left;
    background: rgba(36, 58, 47, 220);
    border-color: rgba(112, 151, 99, 170);
    color: #dbe9d0;
    font-size: 11pt;
}
QPushButton#warningAction {
    text-align: left;
    background: rgba(63, 52, 31, 220);
    border-color: rgba(166, 132, 62, 175);
    color: #ead9aa;
    font-size: 11pt;
}
QPushButton#dangerAction {
    text-align: left;
    background: rgba(73, 35, 38, 225);
    border-color: rgba(163, 72, 77, 180);
    color: #edaaa5;
    font-size: 11pt;
}
QPushButton#markerButton {
    min-height: 42px;
    text-align: left;
    background: rgba(23, 34, 39, 225);
    border-color: rgba(74, 93, 97, 145);
}
QPushButton#markerButton:hover {
    color: #e1c26c;
    border-color: rgba(214, 169, 40, 170);
}
QPushButton#smallButton, QPushButton#ghostButton {
    background: rgba(17, 26, 31, 190);
    color: #aeb8ba;
    padding: 6px 10px;
    font-size: 9pt;
}
QPushButton#primaryCompact {
    background: rgba(72, 94, 59, 215);
    border-color: rgba(142, 174, 97, 165);
    color: #dcebc9;
}
QTableWidget {
    background: rgba(7, 13, 17, 180);
    alternate-background-color: rgba(16, 25, 29, 165);
    border: 1px solid rgba(66, 82, 86, 110);
    border-radius: 7px;
    color: #cfd5d3;
    selection-background-color: rgba(78, 99, 70, 170);
    selection-color: #eef4e6;
}
QHeaderView::section {
    background: rgba(10, 18, 22, 230);
    color: #7f8d90;
    border: none;
    border-bottom: 1px solid rgba(70, 86, 89, 115);
    padding: 7px;
    font-size: 8.5pt;
    font-weight: 700;
}
QLineEdit, QComboBox {
    background: rgba(8, 14, 18, 230);
    border: 1px solid rgba(75, 92, 96, 150);
    border-radius: 7px;
    padding: 8px;
    selection-background-color: #5b6d49;
}
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical {
    background: rgba(8, 14, 18, 160);
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(103, 118, 111, 150);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QWebEngineView#reviewWeb {
    background: #0b100f;
    border: 1px solid rgba(73, 91, 96, 130);
    border-radius: 10px;
}
QStatusBar { color: #879497; }
"""
