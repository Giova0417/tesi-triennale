import os
import subprocess
from pathlib import Path

# Configurazioni base
ROOT_DIR = Path(__file__).parent.parent
SCENARIO_PATH = ROOT_DIR / "scenarios" / "synthetic_4arm" / "scenario.sumocfg"
SRC_DIR = ROOT_DIR / "src"
MAIN_SCRIPT = SRC_DIR / "main.py"
OUTPUT_BASE_DIR = ROOT_DIR / "results"

# Le 3 modalità richieste dal relatore
POLICIES = ["fixed-time", "pressure", "llm"]
SEEDS = [42, 100, 2024]
TRAFFIC_CONDITIONS = ["medium"] # In futuro potrai aggiungere "light", "heavy", ecc.

def run_experiment(policy: str, seed: int, traffic: str) -> None:
    # 1. Creazione cartelle di output dedicate (Richiesta Relatore)
    output_dir = OUTPUT_BASE_DIR / traffic / policy / f"seed_{seed}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    csv_out = output_dir / "simulation_results.csv"
    
    print(f"\n{'='*50}")
    print(f"Lancio esperimento: Policy={policy.upper()} | Seed={seed} | Traffic={traffic}")
    print(f"Cartella output: {output_dir}")
    print(f"{'='*50}\n")
    
    # 2. Impostazione Variabili d'Ambiente 
    # Passiamo la policy e il path di output allo script main.py
    env_vars = os.environ.copy()
    env_vars["TLS_POLICY"] = policy
    env_vars["SUMO_SEED"] = str(seed)
    env_vars["CSV_OUTPUT_PATH"] = str(csv_out)
    
    # Se la policy è fixed-time o pressure, spegniamo Ollama per non sprecare risorse
    if policy != "llm":
        env_vars["DISABLE_LLM"] = "1"
        
    # 3. Lancio del processo
    try:
        # Usa '--nogui' per far girare le simulazioni velocemente in background
        subprocess.run(
            ["python", str(MAIN_SCRIPT), "--nogui"],
            env=env_vars,
            check=True
        )
        print(f"Esperimento {policy}-{seed} completato con successo.\n")
    except subprocess.CalledProcessError as e:
        print(f"ERRORE durante l'esperimento {policy}-{seed}: {e}\n")

def main() -> None:
    print("Inizio campagna sperimentale...")
    
    for traffic in TRAFFIC_CONDITIONS:
        for policy in POLICIES:
            for seed in SEEDS:
                run_experiment(policy, seed, traffic)
                
    print("\nCampagna completata! Tutti i risultati sono salvati nella cartella 'results/'.")

if __name__ == "__main__":
    main()