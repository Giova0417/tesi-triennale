import traci

from src.traffic_state import TrafficState

APPROACH_EDGES = ("N2J", "S2J", "E2J", "W2J")


class TrafficObserver:
    def __init__(self, approach_edges: tuple[str, ...] = APPROACH_EDGES) -> None:
        self._edges = approach_edges
        self._phase_start_time: int | None = None
        self._last_phase_id: str | None = None

    def read_state(self, tls_id: str) -> TrafficState:
        sim_time = int(traci.simulation.getTime())
        phase_id = traci.trafficlight.getPhaseName(tls_id)

        if phase_id != self._last_phase_id:
            self._last_phase_id = phase_id
            self._phase_start_time = sim_time

        phase_elapsed = sim_time - (self._phase_start_time or sim_time)

        queue_by_approach = {
            edge: traci.edge.getLastStepHaltingNumber(edge) for edge in self._edges
        }
        waiting_by_approach = {
            edge: traci.edge.getWaitingTime(edge) for edge in self._edges
        }

        return TrafficState(
            sim_time=sim_time,
            phase_id=phase_id,
            phase_elapsed=phase_elapsed,
            queue_by_approach=queue_by_approach,
            waiting_by_approach=waiting_by_approach,
        )