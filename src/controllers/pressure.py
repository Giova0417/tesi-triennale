from traffic_state import TrafficState


class PressureController:
    def decide(self, state: TrafficState, allowed_actions: list[str]) -> str:
        q = state.queue_by_approach

        pressure_ns = q.get("N2J", 0) + q.get("S2J", 0)
        pressure_ew = q.get("E2J", 0) + q.get("W2J", 0)

        if pressure_ns > pressure_ew and "REQUEST_NS" in allowed_actions:
            return "REQUEST_NS"

        if pressure_ew > pressure_ns and "REQUEST_EW" in allowed_actions:
            return "REQUEST_EW"

        return "HOLD"