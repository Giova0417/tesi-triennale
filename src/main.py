import csv
import dataclasses
import traci

from sumo_env import SumoEnvironment
from llm.ollama_client import OllamaClient
from safety_supervisor import SafetySupervisor

SUMOCFG_PATH = r"C:\Users\giova\Desktop\tesi\llm_tls_sumo\scenarios\synthetic_4arm\scenario.sumocfg"
TLS_ID = "J0"
DECISION_INTERVAL = 10
SIM_DURATION = 3600
CSV_PATH = "simulation_results.csv"

# Indici a 6 fasi (inclusi i tempi di clearance Tutto Rosso)
NS_GREEN = 0
NS_YELLOW = 1
ALL_RED_1 = 2
EW_GREEN = 3
EW_YELLOW = 4
ALL_RED_2 = 5

TRANSITION_PHASES = (NS_YELLOW, ALL_RED_1, EW_YELLOW, ALL_RED_2)

def main() -> None:
    env = SumoEnvironment(SUMOCFG_PATH, tls_id=TLS_ID)
    client = OllamaClient()
    supervisor = SafetySupervisor()

    env.start()
    llm_action = "HOLD"

    # Apertura file CSV per la raccolta dati
    csv_file = open(CSV_PATH, "w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow(["Time", "Phase", "Queue_NS", "Queue_EW", "LLM_Action"])

    try:
        for step in range(SIM_DURATION):
            env.step()
            state = env.get_state()
            current_phase = traci.trafficlight.getPhase(TLS_ID)

            if state.sim_time % DECISION_INTERVAL == 0:
                if current_phase in TRANSITION_PHASES:
                    llm_action = "HOLD"
                else:
                    try:
                        state_dict = dataclasses.asdict(state)
                        decision = client.get_decision(state_dict)
                        llm_action = decision.action_id
                    except Exception as exc:
                        print(f"[{state.sim_time}] LLM fallback -> HOLD ({exc})")
                        llm_action = "HOLD"

            safe_phase = supervisor.get_safe_phase(current_phase, state.phase_elapsed, llm_action)
            env.set_phase(safe_phase)

            # Calcolo code aggregate per asse
            queue_ns = state.queue_by_approach.get("N2J", 0) + state.queue_by_approach.get("S2J", 0)
            queue_ew = state.queue_by_approach.get("E2J", 0) + state.queue_by_approach.get("W2J", 0)

# Scrittura riga su CSV
            writer.writerow([state.sim_time, state.phase_id, queue_ns, queue_ew, llm_action])
            csv_file.flush()  # <--- QUESTA RIGA FORZA IL SALVATAGGIO SU DISCO IN TEMPO REALE

            print(
                f"[t={state.sim_time:4d}] fase={state.phase_id:10s} "
                f"elapsed={state.phase_elapsed:3d} "
                f"queue_ns={queue_ns:3d} queue_ew={queue_ew:3d} "
                f"llm={llm_action:12s} -> fase_sicura={safe_phase}"
            )
    finally:
        csv_file.close()
        env.close()

if __name__ == "__main__":
    main()