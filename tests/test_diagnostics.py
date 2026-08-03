import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from tarkov_agent.observers.logs import LogLine
from tarkov_agent.services.diagnostics import DiagnosticCaptureService, DiagnosticRedactor


class FakeObserver:
    async def lines(self) -> AsyncIterator[LogLine]:
        yield LogLine(
            path=Path(r"C:\Users\Brian\Battlestate Games\Logs\client.log"),
            line_number=1,
            text="email brian@example.com ip 192.168.1.50 token=abcdef123456",
            observed_at=datetime.now(UTC),
        )
        yield LogLine(
            path=Path("client.log"),
            line_number=2,
            text="sessionId=private-value",
            observed_at=datetime.now(UTC),
        )


def test_redactor_masks_common_identifiers() -> None:
    value = DiagnosticRedactor().redact(
        r"C:\Users\Brian\x brian@example.com 10.0.0.1 token=secret"
    )
    assert "Brian" not in value
    assert "brian@example.com" not in value
    assert "10.0.0.1" not in value
    assert "token=secret" not in value


def test_capture_writes_redacted_jsonl(tmp_path: Path) -> None:
    service = DiagnosticCaptureService(tmp_path)
    result = asyncio.run(
        service.capture(
            FakeObserver(),  # type: ignore[arg-type]
            duration_seconds=1,
            maximum_lines=2,
        )
    )
    content = result.events_path.read_text(encoding="utf-8")
    assert result.line_count == 2
    assert "brian@example.com" not in content
    assert "192.168.1.50" not in content
    assert "private-value" not in content
