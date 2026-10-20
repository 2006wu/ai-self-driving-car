"""Normalized simulation contracts, deliberately separate from physical units."""
from dataclasses import dataclass, field
from typing import Protocol
from ..follow import FollowController


@dataclass(frozen=True)
class Observation:
    timestamp_monotonic_seconds: float | None
    tracks: list
    frame_dimensions: tuple  # (height, width), pixels
    age_seconds: float  # measured acquisition/processing age; never inferred from timestamp
    target_id: int | None = None
    target_box: list | None = None
    target_tracking_status: str = 'none'
    target_position: dict | None = None  # coordinate frame/units required by future consumer
    robot_state: dict | None = None
    odometry: dict | None = None


@dataclass(frozen=True)
class Action:
    linear_velocity_command: float
    angular_velocity_command: float
    status: str
    source_controller: str
    valid: bool
    units: str = 'normalized_simulation'
    confidence: float | None = None
    metadata: dict = field(default_factory=dict)


class Controller(Protocol):
    def predict(self, observation: Observation) -> Action: ...


class RuleBasedController:
    """Exact numerical adapter. Selection is explicit and separate from predict.

    FollowController owns the authoritative selected target and safety latch;
    observation target metadata never silently selects or rearms it.
    """
    def __init__(self, **policy):
        self.legacy = FollowController(**policy)

    @staticmethod
    def adapt(output):
        return Action(output['speed'], output['turn'], output['state'],
                      'rule_based', True, metadata=dict(output))

    def select(self, target_id, tracks):
        return self.adapt(self.legacy.select(target_id, tracks))

    def cancel(self):
        return self.adapt(self.legacy.cancel())

    def stop(self, reason='stop', fault=False):
        return self.adapt(self.legacy.stop(reason, fault))

    def predict(self, observation):
        return self.adapt(self.legacy.update(observation.tracks,
                          observation.frame_dimensions, observation.age_seconds))


class AIController:
    """Interface placeholder. No inference, architecture, training or weights."""
    def predict(self, observation):
        return Action(0., 0., 'UNAVAILABLE', 'ai_placeholder', False,
                      metadata={'reason': 'AI control is not implemented'})
