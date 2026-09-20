from __future__ import annotations

from pathlib import Path

from tarkov_agent.config import ObsSettings
from tarkov_agent.integrations.obs_launcher import ObsLauncher, find_obs_executable


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def _exe(tmp_path: Path) -> Path:
    exe = tmp_path / "bin" / "obs64.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"")
    return exe


def _launcher(settings: ObsSettings, port_states: list[bool], calls: list, proc: FakeProcess):
    states = iter(port_states)
    last = {"value": port_states[-1]}

    def port_open(_h: str, _p: int) -> bool:
        last["value"] = next(states, last["value"])
        return last["value"]

    def spawn(cmd: list[str], **kwargs: object) -> FakeProcess:
        calls.append((cmd, kwargs))
        return proc

    tick = iter(range(1000))
    return ObsLauncher(
        settings, spawn=spawn, port_open=port_open, sleep=lambda _s: None,
        clock=lambda: float(next(tick)),
    )


def test_disabled_does_nothing(tmp_path: Path) -> None:
    calls: list = []
    launcher = _launcher(ObsSettings(enabled=True), [False], calls, FakeProcess())
    assert launcher.ensure_running() == "disabled"
    assert calls == []


def test_reuses_running_obs(tmp_path: Path) -> None:
    calls: list = []
    settings = ObsSettings(enabled=True, auto_launch=True, executable=_exe(tmp_path))
    launcher = _launcher(settings, [True], calls, FakeProcess())
    assert launcher.ensure_running() == "already_running"
    assert calls == [] and not launcher.owns_process


def test_launches_hidden_from_obs_folder(tmp_path: Path) -> None:
    calls: list = []
    exe = _exe(tmp_path)
    settings = ObsSettings(enabled=True, auto_launch=True, executable=exe)
    launcher = _launcher(settings, [False, False, False, True], calls, FakeProcess())
    assert launcher.ensure_running() == "launched"
    cmd, kwargs = calls[0]
    assert cmd[0] == str(exe) and "--minimize-to-tray" in cmd
    assert kwargs["cwd"] == str(exe.parent)
    assert launcher.owns_process


def test_missing_executable_is_reported(tmp_path: Path) -> None:
    settings = ObsSettings(
        enabled=True, auto_launch=True, executable=tmp_path / "nope.exe"
    )
    launcher = _launcher(settings, [False], [], FakeProcess())
    assert find_obs_executable(settings.executable, ()) is None
    assert launcher.ensure_running() == "not_found"


def test_timeout_when_websocket_never_opens(tmp_path: Path) -> None:
    settings = ObsSettings(
        enabled=True, auto_launch=True, executable=_exe(tmp_path), launch_wait_seconds=3
    )
    launcher = _launcher(settings, [False], [], FakeProcess())
    assert launcher.ensure_running() == "timeout"


def test_closes_only_when_owned_and_enabled(tmp_path: Path) -> None:
    proc = FakeProcess()
    settings = ObsSettings(
        enabled=True, auto_launch=True, executable=_exe(tmp_path), close_on_exit=True
    )
    launcher = _launcher(settings, [False, True], [], proc)
    launcher.ensure_running()
    assert launcher.close_if_owned() is True and proc.terminated

    kept = FakeProcess()
    keep_settings = settings.model_copy(update={"close_on_exit": False})
    launcher2 = _launcher(keep_settings, [False, True], [], kept)
    launcher2.ensure_running()
    assert launcher2.close_if_owned() is False and not kept.terminated
