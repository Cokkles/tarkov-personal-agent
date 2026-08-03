from pathlib import Path

from tarkov_agent.config import LogSignalRule
from tarkov_agent.domain.state_machine import RaidSignal
from tarkov_agent.observers.logs import LogSignalClassifier, LogTailObserver


def test_log_observer_reads_appended_lines(tmp_path: Path) -> None:
    log_path = tmp_path / "application.log"
    log_path.write_text("existing\n", encoding="utf-8")
    observer = LogTailObserver([tmp_path], start_at_end=True)

    assert observer.scan_once() == []

    with log_path.open("a", encoding="utf-8") as handle:
        handle.write("raid started\n")

    lines = observer.scan_once()
    assert [line.text for line in lines] == ["raid started"]


def test_log_classifier_uses_explicit_rules(tmp_path: Path) -> None:
    log_path = tmp_path / "application.log"
    log_path.write_text("RAID STARTED\n", encoding="utf-8")
    observer = LogTailObserver([tmp_path], start_at_end=False)
    line = observer.scan_once()[0]
    classifier = LogSignalClassifier(
        [
            LogSignalRule(
                name="test-start",
                pattern=r"raid\s+started",
                signal=RaidSignal.RAID_STARTED.value,
                confidence=0.99,
            )
        ]
    )

    classified = classifier.classify(line)

    assert len(classified) == 1
    assert classified[0].signal is RaidSignal.RAID_STARTED
