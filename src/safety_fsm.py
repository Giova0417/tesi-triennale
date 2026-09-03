import traci

NS_GREEN = 0
NS_YELLOW = 1
ALL_RED_1 = 2
EW_GREEN = 3
EW_YELLOW = 4
ALL_RED_2 = 5

PHASE_NAMES = {
    NS_GREEN: "NS_GREEN",
    NS_YELLOW: "NS_YELLOW",
    ALL_RED_1: "ALL_RED_1",
    EW_GREEN: "EW_GREEN",
    EW_YELLOW: "EW_YELLOW",
    ALL_RED_2: "ALL_RED_2",
}

# sequenza fissa di transizione da uno stato stabile all'altro
NS_TO_EW = [NS_YELLOW, ALL_RED_1, EW_GREEN]
EW_TO_NS = [EW_YELLOW, ALL_RED_2, NS_GREEN]


class SafetyFSM:
    MIN_GREEN = 10
    MAX_GREEN = 60
    YELLOW_TIME = 3
    ALL_RED_TIME = 2

    def __init__(self) -> None:
        self.current_phase: int = NS_GREEN
        self.phase_start_time: int = 0
        self.sim_time: int = 0

        self._transition_queue: list[int] = []
        self._pending_phase: int | None = None

    def tick(self, sim_time: int) -> None:
        self.sim_time = sim_time

        if not self._transition_queue:
            return

        elapsed = self.sim_time - self.phase_start_time
        duration = self._phase_duration(self.current_phase)

        if elapsed >= duration:
            self._pending_phase = self._transition_queue.pop(0)

    def _phase_duration(self, phase: int) -> int:
        if phase in (NS_YELLOW, EW_YELLOW):
            return self.YELLOW_TIME
        if phase in (ALL_RED_1, ALL_RED_2):
            return self.ALL_RED_TIME
        return self.MAX_GREEN  # non usato per i verdi, gestiti dall'LLM

    def get_allowed_actions(self, current_phase: str, elapsed_green: int) -> list[str]:
        if current_phase not in ("NS_GREEN", "EW_GREEN"):
            return ["HOLD"]

        if elapsed_green < self.MIN_GREEN:
            return ["HOLD"]

        if current_phase == "NS_GREEN":
            return ["HOLD", "REQUEST_EW"]

        return ["HOLD", "REQUEST_NS"]

    def request(
        self, requested_action: str, elapsed_green: int, opposite_queue: int
    ) -> tuple[str, str]:
        if self.current_phase not in (NS_GREEN, EW_GREEN):
            return "HOLD", "TRANSITION_IN_PROGRESS"

        if elapsed_green >= self.MAX_GREEN and opposite_queue > 0:
            self._start_switch()
            return "SWITCH", "MAX_GREEN_FORCED"

        if requested_action == "HOLD":
            return "HOLD", "LLM_HOLD"

        wants_switch = (
            requested_action == "REQUEST_EW" and self.current_phase == NS_GREEN
        ) or (requested_action == "REQUEST_NS" and self.current_phase == EW_GREEN)

        if not wants_switch:
            return "HOLD", "INVALID_ACTION_FOR_PHASE"

        if elapsed_green < self.MIN_GREEN:
            return "HOLD", "MIN_GREEN_NOT_ELAPSED"

        self._start_switch()
        return "SWITCH", "LLM_APPROVED"

    def _start_switch(self) -> None:
        if self._transition_queue:
            return

        if self.current_phase == NS_GREEN:
            self._transition_queue = list(NS_TO_EW)
        elif self.current_phase == EW_GREEN:
            self._transition_queue = list(EW_TO_NS)

        self._pending_phase = self._transition_queue.pop(0)

    def apply_traci(self, tls_id: str) -> None:
        if self._pending_phase is None:
            return

        traci.trafficlight.setPhase(tls_id, self._pending_phase)
        self.current_phase = self._pending_phase
        self.phase_start_time = self.sim_time
        self._pending_phase = None