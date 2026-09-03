from dataclasses import dataclass, field

@dataclass(frozen=True, slots=True)
class TrafficState:
    sim_time: int
    phase_id: str
    phase_elapsed: int
    queue_by_approach: dict[str, int]
    waiting_by_approach: dict[str, float]