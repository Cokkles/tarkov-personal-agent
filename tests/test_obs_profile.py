from __future__ import annotations

from types import SimpleNamespace

from tarkov_agent.config import ObsSettings
from tarkov_agent.integrations.obs import ObsRecordingController


class FakeClient:
    def __init__(self, recording: bool, current: str) -> None:
        self.recording = recording
        self.current = current
        self.switched: list[str] = []

    def get_record_status(self) -> SimpleNamespace:
        return SimpleNamespace(output_active=self.recording)

    def get_profile_list(self) -> SimpleNamespace:
        return SimpleNamespace(current_profile_name=self.current)

    def set_current_profile(self, name: str) -> None:
        self.switched.append(name)


def _controller(client: FakeClient) -> ObsRecordingController:
    controller = ObsRecordingController(ObsSettings(enabled=True, profile="OBS PPE Record"))
    controller._client = client  # noqa: SLF001
    return controller


def test_switches_profile_when_idle() -> None:
    client = FakeClient(recording=False, current="Untitled")
    _controller(client)._apply_profile()  # noqa: SLF001
    assert client.switched == ["OBS PPE Record"]


def test_leaves_matching_profile_and_active_recordings_alone() -> None:
    same = FakeClient(recording=False, current="OBS PPE Record")
    _controller(same)._apply_profile()  # noqa: SLF001
    busy = FakeClient(recording=True, current="Untitled")
    _controller(busy)._apply_profile()  # noqa: SLF001
    assert same.switched == [] and busy.switched == []
