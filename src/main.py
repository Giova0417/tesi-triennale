import os
import csv
import time
from pathlib import Path
import traci
from pydantic import ValidationError

from sumo_env import SumoEnvironment
from llm.ollama_client import OllamaClient
from llm.schemas import StateEncoder
from safety_supervisor import SafetySupervisor
from controllers.pressure import PressureController

POLICY = os.getenv("TLS_POLICY", "llm")
SEED = int(os.getenv("SUMO_SEED", "42"))
CSV_PATH = os.getenv("CSV_OUTPUT_PATH", "simulation_results.csv")
DISABLE_LLM = os.getenv("DISABLE_LLM", "0") == "1"

# Estraiamo dinamicamente il livello di traffico dal percorso del CSV
def get_traffic_level(path_str):
    if "light" in path_str.lower(): return "light"
    if "heavy" in path_str.lower(): return "heavy"
    return "medium"

TRAFFIC_LEVEL = os.getenv("TRAFFIC_LEVEL", get_traffic_level(CSV_PATH))

# Mappatura livelli di traffico -> fattore di scala (--scale)
SCALE_MAP = {"light": 0.5, "medium": 1.0, "heavy": 1.5}
SCALE = SCALE_MAP.get(TRAFFIC_LEVEL, 1.0)

ROOT_DIR = Path(__file__).parent.parent
SUMOCFG_PATH = ROOT_DIR / "scenarios" / "synthetic_4arm" / "scenario.sumocfg"
TLS_ID = "J0"
DECISION_INTERVAL = 10
SIM_DURATION = 3600

def main() -> None:
    print(f"\n--- AVVIO SIMULAZIONE: Policy={POLICY.upper()}, Seed={SEED}, Traffic={TRAFFIC_LEVEL.upper()} ---")
    
    env = SumoEnvironment(str(SUMOCFG_PATH), tls_id=TLS_ID, seed=SEED, scale=SCALE)
    supervisor = SafetySupervisor()
    pressure_controller = PressureController()
    client = None
    
    if POLICY == "llm" and not DISABLE_LLM:
        client = OllamaClient()
        print("Eseguo WARM-UP dell'LLM (potrebbe volerci qualche secondo)...")
        try:
            dummy_state = {"sim_time": 0, "phase": "NS_GREEN", "elapsed_green": 10, "queues": {"NS": 0, "EW": 0}, "allowed_actions": ["HOLD"]}
            client.get_decision(dummy_state)
            print("WARM-UP completato!\n")
        except Exception as e:
            print(f"Errore nel warm-up: {e}")

    # Creazione cartelle dinamiche e percorsi per CSV, tripinfo e emissions
    results_dir = Path(CSV_PATH).parent
    results_dir.mkdir(parents=True, exist_ok=True)
    
    tripinfo_path = str(results_dir / "tripinfo.xml")
    emissions_path = str(results_dir / "emissions.xml")

    # Avvio ambiente passando i percorsi
    env.start(tripinfo_path=tripinfo_path, emissions_path=emissions_path)
    
    csv_file = open(CSV_PATH, "w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow([
        "Time", "Policy", "Phase", "Phase_Elapsed", "Queue_NS", "Queue_EW", "WaitTime_NS", "WaitTime_EW", 
        "Allowed_Actions", "Proposed_Action", "Is_Fallback", "Fallback_Reason", 
        "Final_Executed_Action", "Supervisor_Feedback", "LLM_Latency_ms", "LLM_Explanation", "LLM_ReasonCodes"
    ])

    try:
        if POLICY in ["llm", "pressure"]:
            traci.trafficlight.setPhaseDuration(TLS_ID, 10000)

        for step in range(SIM_DURATION):
            env.step()
            state = env.get_state()
            
            queue_ns = state.queue_by_approach.get("N2J", 0) + state.queue_by_approach.get("S2J", 0)
            queue_ew = state.queue_by_approach.get("E2J", 0) + state.queue_by_approach.get("W2J", 0)
            wait_ns = state.waiting_by_approach.get("N2J", 0.0) + state.waiting_by_approach.get("S2J", 0.0)
            wait_ew = state.waiting_by_approach.get("E2J", 0.0) + state.waiting_by_approach.get("W2J", 0.0)

            # ALLINEAMENTO LOGGING: preleviamo la fase PRIMA delle modifiche del supervisor
            log_phase = traci.trafficlight.getPhase(TLS_ID)
            log_elapsed = state.phase_elapsed

            if POLICY == "fixed-time":
                writer.writerow([
                    state.sim_time, POLICY, log_phase, log_elapsed, queue_ns, queue_ew, wait_ns, wait_ew,
                    "NONE", "NONE", False, "NONE", "FIXED_TIME", "NONE", 0.0, "", ""
                ])
                csv_file.flush()
                continue

            supervisor.tick(state.sim_time)
            
            proposed_action = "HOLD"
            final_action = "HOLD"
            is_fallback = False
            fallback_reason = "NONE"
            latency = 0.0
            explanation = ""
            reason_codes = ""
            allowed_actions = supervisor.get_allowed_actions()

            if state.sim_time % DECISION_INTERVAL == 0 and len(allowed_actions) > 1:
                
                if POLICY == "llm":
                    state_dict = StateEncoder.encode(state, allowed_actions)
                    start_time = time.time()
                    try:
                        decision = client.get_decision(state_dict)
                        proposed_action = decision.action_id
                        explanation = decision.explanation
                        reason_codes = "-".join(decision.reason_codes)
                        
                        if proposed_action not in allowed_actions:
                            raise ValueError(f"Azione {proposed_action} non permessa")
                        final_action = proposed_action
                    
                    except ValidationError:
                        is_fallback = True
                        fallback_reason = "PYDANTIC_ERROR"
                    except Exception:
                        is_fallback = True
                        fallback_reason = "TIMEOUT_OR_ERROR"
                    
                    latency = round((time.time() - start_time) * 1000, 2)
                    
                    if is_fallback:
                        proposed_action = "FAILED"
                        final_action = pressure_controller.decide(state, allowed_actions)
                
                elif POLICY == "pressure":
                    proposed_action = "PRESSURE_DECISION"
                    final_action = pressure_controller.decide(state, allowed_actions)

            action_executed, supervisor_feedback = supervisor.request(final_action, opposite_queue=(queue_ns if supervisor.current_phase == 3 else queue_ew))
            supervisor.apply_traci(TLS_ID)

            if action_executed == "SWITCH" or (state.sim_time % DECISION_INTERVAL == 0):
                traci.trafficlight.setPhaseDuration(TLS_ID, 10000)

            writer.writerow([
                state.sim_time, POLICY, log_phase, log_elapsed, queue_ns, queue_ew, wait_ns, wait_ew,
                "-".join(allowed_actions), proposed_action, is_fallback, fallback_reason, 
                action_executed, supervisor_feedback, latency, explanation, reason_codes
            ])
            csv_file.flush() 

    finally:
        csv_file.close()
        env.close()

if __name__ == "__main__":
    main()