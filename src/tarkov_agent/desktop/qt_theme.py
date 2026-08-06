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
    border: 1px solid rgba(151, 169, 120, 185);
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
        stop: 0 rgba(8, 14, 18, 180),
        stop: 0.55 rgba(6, 11, 15, 160),
        stop: 1 rgba(5, 10, 13, 205)
    );
    border: 1px solid rgba(87, 105, 104, 110);
    border-radius: 12px;
}
QFrame#sidebar {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(3, 8, 11, 252),
        stop: 1 rgba(7, 13, 17, 238)
    );
    border-right: 1px solid rgba(103, 116, 94, 122);
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
    color: #e5dfc8;
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: 2px;
}
QLabel#brandSubtitle {
    color: #b4dc6d;
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
    color: #f1f2e9;
    background: rgba(77, 89, 71, 108);
    border-color: rgba(120, 139, 106, 124);
}
QPushButton#navButton:checked {
    color: #cced91;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(91, 112, 67, 205),
        stop: 0.72 rgba(48, 64, 45, 142),
        stop: 1 rgba(36, 46, 38, 88)
    );
    border-color: rgba(164, 193, 111, 190);
}
QFrame#sidebarStatus,
QFrame#topbar,
QFrame#panel,
QFrame#heroPanel,
QFrame#pipelinePanel,
QFrame#statusCard,
QFrame#summaryTile,
QFrame#metricBlock,
QFrame#featureCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(29, 39, 42, 229),
        stop: 0.48 rgba(17, 25, 29, 222),
        stop: 1 rgba(9, 16, 20, 229)
    );
    border: 1px solid rgba(87, 105, 108, 148);
    border-radius: 10px;
}
QFrame#panel:hover,
QFrame#summaryTile:hover,
QFrame#featureCard:hover {
    border-color: rgba(140, 158, 122, 175);
}
QFrame#heroPanel {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(35, 48, 42, 238),
        stop: 0.34 rgba(24, 34, 32, 232),
        stop: 0.72 rgba(16, 24, 27, 225),
        stop: 1 rgba(10, 17, 21, 222)
    );
    border: 1px solid rgba(141, 158, 105, 185);
    border-top: 2px solid rgba(197, 176, 91, 190);
}
QFrame#pipelinePanel {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(33, 42, 35, 235),
        stop: 0.48 rgba(20, 29, 29, 228),
        stop: 1 rgba(12, 19, 23, 226)
    );
    border: 1px solid rgba(145, 157, 105, 170);
    border-left: 3px solid rgba(213, 169, 54, 210);
}
QFrame#metricBlock {
    background: rgba(6, 12, 16, 136);
    border-color: rgba(87, 102, 98, 102);
    padding: 4px;
}
QFrame#summaryTile {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(12, 21, 24, 205),
        stop: 1 rgba(7, 14, 18, 194)
    );
    border-color: rgba(81, 101, 103, 142);
}
QFrame#statusCard {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(19, 29, 31, 226),
        stop: 1 rgba(8, 15, 19, 216)
    );
    border-left: 3px solid rgba(145, 174, 99, 176);
}
QFrame#featureCard {
    min-height: 116px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(31, 41, 40, 225),
        stop: 1 rgba(10, 17, 21, 218)
    );
}
QFrame#topbar {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 rgba(5, 11, 15, 238),
        stop: 0.7 rgba(7, 13, 17, 224),
        stop: 1 rgba(16, 22, 20, 220)
    );
    border-color: rgba(89, 104, 101, 142);
}
QFrame#footer {
    background: rgba(5, 11, 15, 218);
    border: 1px solid rgba(79, 96, 98, 100);
    border-radius: 8px;
}
QLabel#phaseBadge {
    color: #d8c172;
    background: rgba(75, 64, 34, 150);
    border: 1px solid rgba(177, 147, 67, 158);
    border-radius: 8px;
    padding: 4px 9px;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#serviceDot[online="true"],
