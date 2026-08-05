import time
from pathlib import Path
from unittest.mock import Mock, patch

from tarkov_agent.config import (
    AppSettings,
    DesktopSettings,
    PathSettings,
    RuntimeSettings,
)
from tarkov_agent.desktop.service import EmbeddedServiceManager


class FakeServer:
    def __init__(self, config: object) -> None:
        self.config = config
        self.should_exit = False

    def run(self) -> None:
        while not self.should_exit:
            time.sleep(0.001)


def test_existing_service_is_not_owned_or_stopped(tmp_path: Path) -> None:
    settings = AppSettings(paths=PathSettings(data_root=tmp_path))
    client = Mock()
    client.is_available.return_value = True
    manager = EmbeddedServiceManager(
        settings,
        client,
        config_path=tmp_path / "config.toml",
    )

    assert manager.start() is False
    assert manager.owns_service is False
    assert manager.stop() is False


def test_embedded_service_is_started_and_stopped_by_owner(
    tmp_path: Path,
) -> None:
    settings = AppSettings(
        paths=PathSettings(data_root=tmp_path),
        desktop=DesktopSettings(service_start_timeout_seconds=1.0),
        runtime=RuntimeSettings(graceful_shutdown_seconds=0.2),
    )
    client = Mock()
    client.is_available.side_effect = [False, True]
    manager = EmbeddedServiceManager(
        settings,
        client,
        config_path=tmp_path / "config.toml",
    )

    with (
        patch(
            "tarkov_agent.desktop.service.build_context",
            return_value=object(),
        ),
        patch(
            "tarkov_agent.desktop.service.create_app",
            return_value=object(),
        ),
        patch(
            "tarkov_agent.desktop.service.uvicorn.Config",
            return_value=object(),
        ),
        patch(
            "tarkov_agent.desktop.service.uvicorn.Server",
            FakeServer,
        ),
    ):
        assert manager.start() is True
        assert manager.owns_service is True
        assert manager.stop() is True
        assert manager.owns_service is False
