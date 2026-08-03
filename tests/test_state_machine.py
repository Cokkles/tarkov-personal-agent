import pytest

from tarkov_agent.domain.models import RaidState
from tarkov_agent.domain.state_machine import InvalidTransition, RaidLifecycle, RaidSignal


def test_happy_path_lifecycle() -> None:
    lifecycle = RaidLifecycle()

    lifecycle.apply(RaidSignal.GAME_FOUND)
    lifecycle.apply(RaidSignal.MATCHMAKING_STARTED)
    lifecycle.apply(RaidSignal.RAID_STARTED)
    lifecycle.apply(RaidSignal.RAID_ENDED)
    lifecycle.apply(RaidSignal.REVIEW_COMPLETED)

    assert lifecycle.state is RaidState.COMPLETE
    assert [transition.to_state for transition in lifecycle.history] == [
        RaidState.GAME_RUNNING,
        RaidState.MATCHMAKING,
        RaidState.IN_RAID,
        RaidState.ENDING,
        RaidState.COMPLETE,
    ]


def test_invalid_transition_is_rejected() -> None:
    lifecycle = RaidLifecycle()

    with pytest.raises(InvalidTransition):
        lifecycle.apply(RaidSignal.RAID_ENDED)