QLabel#sidebarOnline[online="true"] {
    color: #a7d96b;
}
QLabel#serviceDot[online="false"],
QLabel#sidebarOnline[online="false"] {
    color: #d56c66;
}
QLabel#serviceText[online="true"] {
    color: #b2e276;
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
    color: #dadcd1;
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
    color: #d7dcda;
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#metricValue[state="game_running"],
QLabel#metricValue[state="in_raid"] {
    color: #b0df70;
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
    color: #bddf80;
    font-weight: 650;
}
QLabel#summaryValue {
    color: #e0e5df;
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
QLabel#pipelineStatus {
    color: #aeb8b4;
    background: rgba(20, 29, 29, 190);
    border: 1px solid rgba(105, 120, 111, 145);
    border-radius: 9px;
    padding: 5px 10px;
    font-size: 9pt;
    font-weight: 800;
    letter-spacing: 1px;
}
QLabel#pipelineStatus[state="active"] {
    color: #f0d17a;
    background: rgba(79, 61, 29, 175);
    border-color: rgba(194, 154, 66, 190);
}
QLabel#pipelineStatus[state="complete"] {
    color: #c9ec91;
    background: rgba(58, 80, 43, 180);
    border-color: rgba(145, 184, 95, 190);
}
QLabel#pipelineStatus[state="error"] {
    color: #f0aaa4;
    background: rgba(87, 39, 43, 180);
    border-color: rgba(183, 77, 83, 195);
}
QLabel#pipelineMessage {
    color: #aab4b2;
    font-size: 9.5pt;
}
QLabel#pipelineStep {
    color: #707c7e;
    background: rgba(7, 14, 18, 185);
    border: 1px solid rgba(66, 83, 86, 105);
    border-radius: 7px;
    padding: 6px 8px;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.5px;
}
QLabel#pipelineStep[state="active"] {
    color: #f0d17a;
    background: rgba(74, 58, 29, 165);
    border-color: rgba(184, 145, 63, 182);
}
QLabel#pipelineStep[state="done"] {
    color: #c3e487;
    background: rgba(52, 71, 41, 165);
    border-color: rgba(126, 160, 87, 175);
}
QLabel#pipelineStep[state="error"] {
    color: #efaaa4;
    background: rgba(82, 37, 40, 170);
    border-color: rgba(176, 72, 78, 185);
}
QFrame#panelDivider,
QFrame#topDivider {
    color: rgba(100, 113, 108, 112);
}
QPushButton {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(42, 55, 58, 226),
        stop: 1 rgba(22, 32, 36, 230)
    );
    color: #dce2de;
    border: 1px solid rgba(87, 110, 111, 164);
    border-radius: 8px;
    padding: 9px 13px;
    font-weight: 650;
}
QPushButton:hover {
    background: qlineargradient(
        x1: 0, y1: 0, x2: 0, y2: 1,
        stop: 0 rgba(62, 79, 75, 238),
        stop: 1 rgba(35, 48, 48, 235)
    );
    border-color: rgba(160, 181, 137, 190);
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
        stop: 0 rgba(64, 91, 67, 238),
        stop: 0.58 rgba(40, 63, 49, 236),
        stop: 1 rgba(26, 44, 38, 232)
    );
    border-color: rgba(137, 177, 112, 190);
    color: #e5f0d9;
    font-size: 11pt;
}
QPushButton#warningAction {
    text-align: left;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(96, 77, 39, 238),
        stop: 0.58 rgba(66, 53, 31, 236),
        stop: 1 rgba(45, 37, 25, 232)
    );
    border-color: rgba(194, 155, 72, 192);
    color: #efddb0;
    font-size: 11pt;
}
QPushButton#dangerAction {
    text-align: left;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 rgba(99, 46, 50, 238),
        stop: 0.58 rgba(70, 34, 38, 236),
        stop: 1 rgba(48, 25, 28, 232)
    );
    border-color: rgba(190, 82, 87, 192);
    color: #f1b0aa;
    font-size: 11pt;
}
QPushButton#markerButton {
    min-height: 42px;
    text-align: left;
    background: rgba(18, 29, 34, 222);
    border-color: rgba(79, 99, 102, 154);
}
QPushButton#markerButton:hover {
    color: #e6c76f;
    border-color: rgba(214, 169, 40, 185);
    background: rgba(48, 50, 36, 226);
}
QPushButton#smallButton,
QPushButton#ghostButton {
    background: rgba(15, 24, 29, 190);
    color: #aeb8ba;
    padding: 6px 10px;
    font-size: 9pt;
}
QPushButton#primaryCompact {
    background: rgba(72, 94, 59, 220);
    border-color: rgba(142, 174, 97, 175);
    color: #dcebc9;
}
QPushButton#warningCompact {
    background: rgba(88, 66, 29, 205);
    border-color: rgba(190, 149, 64, 180);
    color: #f0d48a;
    padding: 6px 10px;
    font-size: 8.5pt;
}
QProgressBar#finalizationProgress {
    min-height: 8px;
    max-height: 8px;
    background: rgba(4, 10, 13, 210);
    border: 1px solid rgba(74, 88, 86, 118);
    border-radius: 4px;
}
QProgressBar#finalizationProgress::chunk {
    border-radius: 3px;
    background: qlineargradient(
        x1: 0, y1: 0, x2: 1, y2: 0,
        stop: 0 #8eaa5d,
        stop: 0.72 #c5a744,
        stop: 1 #e0c46b
    );
}
QTableWidget {
    background: rgba(5, 11, 15, 182);
    alternate-background-color: rgba(14, 23, 27, 180);
    border: 1px solid rgba(73, 89, 91, 120);
    border-radius: 7px;
    color: #cfd5d3;
    selection-background-color: rgba(82, 105, 71, 180);
    selection-color: #eef4e6;
}
QTableWidget::item {
    padding: 7px;
    border-bottom: 1px solid rgba(63, 78, 81, 58);
}
QHeaderView::section {
    background: rgba(11, 20, 24, 232);
    color: #95a3a4;
    border: none;
    border-bottom: 1px solid rgba(84, 99, 99, 126);
    padding: 7px;
    font-size: 8.5pt;
    font-weight: 700;
}
QLineEdit,
QComboBox,
QTextEdit,
QPlainTextEdit {
    background: rgba(6, 12, 16, 228);
    border: 1px solid rgba(78, 96, 99, 162);
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
    background: rgba(8, 14, 18, 150);
    width: 10px;
    margin: 2px;
}
QScrollBar::handle:vertical {
    background: rgba(113, 126, 113, 170);
    border-radius: 4px;
    min-height: 30px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(151, 166, 143, 195);
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
