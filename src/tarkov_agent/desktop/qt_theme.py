from __future__ import annotations

STYLE = r"""
* {
    outline: none;
}
QWidget {
    background: transparent;
    color: #e5e9e4;
    font-family: "Segoe UI", "Bahnschrift", sans-serif;
    font-size: 10.5pt;
}
QMainWindow,
QDialog,
QMessageBox {
    background-color: #070b0e;
}
QToolTip {
    background-color: #11191d;
    color: #e8eadf;
    border: 1px solid rgba(126, 151, 115, 180);
    border-radius: 6px;
    padding: 6px 8px;
}
QWidget#contentShell,
QStackedWidget#pages,
QWidget#scrollBody,
QWidget#scrollViewport,
QScrollArea#pageScroll,
QScrollArea#pageScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}
QWidget#pageRoot {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(8, 14, 18, 205),
        stop: 0.55 rgba(6, 11, 15, 186),
        stop: 1 rgba(5, 10, 13, 218)
    );
    border: 1px solid rgba(74, 92, 96, 105);
    border-radius: 12px;
}
QFrame#sidebar {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(4, 9, 12, 250),
        stop: 1 rgba(7, 13, 17, 238)
    );
    border-right: 1px solid rgba(83, 101, 98, 105);
}
QFrame#brand {
    background: transparent;
    border: none;
}
QLabel#brandLogo {
    color: #d6a928;
    font-size: 28pt;
    font-weight: 700;
}
QLabel#brandTitle {
    color: #e2dfcb;
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
    border-radius: 9px;
    padding: 12px 12px;
    font-weight: 600;
}
QPushButton#navButton:hover {
    color: #eef1e7;
    background: rgba(66, 80, 71, 96);
    border-color: rgba(102, 123, 105, 110);
}
QPushButton#navButton:checked {
    color: #c5e989;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(83, 105, 66, 190),
        stop: 1 rgba(46, 61, 44, 118)
    );
    border-color: rgba(151, 183, 103, 175);
}
QFrame#sidebarStatus,
QFrame#topbar,
QFrame#panel,
QFrame#heroPanel,
QFrame#statusCard,
QFrame#summaryTile,
QFrame#metricBlock,
QFrame#featureCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(27, 36, 40, 238),
        stop: 0.48 rgba(17, 25, 29, 232),
        stop: 1 rgba(10, 17, 21, 238)
    );
    border: 1px solid rgba(79, 98, 102, 145);
    border-radius: 10px;
}
QFrame#panel:hover,
QFrame#summaryTile:hover,
QFrame#featureCard:hover {
    border-color: rgba(123, 146, 120, 160);
}
QFrame#heroPanel {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(29, 40, 38, 244),
        stop: 0.5 rgba(18, 28, 29, 238),
        stop: 1 rgba(11, 18, 22, 236)
    );
    border-color: rgba(118, 140, 105, 170);
}
QFrame#metricBlock {
    background: rgba(7, 13, 17, 128);
    border-color: rgba(76, 93, 95, 90);
    padding: 4px;
}
QFrame#summaryTile {
    background: rgba(8, 15, 19, 205);
    border-color: rgba(73, 93, 98, 132);
}
QFrame#statusCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(16, 25, 30, 232),
        stop: 1 rgba(9, 16, 20, 224)
    );
}
QFrame#featureCard {
    min-height: 116px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(28, 37, 39, 235),
        stop: 1 rgba(11, 18, 22, 232)
    );
}
QFrame#topbar {
    background: rgba(6, 12, 16, 232);
    border-color: rgba(73, 91, 96, 135);
}
QFrame#footer {
    background: rgba(6, 12, 16, 226);
    border: 1px solid rgba(73, 91, 96, 92);
    border-radius: 8px;
}
QLabel#serviceDot[online="true"],
QLabel#sidebarOnline[online="true"] {
    color: #9dce69;
}
QLabel#serviceDot[online="false"],
QLabel#sidebarOnline[online="false"] {
    color: #d56c66;
}
QLabel#serviceText[online="true"] {
    color: #a9d86f;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#serviceText[online="false"] {
    color: #df756f;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#sidebarOnline {
    font-size: 12pt;
    font-weight: 650;
}
QLabel#sidebarSession {
    color: #9ca8aa;
}
QLabel#topbarMuted,
QLabel#footerMuted {
    color: #879497;
}
QLabel#footerClock {
    color: #e5e9e4;
    font-size: 11pt;
}
QLabel#pageTitle {
    color: #e8eadf;
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: 2px;
}
QLabel#pageSubtitle {
    color: #9ca9aa;
    font-size: 10.5pt;
}
QLabel#sectionTitle {
    color: #d5d9d2;
    font-size: 12pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#microLabel {
    color: #8d9a9d;
    font-size: 8.5pt;
    font-weight: 600;
    letter-spacing: 1px;
}
QLabel#metricValue {
    color: #d2d7d5;
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#metricValue[state="game_running"],
QLabel#metricValue[state="in_raid"] {
    color: #a8d969;
}
QLabel#detailValue {
    color: #d2d7d3;
    font-size: 10.5pt;
}
QLabel#connectionName {
    color: #9ba5a7;
}
QLabel#connectionValue {
    color: #a8d969;
}
QLabel#statusCardValue {
    color: #b6d77a;
    font-weight: 650;
}
QLabel#summaryValue {
    color: #dce1dc;
    font-size: 15pt;
    font-weight: 700;
}
QLabel#mutedText,
QLabel#featureBody {
    color: #9ca8aa;
    font-size: 11pt;
}
QLabel#featureTitle {
    color: #e0e4dc;
    font-size: 12pt;
    font-weight: 700;
}
QLabel#featureDescription {
    color: #97a4a6;
    font-size: 9.5pt;
}
QLabel#featureStatus {
    border: 1px solid rgba(115, 135, 113, 145);
    border-radius: 8px;
    padding: 3px 8px;
    color: #b8c2b8;
    background: rgba(25, 34, 34, 200);
    font-size: 8pt;
    font-weight: 700;
}
QLabel#featureStatus[status="ready"] {
    color: #c7e891;
    border-color: rgba(145, 177, 98, 170);
    background: rgba(65, 82, 49, 155);
}
QLabel#featureStatus[status="next"] {
    color: #efd17a;
    border-color: rgba(181, 143, 65, 170);
    background: rgba(78, 61, 30, 155);
}
QFrame#panelDivider,
QFrame#topDivider {
    color: rgba(92, 109, 111, 108);
}
QPushButton {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(39, 52, 56, 232),
        stop: 1 rgba(24, 34, 38, 235)
    );
    color: #dce2de;
    border: 1px solid rgba(83, 107, 111, 160);
    border-radius: 8px;
    padding: 9px 13px;
    font-weight: 650;
}
QPushButton:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(58, 75, 73, 242),
        stop: 1 rgba(37, 50, 51, 238)
    );
    border-color: rgba(151, 176, 133, 185);
}
QPushButton:pressed {
    background: rgba(22, 31, 34, 248);
}
QPushButton:disabled {
    color: #667174;
    background: rgba(14, 22, 27, 185);
    border-color: rgba(58, 70, 73, 90);
}
QPushButton#primaryAction {
    text-align: left;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(58, 83, 63, 236),
        stop: 1 rgba(31, 50, 42, 235)
    );
    border-color: rgba(122, 163, 104, 185);
    color: #e0edd5;
    font-size: 11pt;
}
QPushButton#warningAction {
    text-align: left;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(84, 68, 38, 236),
        stop: 1 rgba(53, 43, 27, 235)
    );
    border-color: rgba(177, 143, 68, 185);
    color: #ead9aa;
    font-size: 11pt;
}
QPushButton#dangerAction {
    text-align: left;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(91, 43, 47, 238),
        stop: 1 rgba(55, 28, 31, 238)
    );
    border-color: rgba(176, 77, 82, 190);
    color: #f0aca7;
    font-size: 11pt;
}
QPushButton#markerButton {
    min-height: 42px;
    text-align: left;
    background: rgba(20, 31, 36, 232);
    border-color: rgba(76, 96, 100, 152);
}
QPushButton#markerButton:hover {
    color: #e1c26c;
    border-color: rgba(214, 169, 40, 180);
    background: rgba(45, 48, 37, 230);
}
QPushButton#smallButton,
QPushButton#ghostButton {
    background: rgba(17, 26, 31, 200);
    color: #aeb8ba;
    padding: 6px 10px;
    font-size: 9pt;
}
QPushButton#primaryCompact {
    background: rgba(72, 94, 59, 220);
    border-color: rgba(142, 174, 97, 175);
    color: #dcebc9;
}
QTableWidget {
    background: rgba(6, 12, 16, 205);
    alternate-background-color: rgba(15, 24, 28, 195);
    border: 1px solid rgba(66, 82, 86, 118);
    border-radius: 7px;
    color: #cfd5d3;
    selection-background-color: rgba(78, 99, 70, 180);
    selection-color: #eef4e6;
}
QTableWidget::item {
    padding: 7px;
    border-bottom: 1px solid rgba(63, 78, 81, 58);
}
QHeaderView::section {
    background: rgba(12, 21, 25, 242);
    color: #8f9da0;
    border: none;
    border-bottom: 1px solid rgba(78, 95, 98, 125);
    padding: 7px;
    font-size: 8.5pt;
    font-weight: 700;
}
QLineEdit,
QComboBox,
QTextEdit,
QPlainTextEdit {
    background: rgba(7, 13, 17, 236);
    border: 1px solid rgba(75, 92, 96, 158);
    border-radius: 7px;
    padding: 8px;
    color: #e2e6e1;
    selection-background-color: #5b6d49;
}
QComboBox QAbstractItemView {
    background: #10191d;
    border: 1px solid #536165;
    selection-background-color: #536744;
    color: #e2e6e1;
}
QScrollArea {
    background: transparent;
    border: none;
}
QScrollBar:vertical {
    background: rgba(8, 14, 18, 168);
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(103, 118, 111, 165);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(139, 157, 143, 190);
}
QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {
    height: 0;
}
QWebEngineView#reviewWeb {
    background: #0b100f;
    border: 1px solid rgba(73, 91, 96, 140);
    border-radius: 10px;
}
QStatusBar {
    color: #879497;
}
"""
