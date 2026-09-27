import json
from llm.ollama_client import OllamaClient

def run_sanity_test():
    client = OllamaClient()
    
    print("Avvio LLM Sanity Test...\n")
    
    # CASO 1: EW Verde, ma c'è una coda immensa su NS. Deve dire "REQUEST_NS".
    state_ew_green_ns_congested = {
        "sim_time": 100, "phase": "EW_GREEN", "elapsed_green": 25,
        "queues": {"NS": 45, "EW": 2},
        "waiting_time": {"NS": 1200.0, "EW": 10.0},
        "allowed_actions": ["HOLD", "REQUEST_NS"]
    }

    # CASO 2: NS Verde, ma c'è una coda immensa su EW. Deve dire "REQUEST_EW".
    state_ns_green_ew_congested = {
        "sim_time": 200, "phase": "NS_GREEN", "elapsed_green": 30,
        "queues": {"NS": 3, "EW": 50},
        "waiting_time": {"NS": 15.0, "EW": 1400.0},
        "allowed_actions": ["HOLD", "REQUEST_EW"]
    }

    # CASO 3: Traffico bilanciato, verde da poco. Deve dire "HOLD".
    state_balanced = {
        "sim_time": 300, "phase": "NS_GREEN", "elapsed_green": 12,
        "queues": {"NS": 5, "EW": 6},
        "waiting_time": {"NS": 40.0, "EW": 45.0},
        "allowed_actions": ["HOLD", "REQUEST_EW"]
    }

    tests = [
        ("TEST 1 (Coda enorme su asse rosso NS, deve cambiare)", state_ew_green_ns_congested),
        ("TEST 2 (Coda enorme su asse rosso EW, deve cambiare)", state_ns_green_ew_congested),
        ("TEST 3 (Bilanciato, deve mantenere)", state_balanced)
    ]

    for name, state in tests:
        print(f"--- {name} ---")
        print(f"Stato inviato: Queue NS={state['queues']['NS']}, Queue EW={state['queues']['EW']}")
        try:
            decision = client.get_decision(state)
            print(f"Azione Scelta: {decision.action_id}")
            print(f"Motivo (JSON): {decision.reason_codes}")
            print(f"Spiegazione: {decision.explanation}\n")
        except Exception as e:
            print(f"Errore: {e}\n")

if __name__ == "__main__":
    run_sanity_test()