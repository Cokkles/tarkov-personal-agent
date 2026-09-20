from __future__ import annotations

from types import SimpleNamespace

from tarkov_agent.config import ObsSettings
from tarkov_agent.integrations.obs import ObsRecordingController


class FakeClient:
    def __init__(self, mode: str = "Advanced", tracks: str = "1", recording: bool = False) -> None:
        self.mode, self.tracks, self.recording = mode, tracks, recording
        self.audio: list[tuple[str, dict[str, bool]]] = []
        self.params: list[tuple[str, str, str]] = []

    def get_record_status(self) -> SimpleNamespace:
        return SimpleNamespace(output_active=self.recording)

    def set_input_audio_tracks(self, name: str, tracks: dict[str, bool]) -> None:
        self.audio.append((name, tracks))

    def get_profile_parameter(self, category: str, name: str) -> SimpleNamespace:
        return SimpleNamespace(parameter_value=self.mode if name == "Mode" else self.tracks)

    def set_profile_parameter(self, category: str, name: str, value: str) -> None:
        self.params.append((category, name, value))


def _run(client: FakeClient, name: str = "Mic/Aux", track: int = 2) -> None:
    settings = ObsSettings(enabled=True, mic_input_name=name, mic_track=track)
    controller = ObsRecordingController(settings)
    controller._client = client  # noqa: SLF001
    controller._apply_mic_track()  # noqa: SLF001


def test_mic_goes_on_track_two_and_track_is_recorded() -> None:
    client = FakeClient(tracks="1")
    _run(client)
    assert client.audio == [("Mic/Aux", {"2": True})]
    assert client.params == [("AdvOut", "RecTracks", "3")]


def test_no_change_when_track_already_recorded() -> None:
    client = FakeClient(tracks="3")
    _run(client)
    assert client.params == []


def test_simple_mode_is_left_alone() -> None:
    client = FakeClient(mode="Simple")
    _run(client)
    assert client.params == []


def test_never_touches_a_live_recording_or_unset_mic() -> None:
    live = FakeClient(recording=True)
    _run(live)
    unset = FakeClient()
    _run(unset, name="")
    assert live.audio == [] and unset.audio == []
