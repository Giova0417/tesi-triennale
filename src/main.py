import traci
import sumolib

from src.observer import TrafficObserver
from src.safety_fsm import SafetyFSM
from src.controllers.pressure import PressureController

TLS_ID = "J0"
SUMOCFG_PATH = "scenarios/synthetic_4arm/scenario.sumocfg"


def opposite_queue(state, current_phase: str) -> int:
    q = state.queue_by_approach
    if current_phase == "NS_GREEN":
        return q.get("E2J", 0) + q.get("W2J", 0)
    return q.get("N2J", 0) + q.get("S2J", 0)


def main() -> None:
    sumo_binary = sumolib.checkBinary("sumo-gui")
    traci.start([sumo_binary, "-c", SUMOCFG_PATH])

    observer = TrafficObserver()
    fsm = SafetyFSM()
    controller = PressureController()

    try:
        while traci.simulation.getMinExpectedNumber() > 0:
            traci.simulationStep()

            state = observer.read_state(TLS_ID)
            fsm.tick(state.sim_time)

            if not fsm._transition_queue:
                allowed = fsm.get_allowed_actions(state.phase_id, state.phase_elapsed)
                action = controller.decide(state, allowed)
                opp_queue = opposite_queue(state, state.phase_id)

                executed, reason = fsm.request(action, state.phase_elapsed, opp_queue)
                if executed == "SWITCH":
                    print(f"[{state.sim_time}] switch -> {reason}")

            fsm.apply_traci(TLS_ID)

    finally:
        traci.close()


if __name__ == "__main__":
    main()