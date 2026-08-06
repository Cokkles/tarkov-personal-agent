from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from urllib.parse import urlencode

from PySide6.QtCore import QTimer, QUrl, Slot
from PySide6.QtGui import QCloseEvent, QColor, QDesktopServices
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QSystemTrayIcon, QTableWidgetItem

from tarkov_agent.desktop.qt_common import ApiWorker, EndRaidDialog, MARKERS, StartRaidDialog
from tarkov_agent.domain.desktop import DesktopStatus
from tarkov_agent.domain.models import MarkerCommand, MarkerType, RaidRecord

LOGGER = logging.getLogger(__name__)


class OperationsCenterRuntimeMixin:
    def auto_start(self) -> None:
        if self.settings.desktop.auto_start_service:
            self.start_service()
        else:
            self.refresh_all()

    def refresh_all(self) -> None:
        self.refresh_status()
        self.refresh_secondary()

    def start_service(self) -> None:
        self._activity("Connecting to the local agent service", "system")
        self._run_task(self.service.start, self._service_started, "Starting local service…")

    def stop_service(self) -> None:
        if not self.service.owns_service:
            self._activity("This desktop session does not own the running service", "warning")
            return
        self._run_task(self.service.stop, self._service_stopped, "Stopping local service…")

    def refresh_status(self) -> None:
        if self._status_request_active:
            return
        self._status_request_active = True
        worker = ApiWorker(self.client.status)
        worker.signals.result.connect(self._status_received)
        worker.signals.error.connect(self._status_failed)
        worker.signals.finished.connect(lambda: setattr(self, "_status_request_active", False))
        self.pool.start(worker)

    def refresh_secondary(self) -> None:
        if self._secondary_request_active or self._status is None:
            return
        self._secondary_request_active = True
        worker = ApiWorker(lambda: (self.client.list_raids(limit=5), self.client.review_queue(limit=30)))
        worker.signals.result.connect(self._secondary_received)
        worker.signals.error.connect(lambda message: LOGGER.debug("Secondary refresh failed: %s", message))
        worker.signals.finished.connect(lambda: setattr(self, "_secondary_request_active", False))
        self.pool.start(worker)

    def refresh_timeline(self) -> None:
        if self._active_raid_id is None or self._timeline_request_active:
            return
        self._timeline_request_active = True
        worker = ApiWorker(lambda: self.client.timeline(self._active_raid_id or ""))
        worker.signals.result.connect(self._timeline_received)
        worker.signals.error.connect(lambda message: LOGGER.debug("Timeline refresh failed: %s", message))
        worker.signals.finished.connect(lambda: setattr(self, "_timeline_request_active", False))
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
        self._run_task(lambda: self.client.end_raid(result=dialog.selected_result()), self._raid_ended, "Ending raid and finalizing recording…")

    def abort_raid(self) -> None:
        answer = QMessageBox.question(self, "Abort Raid", "Abort the active raid record? OBS recording will also be stopped.")
        if answer == QMessageBox.StandardButton.Yes:
            self._run_task(lambda: self.client.abort_raid(reason="Aborted from Operations Center"), self._raid_aborted, "Aborting raid…")

    def add_marker(self, marker_type: MarkerType) -> None:
        label = next(name for current, _, name in MARKERS if current == marker_type).title()
        command = MarkerCommand(marker_type=marker_type, source="desktop")
        self._run_task(lambda: self.client.add_marker(command), lambda _: self._marker_added(label), f"Adding marker: {label}")

    def _run_task(self, task: Callable[[], object], callback: Callable[[object], None], message: str) -> None:
        self.footer_message.setText(message)
        worker = ApiWorker(task)
        worker.signals.result.connect(callback)
        worker.signals.error.connect(self._task_failed)
        worker.signals.finished.connect(lambda: self.footer_message.setText("Operations Center ready"))
        self.pool.start(worker)

    @Slot(object)
    def _status_received(self, value: object) -> None:
        status = DesktopStatus.model_validate(value)
        previous_raid = self._active_raid_id
        self._status = status
        self._set_online(True)
        self.version_label.setText(f"v{status.version}")
        lifecycle = status.lifecycle_state.replace("_", " ").upper()
        if self._last_lifecycle not in {None, status.lifecycle_state}:
            self._activity(f"Lifecycle: {self._last_lifecycle} → {status.lifecycle_state}", "system")
        self._last_lifecycle = status.lifecycle_state
        self.lifecycle_value.setText(lifecycle)
        self.lifecycle_value.setProperty("state", status.lifecycle_state)
        self.lifecycle_value.style().unpolish(self.lifecycle_value)
        self.lifecycle_value.style().polish(self.lifecycle_value)

        raid = status.active_raid
        self._active_raid_id = str(raid.id) if raid is not None else None
        if previous_raid != self._active_raid_id:
            self._timeline.clear()
            self._seen_timeline_ids.clear()
            self._timeline_initialized = False
            self._render_timeline()
        active = raid is not None
        if raid is None:
            self.active_raid_value.setText("NO ACTIVE RAID")
            self.raid_id_value.setText("—")
            self.raid_objective_value.setText("—")
            self.live_map.setText("—")
            self.live_character.setText("—")
            self.live_objective.setText("—")
            self.sidebar_session.setText("No active raid")
        else:
            map_name = raid.map_name or "Unknown map"
            character = raid.character_type or "Unknown"
            objective = raid.primary_objective or "No objective recorded"
            self.active_raid_value.setText(f"{map_name.upper()}  ·  {character.upper()}")
            self.raid_id_value.setText(str(raid.id))
            self.raid_objective_value.setText(objective)
            self.live_map.setText(map_name.upper())
            self.live_character.setText(character.upper())
            self.live_objective.setText(objective)
            self.sidebar_session.setText(f"{map_name} · {character}")

        if not status.obs.enabled:
            obs = "Disabled"
        elif status.obs.error:
            obs = "Connection error"
        elif status.obs.recording_active:
            obs = "Recording"
        elif status.obs.connected:
            obs = "Connected"
        else:
            obs = "Disconnected"
        if self._last_obs not in {None, obs}:
            self._activity(f"OBS status: {obs}", "system")
        self._last_obs = obs
        self.obs_value.setText(f"• {obs}")
        self.obs_card.setText(obs)
        self.live_recording.setText(obs.upper())
        self.obs_value.setToolTip(status.obs.error or status.obs.output_path or "")

        ppe = f"Profile v{status.ppe_profile_version}" if status.ppe_profile_version is not None else ("Ready" if status.ppe_enabled else "Disabled")
        if self._last_ppe not in {None, status.ppe_profile_version}:
            self._activity(f"PPE profile loaded: {ppe}", "system")
        self._last_ppe = status.ppe_profile_version
        if self._last_rules not in {None, status.automatic_log_rules}:
            self._activity(f"Automatic log rules active: {status.automatic_log_rules}", "system")
        self._last_rules = status.automatic_log_rules
        self.ppe_value.setText(f"• {ppe}")
        self.ppe_card.setText(ppe)
        self.rules_value.setText(f"• {status.automatic_log_rules} active")
        self.queue_card.setText(f"{status.review_queue_count} pending")
        self.media_card.setText("Enabled" if status.media_enabled else "Disabled")

        self.start_raid_button.setEnabled(not active)
        self.end_raid_button.setEnabled(active)
        self.abort_raid_button.setEnabled(active)
        for button in self._marker_buttons:
            button.setEnabled(active)
        self.start_service_button.setEnabled(False)
        self.stop_service_button.setEnabled(self.service.owns_service)
        self.settings_service.setText("Online")
        self._update_elapsed()
        if active:
            self.refresh_timeline()
        QTimer.singleShot(150, self.refresh_secondary)

    @Slot(str)
    def _status_failed(self, message: str) -> None:
        self._set_online(False)
        self.service_label.setToolTip(message)

    @Slot(object)
    def _secondary_received(self, value: object) -> None:
        if not isinstance(value, tuple) or len(value) != 2:
            return
        raids, queue = value
        self._fill_recent([raid for raid in raids if isinstance(raid, RaidRecord)])
        self.queue_card.setText(f"{len(queue)} pending")

    @Slot(object)
    def _timeline_received(self, value: object) -> None:
        if not isinstance(value, list):
            return
        events = [{str(key): entry for key, entry in item.items()} for item in value if isinstance(item, Mapping)]
        events.sort(key=lambda event: str(event.get("occurred_at") or ""))
        if self._timeline_initialized:
            for event in events:
                event_id = str(event.get("id") or "")
                if event_id and event_id not in self._seen_timeline_ids:
                    label = str(event.get("label") or event.get("event_type") or "Event")
                    source = str(event.get("source") or "unknown")
                    kind = "marker" if event.get("event_type") == "marker" else "system"
                    prefix = "Marker" if kind == "marker" else "Trigger"
                    self._activity(f"{prefix}: {label} · {source}", kind)
        self._timeline = events
        self._seen_timeline_ids = {str(event.get("id")) for event in events if event.get("id") is not None}
        self._timeline_initialized = True
        self._render_timeline()

    @Slot(object)
    def _service_started(self, owned: object) -> None:
        self._activity("Embedded local service started" if bool(owned) else "Connected to an existing local service", "success")
        self.refresh_all()

    @Slot(object)
    def _service_stopped(self, _: object) -> None:
        self._activity("Embedded local service stopped", "system")
        self._status = None
        self._set_online(False)

    @Slot(object)
    def _raid_started(self, value: object) -> None:
        raid = RaidRecord.model_validate(value)
        self._activity(f"Raid started on {raid.map_name or raid.id}", "success")
        self.refresh_all()

    @Slot(object)
    def _raid_ended(self, value: object) -> None:
        raid = RaidRecord.model_validate(value)
        self._activity(f"Raid ended and queued for review: {raid.result or raid.id}", "review")
        self.refresh_all()
        self._navigate("reviews")

    @Slot(object)
    def _raid_aborted(self, value: object) -> None:
        raid = RaidRecord.model_validate(value)
        self._activity(f"Raid aborted: {raid.id}", "warning")
        self.refresh_all()

    def _marker_added(self, label: str) -> None:
        self._activity(f"Marker submitted: {label}", "marker")
        QTimer.singleShot(200, self.refresh_timeline)

    @Slot(str)
    def _task_failed(self, message: str) -> None:
        self._activity(f"Error: {message}", "error")
        QMessageBox.warning(self, "Tarkov Personal Agent", message)
        self.refresh_status()

    def _set_online(self, online: bool) -> None:
        self.service_label.setText("SERVICE ONLINE" if online else "SERVICE OFFLINE")
        self.sidebar_online.setText("● Online" if online else "● Offline")
        for widget in (self.service_label, self.service_dot, self.sidebar_online):
            widget.setProperty("online", online)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
        self.start_service_button.setEnabled(not online)
        self.stop_service_button.setEnabled(online and self.service.owns_service)
        self.settings_service.setText("Online" if online else "Offline")
        if not online:
            self.lifecycle_value.setText("OFFLINE")
            self.active_raid_value.setText("—")
            self.start_raid_button.setEnabled(False)
            self.end_raid_button.setEnabled(False)
            self.abort_raid_button.setEnabled(False)
            for button in self._marker_buttons:
                button.setEnabled(False)

    def _activity(self, message: str, kind: str) -> None:
        self.activity_table.insertRow(0)
        time_item = QTableWidgetItem(datetime.now().astimezone().strftime("%I:%M:%S %p").lstrip("0"))
        message_item = QTableWidgetItem(message)
        colors = {"success": "#a9d66f", "marker": "#d9b45d", "warning": "#d9b45d", "review": "#d9b45d", "error": "#e67b72", "system": "#9db8ca"}
        message_item.setForeground(QColor(colors.get(kind, "#cfd5d3")))
        self.activity_table.setItem(0, 0, time_item)
        self.activity_table.setItem(0, 1, message_item)
        if self.activity_table.rowCount() > 120:
            self.activity_table.removeRow(self.activity_table.rowCount() - 1)

    def _render_timeline(self) -> None:
        for table in (self.dashboard_markers, self.markers_table, self.live_timeline):
            rows = self._timeline if bool(table.property("allEvents")) else [event for event in self._timeline if event.get("event_type") == "marker"]
            table.setRowCount(0)
            for event in reversed(rows[-100:]):
                row = table.rowCount()
                table.insertRow(row)
                payload = event.get("payload")
                marker_type = str(payload.get("marker_type") or "") if isinstance(payload, Mapping) else ""
                values = (
                    self._event_time(event.get("occurred_at")),
                    str(event.get("label") or event.get("event_type") or "—"),
                    marker_type or str(event.get("event_type") or "—"),
                    str(event.get("source") or "—").replace("_", " ").title(),
                )
                for column, text in enumerate(values):
                    item = QTableWidgetItem(text)
                    if column == 1 and event.get("event_type") == "marker":
                        item.setForeground(QColor("#d9b45d"))
                    table.setItem(row, column, item)
        count = sum(1 for event in self._timeline if event.get("event_type") == "marker")
        self.marker_count.setText(f"{count} marker events")

    def _fill_recent(self, raids: list[RaidRecord]) -> None:
        self.recent_table.setRowCount(0)
        for raid in raids:
            row = self.recent_table.rowCount()
            self.recent_table.insertRow(row)
            result = QTableWidgetItem(raid.result or "—")
            if (raid.result or "").lower() == "survived":
                result.setForeground(QColor("#9bc76d"))
            elif (raid.result or "").lower() == "kia":
                result.setForeground(QColor("#df756b"))
            self.recent_table.setItem(row, 0, QTableWidgetItem(raid.map_name or "Unknown map"))
            self.recent_table.setItem(row, 1, result)
            self.recent_table.setItem(row, 2, QTableWidgetItem(raid.state.value.replace("_", " ").title()))

    def _update_clock(self) -> None:
        self.footer_clock.setText(datetime.now().astimezone().strftime("%I:%M %p  ·  %m/%d/%Y").lstrip("0"))
        self._update_elapsed()

    def _update_elapsed(self) -> None:
        raid = self._status.active_raid if self._status is not None else None
        if raid is None or raid.started_at is None:
            text = "00:00:00"
        else:
            started = raid.started_at if raid.started_at.tzinfo is not None else raid.started_at.replace(tzinfo=UTC)
            total = max(0, int((datetime.now(UTC) - started.astimezone(UTC)).total_seconds()))
            hours, remainder = divmod(total, 3600)
            minutes, seconds = divmod(remainder, 60)
            text = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.raid_timer_value.setText(text)
        self.live_timer.setText(text)

    @staticmethod
    def _event_time(value: object) -> str:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return str(value or "—")
        return parsed.astimezone().strftime("%I:%M:%S %p").lstrip("0")

    def _local_url(self, path: str) -> str:
        url = f"{self.client.base_url}{path}"
        if not self.settings.api.token:
            return url
        return f"{url}{'&' if '?' in url else '?'}{urlencode({'token': self.settings.api.token})}"

    def open_page(self, path: str) -> None:
        QDesktopServices.openUrl(QUrl(self._local_url(path)))

    def _load_reviews(self) -> None:
        if self.review_web is not None and self._status is not None:
            self.review_web.setUrl(QUrl(self._local_url("/")))

    def _show_page(self, key: str) -> None:
        self.show_from_tray()
        self._navigate(key)

    def show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_application(self) -> None:
        self._allow_close = True
        if self.settings.desktop.stop_service_on_exit and self.service.owns_service:
            self.service.stop()
        if self.tray is not None:
            self.tray.hide()
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._allow_close:
            event.accept()
            return
        if self.tray is not None and self.tray.isVisible():
            event.ignore()
            self.hide()
            if not self._tray_notice_shown:
                self.tray.showMessage("Tarkov Personal Agent", "The Operations Center is still running in the system tray.", QSystemTrayIcon.MessageIcon.Information, 3000)
                self._tray_notice_shown = True
            return
        self.quit_application()
        event.accept()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick}:
            self.show_from_tray()
