from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from tarkov_agent.domain.models import RaidState


class RaidSignal(StrEnum):
    GAME_FOUND = "game_found"
    GAME_LOST = "game_lost"
    MATCHMAKING_STARTED = "matchmaking_started"
    RAID_CANDIDATE_FOUND = "raid_candidate_found"
    RAID_STARTED = "raid_started"
    RAID_ENDED = "raid_ended"
    REVIEW_COMPLETED = "review_completed"
    ABORT = "abort"
    RESET = "reset"


class InvalidTransition(RuntimeError):
    """Raised when a lifecycle signal is not valid for the current state."""


@dataclass(frozen=True, slots=True)
class StateTransition:
    from_state: RaidState
    signal: RaidSignal
    to_state: RaidState
    occurred_at: datetime
    reason: str | None = None


_TRANSITIONS: dict[tuple[RaidState, RaidSignal], RaidState] = {
    (RaidState.IDLE, RaidSignal.GAME_FOUND): RaidState.GAME_RUNNING,
    (RaidState.GAME_RUNNING, RaidSignal.MATCHMAKING_STARTED): RaidState.MATCHMAKING,
    (RaidState.GAME_RUNNING, RaidSignal.RAID_CANDIDATE_FOUND): RaidState.RAID_CANDIDATE,
    (RaidState.MATCHMAKING, RaidSignal.RAID_CANDIDATE_FOUND): RaidState.RAID_CANDIDATE,
    (RaidState.MATCHMAKING, RaidSignal.RAID_STARTED): RaidState.IN_RAID,
    (RaidState.RAID_CANDIDATE, RaidSignal.RAID_STARTED): RaidState.IN_RAID,
    (RaidState.GAME_RUNNING, RaidSignal.RAID_STARTED): RaidState.IN_RAID,
    (RaidState.IN_RAID, RaidSignal.RAID_ENDED): RaidState.ENDING,
    (RaidState.ENDING, RaidSignal.REVIEW_COMPLETED): RaidState.COMPLETE,
    (RaidState.REVIEW_PENDING, RaidSignal.REVIEW_COMPLETED): RaidState.COMPLETE,
    (RaidState.COMPLETE, RaidSignal.RESET): RaidState.GAME_RUNNING,
    (RaidState.ABORTED, RaidSignal.RESET): RaidState.GAME_RUNNING,
    (RaidState.GAME_RUNNING, RaidSignal.GAME_LOST): RaidState.IDLE,
    (RaidState.MATCHMAKING, RaidSignal.GAME_LOST): RaidState.ABORTED,
    (RaidState.RAID_CANDIDATE, RaidSignal.GAME_LOST): RaidState.ABORTED,
    (RaidState.IN_RAID, RaidSignal.GAME_LOST): RaidState.ABORTED,
    (RaidState.ENDING, RaidSignal.GAME_LOST): RaidState.REVIEW_PENDING,
}

for state in RaidState:
    if state not in {RaidState.IDLE, RaidState.COMPLETE, RaidState.ABORTED}:
        _TRANSITIONS.setdefault((state, RaidSignal.ABORT), RaidState.ABORTED)


@dataclass(slots=True)
class RaidLifecycle:
    state: RaidState = RaidState.IDLE
    history: list[StateTransition] = field(default_factory=list)

    def can_apply(self, signal: RaidSignal) -> bool:
        return (self.state, signal) in _TRANSITIONS

    def apply(
        self,
        signal: RaidSignal,
        *,
        reason: str | None = None,
        occurred_at: datetime | None = None,
    ) -> StateTransition:
        key = (self.state, signal)
        try:
            next_state = _TRANSITIONS[key]
        except KeyError as exc:
            message = f"Cannot apply {signal} while lifecycle is {self.state}"
            raise InvalidTransition(message) from exc

        transition = StateTransition(
            from_state=self.state,
            signal=signal,
            to_state=next_state,
            occurred_at=occurred_at or datetime.now(UTC),
            reason=reason,
        )
        self.state = next_state
        self.history.append(transition)
        return transition
