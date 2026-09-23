import csv
import time
import traci
from pathlib import Path
from pydantic import ValidationError

from sumo_env import SumoEnvironment
from llm.ollama_client import OllamaClient
from llm.schemas import StateEncoder
from safety_supervisor import SafetySupervisor
# Importiamo il fallback Queue-Pressure come richiesto dal relatore
from controllers.pressure import PressureController

#Path relativi per riproducibilità totale
ROOT_DIR = Path(__file__).parent.parent
SUMOCFG_PATH = ROOT_DIR / "scenarios" / "synthetic_4arm" / "scenario.sumocfg"
CSV_PATH = ROOT_DIR / "src" / "simulation_results.csv"

TLS_ID = "J0"
DECISION_INTERVAL = 10
SIM_DURATION = 3600

def main() -> None:
    # Conversione in stringa per TraCI
    env = SumoEnvironment(str(SUMOCFG_PATH), tls_id=TLS_ID)
    client = OllamaClient()
    supervisor = SafetySupervisor()
    pressure_fallback = PressureController()

    env.start()
    
    # Intestazione CSV estesa richiesta dal relatore
    csv_file = open(CSV_PATH, "w", newline="")
    writer = csv.writer(csv_file)
    writer.writerow([
        "Time", "Phase", "Phase_Elapsed", "Queue_NS", "Queue_EW", "WaitTime_NS", "WaitTime_EW", 
        "Allowed_Actions", "Proposed_LLM_Action", "Is_Fallback", "Fallback_Reason", 
        "Final_Executed_Action", "Supervisor_Feedback", "LLM_Latency_ms", "LLM_Explanation", "LLM_ReasonCodes"
    ])

    try:
        for step in range(SIM_DURATION):
            env.step()
            state = env.get_state()
            
            # 1. Calcolo aggregato delle Code e Tempi di attesa
            queue_ns = state.queue_by_approach.get("N2J", 0) + state.queue_by_approach.get("S2J", 0)
            queue_ew = state.queue_by_approach.get("E2J", 0) + state.queue_by_approach.get("W2J", 0)
            wait_ns = state.waiting_by_approach.get("N2J", 0.0) + state.waiting_by_approach.get("S2J", 0.0)
            wait_ew = state.waiting_by_approach.get("E2J", 0.0) + state.waiting_by_approach.get("W2J", 0.0)

            # Sincronizza lo stato di SUMO con il Supervisor
            supervisor.tick(state.sim_time)
            
            # Variabili di default per il CSV in questo step
            llm_proposed_action = "HOLD"
            final_action = "HOLD"
            is_fallback = False
            fallback_reason = "NONE"
            llm_latency = 0.0
            explanation = ""
            reason_codes = ""
            allowed_actions = supervisor.get_allowed_actions()

            # 2. LOGICA "ONE-SHOT" & FALLBACK
            # Interroghiamo l'LLM solo se ha legalmente almeno 2 scelte (HOLD o REQUEST_x)
            if state.sim_time % DECISION_INTERVAL == 0 and len(allowed_actions) > 1:
                
                # Utilizzo dello StateEncoder
                state_dict = StateEncoder.encode(state, allowed_actions)
                
                start_time = time.time()
                try:
                    # Chiamata LLM
                    decision = client.get_decision(state_dict)
                    llm_proposed_action = decision.action_id
                    explanation = decision.explanation
                    reason_codes = "-".join(decision.reason_codes)
                    
                    #Validazione Azione Esplicita
                    if llm_proposed_action not in allowed_actions:
                        raise ValueError(f"Azione {llm_proposed_action} non permessa dal Supervisor")
                        
                    final_action = llm_proposed_action

                except ValidationError as e:
                    is_fallback = True
                    fallback_reason = "PYDANTIC_VALIDATION_ERROR"
                except Exception as e:
                    is_fallback = True
                    fallback_reason = f"TIMEOUT_OR_ILLEGAL_ACTION"

                llm_latency = round((time.time() - start_time) * 1000, 2)

                #Queue-Pressure come architettura Fail-Safe
                if is_fallback:
                    llm_proposed_action = "FAILED"
                    # Passiamo lo stato al tuo PressureController
                    final_action = pressure_fallback.decide(state, allowed_actions)

            # 3. Invio azione decisa al Supervisor
            action_executed, supervisor_feedback = supervisor.request(final_action, opposite_queue=(queue_ns if supervisor.current_phase == 3 else queue_ew))
            supervisor.apply_traci(TLS_ID)

            # 4. Scrittura log CSV esteso (flush per salvare frame by frame)
            writer.writerow([
                state.sim_time, supervisor.current_phase, state.phase_elapsed, queue_ns, queue_ew, wait_ns, wait_ew,
                "-".join(allowed_actions), llm_proposed_action, is_fallback, fallback_reason, 
                action_executed, supervisor_feedback, llm_latency, explanation, reason_codes
            ])
            csv_file.flush() 

            print(
                f"[t={state.sim_time:4d}] Fase={supervisor.current_phase} "
                f"Q_NS={queue_ns:2d} Q_EW={queue_ew:2d} "
                f"LLM={llm_proposed_action:10s} Fallback={is_fallback} -> Executed={action_executed} ({supervisor_feedback})"
            )

    finally:
        csv_file.close()
        env.close()

if __name__ == "__main__":
    main()